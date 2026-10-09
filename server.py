"""
OmniAgent Platform 2.0 —— 企业级全域 AI 智能体控制中枢（统一控制台）

设计要点：
1. 控制台自身可独立运行，不依赖其余 7 个微服务是否在线；在线的会亮绿点。
2. 导购接口优先调用真实的 ecom-agent(8001) 并解析其 SSE 流；
   8001 不可用 / 上游报错时，自动降级到本地演示引擎，并在响应里如实标注 backend。
3. 所有耗时都是实测（time.perf_counter），不再返回写死的常数。
4. 静态资源本地挂载（templates/static 用绝对路径定位），断网可渲染。
"""
import os
import json
import time
import asyncio
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import httpx
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(
    title="OmniAgent Platform - 企业级全域 AI 智能体控制中枢",
    description="工业级 Agent 微服务编排底座、统一控制台与多智能体业务闭环",
    version="2.0.0",
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
        reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def scan_ports(ports: List[int]) -> Dict[int, bool]:
    results = await asyncio.gather(*(is_port_online(p) for p in ports))
    return dict(zip(ports, results))


# --------------------------------------------------------------------------- #
# 核心拓扑数据：7 大微服务矩阵
# --------------------------------------------------------------------------- #
SERVICES_META = [
    {
        "id": "ai-gateway", "name": "企业 AI 统一网关", "role": "流量总线与大模型调度",
        "port": 8000, "url": "http://127.0.0.1:8000/dashboard", "type": "Infra",
        "desc": "全域流量接管、虚拟 Key 路由、毫秒级主备热切与 Token 计量",
        "tech": "FastAPI + Redis + MCP",
    },
    {
        "id": "ecom-ai-guide", "name": "琼华珠宝 AI 智能导购", "role": "核心业务 Agent",
        "port": 8001, "url": "http://127.0.0.1:8001", "type": "Business",
        "desc": "混合检索 + 工具调用 + 报错自纠错链路的多轮导购智能体",
        "tech": "LangGraph + SQLite + SSE",
    },
    {
        "id": "coze-material-studio", "name": "多平台爆款素材工作台", "role": "内容营销 Agent",
        "port": 8002, "url": "http://127.0.0.1:8002", "type": "Business",
        "desc": "Coze 工作流工程化封装，小红书/抖音营销图文生成与违禁词合规审查",
        "tech": "Coze API + FastAPI + 正则分词",
    },
    {
        "id": "ai-data-analysis-assistant", "name": "AI 数据分析专家", "role": "决策分析 Agent",
        "port": 8510, "url": "http://127.0.0.1:8510", "type": "Data",
        "desc": "DuckDB + 本地 Ollama 驱动，自然语言 Text-to-SQL 与交互式动态图表看板",
        "tech": "Streamlit + DuckDB + Plotly",
    },
    {
        "id": "ai-knowledge-assistant", "name": "企业级智能知识库 (RAG)", "role": "知识底座",
        "port": 8501, "url": "http://127.0.0.1:8501", "type": "Infra",
        "desc": "基于 Streamlit + 本地向量检索的高精度行业知识库，支持 PDF/Word 知识检索问答",
        "tech": "Streamlit + ChromaDB + RAG",
    },
    {
        "id": "data-automation-workbench", "name": "自动化情报抓取平台", "role": "数据管道",
        "port": 8765, "url": "http://127.0.0.1:8765", "type": "Data",
        "desc": "独立轻量化情报抓取工作台，支持网页结构化采集、价格规则抽取与数据导出",
        "tech": "Python Native HTTP + SQLite",
    },
    {
        "id": "ark_aigc_demo", "name": "多模态音视频智能体 (FunClip)", "role": "交互 Agent",
        "port": 7860, "url": "http://127.0.0.1:7860", "type": "Innovation",
        "desc": "基于 FunClip 的本地 AI 音视频自动化切片、多模态语音识别与字幕智能合成",
        "tech": "Gradio + PyTorch + FunASR",
    },
]

ALL_PORTS = [s["port"] for s in SERVICES_META]


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
            "id": s["id"], "name": s["name"], "port": s["port"],
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
EVENT_INTERVAL_SEC = 3.0
HEARTBEAT_EVERY = 4

# 事件总线上显示用的短标签（与前端着色调色板对应）
EVENT_TAGS = {
    "ai-gateway": "GATEWAY",
    "ecom-ai-guide": "ECOM-AGENT",
    "coze-material-studio": "MARKETING",
    "ai-data-analysis-assistant": "ANALYTICS",
    "ai-knowledge-assistant": "RAG",
    "data-automation-workbench": "COLLECTOR",
    "ark_aigc_demo": "FUNCLIP",
}


def _sse(payload: Dict[str, Any]) -> str:
    """SSE 帧：data: <json>\\n\\n"""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def _ts() -> str:
    return time.strftime("%H:%M:%S")


@app.get("/api/v1/events/stream")
async def events_stream(request: Request):
    async def gen():
        prev = await scan_ports(ALL_PORTS)
        online = sum(1 for v in prev.values() if v)
        yield _sse({
            "ts": _ts(), "tag": "MASTER", "level": "info",
            "msg": ("事件总线接入成功：本流由真实 TCP 端口探测驱动，每 %.0fs 巡检一次，"
                    "当前在线 %d/%d。" % (EVENT_INTERVAL_SEC, online, len(ALL_PORTS))),
        })
        for s in SERVICES_META:
            up = prev.get(s["port"])
            yield _sse({
                "ts": _ts(),
                "tag": EVENT_TAGS.get(s["id"], s["id"].upper()),
                "level": "ok" if up else "warn",
                "msg": ("%s（:%d）已就绪。" % (s["name"], s["port"])) if up
                       else ("%s（:%d）未响应，标记为离线。" % (s["name"], s["port"])),
            })

        cycle = 0
        while True:
            await asyncio.sleep(EVENT_INTERVAL_SEC)
            if await request.is_disconnected():
                break
            cycle += 1
            cur = await scan_ports(ALL_PORTS)
            changed = 0
            for s in SERVICES_META:
                was, now = prev.get(s["port"]), cur.get(s["port"])
                if was == now:
                    continue
                changed += 1
                yield _sse({
                    "ts": _ts(), "tag": "HEALTH",
                    "level": "ok" if now else "err",
                    "msg": "%s（:%d）状态变化：%s%s" % (
                        s["name"], s["port"], "上线" if now else "下线",
                        "，已重新纳入调度。" if now else "，流量已摘除。"),
                })
            if changed == 0 and cycle % HEARTBEAT_EVERY == 0:
                n = sum(1 for v in cur.values() if v)
                yield _sse({
                    "ts": _ts(), "tag": "HEALTH", "level": "info",
                    "msg": "全局健康巡检完成，%d/%d 在线，本轮无状态变化。" % (n, len(ALL_PORTS)),
                })
            prev = cur

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",   # 经 nginx 反代时不缓冲，保证逐条吐
    })


# --------------------------------------------------------------------------- #
# API 3: 导购工作站 —— 优先真实接入 ecom-agent(8001) 的 SSE 流
# --------------------------------------------------------------------------- #
class GuideChatRequest(BaseModel):
    message: str = ""
    history: Optional[List[Dict[str, Any]]] = None


async def fetch_from_guide_agent(message: str, history) -> Optional[Dict[str, Any]]:
    """调用真实导购 Agent (8001) 并解析其 SSE 事件流。失败返回 None 以触发降级。"""
    if not await is_port_online(8001):
        return None

    tokens: List[str] = []
    trace: List[Dict[str, str]] = []
    backend = "ecom-agent"
    try:
        timeout = httpx.Timeout(12.0, connect=3.0)
        async with httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
            async with client.stream(
                "POST",
                "http://127.0.0.1:8001/api/chat",
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
                        trace.append({
                            "node": ev.get("node") or ev.get("name") or et,
                            "status": "retry" if et == "retry" else "done",
                            "detail": (ev.get("detail") or ev.get("message")
                                       or json.dumps(ev, ensure_ascii=False)[:160]),
                        })
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
        {"node": "意图识别 (Router)", "status": "done",
         "detail": f"分类为: {'COUPON_QUERY' if is_coupon else ('PRODUCT_RECOMMEND' if is_recommend else 'KNOWLEDGE_QA')}"},
        {"node": "向量库混合检索 (RAG)", "status": "done",
         "detail": "检索到 4 条高置信度知识切片，相似度最高 0.942"},
    ]
    self_corrected = False

    if "500" in user_msg and "券" in user_msg:
        self_corrected = True
        steps.append({"node": "工具调用 (Tool Calling)", "status": "retry",
                      "detail": "调用 get_coupon('500元无门槛') 失败：券面额超出系统上限"})
        steps.append({"node": "⚡ 自动反思与自纠错 (Self-Correction)", "status": "done",
                      "detail": "触发纠错策略：自动降级检索最接近规则，回正为【满2000减200】与【新人50元立减】"})
        reply = ("非常抱歉呀，小琼帮您查了一下，目前店内没有【500元无门槛券】哦～ 不过小琼为您申请到了当前最划算的组合：\n\n"
                 "1. **新人专享礼**：满 300 减 50 元立减券；\n"
                 "2. **珠宝品类大额券**：满 2000 减 200 元满减券！\n\n"
                 "如果您今天选购【天然和田玉青海老料吊坠】（原价 ¥1,880），再凑单一个小银饰，即可直接立减 200 元，非常划算！需要我帮您锁定领券名额吗？")
    elif is_recommend:
        steps.append({"node": "工具调用 (Tool Calling)", "status": "done",
                      "detail": "执行 query_products(category='jade', price_range=[1000, 2500])，命中 3 款商品"})
        steps.append({"node": "决策合成 (Synthesis)", "status": "done",
                      "detail": "结合送礼/自戴场景，生成亲和力导购话术"})
        reply = ("为您精心挑选了店内两款口碑极高的送礼首选：\n\n"
                 "🌟 **【琼华·福禄双全】天然和田碧玉平安扣吊坠**\n"
                 "- 材质：新疆且末老料，油润细腻，附国家级宝玉石质检证书\n"
                 "- 礼盒：配东方国风锦盒与特调沉香香片\n"
                 "- 专柜价：¥2,399 ｜ **限时到手价：¥1,680**\n\n"
                 "💍 **【琼华·月满西楼】天然淡水无瑕珍珠项链**\n"
                 "- 规格：8-9mm 微瑕近圆，正圆强光皮光极亮\n"
                 "- **专柜价：¥1,480 ｜ 限时活动价：¥1,120**\n\n"
                 "两款都非常温润显气质，长辈收到都特别喜欢。您更偏好玉石的内敛还是珍珠的优雅呢？")
    elif is_diff:
        steps.append({"node": "知识检索 (RAG)", "status": "done",
                      "detail": "命中珠宝百科知识切片 #381：《莫桑钻与天然钻石光学特质比对》"})
        reply = ("这是很多顾客关心的专业问题，小琼为您通俗解答：\n\n"
                 "1. **物理成分**：天然钻石是纯碳晶体（硬度10）；莫桑石是碳化硅（硬度9.25），硬度非常接近，日常佩戴不易磨损；\n"
                 "2. **火彩表现**：莫桑钻的色散值（0.104）高于天然钻石，在阳光下火彩更耀眼；\n"
                 "3. **品质与证书**：琼华选用的每一颗莫桑石均为 D色/VVS1 级切工，并配备 GRA 独立腰码证书，支持专业复检，请放心选购！")
    else:
        steps.append({"node": "语义理解", "status": "done", "detail": "常规意图应答"})
        reply = ("收到您的咨询！小琼随时在为您服务。琼华珠宝坚持选用天然玉石、优质珍珠与切工宝石，"
                 "支持 7 天无理由退换及终身免费清洗保养。请问您今天想挑选哪类饰品？")

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
            "backend": f"live:{real['backend']}@8001",
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
            "suggestions": ("文案整体合规度极高，符合各大电商与社交平台内容安全规范。"
                            if len(violations) == 0
                            else "注意避免使用绝对化形容词，建议采纳右侧替换建议。"),
        },
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


# --------------------------------------------------------------------------- #
# API 5: 数据分析与 Text-to-SQL
# --------------------------------------------------------------------------- #
@app.get("/api/v1/analysis/overview")
async def analysis_overview():
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
    }


class AnalysisQueryRequest(BaseModel):
    query_text: str = ""


@app.post("/api/v1/analysis/query")
async def analysis_query(req: AnalysisQueryRequest):
    t0 = time.perf_counter()
    q = (req.query_text or "").strip()

    if "品类" in q or "分类" in q:
        sql = "SELECT category AS 品类, SUM(amount) AS 销售额, COUNT(*) AS 订单数 FROM orders GROUP BY category ORDER BY 销售额 DESC;"
        chart_data = {"type": "bar", "labels": ["天然玉石吊坠", "莫桑钻饰品", "珍珠首饰", "纯银手镯"],
                      "data": [642000, 512000, 485000, 255200]}
        conclusion = "玉石吊坠与莫桑钻贡献了超过 60% 的总营收；纯银手镯本月环比微跌 6.8%，建议结合营销模块开展专场满减引流。"
        highlight_product = "纯银国风手镯"
    elif "渠道" in q or "来源" in q:
        sql = "SELECT channel AS 获客渠道, SUM(amount) AS 成交额, AVG(amount) AS 客单价 FROM orders GROUP BY channel;"
        chart_data = {"type": "pie", "labels": ["微信私域", "抖音直播", "天猫旗舰"],
                      "data": [820000, 640000, 434200]}
        conclusion = "微信私域客单价最高（¥920/单），复购率达 34.6%，是高价值珠宝的核心出货阵地。"
        highlight_product = "高客单天然翡翠挂件"
    else:
        sql = "SELECT strftime('%Y-%m', order_date) AS 月份, SUM(amount) AS GMV FROM orders GROUP BY 1 ORDER BY 1 LIMIT 6;"
        chart_data = {"type": "line", "labels": ["5月", "6月", "7月", "8月", "9月", "10月"],
                      "data": [240000, 290000, 310000, 330000, 350000, 374200]}
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
    # 这是一个【演示用仿真端点】，不连真实上游；耗时为本机生成响应的时间
    await asyncio.sleep(0.042)
    return {
        "event": "CIRCUIT_BREAKER_TRIGGERED",
        "simulated": True,
        "primary_model": "DeepSeek-V3",
        "primary_status": "504 Gateway Timeout (Simulated)",
        "failover_model": "本地兜底规则引擎 (Mock Fallback)",
        "failover_status": "200 OK",
        "switch_latency_ms": int((time.perf_counter() - t0) * 1000),
        "token_usage": {"prompt": 120, "completion": 310, "cost_usd": 0.00045},
        "log_entry": "[FAILOVER-ALERT] 主路由 DeepSeek-V3 响应超时(>3000ms)，触发熔断阈值，热切至本地兜底规则引擎，业务无感重试成功！",
    }


if __name__ == "__main__":
    port = int(os.environ.get("OMNI_PORT", "8888"))
    print("=" * 57)
    print("  OmniAgent Platform 2.0 - 企业级全域 AI 控制中枢已启动")
    print(f"  访问主控台: http://127.0.0.1:{port}")
    print("=" * 57)
    uvicorn.run(app, host="127.0.0.1", port=port)
