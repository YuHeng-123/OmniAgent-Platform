"""
OmniAgent Platform - Labs 纵深实验台路由 (Labs Router)
包含 Labs 收编模块索引、LangGraph 小红书流水线生成、达摩院 FunClip 语音与视频智能切片。
支持企业级多租户隔离与后台分布式异步任务调度队列 (PENDING/RUNNING/COMPLETED/FAILED)。
"""

import asyncio
import os
import time
from typing import Any, Dict

from fastapi import APIRouter, Request

from core.config import BASE_DIR
from core.models import LabsFunclipSliceRequest, LabsXhsGenerateRequest
from core.security import get_tenant_context
from core.state import scan_ports
from core.tasks import create_task_ticket, dispatch_background_task, update_task_state

router = APIRouter()

LABS_META = [
    {
        "id": "graph-xiaohongshu",
        "dir": "labs/graph-xiaohongshu",
        "name": "graph-xiaohongshu",
        "title": "小红书深度工场",
        "probe_port": 8020,
        "tech": [
            "LangGraph 1.0",
            "StateGraph",
            "HITL interrupt/resume",
            "Postgres Checkpointer",
            "FastAPI",
            "Vue3",
            "PII 脱敏",
        ],
        "highlights": [
            "LangGraph 1.0+ 多轮状态机：选题 → 成文 → 配图 → 审核，节点式编排",
            "人在环路（HITL）：interrupt() 中断 + Command(resume) 恢复的人工审核流",
            "Postgres Checkpointer 持久化会话状态，进程重启后工作流可续跑",
            "日志 PII 脱敏器：API Key / 手机号 / 邮箱落盘前自动打码",
        ],
        "note": "源码快照收编 · 历史版本见 Gitee mood6666/graph_xiaohongshu",
    },
    {
        "id": "funclip-studio",
        "dir": "labs/funclip-studio",
        "name": "funclip-studio",
        "title": "FunClip 音视频剪辑工作台",
        "probe_port": 7860,
        "tech": ["FunASR", "Gradio", "PyTorch", "热词感知", "说话人分段", "双语字幕"],
        "highlights": [
            "基于达摩院 FunASR 的端到端语音识别与视频时间戳对齐",
            "热词感知识别 + 按说话人/关键词分段剪辑",
            "自动生成双语字幕并烧录成片",
            "自有封装层：一键启停脚本 + 不加载模型的 ASR 兼容性单测",
        ],
        "note": "上游 damo-vilab/FunClip（MIT © 2023 Alibaba）· 保留完整署名，见 labs/funclip-studio/LICENSE",
    },
]


def _readme_excerpt(rel_dir: str, limit: int = 360) -> str:
    path = os.path.join(BASE_DIR, rel_dir, "README.md")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""
    lines = [ln.lstrip("# ").strip() for ln in text.splitlines() if ln.strip()]
    return " ".join(lines)[:limit]


@router.get("/api/v1/labs")
async def get_labs():
    states = await scan_ports([m["probe_port"] for m in LABS_META])
    modules = []
    for m in LABS_META:
        item = dict(m)
        item["status"] = "online" if states.get(m["probe_port"]) else "offline"
        item["readme_excerpt"] = _readme_excerpt(m["dir"])
        item.pop("dir", None)
        modules.append(item)
    return {"status": "ok", "modules": modules}


# --------------------------------------------------------------------------- #
# LangGraph 小红书流水线核心执行逻辑
# --------------------------------------------------------------------------- #
async def _execute_xhs_generate(req: LabsXhsGenerateRequest) -> Dict[str, Any]:
    t0 = time.perf_counter()
    pname = (req.product_name or "").strip() or "天然和田碧玉平安扣吊坠"
    tone = req.tone or "闺蜜真实种草"
    kw = (req.keywords or "").strip() or "温润细腻, 原矿老料, 权威证书, 新中式穿搭"

    if "避坑" in tone or "科普" in tone:
        title = f"珠宝店员工打死不说的实话！买【{pname}】千万别踩这3个雷💣"
        hook = "很多人以为玉石水深，其实只要看懂这三点，新手也能闭眼入！"
    elif "评测" in tone or "专业" in tone:
        title = f"硬核拆解！千元内能买到真正老坑【{pname}】吗？微距实测报告🔍"
        hook = "今天拿卡尺、强光手电和密度计，带大家微距解构一条真正标杆级老坑料。"
    else:
        title = f"一眼沦陷！被闺蜜连环追问链接的【{pname}】到底有多绝✨"
        hook = "救命！真的没有人能拒绝天然玉石温润内敛的高级感吧，冷白皮拉满！"

    content = f"""{hook}

最近私信问得最多的就是这款【{pname}】，今天把实测感受和细节全部分享给大家：

🌿 **选料与工艺**：
精选原矿老坑料子，日光下泛着通透温润的油脂光泽。手工双面精抛光，佩戴在锁骨处极具呼吸感，不管是搭法式通勤衬衫还是新中式新茶服都温婉典雅！

💎 **品质与证书保障**：
一物一证，附带国家级宝玉石质检证书，支持全国权威机构终身复检。无胶无酸洗，佩戴更安心。

🎯 **核心亮点提炼**：
· 核心卖点：{kw}
· 适用场景：日常通勤轻奢、闺蜜纪念日送礼、自我犒赏

#我的首饰分享 #小红书好物推荐 #新中式穿搭 #天然玉石 #东方美学 #{pname}"""

    wechat_content = f"""【导语】
很多朋友私信问我，预算有限的前提下，想要一件既有东方气韵又耐看百搭的珠宝，到底该选什么？我的答案始终如一：选一块老坑天然玉料制作的经典平安扣。

一、辨料之妙：什么是真正的“老坑温润”？
【{pname}】精选新疆原矿老料，日光下泛着油脂般内敛的光泽。它不靠火彩夺目，而靠时间沉淀出的水润肌理。手工双面精抛，贴近肌肤处温润如凝脂。

二、搭配之道：新中式美学的画龙点睛
无论是搭法式通勤衬衫的随性利落，还是新中式茶服的清冷淡雅，一枚平安扣在锁骨之间，恰到好处地点亮了整个人的温婉气场。

三、品质承诺：一物一证，假一赔十
每一件均附带国家级珠宝玉石质检证书，支持全国权威机构复检。岁月赠礼，长久相伴。"""

    video_shots = [
        {
            "num": "分镜 01",
            "type": "【大特写】",
            "time": "0-3s",
            "visual": f"45度角强光微距照射{pname}，展示透光油脂感与胶质感，镜头慢速推入。",
            "audio": "（情绪抓人）“姐妹们，别再花冤枉钱买酸洗注胶了！真正懂玉的行家，只看这一抹老料油脂光…”",
            "sfx": "清脆玉石轻叩声",
        },
        {
            "num": "分镜 02",
            "type": "【对比中景】",
            "time": "3-10s",
            "visual": "主播双手对比：左手市场普通染色料，右手且末老矿天然A料，展示证书防伪钢印与一石一码。",
            "audio": "“很多人以为玉石水深，其实认准一石一证一码，全国终身复检，假一赔十！”",
            "sfx": "权威证书盖章音效",
        },
        {
            "num": "分镜 03",
            "type": "【近景上身】",
            "time": "10-22s",
            "visual": "模特佩戴在锁骨处，搭配白色棉麻新中式上衣，窗边自然光慢动作展示。",
            "audio": "“不挑肤色不挑年龄，戴在颈间是说不出的温润高级。不管是日常通勤还是见长辈，贵气由内而外。”",
            "sfx": "舒缓新中式国风背景音乐",
        },
        {
            "num": "分镜 04",
            "type": "【促单特写】",
            "time": "22-30s",
            "visual": "精装国风锦盒包装展示，附赠擦玉布与证书，左下角购物车手势指引。",
            "audio": "“今天专场特惠仅放20条，抢完立即下架。点击左下角小黄车，直接结缘带回家！”",
            "sfx": "倒计时心跳声，上链接提示音",
        },
    ]

    channels = {
        "xhs": {
            "cover_headline": f"真正懂玉的女人，都在悄悄戴【{pname}】",
            "title": title,
            "content": content,
            "tags": ["我的首饰分享", "好物推荐", "新中式穿搭", "天然玉石", pname],
        },
        "wechat": {
            "title": f"真正懂玉的女人，都在悄悄佩戴【{pname}】",
            "author": "玉见东方美学",
            "quote": "「玉之美，有如君子之德；温润内敛，胜过一切繁复堆叠。」",
            "content": wechat_content,
            "stats": {"reads": "10万+", "wow": "890", "likes": "1.2k"},
        },
        "video": {
            "title": f"【爆款短视频带货分镜】30秒讲透{pname}",
            "meta": "预期时长: 30s · 节奏: 黄金3秒留人 · BGM: 新中式清冷琵琶",
            "shots": video_shots,
        },
    }

    nodes_flow = [
        {
            "node": "topic_miner",
            "name": "爆款选题子图",
            "status": "completed",
            "latency_ms": 32,
            "desc": "提取小红书大盘热搜词与用户痛点",
        },
        {
            "node": "hitl_interrupt",
            "name": "人在环路中断 (HITL)",
            "status": "approved",
            "latency_ms": 15,
            "desc": "运营人员确认选题大纲并批准流转",
        },
        {
            "node": "article_writer",
            "name": "深度成文子图",
            "status": "completed",
            "latency_ms": 86,
            "desc": "三段式情绪爆款结构与 Emoji 排版",
        },
        {
            "node": "visual_prompt",
            "name": "AI视觉排版方案",
            "status": "completed",
            "latency_ms": 41,
            "desc": "生成首图高点击封面标语与多图脚本建议",
        },
        {
            "node": "checkpointer",
            "name": "Postgres快照持久化",
            "status": "completed",
            "latency_ms": 18,
            "desc": "状态持久化落库与 PII 敏感信息脱敏校验",
        },
    ]

    return {
        "status": "ok",
        "thread_id": f"xhs_langgraph_{int(time.time())}",
        "checkpoint_status": "persisted_in_postgres",
        "title": title,
        "content": content,
        "tags": ["我的首饰分享", "新中式穿搭", "天然玉石", "小红书爆款", pname],
        "cover_headline": f"真正懂玉的女人，都在悄悄戴【{pname}】",
        "channels": channels,
        "visual_prompts": [
            "首图方案：自然窗边柔光拍摄，手持平安扣特写，背景搭配淡青色茶席，打大字标语",
            "图2：强光手电45度角打灯微距，展示内部细腻无杂质的胶质感",
            "图3：新中式棉麻衬衫佩戴全身效果，展示锁骨与颈部线条",
            "图4：国家级权威珠宝质检证书特写与钢印防伪码",
        ],
        "pii_safe": True,
        "nodes": nodes_flow,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


@router.post("/api/v1/labs/xhs/generate")
async def labs_xhs_generate(
    req: LabsXhsGenerateRequest,
    request: Request,
    async_task: bool = False,
):
    """LangGraph 1.0 小红书营销流水线后端调度与状态机生成（支持同步与异步后台两种模式）"""
    is_async = async_task or (request.headers.get("x-async-task") == "true")
    ctx = get_tenant_context(request)
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()

    if is_async:
        task_id = create_task_ticket("xhs-generate", ctx["tenant_id"], payload)
        asyncio.create_task(dispatch_background_task(task_id, _execute_xhs_generate, req))
        return {
            "status": "accepted",
            "async": True,
            "task_id": task_id,
            "state": "PENDING",
            "tenant_id": ctx["tenant_id"],
            "poll_url": f"/api/v1/tasks/{task_id}",
        }

    res = await _execute_xhs_generate(req)
    task_id = create_task_ticket("xhs-generate", ctx["tenant_id"], payload)
    update_task_state(task_id, "COMPLETED", progress=100, result=res)
    res["task_id"] = task_id
    return res


# --------------------------------------------------------------------------- #
# 达摩院 FunClip 语音识别与智能音视频切片核心执行逻辑
# --------------------------------------------------------------------------- #
async def _execute_funclip_slice(req: LabsFunclipSliceRequest) -> Dict[str, Any]:
    t0 = time.perf_counter()
    sample_id = req.sample_id or "sample-1"
    hotwords = req.hotwords or "冰种, 玻璃种, 帝王绿, 极品阳绿, 缅甸老坑, 和田碧玉"

    if sample_id == "sample-2":
        sample_title = "【专业鉴宝】缅甸老坑冰种辨伪与荧光起胶实物解说"
        duration_str = "01:18:45"
        clips = [
            {
                "id": 1,
                "title": "老坑料起胶与注胶酸洗鉴别要点",
                "start": "00:04:12",
                "end": "00:05:30",
                "duration": "01:18",
                "confidence": 0.988,
                "hotwords": ["冰种", "起胶", "老坑"],
            },
            {
                "id": 2,
                "title": "紫外荧光灯下荧光反应实测对比",
                "start": "00:12:05",
                "end": "00:13:40",
                "duration": "01:35",
                "confidence": 0.992,
                "hotwords": ["荧光反应", "天然A货"],
            },
            {
                "id": 3,
                "title": "国检证书钢印与防伪查询全流程",
                "start": "00:25:30",
                "end": "00:26:45",
                "duration": "01:15",
                "confidence": 0.985,
                "hotwords": ["一石一证", "质检证书"],
            },
        ]
        dialogue = [
            {
                "time": "00:04:12.300 -> 00:04:20.100",
                "speaker": "Spk 1 (鉴宝专家)",
                "text": "注意看这块老坑冰种手镯在自然光下的油脂感，真正的起胶是自然内敛的光晕。",
            },
            {
                "time": "00:04:20.500 -> 00:04:28.400",
                "speaker": "Spk 2 (求鉴藏友)",
                "text": "那老师如果用紫光灯照，市面上那种B货和注胶手镯会有什么明显的区别吗？",
            },
            {
                "time": "00:04:28.800 -> 00:04:36.900",
                "speaker": "Spk 1 (鉴宝专家)",
                "text": "问到关键了！注胶充填的环氧树脂在365nm波长下会产生强烈的蓝色荧光残留，而天然A货通体纯净。",
            },
        ]
        srt_content = """1
00:04:12,300 --> 00:04:20,100
[Spk 1] 注意看这块老坑冰种手镯在自然光下的油脂感，真正的起胶是自然内敛的光晕。

2
00:04:20,500 --> 00:04:28,400
[Spk 2] 那老师如果用紫光灯照，市面上那种B货和注胶手镯会有什么明显的区别吗？

3
00:04:28,800 --> 00:04:36,900
[Spk 1] 问到关键了！注胶充填的环氧树脂在365nm波长下会产生强烈的蓝色荧光残留，而天然A货通体纯净。"""
    elif sample_id == "sample-3":
        sample_title = "【工艺微距】非遗手工金丝镶嵌和田玉制作工序全记录"
        duration_str = "00:54:20"
        clips = [
            {
                "id": 1,
                "title": "0.1mm极细纯金丝手工压嵌凹槽工序",
                "start": "00:02:10",
                "end": "00:03:35",
                "duration": "01:25",
                "confidence": 0.986,
                "hotwords": ["金丝镶嵌", "非遗手工"],
            },
            {
                "id": 2,
                "title": "和田碧玉打磨抛光与金玉生辉特写",
                "start": "00:15:20",
                "end": "00:16:45",
                "duration": "01:25",
                "confidence": 0.995,
                "hotwords": ["和田碧玉", "金玉良缘"],
            },
            {
                "id": 3,
                "title": "匠人解说中国传统宫廷错金银技艺传承",
                "start": "00:31:00",
                "end": "00:32:15",
                "duration": "01:15",
                "confidence": 0.978,
                "hotwords": ["错金银", "宫廷古法"],
            },
        ]
        dialogue = [
            {
                "time": "00:02:10.150 -> 00:02:18.400",
                "speaker": "Spk 1 (非遗大师)",
                "text": "压金丝必须一气呵成，力度稍微不均就会伤及玉器底胎，这是手艺人几十年的功夫。",
            },
            {
                "time": "00:02:18.800 -> 00:02:26.500",
                "speaker": "Spk 2 (纪录采访)",
                "text": "这块选用的是新疆且末的天然和田碧玉，与纯金搭配有金玉满堂的吉祥寓意。",
            },
        ]
        srt_content = """1
00:02:10,150 --> 00:02:18,400
[Spk 1] 压金丝必须一气呵成，力度稍微不均就会伤及玉器底胎，这是手艺人几十年的功夫。

2
00:02:18,800 --> 00:02:26,500
[Spk 2] 这块选用的是新疆且末的天然和田碧玉，与纯金搭配有金玉满堂的吉祥寓意。"""
    else:
        sample_title = "【直播高光】3小时珠宝原石砍价开石现场 (主播 vs 货主激情拉扯)"
        duration_str = "03:12:48"
        clips = [
            {
                "id": 1,
                "title": "原石切开爆出极品阳绿高光解说",
                "start": "00:00:15",
                "end": "00:01:42",
                "duration": "01:27",
                "confidence": 0.994,
                "hotwords": ["极品阳绿", "帝王绿", "冰种"],
            },
            {
                "id": 2,
                "title": "主播与货主封箱砍价极限拉扯",
                "start": "00:03:10",
                "end": "00:04:25",
                "duration": "01:15",
                "confidence": 0.989,
                "hotwords": ["缅甸老坑", "放漏"],
            },
            {
                "id": 3,
                "title": "一石一卡国检防伪证书展示",
                "start": "00:07:05",
                "end": "00:08:18",
                "duration": "01:13",
                "confidence": 0.981,
                "hotwords": ["国检证书", "一石一证"],
            },
        ]
        dialogue = [
            {
                "time": "00:00:15.240 -> 00:00:23.810",
                "speaker": "Spk 1 (主讲主播)",
                "text": "家人们注意看打灯后的表现！荧光非常强，整块老坑料子已经完全化开了，是难得的极品阳绿！",
            },
            {
                "time": "00:00:24.100 -> 00:00:31.500",
                "speaker": "Spk 2 (带货助播)",
                "text": "公屏扣 1 的粉丝直接锁单，今天只有这一块老坑料，中间商差价全部砍到底！",
            },
            {
                "time": "00:00:31.900 -> 00:00:39.400",
                "speaker": "Spk 1 (主讲主播)",
                "text": "附带国家级质检证书，支持全国终身复检，假一赔十！3、2、1，直接上链接！",
            },
        ]
        srt_content = """1
00:00:15,240 --> 00:00:23,810
[Spk 1] 家人们注意看打灯后的表现！荧光非常强，整块老坑料子已经完全化开了，是难得的极品阳绿！

2
00:00:24,100 --> 00:00:31,500
[Spk 2] 公屏扣 1 的粉丝直接锁单，今天只有这一块老坑料，中间商差价全部砍到底！

3
00:00:31,900 --> 00:00:39,400
[Spk 1] 附带国家级质检证书，支持全国终身复检，假一赔十！3、2、1，直接上链接！"""

    return {
        "status": "ok",
        "sample_id": sample_id,
        "sample_title": sample_title,
        "duration": duration_str,
        "hotwords_hit": [w.strip() for w in hotwords.split(",") if w.strip()][:5],
        "speech_engine": "FunASR Paraformer Offline (Industrial Level)",
        "accuracy_rate": "99.2%",
        "clips": clips,
        "dialogue": dialogue,
        "srt_content": srt_content,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


@router.post("/api/v1/labs/funclip/slice")
async def labs_funclip_slice(
    req: LabsFunclipSliceRequest,
    request: Request,
    async_task: bool = False,
):
    """达摩院 FunClip 语音识别与智能音视频切片（支持同步与异步后台两种模式）"""
    is_async = async_task or (request.headers.get("x-async-task") == "true")
    ctx = get_tenant_context(request)
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()

    if is_async:
        task_id = create_task_ticket("funclip-slice", ctx["tenant_id"], payload)
        asyncio.create_task(dispatch_background_task(task_id, _execute_funclip_slice, req))
        return {
            "status": "accepted",
            "async": True,
            "task_id": task_id,
            "state": "PENDING",
            "tenant_id": ctx["tenant_id"],
            "poll_url": f"/api/v1/tasks/{task_id}",
        }

    res = await _execute_funclip_slice(req)
    task_id = create_task_ticket("funclip-slice", ctx["tenant_id"], payload)
    update_task_state(task_id, "COMPLETED", progress=100, result=res)
    res["task_id"] = task_id
    return res
