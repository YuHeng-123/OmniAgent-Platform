"""
OmniAgent Platform - 业务智能体路由 (Business Router)
包含导购工作站 (AI Guide Agent)、营销素材工场 (Marketing Studio)、数据分析看板 (Text-to-SQL)。
"""

import json
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter

from core.config import GUIDE_CHAT_PATH, GUIDE_PORT, PROBE_HOST, PROBE_TIMEOUT
from core.models import AnalysisQueryRequest, GenerateMarketingRequest, GuideChatRequest
from core.state import is_port_online

router = APIRouter()


# --------------------------------------------------------------------------- #
# 导购工作站 —— 优先真实接入 ecom-agent(8001) 的 SSE 流
# --------------------------------------------------------------------------- #
async def fetch_from_guide_agent(message: str, history) -> Optional[Dict[str, Any]]:
    """调用真实导购 Agent 并解析其 SSE 事件流。失败返回 None 以触发降级。"""
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
        return None
    return {"reply": text, "trace": trace, "backend": backend}


GUIDE_PRODUCTS = [
    {
        "tag": "福禄双全",
        "name": "【玉见·福禄双全】天然和田碧玉平安扣吊坠",
        "price": 1680,
        "list": 2399,
        "spec": "新疆且末老料，油润细腻，附国家级宝玉石质检证书",
        "fit": ["长辈", "妈妈", "婆婆", "平安", "玉"],
    },
    {
        "tag": "月满西楼",
        "name": "【玉见·月满西楼】天然淡水无瑕珍珠项链",
        "price": 1120,
        "list": 1480,
        "spec": "8-9mm 微瑕近圆，正圆强光皮光极亮",
        "fit": ["长辈", "妈妈", "婆婆", "优雅", "珍珠", "通勤"],
    },
    {
        "tag": "星辰大海",
        "name": "【玉见·星辰大海】D色莫桑钻经典六爪戒指",
        "price": 699,
        "list": 2999,
        "spec": "D色/VVS1 切工，GRA 独立腰码证书，火彩直逼天然钻",
        "fit": ["女友", "老婆", "求婚", "结婚", "纪念", "戒指", "莫桑"],
    },
    {
        "tag": "竹报平安",
        "name": "【玉见·竹报平安】天然和田玉青白玉竹节手串",
        "price": 668,
        "list": 880,
        "spec": "青白玉竹节雕工，15颗均色，弹力绳双层打结",
        "fit": ["自己", "手串", "日常", "玉"],
    },
    {
        "tag": "鸿运当头",
        "name": "【玉见·鸿运当头】天然南红玛瑙平安无事牌",
        "price": 968,
        "list": 1280,
        "spec": "川料柿子红，满色满肉，牌形方正",
        "fit": ["爸爸", "男士", "本命年", "转运"],
    },
    {
        "tag": "映月",
        "name": "【玉见·映月】925银镶和田玉小方牌项链",
        "price": 359,
        "list": 459,
        "spec": "入门款，青白玉小方牌+925银链，白领通勤首选",
        "fit": ["入门", "学生", "预算", "通勤", "项链"],
    },
    {
        "tag": "岁岁团圆",
        "name": "【玉见·岁岁团圆】天然珍珠耳钉 7-8mm",
        "price": 528,
        "list": 680,
        "spec": "正圆强光，耳针925银，配防丢耳塞",
        "fit": ["女友", "老婆", "耳饰", "珍珠", "日常"],
    },
    {
        "tag": "金玉满堂",
        "name": "【玉见·金玉满堂】足金镶嵌和田玉小吊坠",
        "price": 1688,
        "list": 1980,
        "spec": "足金镶口+和田青玉，金玉良缘的经典组合",
        "fit": ["金", "贵气", "婚嫁", "妈妈"],
    },
]

GUIDE_COUPON_REPLY = (
    "现在店内能叠的优惠小玉帮您理好了：\n\n"
    "1. **新人专享礼**：满 300 减 50 元立减券（下单页自动带出）；\n"
    "2. **珠宝品类大额券**：满 2000 减 200 元，玉石/珍珠通用；\n"
    "3. **私域暗号**：直播间蹲「整点福袋」，可抽 88 折码，与大额券二选一不叠加。\n\n"
    "搭配建议：选【映月】925银镶和田玉方牌（¥359）可直接用新人券；两件拼到 ¥2,000 用大额券最划算。需要我按您的预算配个组合吗？"
)

GUIDE_AFTER_SALES_REPLY = (
    "小玉把售后政策给您讲清楚，放心买：\n\n"
    "1. **7 天无理由退换**：签收起 7 天内、吊牌完好的都可退换，店铺运费险已默认勾选；\n"
    "2. **1 年免费质保**：绳线老化、佩戴中断线，免费换新绳并重新手工编织；\n"
    "3. **终身免费养护**：清洗、抛光、换耳针，寄回或到店都行；\n"
    "4. **证书复验**：每件附国家级 CMA/CNAS 质检证书，支持任何权威机构复检，假一赔十。\n\n"
    "您是想办理退换，还是想给手上的宝贝做个养护？"
)

GUIDE_CARE_JADE_REPLY = (
    "玉石保养记住「三避一养」就够了：\n\n"
    "1. **避磕碰**：玉硬度高但脆，运动、健身、做家务建议取下；\n"
    "2. **避化学品**：香水、洗手液会慢慢蚀损光泽，护肤化妆完成后再佩戴；\n"
    "3. **避高温暴晒**：长期暴晒会让玉「失水」发干，洗澡温泉记得摘；\n"
    "4. **常佩戴是最好的养玉**：人体油脂让玉越来越温润，「人养玉三年，玉养人一生」。\n\n"
    "日常用软布蘸清水擦干即可，**忌超声波机洗**。到店可免费做一次深度养护～"
)

GUIDE_CARE_PEARL_REPLY = (
    "珍珠是有机宝石，比玉石更娇贵，记住「后戴先摘」四个字：\n\n"
    "1. 化妆、喷香水**之后**再戴——汗液与化妆品的酸碱会蚀损珍珠层；\n"
    "2. 回家卸妆**之前**先摘，用眼镜布这类软布干擦汗渍；\n"
    "3. 存放时平铺在绒布盒里，**别挂在钩上**（珠层怕拉丝）；\n"
    "4. 忌直接水洗——项链绳线遇水易松，脏了寄回，免费做超声波护理。"
)

GUIDE_COMPARE_REPLY = (
    "很多顾客在玉和珍珠之间纠结，其实看场景就清楚了：\n\n"
    "- **送长辈、讲平安寓意** → 选玉。和田玉温润内敛，平安扣、无事牌都是经典；\n"
    "- **日常通勤、气质百搭** → 选珍珠。正圆强光最抬气色，衬衫针织全适配；\n"
    "- **预算 500-800** → 珍珠耳钉或玉手串最从容；**预算 1500+** → 碧玉吊坠、珍珠项链一步到位。\n\n"
    "当然不少老客是「左手玉、右手珠」都收 😊 您想先看哪一类？"
)


def _recommend_hit(user_msg: str) -> bool:
    return any(k in user_msg for k in ["推荐", "买", "送", "项链", "手串", "戒指", "玉", "翡翠", "看", "挑"])


def _pick_guide_product(user_msg: str):
    scored = []
    for p in GUIDE_PRODUCTS:
        s = sum(1 for k in p["fit"] if k in user_msg)
        if s:
            scored.append((s, p))
    scored.sort(key=lambda t: -t[0])
    if scored:
        top_score = scored[0][0]
        return [p for s, p in scored if s == top_score][:3]

    m = re.search(r"(\d{3,5})", user_msg)
    if m:
        budget = int(m.group(1))
        in_range = [p for p in GUIDE_PRODUCTS if p["price"] <= budget * 1.2]
        in_range.sort(key=lambda p: -p["price"])
        if in_range:
            return in_range[:3]
        return sorted(GUIDE_PRODUCTS, key=lambda p: p["price"])[:2]
    return []


def local_guide_reply(user_msg: str):
    is_coupon = any(k in user_msg for k in ["券", "优惠", "打折", "便宜", "省钱", "满减"])
    is_diff = any(k in user_msg for k in ["区别", "真假", "莫桑", "培育", "天然", "证书"])
    is_after_sales = any(k in user_msg for k in ["退", "换", "售后", "保修", "维修", "断线", "坏"])
    is_care = any(k in user_msg for k in ["保养", "清洗", "变黑", "氧化", "佩戴", "护理", "发干"])
    is_compare = any(k in user_msg for k in ["哪个好", "比", "vs", "选", "值得"]) and (
        "玉" in user_msg or "珍珠" in user_msg
    )
    if is_coupon:
        intent_label = "COUPON_QUERY"
    elif is_after_sales:
        intent_label = "AFTER_SALES"
    elif is_care:
        intent_label = "CARE_GUIDE"
    elif is_compare:
        intent_label = "MATERIAL_COMPARE"
    elif is_diff:
        intent_label = "KNOWLEDGE_QA"
    elif _recommend_hit(user_msg) or _pick_guide_product(user_msg):
        intent_label = "PRODUCT_RECOMMEND"
    else:
        intent_label = "KNOWLEDGE_QA"

    steps = [
        {
            "node": "意图识别 (Router)",
            "status": "done",
            "detail": f"分类为: {intent_label}",
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
            "非常抱歉呀，小玉帮您查了一下，目前店内没有【500元无门槛券】哦～ 不过小玉为您申请到了当前最划算的组合：\n\n"
            "1. **新人专享礼**：满 300 减 50 元立减券；\n"
            "2. **珠宝品类大额券**：满 2000 减 200 元满减券！\n\n"
            "如果您今天选购【天然和田玉青海老料吊坠】（原价 ¥1,880），再凑单一个小银饰，即可直接立减 200 元，非常划算！需要我帮您锁定领券名额吗？"
        )
    elif is_coupon:
        steps.append(
            {
                "node": "工具调用 (Tool Calling)",
                "status": "done",
                "detail": "执行 list_coupons(active=True)，返回 2 张可用券 + 1 条直播福袋规则",
            }
        )
        reply = GUIDE_COUPON_REPLY
    elif is_after_sales:
        steps.append(
            {
                "node": "工具调用 (Tool Calling)",
                "status": "done",
                "detail": "执行 query_after_sales_policy()，命中《售后服务手册 v3.2》4 条",
            }
        )
        reply = GUIDE_AFTER_SALES_REPLY
    elif is_care:
        pearl = "珍珠" in user_msg
        steps.append(
            {
                "node": "知识检索 (RAG)",
                "status": "done",
                "detail": "命中《珠宝养护百科》切片 #%s"
                % ("117：珍珠（有机宝石）养护" if pearl else "092：和田玉日常养护"),
            }
        )
        reply = GUIDE_CARE_PEARL_REPLY if pearl else GUIDE_CARE_JADE_REPLY
    elif is_compare:
        steps.append(
            {
                "node": "知识检索 (RAG)",
                "status": "done",
                "detail": "命中珠宝百科切片 #402：《选品指南：玉石 vs 有机宝石》",
            }
        )
        reply = GUIDE_COMPARE_REPLY
    elif is_diff:
        steps.append(
            {
                "node": "知识检索 (RAG)",
                "status": "done",
                "detail": "命中珠宝百科知识切片 #381：《莫桑钻与天然钻石光学特质比对》",
            }
        )
        reply = (
            "这是很多顾客关心的专业问题，小玉为您通俗解答：\n\n"
            "1. **物理成分**：天然钻石是纯碳晶体（硬度10）；莫桑石是碳化硅（硬度9.25），硬度非常接近，日常佩戴不易磨损；\n"
            "2. **火彩表现**：莫桑钻的色散值（0.104）高于天然钻石，在阳光下火彩更耀眼；\n"
            "3. **品质与证书**：玉见选用的每一颗莫桑石均为 D色/VVS1 级切工，并配备 GRA 独立腰码证书，支持专业复检，请放心选购！"
        )
    else:
        picks = _pick_guide_product(user_msg)
        if picks:
            steps.append(
                {
                    "node": "工具调用 (Tool Calling)",
                    "status": "done",
                    "detail": "执行 query_products(keywords=%r)，命中 %d 款商品"
                    % (user_msg[:12], len(picks)),
                }
            )
            steps.append(
                {
                    "node": "决策合成 (Synthesis)",
                    "status": "done",
                    "detail": "结合送礼/自戴场景与预算，生成亲和力导购话术",
                }
            )
            icons = ["🌟", "💍", "📿"]
            lines = ["按您提到的需求，小玉挑了这几款最合适的：", ""]
            for i, p in enumerate(picks):
                lines.append(
                    "%s **%s**\n- %s\n- 专柜价 ¥%s ｜ **限时到手价：¥%s**"
                    % (
                        icons[i % len(icons)],
                        p["name"],
                        p["spec"],
                        format(p["list"], ","),
                        format(p["price"], ","),
                    )
                )
                lines.append("")
            lines.append("您更中意哪一款？我可以帮您把参数、证书样张再展开讲讲～")
            reply = "\n".join(lines).rstrip()
        else:
            steps.append({"node": "语义理解", "status": "done", "detail": "常规意图应答"})
            welcome_pool = [
                "收到您的咨询！小玉随时在为您服务。玉见珠宝坚持选用天然玉石、优质珍珠与切工宝石，"
                "支持 7 天无理由退换及终身免费清洗保养。请问您今天想挑选哪类饰品？",
                "您好呀～小玉在的。无论想找送长辈的平安扣、送爱人的珍珠，还是日常戴的入门款，"
                "告诉我场合和预算，我来帮您配三套方案。也可以直接问我优惠、售后和保养～",
                "欢迎光临玉见珠宝 🌸 小玉可以帮您：按预算选款、讲清证书与材质、查优惠组合、"
                "安排售后养护。您先说说想看哪一类？",
            ]
            reply = welcome_pool[len(user_msg) % len(welcome_pool)]

    return reply, steps, self_corrected


@router.post("/api/v1/guide/chat")
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
# 营销工场与合规质检
# --------------------------------------------------------------------------- #
BANNED_WORDS_DB = [
    {"word": "顶级", "reason": "违反《新广告法》绝对化极限词", "suggest": "高规格 / 典雅品质"},
    {"word": "第一", "reason": "违反《新广告法》极限用语，禁止排他性宣传", "suggest": "名列前茅 / 匠心之选"},
    {"word": "最好", "reason": "违反《广告法》绝对化用语", "suggest": "品质出众"},
    {"word": "最佳", "reason": "违反《广告法》绝对化用语", "suggest": "出色之选"},
    {"word": "最高级", "reason": "《广告法》明令禁止用语", "suggest": "高级感 / 轻奢质感"},
    {"word": "国家级", "reason": "《广告法》禁止的无依据等级用语", "suggest": "权威认证（附证书编号）"},
    {"word": "世界级", "reason": "无依据的等级用语", "suggest": "国际水准设计"},
    {"word": "绝无仅有", "reason": "虚假夸大宣传", "suggest": "稀有难得 / 珍藏款"},
    {"word": "全网唯一", "reason": "不可证实的虚假陈述", "suggest": "独具匠心 / 原创设计"},
    {"word": "全网最低", "reason": "价格绝对化承诺，无法证实", "suggest": "限时优惠价"},
    {"word": "销量第一", "reason": "排他性数据宣传，需权威数据支撑", "suggest": "热销口碑款"},
    {"word": "永久", "reason": "绝对化承诺，不可证实", "suggest": "长期有效"},
    {"word": "永远", "reason": "绝对化承诺", "suggest": "长久相伴"},
    {"word": "100%保真", "reason": "金融担保类承诺，严禁绝对化承诺", "suggest": "附权威质检证书 / 假一赔十"},
    {"word": "假一赔万", "reason": "赔付承诺过度，超出可履行范围", "suggest": "假一赔十（写入售后条款）"},
    {"word": "纯天然无添加", "reason": "绝对化质量承诺", "suggest": "天然原矿（附证书）"},
    {"word": "无效退款", "reason": "功效类退款承诺", "suggest": "不满意支持 7 天退换"},
    {"word": "稳赚", "reason": "投资回报承诺，涉金融风险", "suggest": "具有收藏价值"},
    {"word": "升值", "reason": "投资收益承诺，不可证实", "suggest": "具有收藏潜力"},
    {"word": "包治百病", "reason": "医疗夸大功效违禁词", "suggest": "温润养人 / 身心愉悦"},
    {"word": "抗衰老", "reason": "医疗功效宣传，饰品不具备", "suggest": "温润养人"},
    {"word": "立即见效", "reason": "功效承诺", "suggest": "佩戴体验佳"},
    {"word": "保平安", "reason": "功效承诺（平台敏感词）", "suggest": "平安寓意"},
    {"word": "辟邪", "reason": "封建迷信宣传，平台禁止", "suggest": "祈福寓意"},
    {"word": "开光", "reason": "封建迷信宣传，平台禁止", "suggest": "祈愿主题设计"},
    {"word": "镇宅", "reason": "封建迷信宣传", "suggest": "居家陈设雅趣"},
    {"word": "招财", "reason": "迷信功效宣传（部分平台禁）", "suggest": "美好寓意"},
    {"word": "祖传", "reason": "虚构渊源宣传", "suggest": "传统工艺"},
    {"word": "宫廷御用", "reason": "虚假出身宣传", "suggest": "宫廷风设计"},
    {"word": "包老", "reason": "年代不可证实的宣传", "suggest": "经典器形"},
]


@router.post("/api/v1/marketing/generate")
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
以前专柜随随便便都要两三千，今天在小玉的直播间，直接把中间商差价砍到底！
左下角小黄车直接拍，支持全国权威机构复检，假一赔十！3、2、1，上链接！”"""
    elif platform == "tmall":
        title = f"【玉见甄选】{pname} —— 一证一物，戴得放心"
        content = f"""【商品亮点】
· {req.selling_points.strip() or "原矿老料 · 手工精雕 · 一物一证"}
· 权威机构质检证书随货同行，支持任意权威机构复检

【参数规格】
· 材质：天然和田玉 / 淡水珍珠 / 莫桑石（按款）｜金属：S925 / 足金镶口
· 赠品：东方国风锦盒 + 沉香香片 + 专业擦玉布 + 证书保护套

【贴心服务】
✓ 7 天无理由退换（吊牌完好），运费险默认赠送
✓ 1 年免费换绳织补，终身免费清洗养护
✓ 收货后 48 小时内发货，顺丰保价包邮

【温馨提示】玉石色泽自然天成，同一块料不同光线下呈现略有差异，实物为准。"""
    elif platform == "moments":
        title = f"朋友圈日常分享 · {pname}"
        content = f"""老客都懂，一年就开两次的玉料 😊
【{pname}】到货实拍，日光下没加滤镜。

· 温润挂，上手比照片好看十倍
· 证书齐全，支持复检（不接受验货可以退）
· 这批只有 12 件，老规矩：老客优先，先到先挑

私信我发细节图，暗号「看货」📖"""
    else:
        title = f"【私域臻品】温润如玉，岁岁平安 —— {pname}年度私享鉴赏"
        content = f"""尊敬的贵宾客户：

玉能养人，亦能寄托心愿。玉见工坊历时三月精雕细琢，甄选上乘玉料，为您呈献本季限定之作 ——【{pname}】。

· 原矿老料手工开相，触手温润如凝脂；
· 搭配特制国风沉香礼盒，随礼赠定制保养真皮擦布；
· VIP 私享专线特权，尊享终身免费复检与绳线焕新服务。

愿此玉伴您与家人四季常安，福泽绵长。欢迎垂询您的专属珠宝顾问。"""

    kw = req.keywords or ""
    haystack = pname + "|" + kw + "|" + title + "|" + content
    violations = [bw for bw in BANNED_WORDS_DB if bw["word"] in haystack]
    compliance_score = max(60, 100 - len(violations) * 10)

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
# 数据分析与 Text-to-SQL
# --------------------------------------------------------------------------- #
@router.get("/api/v1/analysis/overview")
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
        "metrics_source": "demo-sample",
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


@router.post("/api/v1/analysis/query")
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
    elif "客单" in q or "复购" in q:
        sql = (
            "SELECT channel AS 渠道, ROUND(AVG(amount),1) AS 客单价, "
            "ROUND(SUM(CASE WHEN is_repurchase=1 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) AS 复购率 "
            "FROM orders GROUP BY channel;"
        )
        chart_data = {
            "type": "bar",
            "labels": ["微信私域", "抖音直播", "天猫旗舰"],
            "data": [920, 640, 588],
        }
        conclusion = (
            "私域客单价 ¥920、复购率 34.6% 双第一；直播间拉新强但留存弱（复购 22.1%），"
            "建议直播话术固定埋点「加企微领保养券」，把公域流量沉到私域。"
        )
        highlight_product = "私域专供高定款"
    elif "top" in q.lower() or "最畅销" in q or "爆款" in q or "排行" in q:
        sql = (
            "SELECT product_name AS 商品, SUM(qty) AS 销量, SUM(amount) AS 销售额 "
            "FROM orders GROUP BY product_name ORDER BY 销售额 DESC LIMIT 5;"
        )
        chart_data = {
            "type": "bar",
            "labels": ["碧玉平安扣", "莫桑六爪戒指", "珍珠项链", "竹节手串", "南红无事牌"],
            "data": [186000, 152000, 141000, 96000, 88000],
        }
        conclusion = (
            "碧玉平安扣连续 3 个月销冠，是利润基本盘；莫桑戒指靠直播翻 2.4 倍但毛利偏低，"
            "定位引流款，不要占用核心玉石的推广预算。"
        )
        highlight_product = "天然和田碧玉平安扣"
    elif "新客" in q or "会员" in q or "用户" in q:
        sql = (
            "SELECT strftime('%Y-%m', first_order_date) AS 月份, COUNT(*) AS 新客数 "
            "FROM customers GROUP BY 1 ORDER BY 1 LIMIT 6;"
        )
        chart_data = {
            "type": "line",
            "labels": ["5月", "6月", "7月", "8月", "9月", "10月"],
            "data": [310, 345, 380, 412, 438, 465],
        }
        conclusion = (
            "新客月均增速 +8.4%，六成来自抖音直播间；会员复购贡献 41% GMV。"
            "建议把「新人 50 元券」与私域入会动作绑定，先入会再发券。"
        )
        highlight_product = "新人首单引流款"
    elif "退货" in q or "退款" in q or "售后率" in q:
        sql = (
            "SELECT category AS 品类, ROUND(SUM(CASE WHEN status='refunded' THEN 1 ELSE 0 END)"
            "*100.0/COUNT(*),2) AS 退款率 FROM orders GROUP BY category;"
        )
        chart_data = {
            "type": "bar",
            "labels": ["莫桑钻饰品", "纯银手镯", "珍珠首饰", "天然玉石"],
            "data": [8.2, 5.6, 4.1, 2.3],
        }
        conclusion = (
            "莫桑钻退款率 8.2% 最高，主因「火彩预期差」——详情页补实拍视频可压一半；"
            "玉石 2.3% 最低，品质信任度最高，可加大投放。"
        )
        highlight_product = "碧玉平安扣（低退款标杆）"
    elif "环比" in q or "增长" in q or "趋势" in q:
        sql = (
            "SELECT strftime('%Y-%m', order_date) AS 月份, SUM(amount) AS GMV, "
            "LAG(SUM(amount)) OVER (ORDER BY 1) AS 上月GMV FROM orders GROUP BY 1;"
        )
        chart_data = {
            "type": "line",
            "labels": ["3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月"],
            "data": [188000, 205000, 240000, 290000, 310000, 330000, 350000, 374200],
        }
        conclusion = (
            "环比连续 7 个月为正，Q3 月均环比 +9.7%；按当前斜率 Q4 首月可突破 ¥40 万。"
            "注意 10 月增速放缓到 +6.9%，需观察是否受大促透支影响。"
        )
        highlight_product = "天然和田玉青海老料吊坠"
    else:
        sql = "SELECT strftime('%Y-%m', order_date) AS 月份, SUM(amount) AS GMV FROM orders GROUP BY 1 ORDER BY 1 LIMIT 6;"
        chart_data = {
            "type": "line",
            "labels": ["5月", "6月", "7月", "8月", "9月", "10月"],
            "data": [240000, 290000, 310000, 330000, 350000, 374200],
        }
        conclusion = "近 6 个月业务呈现平稳增长态势，复合月环比增长率达到 9.2%，预计第四季度珠宝旺季有望突破 45 万月销大关。试试问我：品类结构 / 渠道分布 / 客单价与复购 / 爆款排行 / 新客趋势 / 退款率 / 环比增长。"
        highlight_product = "天然和田玉青海老料吊坠"

    return {
        "sql": sql,
        "chart": chart_data,
        "conclusion": conclusion,
        "highlight_product": highlight_product,
        "metrics_source": "demo-sample",
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }
