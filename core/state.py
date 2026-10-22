"""
OmniAgent Platform - 企业级状态机、巡检器与探针历史库 (Core State)
包含 Trace ID 审计流水线、全局巡检器 ServiceMonitor、SQLite 历史落盘与端口探测。
"""

import asyncio
import datetime
import json
import os
import sqlite3
import time
import uuid
from collections import deque
from typing import Any, Dict, List, Optional

from core.config import (
    ALL_PORTS,
    DATA_DIR,
    EVENT_INTERVAL_SEC,
    EVENT_KEEP,
    EVENT_TAGS,
    HEARTBEAT_EVERY,
    PROBE_HOST,
    PROBE_RETENTION_SEC,
    PROBE_TIMEOUT,
    SERVICES_META,
)

# --------------------------------------------------------------------------- #
# 全链路 Trace ID 追踪与审计缓冲区
# --------------------------------------------------------------------------- #
TRACE_AUDIT_LOGS = deque(maxlen=100)


def generate_trace_id(prefix: str = "tr") -> str:
    """生成具备高熵特征与时间戳前缀的标准 Trace ID"""
    return f"{prefix}-{int(time.time()) % 100000:05d}-{uuid.uuid4().hex[:8]}"


# 启动预置 5 条样例 Trace，确保首次打开控制台 HUD 即可观测
_init_now = datetime.datetime.now()
TRACE_AUDIT_LOGS.extendleft(
    [
        {
            "trace_id": "tr-8820-boot-01",
            "timestamp": (_init_now - datetime.timedelta(seconds=12)).strftime("%H:%M:%S"),
            "method": "POST",
            "path": "/api/v1/gateway/simulate_failover",
            "service": "ai-gateway",
            "status_code": 200,
            "latency_ms": 42,
            "model": "Qwen-Max",
            "tokens": 430,
        },
        {
            "trace_id": "tr-8820-boot-02",
            "timestamp": (_init_now - datetime.timedelta(seconds=9)).strftime("%H:%M:%S"),
            "method": "POST",
            "path": "/api/v1/guide/chat",
            "service": "guide-agent",
            "status_code": 200,
            "latency_ms": 38,
            "model": "Qwen-Max",
            "tokens": 280,
        },
        {
            "trace_id": "tr-8820-boot-03",
            "timestamp": (_init_now - datetime.timedelta(seconds=6)).strftime("%H:%M:%S"),
            "method": "POST",
            "path": "/api/v1/labs/xhs/generate",
            "service": "content-factory",
            "status_code": 200,
            "latency_ms": 52,
            "model": "LangGraph-1.0",
            "tokens": 620,
        },
        {
            "trace_id": "tr-8820-boot-04",
            "timestamp": (_init_now - datetime.timedelta(seconds=3)).strftime("%H:%M:%S"),
            "method": "POST",
            "path": "/api/v1/labs/funclip/slice",
            "service": "funclip-studio",
            "status_code": 200,
            "latency_ms": 45,
            "model": "FunASR-Paraformer",
            "tokens": 310,
        },
        {
            "trace_id": "tr-8820-ok",
            "timestamp": _init_now.strftime("%H:%M:%S"),
            "method": "GET",
            "path": "/api/v1/overview/stats",
            "service": "core-hub",
            "status_code": 200,
            "latency_ms": 28,
            "model": "Hybrid-Engine",
            "tokens": 95,
        },
    ]
)


# --------------------------------------------------------------------------- #
# 辅助函数：异步端口探测（不阻塞事件循环）
# --------------------------------------------------------------------------- #
async def is_port_online(port: int, timeout: float = 0.35) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(PROBE_HOST, port), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def probe_port(port: int, timeout: float = 0.35):
    """探测端口并测量 TCP connect 耗时 —— 返回 (online, latency_ms)。

    latency 只在在线时有值（None 表示离线）。历史曲线用它画真实延迟，
    数值是本机回环的 connect 耗时，通常在 1ms 以内 —— 这就是「真实」的样子。
    """
    t0 = time.perf_counter()
    online = await is_port_online(port, timeout)
    latency = (time.perf_counter() - t0) * 1000.0 if online else None
    return online, latency


async def scan_ports(ports: List[int]) -> Dict[int, bool]:
    results = await asyncio.gather(*(is_port_online(p, PROBE_TIMEOUT) for p in ports))
    # strict=True：gather 与 ports 本应一一对应，真错位了要立刻炸，而不是静默截断
    return dict(zip(ports, results, strict=True))


# --------------------------------------------------------------------------- #
# 轻量 SQLite 落盘：探测明细（画曲线）+ 事件流水（做回放）
# --------------------------------------------------------------------------- #
class HistoryDB:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")  # 读写不互斥
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS probes (ts REAL, port INTEGER, online INTEGER, latency_ms REAL)"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_probes_ts ON probes(ts)")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, ts_label TEXT,"
            " tag TEXT, level TEXT, msg TEXT)"
        )
        self.conn.commit()

    # ---- 写 ----
    def record_probe(self, ts: float, port: int, online: bool, latency_ms):
        self.conn.execute(
            "INSERT INTO probes (ts, port, online, latency_ms) VALUES (?,?,?,?)",
            (ts, port, 1 if online else 0, latency_ms),
        )

    def record_events(self, events: List[Dict[str, Any]]):
        now = time.time()
        self.conn.executemany(
            "INSERT INTO events (ts, ts_label, tag, level, msg) VALUES (?,?,?,?,?)",
            [(now, e.get("ts", ""), e.get("tag", ""), e.get("level", ""), e.get("msg", "")) for e in events],
        )

    def commit(self):
        self.conn.commit()

    def prune(self):
        """滑动窗口清理：探测明细按时间过期，事件按条数封顶。"""
        self.conn.execute("DELETE FROM probes WHERE ts < ?", (time.time() - PROBE_RETENTION_SEC,))
        self.conn.execute("DELETE FROM events WHERE id <= (SELECT MAX(id) FROM events) - ?", (EVENT_KEEP,))
        self.conn.commit()

    # ---- 读 ----
    def series(self, ports: List[int], since_ts: float, bucket_sec: float) -> Dict[int, list]:
        """把探测明细按时间桶聚合成曲线点：{port: [[桶起点, 在线率%, 平均延迟ms], ...]}。"""
        rows = self.conn.execute(
            "SELECT port, CAST(ts / ? AS INTEGER) * ? AS bucket,"
            "       AVG(online) * 100.0, AVG(latency_ms)"
            "  FROM probes WHERE ts >= ? AND port IN (%s)"
            " GROUP BY port, bucket ORDER BY bucket" % ",".join("?" * len(ports)),
            [bucket_sec, bucket_sec, since_ts] + list(ports),
        ).fetchall()
        out: Dict[int, list] = {p: [] for p in ports}
        for port, bucket, online_pct, lat in rows:
            out.setdefault(port, []).append(
                [round(bucket * bucket_sec), round(online_pct, 1), None if lat is None else round(lat, 3)]
            )
        return out

    def recent_events(self, limit: int = 60) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT ts_label, tag, level, msg FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"ts": r[0], "tag": r[1], "level": r[2], "msg": r[3]} for r in rows]

    def stats(self) -> Dict[str, Any]:
        probes = self.conn.execute("SELECT COUNT(*) FROM probes").fetchone()[0]
        events = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return {"probes": probes, "events": events, "path": self.path}


def _sse(payload: Dict[str, Any]) -> str:
    """SSE 帧：data: <json>\\n\\n"""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def build_initial_events(prev: Dict[int, bool]) -> List[Dict[str, Any]]:
    """打开事件流时立刻推送的首帧：1 条接入说明 + 每个服务一条就绪播报。"""
    online = sum(1 for v in prev.values() if v)
    events: List[Dict[str, Any]] = [
        {
            "ts": _ts(),
            "tag": "MASTER",
            "level": "info",
            "msg": (
                "事件总线接入成功：本流由真实 TCP 端口探测驱动，每 %.0fs 巡检一次，"
                "当前在线 %d/%d。" % (EVENT_INTERVAL_SEC, online, len(ALL_PORTS))
            ),
        }
    ]
    for s in SERVICES_META:
        up = prev.get(s["port"])
        events.append(
            {
                "ts": _ts(),
                "tag": EVENT_TAGS.get(s["id"], s["id"].upper()),
                "level": "ok" if up else "warn",
                "msg": ("%s（:%d）已就绪。" % (s["name"], s["port"]))
                if up
                else ("%s（:%d）未响应，标记为离线。" % (s["name"], s["port"])),
            }
        )
    return events


def diff_events(prev: Dict[int, bool], cur: Dict[int, bool]) -> List[Dict[str, Any]]:
    """比对两轮端口快照，仅返回「状态发生变化」的服务对应的事件（无变化 → 空列表）。"""
    events: List[Dict[str, Any]] = []
    for s in SERVICES_META:
        was, now = prev.get(s["port"]), cur.get(s["port"])
        if was == now:
            continue
        events.append(
            {
                "ts": _ts(),
                "tag": "HEALTH",
                "level": "ok" if now else "err",
                "msg": "%s（:%d）状态变化：%s%s"
                % (
                    s["name"],
                    s["port"],
                    "上线" if now else "下线",
                    "，已重新纳入调度。" if now else "，流量已摘除。",
                ),
            }
        )
    return events


class ServiceMonitor:
    """全局共享巡检器"""

    def __init__(self):
        self.states: Dict[int, bool] = {p: False for p in ALL_PORTS}
        self.latency: Dict[int, Optional[float]] = {p: None for p in ALL_PORTS}
        self.cycle = 0
        self.dropped = 0  # 因订阅者消费慢而被丢弃的事件数
        self._subs: List[asyncio.Queue] = []
        self._task = None
        self._prune_task = None
        self.db: Optional[HistoryDB] = None

    # ---- 生命周期 ----
    async def start(self):
        if self._task:
            return
        self.db = HistoryDB(os.path.join(DATA_DIR, "omni_history.db"))
        self._task = asyncio.create_task(self._loop())
        self._prune_task = asyncio.create_task(self._prune_loop())

    async def stop(self):
        for t in (self._task, self._prune_task):
            if t:
                t.cancel()
        self._task = self._prune_task = None

    async def _loop(self):
        while True:
            await asyncio.sleep(EVENT_INTERVAL_SEC)
            try:
                await self.tick()
            except Exception as exc:  # noqa: BLE001
                self.publish(
                    {
                        "ts": _ts(),
                        "tag": "MASTER",
                        "level": "err",
                        "msg": "巡检轮次异常（已忽略，不中断循环）：%s" % exc,
                    },
                    persist=False,
                )

    async def _prune_loop(self):
        while True:
            await asyncio.sleep(1800)
            try:
                if self.db is not None:
                    self.db.prune()
            except Exception:  # noqa: BLE001
                pass

    # ---- 订阅（给 SSE 用）----
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subs:
            self._subs.remove(q)

    def publish(self, event: Dict[str, Any], persist: bool = True):
        if persist and self.db is not None:
            try:
                self.db.record_events([event])
                self.db.commit()
            except Exception:  # noqa: BLE001
                pass
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                self.dropped += 1

    # ---- 一轮巡检 ----
    async def tick(self):
        results = await asyncio.gather(*(probe_port(p, PROBE_TIMEOUT) for p in ALL_PORTS))
        cur = {p: r[0] for p, r in zip(ALL_PORTS, results, strict=True)}
        self.latency = {p: r[1] for p, r in zip(ALL_PORTS, results, strict=True)}
        self.cycle += 1
        now = time.time()

        changed = diff_events(self.states, cur)
        for ev in changed:
            self.publish(ev)
        if not changed and self.cycle % HEARTBEAT_EVERY == 0:
            n = sum(1 for v in cur.values() if v)
            self.publish(
                {
                    "ts": _ts(),
                    "tag": "HEALTH",
                    "level": "info",
                    "msg": "全局健康巡检完成，%d/%d 在线，本轮无状态变化。" % (n, len(ALL_PORTS)),
                }
            )

        if self.db is not None:
            try:
                for p in ALL_PORTS:
                    self.db.record_probe(now, p, cur.get(p, False), self.latency.get(p))
                self.db.commit()
            except Exception:  # noqa: BLE001
                pass

        self.states = cur
        return changed


MONITOR = ServiceMonitor()
