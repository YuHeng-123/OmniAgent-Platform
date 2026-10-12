"""
OmniAgent Platform - 事件总线与监控历史路由 (Events Router)
包含 SSE 实时事件流、历史探测明细曲线、最近事件回放。
"""

import asyncio
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from core.config import (
    ALL_PORTS,
    EVENT_INTERVAL_SEC,
    HEARTBEAT_EVERY,
    PROBE_RETENTION_SEC,
    SERVICES_META,
)
from core.state import (
    MONITOR,
    _sse,
    _ts,
    build_initial_events,
    diff_events,
    scan_ports,
)

router = APIRouter()


@router.get("/api/v1/events/stream")
async def events_stream(request: Request):
    async def gen():
        # 正常路径：订阅共享巡检器（所有连接共享同一套探测与事件流）
        if MONITOR._task is not None:
            queue = MONITOR.subscribe()
            try:
                for ev in build_initial_events(MONITOR.states):
                    yield _sse(ev)
                while True:
                    try:
                        ev = await asyncio.wait_for(queue.get(), timeout=EVENT_INTERVAL_SEC * 2 + 1)
                        yield _sse(ev)
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
            finally:
                MONITOR.unsubscribe(queue)
            return

        # 降级路径：巡检器未走 lifespan 启动
        prev = await scan_ports(ALL_PORTS)
        for ev in build_initial_events(prev):
            yield _sse(ev)

        cycle = 0
        while True:
            await asyncio.sleep(EVENT_INTERVAL_SEC)
            if await request.is_disconnected():
                break
            cycle += 1
            cur = await scan_ports(ALL_PORTS)
            changed = diff_events(prev, cur)
            for ev in changed:
                yield _sse(ev)
            if not changed and cycle % HEARTBEAT_EVERY == 0:
                n = sum(1 for v in cur.values() if v)
                yield _sse(
                    {
                        "ts": _ts(),
                        "tag": "HEALTH",
                        "level": "info",
                        "msg": "全局健康巡检完成，%d/%d 在线，本轮无状态变化。" % (n, len(ALL_PORTS)),
                    }
                )
            prev = cur

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/v1/history/probes")
async def history_probes(minutes: int = 60, buckets: int = 120):
    """按时间窗口返回各服务的在线率 / 平均延迟曲线。"""
    minutes = max(1, min(int(minutes or 60), 1440))
    buckets = max(10, min(int(buckets or 120), 480))
    window_sec = minutes * 60
    bucket_sec = max(EVENT_INTERVAL_SEC, window_sec / buckets)

    if MONITOR.db is None:
        return {
            "status": "ok",
            "minutes": minutes,
            "bucket_sec": bucket_sec,
            "source": "monitor-not-started",
            "series": {},
        }
    series = MONITOR.db.series(ALL_PORTS, time.time() - window_sec, bucket_sec)
    return {
        "status": "ok",
        "minutes": minutes,
        "bucket_sec": bucket_sec,
        "source": "sqlite-history",
        "retention_sec": PROBE_RETENTION_SEC,
        "series": [
            {
                "id": s["id"],
                "name": s["name"],
                "port": s["port"],
                "points": series.get(s["port"], []),
            }
            for s in SERVICES_META
        ],
    }


@router.get("/api/v1/events/recent")
async def events_recent(limit: int = 60):
    """最近事件的倒序回放（给「历史趋势」页签的事件流水用）。"""
    limit = max(1, min(int(limit or 60), 500))
    if MONITOR.db is None:
        return {"status": "ok", "limit": limit, "source": "monitor-not-started", "events": []}
    return {
        "status": "ok",
        "limit": limit,
        "source": "sqlite-history",
        "dropped_for_slow_subscribers": MONITOR.dropped,
        "events": MONITOR.db.recent_events(limit),
    }
