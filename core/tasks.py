"""
OmniAgent Platform - 后台异步任务队列与分布式状态机 (Core Tasks)
管理耗时计算（视频切片、长文生成等）的异步入队、状态机流转 (PENDING->RUNNING->COMPLETED/FAILED) 与多租户隔离。
"""

import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

# 内存任务注册表 (带 LRU 容量保护)
TASK_REGISTRY: Dict[str, Dict[str, Any]] = {}
MAX_TASK_RECORDS = 500


def create_task_ticket(task_type: str, tenant_id: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """初始化并登记一个异步后台任务票据"""
    task_id = f"task-{task_type[:10]}-{int(time.time()) % 100000:05d}-{uuid.uuid4().hex[:6]}"
    now_ts = time.time()

    record = {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "task_type": task_type,
        "status": "PENDING",  # PENDING | RUNNING | COMPLETED | FAILED
        "progress": 0,
        "created_at": now_ts,
        "started_at": None,
        "completed_at": None,
        "execution_ms": None,
        "payload": payload or {},
        "result": None,
        "error": None,
    }

    if len(TASK_REGISTRY) >= MAX_TASK_RECORDS:
        oldest_k = next(iter(TASK_REGISTRY))
        TASK_REGISTRY.pop(oldest_k, None)

    TASK_REGISTRY[task_id] = record
    return task_id


def update_task_state(
    task_id: str,
    status: str,
    progress: int = 0,
    result: Any = None,
    error: Optional[str] = None,
):
    """更新任务状态机状态与执行成果"""
    if task_id not in TASK_REGISTRY:
        return
    item = TASK_REGISTRY[task_id]
    item["status"] = status
    item["progress"] = progress

    now = time.time()
    if status == "RUNNING" and not item["started_at"]:
        item["started_at"] = now
    elif status in ("COMPLETED", "FAILED"):
        item["completed_at"] = now
        start = item["started_at"] or item["created_at"]
        item["execution_ms"] = int((now - start) * 1000)
        item["result"] = result
        item["error"] = error


def get_task_by_id(task_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """查询指定任务状态与结果（支持租户权限隔离过滤）"""
    task = TASK_REGISTRY.get(task_id)
    if not task:
        return None
    # 若指定了租户，非同租户且非全局租户不可见
    if (
        tenant_id
        and tenant_id not in ("tenant-enterprise-default", "admin")
        and task["tenant_id"] != tenant_id
    ):
        return None
    return task


def list_tasks(tenant_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """按租户倒序查询最近的异步任务"""
    all_tasks = sorted(TASK_REGISTRY.values(), key=lambda t: t["created_at"], reverse=True)
    if tenant_id and tenant_id not in ("tenant-enterprise-default", "admin"):
        all_tasks = [t for t in all_tasks if t["tenant_id"] == tenant_id]
    return all_tasks[:limit]


async def dispatch_background_task(task_id: str, runner_func: Callable, *args, **kwargs):
    """将任务投入异步事件循环执行，自动流转状态机"""
    update_task_state(task_id, "RUNNING", progress=15)
    try:
        # 模拟分段进度推进
        await asyncio.sleep(0.02)
        update_task_state(task_id, "RUNNING", progress=60)

        # 执行真实业务协程
        if asyncio.iscoroutinefunction(runner_func):
            res = await runner_func(*args, **kwargs)
        else:
            res = await asyncio.to_thread(runner_func, *args, **kwargs)

        update_task_state(task_id, "COMPLETED", progress=100, result=res)
    except Exception as exc:
        update_task_state(task_id, "FAILED", progress=100, error=str(exc))
