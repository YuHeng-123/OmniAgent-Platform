"""
OmniAgent Platform - 系统与大盘路由 (System Router)
包含首页渲染、/healthz 健康检查、/api/v1/overview/stats 大盘统计、微服务起停管控。
"""

import asyncio
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from core.config import (
    ALL_PORTS,
    APP_VERSION,
    BIND_HOST,
    CONFIG_SOURCE,
    EVENT_INTERVAL_SEC,
    PROBE_HOST,
    PROBE_TIMEOUT,
    SERVICE_INDEX,
    SERVICES_META,
    STARTED_AT,
)
from core.models import AuthTokenRequest
from core.process import start_service_process, stop_port_processes
from core.security import (
    create_tenant_jwt,
    enforce_sensitive_action_role,
    get_tenant_context,
)
from core.state import MONITOR, is_port_online, scan_ports
from core.tasks import get_task_by_id, list_tasks
from core.templates import templates

router = APIRouter()


def _service_or_404(service_id: str) -> Dict[str, Any]:
    meta = SERVICE_INDEX.get(service_id)
    if not meta:
        raise HTTPException(
            404,
            detail="未知服务 id：%s；可用：%s" % (service_id, ", ".join(SERVICE_INDEX)),
        )
    return meta


@router.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    states = await scan_ports(ALL_PORTS)
    service_states = []
    for s in SERVICES_META:
        item = dict(s)
        item["status"] = "online" if states.get(s["port"]) else "offline"
        service_states.append(item)
    online_count = sum(1 for i in service_states if i["status"] == "online")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "services": service_states,
            "online_count": online_count,
            "total_count": len(SERVICES_META),
            "app_version": APP_VERSION,
        },
    )


@router.get("/healthz")
async def healthz():
    states = await scan_ports(ALL_PORTS)
    online = sum(1 for v in states.values() if v)
    return {
        "status": "ok",
        "version": APP_VERSION,
        "uptime_sec": round(time.time() - STARTED_AT, 1),
        "config_source": CONFIG_SOURCE,
        "networking": {
            "bind_host": BIND_HOST,
            "probe_host": PROBE_HOST,
        },
        "services_online": online,
        "services_total": len(SERVICES_META),
        "monitor": {
            "running": MONITOR._task is not None,
            "cycle": MONITOR.cycle,
            "subscribers": len(MONITOR._subs),
            "dropped_for_slow_subscribers": MONITOR.dropped,
            "history": MONITOR.db.stats() if MONITOR.db is not None else None,
        },
        "services": [
            {"id": s["id"], "port": s["port"], "online": bool(states.get(s["port"]))} for s in SERVICES_META
        ],
    }


@router.get("/api/v1/overview/stats")
async def get_overview_stats():
    states = await scan_ports(ALL_PORTS)
    services = [
        {
            "id": s["id"],
            "name": s["name"],
            "port": s["port"],
            "status": "online" if states.get(s["port"]) else "offline",
            "type": s["type"],
        }
        for s in SERVICES_META
    ]
    online_count = sum(1 for i in services if i["status"] == "online")
    return {
        "status": "ok",
        "online_count": online_count,
        "total_count": len(SERVICES_META),
        "qps_24h": 3482,
        "total_tokens": "1.48M",
        "knowledge_hit_rate": "95.6%",
        "cost_saved_usd": "$48.20",
        "config_source": CONFIG_SOURCE,
        "metrics_source": "demo-sample",
        "services": services,
    }


@router.get("/api/v1/services/control-capabilities")
async def control_capabilities():
    """告诉前端每个服务能做什么操作（决定按钮可用态）。"""
    return {
        "status": "ok",
        "can_stop": True,
        "services": [
            {
                "id": s["id"],
                "port": s["port"],
                "can_start": bool(s.get("start_cmd")),
                "start_cwd": s.get("start_cwd") or "",
            }
            for s in SERVICES_META
        ],
    }


@router.post("/api/v1/services/{service_id}/stop")
async def service_stop(service_id: str, request: Request):
    """敏感操作：终止微服务进程（具备企业级 RBAC 权限校验与租户审计）"""
    meta = _service_or_404(service_id)
    ctx = enforce_sensitive_action_role(request, allowed_roles=["admin", "operator"])
    result = await asyncio.to_thread(stop_port_processes, meta["port"])
    return {
        "status": "ok",
        "tenant_id": ctx["tenant_id"],
        "operator": ctx["user_id"],
        "service_id": meta["id"],
        "name": meta["name"],
        "port": meta["port"],
        "event_hint": ("巡检器将在约 %.0f 秒内探测到下线并推送事件。" % EVENT_INTERVAL_SEC)
        if result.get("stopped")
        else "",
        **result,
    }


@router.post("/api/v1/services/{service_id}/start")
async def service_start(service_id: str, request: Request):
    """敏感操作：拉起微服务进程（具备企业级 RBAC 权限校验与租户审计）"""
    meta = _service_or_404(service_id)
    ctx = enforce_sensitive_action_role(request, allowed_roles=["admin", "operator"])
    if await is_port_online(meta["port"], PROBE_TIMEOUT):
        return {
            "status": "ok",
            "started": False,
            "reason": "already-online",
            "tenant_id": ctx["tenant_id"],
            "operator": ctx["user_id"],
            "service_id": meta["id"],
            "name": meta["name"],
            "port": meta["port"],
            "detail": "服务已在线，无需启动。",
        }
    result = await asyncio.to_thread(start_service_process, meta)
    return {
        "status": "ok",
        "tenant_id": ctx["tenant_id"],
        "operator": ctx["user_id"],
        "service_id": meta["id"],
        "name": meta["name"],
        "port": meta["port"],
        **result,
    }


# --------------------------------------------------------------------------- #
# 企业准入鉴权与租户上下文端点 (Auth & Multi-Tenant Endpoints)
# --------------------------------------------------------------------------- #
@router.post("/api/v1/auth/token")
async def issue_auth_token(req: AuthTokenRequest):
    """企业准入：颁发带租户标识与角色的 JWT Token"""
    token = create_tenant_jwt(
        tenant_id=req.tenant_id,
        role=req.role,
        user_id=req.user_id,
        expires_in_sec=86400 * 7,
    )
    return {
        "status": "ok",
        "access_token": token,
        "token_type": "Bearer",
        "tenant_id": req.tenant_id,
        "role": req.role,
        "user_id": req.user_id,
        "expires_in": 86400 * 7,
    }


@router.get("/api/v1/auth/me")
async def get_current_user_tenant(request: Request):
    """查询当前请求的租户上下文与权限"""
    ctx = get_tenant_context(request)
    return {
        "status": "ok",
        "tenant_context": ctx,
    }


# --------------------------------------------------------------------------- #
# 异步后台任务队列与状态机端点 (Async Tasks Query Endpoints)
# --------------------------------------------------------------------------- #
@router.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str, request: Request):
    """查询后台异步任务状态机流转 (PENDING/RUNNING/COMPLETED/FAILED) 与执行产物"""
    ctx = get_tenant_context(request)
    task = get_task_by_id(task_id, tenant_id=ctx["tenant_id"])
    if not task:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "task_id": task_id, "hint": "异步任务不存在或无权访问"},
        )
    return {
        "status": "ok",
        "task": task,
    }


@router.get("/api/v1/tasks")
async def list_recent_tasks(request: Request, limit: int = 20):
    """查询当前租户最近排队或完成的异步任务流水"""
    ctx = get_tenant_context(request)
    tasks = list_tasks(tenant_id=ctx["tenant_id"], limit=limit)
    return {
        "status": "ok",
        "tenant_id": ctx["tenant_id"],
        "total": len(tasks),
        "tasks": tasks,
    }
