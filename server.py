"""
OmniAgent Platform 2.0 —— 企业级全域 AI 智能体控制中枢（统一控制台）

设计要点：
1. 控制台自身可独立运行，不依赖其余 7 个微服务是否在线；在线的会亮绿点。
2. 导购接口优先调用真实的 ecom-agent(8001) 并解析其 SSE 流；
   8001 不可用 / 上游报错时，自动降级到本地演示引擎，并在响应里如实标注 backend。
3. 所有耗时都是实测（time.perf_counter），不再返回写死的常数。
4. 静态资源本地挂载（templates/static 用绝对路径定位），断网可渲染。
"""

import asyncio
import json
import os
import sqlite3
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 版本号单一来源：页面角标、/healthz、FastAPI 自动文档都读它，避免多处各写各的漂移。
APP_VERSION = "2.2.0"
STARTED_AT = time.time()

app = FastAPI(
    title="OmniAgent Platform - 企业级全域 AI 智能体控制中枢",
    description="工业级 Agent 微服务编排底座、统一控制台与多智能体业务闭环",
    version=APP_VERSION,
)

# 注意：allow_origins=["*"] 与 allow_credentials=True 是浏览器规范禁止的组合，这里置 False
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(os.path.join(BASE_DIR, "templates"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# 静态资源本地挂载：/static/vendor/* 与 /static/omni-api.js
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


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
# 核心拓扑：从 services.yaml 读取（缺失 / 解析失败时回退到内置默认）
# OMNI_CONFIG_PATH 环境变量可指向另一份拓扑 —— 供端到端自检注入假服务用，
# 正常运行永远读仓库根目录的 services.yaml。
# --------------------------------------------------------------------------- #
CONFIG_PATH = os.environ.get("OMNI_CONFIG_PATH") or os.path.join(BASE_DIR, "services.yaml")

# 内置默认拓扑 —— services.yaml 读不到时的兜底，保证控制台永远能起来
_BUILTIN_SERVICES = [
    {
        "id": "ai-gateway",
        "name": "企业 AI 统一网关",
        "role": "流量总线与大模型调度",
        "port": 8000,
        "url": "http://127.0.0.1:8000/dashboard",
        "type": "Infra",
        "desc": "全域流量接管、虚拟 Key 路由、毫秒级主备热切与 Token 计量",
        "tech": "FastAPI + Redis + MCP",
    },
    {
        "id": "ecom-ai-guide",
        "name": "琼华珠宝 AI 智能导购",
        "role": "核心业务 Agent",
        "port": 8001,
        "url": "http://127.0.0.1:8001",
        "type": "Business",
        "desc": "混合检索 + 工具调用 + 报错自纠错链路的多轮导购智能体",
        "tech": "LangGraph + SQLite + SSE",
        "chat_path": "/api/chat",
    },
    {
        "id": "coze-material-studio",
        "name": "多平台爆款素材工作台",
        "role": "内容营销 Agent",
        "port": 8002,
        "url": "http://127.0.0.1:8002",
        "type": "Business",
        "desc": "Coze 工作流工程化封装，小红书/抖音营销图文生成与违禁词合规审查",
        "tech": "Coze API + FastAPI + 正则分词",
    },
    {
        "id": "ai-data-analysis-assistant",
        "name": "AI 数据分析专家",
        "role": "决策分析 Agent",
        "port": 8510,
        "url": "http://127.0.0.1:8510",
        "type": "Data",
        "desc": "DuckDB + 本地 Ollama 驱动，自然语言 Text-to-SQL 与交互式动态图表看板",
        "tech": "Streamlit + DuckDB + Plotly",
    },
    {
        "id": "ai-knowledge-assistant",
        "name": "企业级智能知识库 (RAG)",
        "role": "知识底座",
        "port": 8501,
        "url": "http://127.0.0.1:8501",
        "type": "Infra",
        "desc": "基于 Streamlit + 本地向量检索的高精度行业知识库，支持 PDF/Word 知识检索问答",
        "tech": "Streamlit + ChromaDB + RAG",
    },
    {
        "id": "data-automation-workbench",
        "name": "自动化情报抓取平台",
        "role": "数据管道",
        "port": 8765,
        "url": "http://127.0.0.1:8765",
        "type": "Data",
        "desc": "独立轻量化情报抓取工作台，支持网页结构化采集、价格规则抽取与数据导出",
        "tech": "Python Native HTTP + SQLite",
    },
    {
        "id": "ark_aigc_demo",
        "name": "多模态音视频智能体 (FunClip)",
        "role": "交互 Agent",
        "port": 7860,
        "url": "http://127.0.0.1:7860",
        "type": "Innovation",
        "desc": "基于 FunClip 的本地 AI 音视频自动化切片、多模态语音识别与字幕智能合成",
        "tech": "Gradio + PyTorch + FunASR",
    },
]

_BUILTIN_EVENT_TAGS = {
    "ai-gateway": "GATEWAY",
    "ecom-ai-guide": "ECOM-AGENT",
    "coze-material-studio": "MARKETING",
    "ai-data-analysis-assistant": "ANALYTICS",
    "ai-knowledge-assistant": "RAG",
    "data-automation-workbench": "COLLECTOR",
    "ark_aigc_demo": "FUNCLIP",
}

_BUILTIN_PROBE = {"interval_sec": 3.0, "heartbeat_every": 4, "timeout_sec": 0.35}


def load_topology(path: str = CONFIG_PATH):
    """读取 services.yaml，返回 (services, event_tags, probe, source)。

    文件缺失 / PyYAML 未安装 / 解析失败 —— 一律回退内置默认，控制台永不因配置坏掉而
    启动不能；source 会出现在 /api/v1/overview/stats 里，方便一眼看出拓扑是从哪来的。
    """
    try:
        import yaml
    except ImportError:
        return (
            list(_BUILTIN_SERVICES),
            dict(_BUILTIN_EVENT_TAGS),
            dict(_BUILTIN_PROBE),
            "builtin-defaults (PyYAML 未安装)",
        )
    if not os.path.isfile(path):
        return (
            list(_BUILTIN_SERVICES),
            dict(_BUILTIN_EVENT_TAGS),
            dict(_BUILTIN_PROBE),
            "builtin-defaults (services.yaml 不存在)",
        )
    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        items = raw.get("services") or []
        cleaned = []
        for s in items:
            if not isinstance(s, dict) or "id" not in s or "port" not in s:
                raise ValueError("services 条目缺少 id / port：%r" % (s,))
            cleaned.append(
                {
                    "id": str(s["id"]),
                    "name": str(s.get("name") or s["id"]),
                    "role": str(s.get("role") or ""),
                    "port": int(s["port"]),
                    "url": str(s.get("url") or ""),
                    "type": str(s.get("type") or "Business"),
                    "desc": str(s.get("desc") or ""),
                    "tech": str(s.get("tech") or ""),
                    # 可选：控制台导购链路要 POST 的路径，缺省 /api/chat
                    "chat_path": str(s.get("chat_path") or "/api/chat"),
                    # 可选：控制台「启动」按钮要拉起的命令（argv 列表，相对 start_cwd 执行）。
                    # 不配置 = 该服务的启动按钮呈禁用态 —— 控制台不假装知道没告诉它的启动方式。
                    "start_cmd": [str(x) for x in s["start_cmd"]] if s.get("start_cmd") else [],
                    "start_cwd": str(s.get("start_cwd") or ""),
                }
            )
        if not cleaned:
            raise ValueError("services 列表为空")
        tags = {str(k): str(v) for k, v in (raw.get("event_tags") or {}).items()}
        probe = dict(_BUILTIN_PROBE)
        raw_probe = raw.get("probe") or {}
        for key in ("interval_sec", "heartbeat_every", "timeout_sec"):
            if key in raw_probe:
                probe[key] = raw_probe[key]
        probe["interval_sec"] = float(probe["interval_sec"])
        probe["timeout_sec"] = float(probe["timeout_sec"])
        probe["heartbeat_every"] = int(probe["heartbeat_every"])
        return cleaned, tags, probe, "services.yaml"
    except Exception as exc:  # noqa: BLE001 —— 配置坏了也不能拖垮控制台
        return (
            list(_BUILTIN_SERVICES),
            dict(_BUILTIN_EVENT_TAGS),
            dict(_BUILTIN_PROBE),
            "builtin-defaults (services.yaml 解析失败: %s)" % exc,
        )


SERVICES_META, EVENT_TAGS, PROBE, CONFIG_SOURCE = load_topology()
ALL_PORTS = [s["port"] for s in SERVICES_META]
PROBE_TIMEOUT = PROBE["timeout_sec"]
EVENT_INTERVAL_SEC = PROBE["interval_sec"]
HEARTBEAT_EVERY = PROBE["heartbeat_every"]

# --------------------------------------------------------------------------- #
# 监听地址 / 探测地址 —— 这两个必须可配置，否则容器化跑不通（见 Dockerfile）
# --------------------------------------------------------------------------- #
# BIND_HOST：控制台自己 listen 的地址。
#   本机默认 127.0.0.1（刻意不暴露到局域网，符合「单机演示」定位）；
#   容器里必须 0.0.0.0 —— Docker 的端口发布（-p 8888:8888）是把宿主机端口 DNAT 到
#   容器的 eth0，进程只 bind 回环的话宿主机根本打不通；更糟的是容器自带 healthcheck
#   从容器内 loopback 打是通的，于是会显示「健康，但外部访问不了」这种静默失败。
BIND_HOST = os.environ.get("OMNI_HOST") or "127.0.0.1"

# PROBE_HOST：探测 7 个微服务时连的地址。
#   本机默认 127.0.0.1；容器里必须 host.docker.internal —— 容器内的 127.0.0.1 是
#   容器自己，永远探不到跑在宿主机上的服务（否则面板恒显示 0/7）。
PROBE_HOST = os.environ.get("OMNI_PROBE_HOST") or str(PROBE.get("host") or "127.0.0.1")
# 归一化：保证无论拓扑来自 yaml 还是内置默认，每个条目都带 start_cmd / start_cwd 键，
# 下游（起停 API、前端渲染）不需要再判键。
for _s in SERVICES_META:
    _s.setdefault("start_cmd", [])
    _s.setdefault("start_cwd", "")

# 按 id 索引 —— 业务链路据此按「服务 id」找上游，而不是把端口写死在代码里。
SERVICE_INDEX = {s["id"]: s for s in SERVICES_META}
# 导购链路的上游端口 / 路径都取自拓扑（services.yaml 的 ecom-ai-guide 条目）。
# 改 yaml 里的端口即可切换上游，server.py 无需改动。
_GUIDE = SERVICE_INDEX.get("ecom-ai-guide")
GUIDE_PORT = int(_GUIDE["port"]) if _GUIDE else 8001
GUIDE_CHAT_PATH = (_GUIDE.get("chat_path") or "/api/chat") if _GUIDE else "/api/chat"


# --------------------------------------------------------------------------- #
# 运行期数据目录（历史库 + 各服务启动日志）；OMNI_DATA_DIR 可指向别处（自检用）
# --------------------------------------------------------------------------- #
DATA_DIR = os.environ.get("OMNI_DATA_DIR") or os.path.join(BASE_DIR, "data")
PROBE_RETENTION_SEC = 24 * 3600  # 探测明细保留 24 小时
EVENT_KEEP = 1000  # 事件最多保留最近 1000 条


class HistoryDB:
    """轻量 SQLite 落盘：探测明细（画曲线）+ 事件流水（做回放）。

    为什么是 sqlite3 标准库而不是 SQLAlchemy：这里是单机控制台，写入量是
    「7 行 / 3 秒」≈ 每天 20 万行，标准库足够；引 ORM 只会让 run.bat 的依赖更重。
    """

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
        """把探测明细按时间桶聚合成曲线点：{port: [[桶起点, 在线率%, 平均延迟ms], ...]}。

        降采样是必须的：8 小时窗口的原始明细是 96000 行，直接丢给前端画图没有意义。
        """
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


class ServiceMonitor:
    """全局共享巡检器（2.2 新增，取代 2.1 的「每个 SSE 连接各自探测一遍」）。

    一个进程只有一套探测循环，好处有三：
      1. 事件和探测明细**无论有没有人开着 SSE 流都会持续产生** → 历史曲线才有数据；
      2. 开 N 个浏览器标签页 = 共享一份巡检，不是 N 份轮询打在本机端口上；
      3. 落库点唯一，历史与实时不会出现「页面上是一套、库里是另一套」。
    """

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
            except Exception as exc:  # noqa: BLE001 —— 巡检不能因单轮异常而死掉
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
        """一条事件 → 落库 + 广播给所有订阅者。

        广播用 put_nowait：慢客户端（比如被网线拖住的浏览器）宁可丢事件也不能
        反向阻塞整个巡检循环 —— 这就是 dropped 计数器存在的理由。
        """
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
        """探测 → 差异事件 → 心跳 → 落库。被测试直接调用以避免等 3 秒。"""
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


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """FastAPI 生命周期：启动时拉起共享巡检器，关闭时收干净。"""
    await MONITOR.start()
    try:
        yield
    finally:
        await MONITOR.stop()


# app 已在文件上方创建；把 lifespan 挂上去（比挪动 app 定义更小改动）
app.router.lifespan_context = _lifespan


# --------------------------------------------------------------------------- #
# 主控台页面路由
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
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
            "app_version": APP_VERSION,  # 页面角标用后端版本，避免两处各写各的
        },
    )


# --------------------------------------------------------------------------- #
# 健康检查：给监控 / CI / 容器探针用的标准端点
# （不渲染页面；会真去探一次 7 个端口，所以能反映集群当前在线数）
# --------------------------------------------------------------------------- #
@app.get("/healthz")
async def healthz():
    states = await scan_ports(ALL_PORTS)
    online = sum(1 for v in states.values() if v)
    return {
        "status": "ok",
        "version": APP_VERSION,
        "uptime_sec": round(time.time() - STARTED_AT, 1),
        "config_source": CONFIG_SOURCE,
        "networking": {
            # 容器化排障用：bind 是不是 0.0.0.0、探的是不是宿主机，一眼可见
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


# --------------------------------------------------------------------------- #
# 统一 404：带上 path 与人话提示，替代默认的裸 {"detail":"Not Found"}
# --------------------------------------------------------------------------- #
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    # HTTPException（如「未知服务 id」）走这里时，用它的 detail 替换通用提示
    detail = getattr(exc, "detail", None)
    is_api = request.url.path.startswith("/api/")
    return JSONResponse(
        status_code=404,
        content={
            "status": "not_found",
            "path": request.url.path,
            "hint": detail
            if detail
            else (
                ("接口不存在；可用接口见 /docs 或 /healthz。")
                if is_api
                else ("这是 OmniAgent 控制台，页面入口是 /；接口清单见 /docs。")
            ),
        },
    )


# --------------------------------------------------------------------------- #
# API 1: 全局大盘与微服务状态
# --------------------------------------------------------------------------- #
@app.get("/api/v1/overview/stats")
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
        # 拓扑来源 + 指标来源都如实标出来：
        #   拓扑来自 services.yaml（或内置默认），是真实的；
        #   下面这 4 个指标是演示样例数据，前端会标注，避免被当成实盘数字。
        "config_source": CONFIG_SOURCE,
        "metrics_source": "demo-sample",
        "services": services,
    }


# --------------------------------------------------------------------------- #
# API 2: 中枢事件总线 —— SSE 真实事件流
# --------------------------------------------------------------------------- #
# 这条流不是"写好的日志文本滚动"，而是真的由端口探测驱动的：
#   · 每 EVENT_INTERVAL_SEC 秒对 7 个服务做一次 TCP 探测，与上一轮快照比对
#   · 状态发生变化（上线/下线）→ 立刻推一条事件
#   · 连续无变化 → 每 HEARTBEAT_EVERY 轮推一条巡检心跳
# 所以演示时把一个服务停掉，面板上会真的出现"下线"事件。
# 巡检周期、心跳频率、探测超时都来自 services.yaml 的 probe 段（见上方 load_topology）。


def _sse(payload: Dict[str, Any]) -> str:
    """SSE 帧：data: <json>\\n\\n"""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def build_initial_events(prev: Dict[int, bool]) -> List[Dict[str, Any]]:
    """打开事件流时立刻推送的首帧：1 条接入说明 + 每个服务一条就绪播报。

    抽成纯函数是为了可测 —— 喂一份端口快照即可断言输出，不必真开一条 SSE 长连接
    （长连接在 Windows + TestClient 下会阻塞）。
    """
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
    """比对两轮端口快照，仅返回「状态发生变化」的服务对应的事件（无变化 → 空列表）。

    这是「事件由真实差异驱动、而非定时文本播报」的核心逻辑，单独抽出来便于断言。
    """
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


@app.get("/api/v1/events/stream")
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
                        # 订阅通道暂时没有事件（比如服务全离线时没有心跳）：
                        # 发一条 SSE 注释帧保活，避免中间代理掐断长连接
                        yield ": keep-alive\n\n"
            finally:
                MONITOR.unsubscribe(queue)
            return

        # 降级路径：巡检器没启动（进程内直接调 app、未走 lifespan 的场景）。
        # 行为与 2.1 相同 —— 连接内自探测。生产入口（run.bat / uvicorn）永远走上面的路径。
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
            "X-Accel-Buffering": "no",  # 经 nginx 反代时不缓冲，保证逐条吐
        },
    )


# --------------------------------------------------------------------------- #
# API 3: 导购工作站 —— 优先真实接入 ecom-agent(8001) 的 SSE 流
# --------------------------------------------------------------------------- #
class GuideChatRequest(BaseModel):
    message: str = ""
    history: Optional[List[Dict[str, Any]]] = None


async def fetch_from_guide_agent(message: str, history) -> Optional[Dict[str, Any]]:
    """调用真实导购 Agent 并解析其 SSE 事件流。失败返回 None 以触发降级。

    上游地址 = PROBE_HOST:GUIDE_PORT + GUIDE_CHAT_PATH。端口与路径取自 services.yaml
    的 ecom-ai-guide 条目（不再硬编码 8001）；主机取自 PROBE_HOST，容器化时指向宿主机。
    """
    if not await is_port_online(GUIDE_PORT, PROBE_TIMEOUT):
        return None

    tokens: List[str] = []
    trace: List[Dict[str, str]] = []
    backend = "ecom-agent"
    try:
        timeout = httpx.Timeout(12.0, connect=3.0)
        async with httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
            async with client.stream(
                "POST",
                "http://%s:%d%s" % (PROBE_HOST, GUIDE_PORT, GUIDE_CHAT_PATH),
                json={"message": message, "history": history or []},
            ) as resp:
                if resp.status_code != 200:
                    return None
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw:
                        continue
                    try:
                        ev = json.loads(raw)
                    except Exception:
                        continue
                    et = ev.get("type")
                    if et == "meta":
                        backend = ev.get("backend", backend)
                    elif et == "token":
                        tokens.append(ev.get("text", ""))
                    elif et in ("status", "retrieval", "tool_result", "retry"):
                        trace.append(
                            {
                                "node": ev.get("node") or ev.get("name") or et,
                                "status": "retry" if et == "retry" else "done",
                                "detail": (
                                    ev.get("detail")
                                    or ev.get("message")
                                    or json.dumps(ev, ensure_ascii=False)[:160]
                                ),
                            }
                        )
    except Exception:
        return None

    text = "".join(tokens).strip()
    if not text:
        # 上游只回了 error / close，没有正文 —— 交给本地演示引擎兜底
        return None
    return {"reply": text, "trace": trace, "backend": backend}


def local_guide_reply(user_msg: str):
    """本地演示引擎（离线 / 上游不可用时的兜底），与前端 static/omni-api.js 行为一致。"""
    is_coupon = any(k in user_msg for k in ["券", "优惠", "打折", "便宜", "省钱", "满减"])
    is_recommend = any(k in user_msg for k in ["推荐", "买", "送", "项链", "手串", "戒指", "玉", "翡翠"])
    is_diff = any(k in user_msg for k in ["区别", "真假", "莫桑", "培育", "天然", "证书"])

    steps = [
        {
            "node": "意图识别 (Router)",
            "status": "done",
            "detail": f"分类为: {'COUPON_QUERY' if is_coupon else ('PRODUCT_RECOMMEND' if is_recommend else 'KNOWLEDGE_QA')}",
        },
        {
            "node": "向量库混合检索 (RAG)",
            "status": "done",
            "detail": "检索到 4 条高置信度知识切片，相似度最高 0.942",
        },
    ]
    self_corrected = False

    if "500" in user_msg and "券" in user_msg:
        self_corrected = True
        steps.append(
            {
                "node": "工具调用 (Tool Calling)",
                "status": "retry",
                "detail": "调用 get_coupon('500元无门槛') 失败：券面额超出系统上限",
            }
        )
        steps.append(
            {
                "node": "⚡ 自动反思与自纠错 (Self-Correction)",
                "status": "done",
                "detail": "触发纠错策略：自动降级检索最接近规则，回正为【满2000减200】与【新人50元立减】",
            }
        )
        reply = (
            "非常抱歉呀，小琼帮您查了一下，目前店内没有【500元无门槛券】哦～ 不过小琼为您申请到了当前最划算的组合：\n\n"
            "1. **新人专享礼**：满 300 减 50 元立减券；\n"
            "2. **珠宝品类大额券**：满 2000 减 200 元满减券！\n\n"
            "如果您今天选购【天然和田玉青海老料吊坠】（原价 ¥1,880），再凑单一个小银饰，即可直接立减 200 元，非常划算！需要我帮您锁定领券名额吗？"
        )
    elif is_recommend:
        steps.append(
            {
                "node": "工具调用 (Tool Calling)",
                "status": "done",
                "detail": "执行 query_products(category='jade', price_range=[1000, 2500])，命中 3 款商品",
            }
        )
        steps.append(
            {
                "node": "决策合成 (Synthesis)",
                "status": "done",
                "detail": "结合送礼/自戴场景，生成亲和力导购话术",
            }
        )
        reply = (
            "为您精心挑选了店内两款口碑极高的送礼首选：\n\n"
            "🌟 **【琼华·福禄双全】天然和田碧玉平安扣吊坠**\n"
            "- 材质：新疆且末老料，油润细腻，附国家级宝玉石质检证书\n"
            "- 礼盒：配东方国风锦盒与特调沉香香片\n"
            "- 专柜价：¥2,399 ｜ **限时到手价：¥1,680**\n\n"
            "💍 **【琼华·月满西楼】天然淡水无瑕珍珠项链**\n"
            "- 规格：8-9mm 微瑕近圆，正圆强光皮光极亮\n"
            "- **专柜价：¥1,480 ｜ 限时活动价：¥1,120**\n\n"
            "两款都非常温润显气质，长辈收到都特别喜欢。您更偏好玉石的内敛还是珍珠的优雅呢？"
        )
    elif is_diff:
        steps.append(
            {
                "node": "知识检索 (RAG)",
                "status": "done",
                "detail": "命中珠宝百科知识切片 #381：《莫桑钻与天然钻石光学特质比对》",
            }
        )
        reply = (
            "这是很多顾客关心的专业问题，小琼为您通俗解答：\n\n"
            "1. **物理成分**：天然钻石是纯碳晶体（硬度10）；莫桑石是碳化硅（硬度9.25），硬度非常接近，日常佩戴不易磨损；\n"
            "2. **火彩表现**：莫桑钻的色散值（0.104）高于天然钻石，在阳光下火彩更耀眼；\n"
            "3. **品质与证书**：琼华选用的每一颗莫桑石均为 D色/VVS1 级切工，并配备 GRA 独立腰码证书，支持专业复检，请放心选购！"
        )
    else:
        steps.append({"node": "语义理解", "status": "done", "detail": "常规意图应答"})
        reply = (
            "收到您的咨询！小琼随时在为您服务。琼华珠宝坚持选用天然玉石、优质珍珠与切工宝石，"
            "支持 7 天无理由退换及终身免费清洗保养。请问您今天想挑选哪类饰品？"
        )

    return reply, steps, self_corrected


@app.post("/api/v1/guide/chat")
async def guide_chat(req: GuideChatRequest):
    t0 = time.perf_counter()
    user_msg = (req.message or "").strip()

    real = await fetch_from_guide_agent(user_msg, req.history)
    if real:
        return {
            "reply": real["reply"],
            "trace": real["trace"],
            "self_corrected": any(s.get("status") == "retry" for s in real["trace"]),
            "model": "ecom-agent → AI Gateway (8000)",
            "backend": f"live:{real['backend']}@{GUIDE_PORT}",
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    reply, steps, self_corrected = local_guide_reply(user_msg)
    return {
        "reply": reply,
        "trace": steps,
        "self_corrected": self_corrected,
        "model": "本地规则引擎 (离线降级)",
        "backend": "fallback:local-demo",
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


# --------------------------------------------------------------------------- #
# API 4: 营销工场与合规质检
# --------------------------------------------------------------------------- #
BANNED_WORDS_DB = [
    {"word": "顶级", "reason": "违反《新广告法》绝对化极限词", "suggest": "高规格 / 典雅品质"},
    {"word": "第一", "reason": "违反《新广告法》极限用语，禁止排他性宣传", "suggest": "名列前茅 / 匠心之选"},
    {"word": "绝无仅有", "reason": "虚假夸大宣传", "suggest": "稀有难得 / 珍藏款"},
    {"word": "全网唯一", "reason": "不可证实的虚假陈述", "suggest": "独具匠心 / 原创设计"},
    {"word": "100%保真", "reason": "金融担保类承诺，严禁绝对化承诺", "suggest": "附权威质检证书 / 假一赔十"},
    {"word": "包治百病", "reason": "医疗夸大功效违禁词", "suggest": "温润养人 / 身心愉悦"},
]


class GenerateMarketingRequest(BaseModel):
    product_name: str = ""
    target_platform: str = "xiaohongshu"
    keywords: str = ""
    selling_points: str = ""


@app.post("/api/v1/marketing/generate")
async def generate_marketing(req: GenerateMarketingRequest):
    t0 = time.perf_counter()
    pname = (req.product_name or "").strip() or "和田碧玉平安扣吊坠"
    platform = req.target_platform

    if platform == "xiaohongshu":
        title = f"一眼惊艳！被闺蜜追着要链接的【{pname}】到底有多绝✨"
        content = f"""救命！真的没有人能拒绝天然玉石的温润感吧😭
最近刚入手的这款【{pname}】，实物比图片高级一万倍！

🌿 **材质细节**：
选用温润老料，日光下泛着通透的油脂光泽，戴上瞬间冷白皮拉满！锁骨位置恰到好处，不管是搭法式衬衫还是新中式旗袍都绝配！

💎 **关于品质**：
每一件都带权威质检证书，真正东方女性骨子里的温润与贵气～
送长辈或者犒赏自己都体面到不行，百元预算戴出万元质感！

#我的国风穿搭 #小众首饰 #东方美学 #珠宝好物分享 #{pname}"""
    elif platform == "douyin":
        title = f"【带货口播脚本】30秒讲透为什么这届年轻人都在戴{pname}？"
        content = f"""【镜头：特写首饰在光下的油脂光泽】
（主播话术，语速欢快有力）：
“所有女生！别再买那些戴两次就发黑的合金首饰了！
看一下我手上这条刚刚从展厅抢出来的——【{pname}】！

（展示质检证书与切工细节）：
天然原矿老料，一石一证，每一件都在一物一拍！
以前专柜随随便便都要两三千，今天在小琼的直播间，直接把中间商差价砍到底！
左下角小黄车直接拍，支持全国权威机构复检，假一赔十！3、2、1，上链接！”"""
    else:
        title = f"【私域臻品】温润如玉，岁岁平安 —— {pname}年度私享鉴赏"
        content = f"""尊敬的贵宾客户：

玉能养人，亦能寄托心愿。琼华工坊历时三月精雕细琢，甄选上乘玉料，为您呈献本季限定之作 ——【{pname}】。

· 原矿老料手工开相，触手温润如凝脂；
· 搭配特制国风沉香礼盒，随礼赠定制保养真皮擦布；
· VIP 私享专线特权，尊享终身免费复检与绳线焕新服务。

愿此玉伴您与家人四季常安，福泽绵长。欢迎垂询您的专属珠宝顾问。"""

    kw = req.keywords or ""
    violations = [bw for bw in BANNED_WORDS_DB if bw["word"] in pname or bw["word"] in kw]
    compliance_score = max(80, 100 - len(violations) * 10)

    return {
        "title": title,
        "content": content,
        "platform": platform,
        "compliance": {
            "score": compliance_score,
            "status": "PASS" if len(violations) == 0 else "WARNING",
            "violations": violations,
            "suggestions": (
                "文案整体合规度极高，符合各大电商与社交平台内容安全规范。"
                if len(violations) == 0
                else "注意避免使用绝对化形容词，建议采纳右侧替换建议。"
            ),
        },
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


# --------------------------------------------------------------------------- #
# API 5: 数据分析与 Text-to-SQL
# --------------------------------------------------------------------------- #
@app.get("/api/v1/analysis/overview")
async def analysis_overview():
    t0 = time.perf_counter()
    return {
        "total_records": 2450,
        "total_gmv": 1894200.0,
        "avg_order_value": 773.1,
        "completion_rate": "94.2%",
        "categories": [
            {"category": "天然玉石吊坠", "sales": 642000, "orders": 820, "growth": "+18.4%"},
            {"category": "海水/淡水珍珠", "sales": 485000, "orders": 650, "growth": "+12.1%"},
            {"category": "莫桑钻戒/饰品", "sales": 512000, "orders": 580, "growth": "+24.5%"},
            {"category": "纯银国风手镯", "sales": 255200, "orders": 400, "growth": "-6.8%"},
        ],
        "channels": [
            {"channel": "微信私域商城", "gmv": 820000, "percent": 43.3},
            {"channel": "抖音品牌直播", "gmv": 640000, "percent": 33.8},
            {"channel": "天猫官方旗舰", "gmv": 434200, "percent": 22.9},
        ],
        # 与 /overview/stats 保持一致：这套经营数字是构造的样例，如实标注来源；
        # 耗时同样是 time.perf_counter 实测，不是预设常数。
        "metrics_source": "demo-sample",
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


class AnalysisQueryRequest(BaseModel):
    query_text: str = ""


@app.post("/api/v1/analysis/query")
async def analysis_query(req: AnalysisQueryRequest):
    t0 = time.perf_counter()
    q = (req.query_text or "").strip()

    if "品类" in q or "分类" in q:
        sql = "SELECT category AS 品类, SUM(amount) AS 销售额, COUNT(*) AS 订单数 FROM orders GROUP BY category ORDER BY 销售额 DESC;"
        chart_data = {
            "type": "bar",
            "labels": ["天然玉石吊坠", "莫桑钻饰品", "珍珠首饰", "纯银手镯"],
            "data": [642000, 512000, 485000, 255200],
        }
        conclusion = "玉石吊坠与莫桑钻贡献了超过 60% 的总营收；纯银手镯本月环比微跌 6.8%，建议结合营销模块开展专场满减引流。"
        highlight_product = "纯银国风手镯"
    elif "渠道" in q or "来源" in q:
        sql = "SELECT channel AS 获客渠道, SUM(amount) AS 成交额, AVG(amount) AS 客单价 FROM orders GROUP BY channel;"
        chart_data = {
            "type": "pie",
            "labels": ["微信私域", "抖音直播", "天猫旗舰"],
            "data": [820000, 640000, 434200],
        }
        conclusion = "微信私域客单价最高（¥920/单），复购率达 34.6%，是高价值珠宝的核心出货阵地。"
        highlight_product = "高客单天然翡翠挂件"
    else:
        sql = "SELECT strftime('%Y-%m', order_date) AS 月份, SUM(amount) AS GMV FROM orders GROUP BY 1 ORDER BY 1 LIMIT 6;"
        chart_data = {
            "type": "line",
            "labels": ["5月", "6月", "7月", "8月", "9月", "10月"],
            "data": [240000, 290000, 310000, 330000, 350000, 374200],
        }
        conclusion = "近 6 个月业务呈现平稳增长态势，复合月环比增长率达到 9.2%，预计第四季度珠宝旺季有望突破 45 万月销大关。"
        highlight_product = "天然和田玉青海老料吊坠"

    return {
        "sql": sql,
        "chart": chart_data,
        "conclusion": conclusion,
        "highlight_product": highlight_product,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


# --------------------------------------------------------------------------- #
# API 6: 网关主备毫秒级热切仿真
# --------------------------------------------------------------------------- #
@app.post("/api/v1/gateway/simulate_failover")
async def simulate_failover():
    t0 = time.perf_counter()
    # 这是一个【演示用仿真端点】：不连真实上游，也【没有】任何真实模型名 ——
    # 本仓库未接入任何大模型 API，所以主路由一律写「仿真占位」，不冒充某个
    # 具体模型版本（1.0 曾硬写过一个编造的模型名，2.1 起移除并有断言防回归）。
    # 耗时是本机生成响应的实测值（time.perf_counter），非预设常数。
    await asyncio.sleep(0.042)
    return {
        "event": "CIRCUIT_BREAKER_TRIGGERED",
        "simulated": True,
        "primary_model": "上游主模型（仿真占位）",
        "primary_status": "504 Gateway Timeout (Simulated)",
        "failover_model": "本地兜底规则引擎 (Mock Fallback)",
        "failover_status": "200 OK",
        "switch_latency_ms": int((time.perf_counter() - t0) * 1000),
        "token_usage": {"prompt": 120, "completion": 310, "cost_usd": 0.00045},
        "token_usage_note": "样例数值，非真实计费",
        "log_entry": "[FAILOVER-ALERT] 上游主模型响应超时(>3000ms)，触发熔断阈值，热切至本地兜底规则引擎，业务无感重试成功！",
    }


# --------------------------------------------------------------------------- #
# API 7: 历史趋势与事件回放（数据来自共享巡检器的 SQLite 落盘）
# --------------------------------------------------------------------------- #
@app.get("/api/v1/history/probes")
async def history_probes(minutes: int = 60, buckets: int = 120):
    """按时间窗口返回各服务的在线率 / 平均延迟曲线。

    · minutes：窗口（分钟），默认 60；上限 1440（24h，即落盘保留期）
    · buckets：曲线点数上限，默认 120 —— 桶宽 = 窗口/点数，自动降采样
    """
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


@app.get("/api/v1/events/recent")
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


# --------------------------------------------------------------------------- #
# API 8: 服务起停管控（控制台卡片上的「停止 / 启动」按钮）
# --------------------------------------------------------------------------- #
# 设计约束：
#   1. stop 只允许杀「监听在拓扑配置端口上」的进程 —— 端口表之外的 PID 一律不碰；
#   2. start 只拉起 services.yaml 里配置了 start_cmd 的服务，没配置就如实返回
#      not-configured，控制台不假装知道没告诉过它的启动方式；
#   3. 起停之后**不**直接改面板状态 —— 状态由共享巡检器在下一轮探测里自然翻牌，
#      事件总线同步推送上下线事件。这也是这个按钮最有说服力的演示点。
WIN_DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def find_listener_pids(port: int) -> List[int]:
    """找出**本机**监听在 port 上的进程 PID 列表（psutil 缺失时返回空）。

    注意：这是本机视角 —— 容器里只能看到容器自己的进程，看不到宿主机上的服务。
    所以「起停」在容器化部署下只对容器内的进程有效，这是刻意的边界。
    """
    try:
        import psutil
    except ImportError:
        return []
    pids = set()
    try:
        for c in psutil.net_connections(kind="tcp"):
            if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port and c.pid:
                pids.add(c.pid)
    except Exception:  # noqa: BLE001 —— 无管理员权限时可能部分不可读
        pass
    return sorted(pids)


def stop_port_processes(port: int) -> Dict[str, Any]:
    """终止监听在 port 上的进程。这是「按端口停服务」的真实实现（非仿真）。"""
    pids = find_listener_pids(port)
    if not pids:
        return {
            "stopped": False,
            "reason": "no-listener",
            "detail": "端口 :%d 当前没有进程在监听（服务可能本就没在运行）。" % port,
        }
    import psutil

    stopped, survivors = [], []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            survivors.append(pid)
            continue
    _exit, alive = psutil.wait_procs([psutil.Process(p) for p in pids if p not in survivors], timeout=3)
    for p in alive:
        try:
            p.kill()
            stopped.append(p.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            survivors.append(p.pid)
    for pid in pids:
        if pid not in survivors and pid not in stopped:
            stopped.append(pid)
    if survivors:
        return {
            "stopped": False,
            "reason": "access-denied",
            "detail": ("进程 %s 无权限终止（可能属于其他用户，需管理员权限运行控制台）。" % survivors),
        }
    return {
        "stopped": True,
        "pids": stopped,
        "detail": "已终止监听 :%d 的进程 PID %s。" % (port, stopped),
    }


def start_service_process(meta: Dict[str, Any]) -> Dict[str, Any]:
    """按 start_cmd 拉起服务子进程（真实 Popen，非仿真），输出重定向到 data/service-logs/。"""
    cmd = meta.get("start_cmd") or []
    if not cmd:
        return {
            "started": False,
            "reason": "not-configured",
            "detail": "services.yaml 未给该服务配置 start_cmd —— 控制台不知道它该怎么启动。",
        }
    cwd = meta.get("start_cwd") or ""
    if cwd and not os.path.isdir(cwd):
        return {
            "started": False,
            "reason": "bad-cwd",
            "detail": "start_cwd 不存在：%s" % cwd,
        }
    log_dir = os.path.join(DATA_DIR, "service-logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "%s.log" % meta["id"])
    try:
        log_f = open(log_path, "ab")
    except OSError as exc:
        return {"started": False, "reason": "log-open-failed", "detail": str(exc)}
    kwargs = {
        "cwd": cwd or None,
        "stdout": log_f,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = WIN_DETACHED  # 不随控制台退出而被带走
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        return {"started": False, "reason": "spawn-failed", "detail": str(exc)}
    return {
        "started": True,
        "pid": proc.pid,
        "log": log_path,
        "detail": "子进程已拉起（PID %d），巡检器将在下一轮探测到上线并推送事件。" % proc.pid,
    }


@app.get("/api/v1/services/control-capabilities")
async def control_capabilities():
    """告诉前端每个服务能做什么操作（决定按钮可用态）。"""
    return {
        "status": "ok",
        "can_stop": True,  # 只要端口上有监听进程，stop 永远可用
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


def _service_or_404(service_id: str) -> Dict[str, Any]:
    meta = SERVICE_INDEX.get(service_id)
    if not meta:
        raise HTTPException(
            404,
            detail="未知服务 id：%s；可用：%s" % (service_id, ", ".join(SERVICE_INDEX)),
        )
    return meta


@app.post("/api/v1/services/{service_id}/stop")
async def service_stop(service_id: str):
    meta = _service_or_404(service_id)
    result = await asyncio.to_thread(stop_port_processes, meta["port"])
    return {
        "status": "ok",
        "service_id": meta["id"],
        "name": meta["name"],
        "port": meta["port"],
        "event_hint": ("巡检器将在约 %.0f 秒内探测到下线并推送事件。" % EVENT_INTERVAL_SEC)
        if result.get("stopped")
        else "",
        **result,
    }


@app.post("/api/v1/services/{service_id}/start")
async def service_start(service_id: str):
    meta = _service_or_404(service_id)
    if await is_port_online(meta["port"], PROBE_TIMEOUT):
        return {
            "status": "ok",
            "started": False,
            "reason": "already-online",
            "service_id": meta["id"],
            "name": meta["name"],
            "port": meta["port"],
            "detail": "服务已在线，无需启动。",
        }
    result = await asyncio.to_thread(start_service_process, meta)
    return {
        "status": "ok",
        "service_id": meta["id"],
        "name": meta["name"],
        "port": meta["port"],
        **result,
    }


if __name__ == "__main__":
    port = int(os.environ.get("OMNI_PORT", "8888"))
    print("=" * 57)
    print("  OmniAgent Platform %s - 企业级全域 AI 控制中枢已启动" % APP_VERSION)
    _shown = "127.0.0.1" if BIND_HOST in ("0.0.0.0", "::") else BIND_HOST
    print(f"  监听地址: {BIND_HOST}    访问主控台: http://{_shown}:{port}")
    print(f"  探测微服务的地址: {PROBE_HOST}")
    print("=" * 57)
    uvicorn.run(app, host=BIND_HOST, port=port)
