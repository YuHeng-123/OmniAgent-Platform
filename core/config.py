"""
OmniAgent Platform - 企业级核心配置模块 (Core Config)
集中管理全局常量、拓扑配置解析、网络监听与探测配置。
"""

import os
import time

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 版本号单一来源：页面角标、/healthz、FastAPI 自动文档都读它
APP_VERSION = "2.8.0"
STARTED_AT = time.time()

# --------------------------------------------------------------------------- #
# 核心拓扑：从 services.yaml 读取（缺失 / 解析失败时回退到内置默认）
# OMNI_CONFIG_PATH 环境变量可指向另一份拓扑 —— 供端到端自检注入假服务用，
# 正常运行读仓库根目录的 services.yaml。
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
        "desc": "FunClip 音视频自动化切片与字幕合成 · 上游源码已收编 labs/funclip-studio",
        "tech": "Gradio + PyTorch + FunASR",
    },
    {
        "id": "graph-xiaohongshu",
        "name": "内容工厂 (Labs)",
        "role": "内容营销 Agent",
        "port": 8020,
        "url": "http://127.0.0.1:8020",
        "type": "Innovation",
        "desc": "LangGraph 1.0 多轮状态机营销流水线——选题→成文→配图，HITL 人工审核中断恢复",
        "tech": "LangGraph 1.0 + Postgres Checkpointer + Vue3",
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
    "graph-xiaohongshu": "LABS-XHS",
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
BIND_HOST = os.environ.get("OMNI_HOST") or "127.0.0.1"
PROBE_HOST = os.environ.get("OMNI_PROBE_HOST") or str(PROBE.get("host") or "127.0.0.1")

# 归一化：保证无论拓扑来自 yaml 还是内置默认，每个条目都带 start_cmd / start_cwd 键
for _s in SERVICES_META:
    _s.setdefault("start_cmd", [])
    _s.setdefault("start_cwd", "")

# 按 id 索引
SERVICE_INDEX = {s["id"]: s for s in SERVICES_META}

# 导购链路的上游端口 / 路径
_GUIDE = SERVICE_INDEX.get("ecom-ai-guide")
GUIDE_PORT = int(_GUIDE["port"]) if _GUIDE else 8001
GUIDE_CHAT_PATH = (_GUIDE.get("chat_path") or "/api/chat") if _GUIDE else "/api/chat"

# 运行期数据目录
DATA_DIR = os.environ.get("OMNI_DATA_DIR") or os.path.join(BASE_DIR, "data")
PROBE_RETENTION_SEC = 24 * 3600  # 探测明细保留 24 小时
EVENT_KEEP = 1000  # 事件最多保留最近 1000 条
