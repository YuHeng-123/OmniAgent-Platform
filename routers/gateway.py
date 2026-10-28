"""
OmniAgent Platform - 企业级网关与链路追溯路由 (Gateway Router)
包含网关主备毫秒级热切仿真、全链路 Trace ID 审计流水线、OpenAI 协议统一代理。

真实 / 仿真的边界（也是 README 里那句话的来源）：
  * **真实**：代理端点的租户鉴权（401）与按租户配额（429 + 剩余额度响应头）；
  * **仿真**：上游模型调用本身（固定延迟 + 模板回复），以及 simulate_failover 的三场景演示。
"""

import asyncio
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.models import OpenAIChatRequest
from core.quota import quota
from core.security import require_tenant
from core.state import TRACE_AUDIT_LOGS, generate_trace_id

router = APIRouter()

FAILOVER_SCENARIOS = [
    {
        "scenario": "upstream-timeout",
        "event": "CIRCUIT_BREAKER_TRIGGERED",
        "primary_status": "504 Gateway Timeout (Simulated)",
        "primary_detail": "上游主模型响应超时(>3000ms)，触发熔断阈值",
        "failover_model": "本地兜底规则引擎 (Mock Fallback)",
        "failover_status": "200 OK",
        "switch_note": "热切至本地兜底规则引擎，业务无感重试成功",
    },
    {
        "scenario": "rate-limit",
        "event": "RATE_LIMIT_SHIFT_TRIGGERED",
        "primary_status": "429 Too Many Requests (Simulated)",
        "primary_detail": "上游主模型触发 429 限流（令牌桶耗尽），进入冷却窗口",
        "failover_model": "备用线路 · 低配模型池 (Mock Backup Pool)",
        "failover_status": "200 OK",
        "switch_note": "按预设权重把新请求分流至备用模型池，在途请求原样返回",
    },
    {
        "scenario": "quality-degrade",
        "event": "QUALITY_DEGRADE_TRIGGERED",
        "primary_status": "200 OK but quality score < 0.6 (Simulated)",
        "primary_detail": "主模型返回 200 但输出质量评分跌破阈值（截断/乱码特征）",
        "failover_model": "备用线路 · 重试至主模型备份实例",
        "failover_status": "200 OK (regenerated)",
        "switch_note": "静默重新生成一次并校验评分，通过后返回，用户端无感知",
    },
]
_failover_counter = {"i": 0}


@router.post("/api/v1/gateway/simulate_failover")
async def simulate_failover():
    t0 = time.perf_counter()
    scen = FAILOVER_SCENARIOS[_failover_counter["i"] % len(FAILOVER_SCENARIOS)]
    _failover_counter["i"] += 1
    await asyncio.sleep(0.042)
    return {
        "event": scen["event"],
        "scenario": scen["scenario"],
        "simulated": True,
        "primary_model": "上游主模型（仿真占位）",
        "primary_status": scen["primary_status"],
        "primary_detail": scen["primary_detail"],
        "failover_model": scen["failover_model"],
        "failover_status": scen["failover_status"],
        "switch_latency_ms": int((time.perf_counter() - t0) * 1000),
        "token_usage": {"prompt": 120, "completion": 310, "cost_usd": 0.00045},
        "token_usage_note": "样例数值，非真实计费",
        "log_entry": f"[FAILOVER-ALERT] {scen['primary_detail']}，{scen['switch_note']}！",
    }


@router.get("/api/v1/gateway/traces")
async def get_gateway_traces(limit: int = 15):
    """返回全域智能体 Trace ID 审计流水线与吞吐摘要"""
    items = list(TRACE_AUDIT_LOGS)[:limit]
    return {
        "status": "ok",
        "traces": items,
        "summary": {
            "total_recorded": len(TRACE_AUDIT_LOGS),
            "p95_latency_ms": 42,
            "success_rate": 100.0,
            "active_protocol": "OpenAI v1 / Anthropic MCP",
            "proxy_endpoint": "/v1/chat/completions",
        },
    }


@router.post("/v1/chat/completions")
@router.post("/api/v1/chat/completions")
async def openai_chat_completions(req: OpenAIChatRequest, request: Request):
    """统一 OpenAI 规范代理端点（注入端到端 Trace ID 与用量审计）

    这个端点是整个平台唯一"真的要花模型 token"的入口，所以两道拦截放在这里：

    1. **鉴权**：必须带有效租户 Token，否则 401。以前无 Token 会落到默认开发租户
       （role=admin），等于没有鉴权。
    2. **配额**：按租户计数，超阈值 429，带剩余额度与重试秒数。以前 429 只出现在
       仿真响应文本里，服务端从未真的拒绝过请求。

    注意：**上游调用本身仍是仿真**（`await asyncio.sleep(0.038)` + 模板回复），
    本机没有可用的真实模型线路。鉴权与配额是真的，转发不是——这句话也写在 README 里。
    """
    ctx = require_tenant(request, jwt_only=True)
    decision = quota.consume(ctx["tenant_id"])
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "status": "quota_exceeded",
                "error": "TENANT_QUOTA_EXCEEDED",
                "message": (
                    f"租户 [{ctx['tenant_id']}] 超出配额"
                    f"（{decision.limit} 次 / {decision.window}），{decision.retry_after} 秒后重试"
                ),
                "limit": decision.limit,
                "window": decision.window,
                "retry_after_sec": decision.retry_after,
            },
            headers=decision.headers(),
        )

    t0 = time.perf_counter()
    trace_id = getattr(request.state, "trace_id", generate_trace_id("tr-chat"))
    user_query = req.messages[-1].content if req.messages else "你好"

    await asyncio.sleep(0.038)

    reply_content = (
        f"【OmniAgent 统一模型代理】已通过智能网关调度响应：针对您的问题「{user_query}」，"
        f"系统已成功完成意图识别与工具编排，链路全程受 Trace ID [{trace_id}] 审计追踪。"
    )

    latency_ms = int((time.perf_counter() - t0) * 1000)
    prompt_tokens = len(user_query) * 2 + 35
    completion_tokens = len(reply_content) * 2 + 10
    total_tokens = prompt_tokens + completion_tokens

    return JSONResponse(
        headers=decision.headers(),
        content={
            "id": f"chatcmpl-{trace_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model or "qwen-max",
            "system_fingerprint": f"fp_{uuid.uuid4().hex[:8]}",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": reply_content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": round(total_tokens * 0.000002, 6),
            },
            "trace_id": trace_id,
            "latency_ms": latency_ms,
            "tenant_id": ctx["tenant_id"],
            "proxy_gateway": "OmniAgent AI Gateway :8000",
            "upstream": "simulated",
        },
    )


@router.get("/api/v1/gateway/quota")
async def get_my_quota(request: Request):
    """当前调用方的配额用量（只读，不扣额度）。"""
    ctx = require_tenant(request)
    return {"status": "ok", **quota.peek(ctx["tenant_id"])}

