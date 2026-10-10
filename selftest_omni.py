"""
selftest_omni.py —— 一条命令跑完的离线自检

为什么要有它：控制台是长驻服务，正常要 `python server.py` 起在 8888 再看效果。
但在 CI / 无交互环境里没法长驻，所以这里在同一进程内：
  1. 用 uvicorn 在后台线程起 API（端口自动挑空闲的）
  2. 用 http.server 在后台线程起 docs/ 静态站（模拟 GitHub Pages 无后端场景）
  3. 逐个打真实 HTTP 请求，把响应落盘成证据
  4. 关掉两个服务，进程干净退出

跑法：
    .venv\\Scripts\\python.exe selftest_omni.py [证据输出路径]
"""

import http.server
import json
import os
import socket
import socketserver
import sys
import threading
import time

import httpx
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from server import SERVICES_META, app  # noqa: E402

DOCS_DIR = os.path.join(BASE_DIR, "docs")
OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "evidence", "selftest-omni.txt")

lines = []


def section(title):
    lines.append("")
    lines.append("=" * 72)
    lines.append("== " + title)
    lines.append("=" * 72)


def emit(text):
    lines.append(str(text))


def port_free(p):
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", p))
        s.close()
        return True
    except OSError:
        try:
            s.close()
        except Exception:
            pass
        return False


def pick_port(start):
    p = start
    while not port_free(p):
        p += 1
    return p


API_PORT = pick_port(8899)
STATIC_PORT = pick_port(API_PORT + 1)

# ---------------------------------------------------------------- 起 API
cfg = uvicorn.Config(app, host="127.0.0.1", port=API_PORT, log_level="error")
srv = uvicorn.Server(cfg)
srv.install_signal_handlers = lambda: None  # 非主线程装信号处理器会报错，绕开
t_api = threading.Thread(target=srv.run, daemon=True)
t_api.start()

api_up = False
for _ in range(120):
    try:
        httpx.get("http://127.0.0.1:%d/api/v1/overview/stats" % API_PORT, timeout=1.0, trust_env=False)
        api_up = True
        break
    except Exception:
        time.sleep(0.15)

if not api_up:
    emit("FATAL: API 未能在 18s 内启动")
    print("\n".join(lines))
    sys.exit(1)


# ---------------------------------------------------------------- 起静态站
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE_DIR, **kw)

    def log_message(self, *a):
        pass


httpd = socketserver.TCPServer(("127.0.0.1", STATIC_PORT), QuietHandler)
httpd.allow_reuse_address = True
threading.Thread(target=httpd.serve_forever, daemon=True).start()

client = httpx.Client(base_url="http://127.0.0.1:%d" % API_PORT, timeout=40.0, trust_env=False)
static = httpx.Client(base_url="http://127.0.0.1:%d" % STATIC_PORT, timeout=20.0, trust_env=False)

section("环境")
emit("python            = %s" % sys.version.split()[0])
emit("API 端口          = %d" % API_PORT)
emit("静态站端口        = %d  (模拟 GitHub Pages 无后端)" % STATIC_PORT)
emit("docs/ 存在        = %s" % os.path.isdir(DOCS_DIR))


# ================================================================ 第 1 组：后端 API
section("[1] GET /  主控台页面")
r = client.get("/")
emit("HTTP %d, %d bytes" % (r.status_code, len(r.content)))
emit("含 'OmniAgent'    = %s" % ("OmniAgent" in r.text))
emit(
    "含外部 CDN 引用   = %s  (必须为 False，否则断网白屏)"
    % any(
        k in r.text
        for k in ("cdn.tailwindcss.com", "cdn.jsdelivr.net", "cdnjs.cloudflare.com", "fonts.googleapis.com")
    )
)
emit("引用 ./static/    = %s" % ("./static/" in r.text or "/static/" in r.text))

section("[2] GET /api/v1/overview/stats  微服务真实在线数")
d = client.get("/api/v1/overview/stats").json()
emit(json.dumps({k: v for k, v in d.items() if k != "services"}, ensure_ascii=False, indent=2))
for s in d["services"]:
    emit("  port %-5d %-9s %s" % (s["port"], s["status"], s["name"]))

section("[3] POST /api/v1/guide/chat  导购：真上游优先，失败降级")
res = client.post(
    "/api/v1/guide/chat", json={"message": "你们支持刻字定制吗？多久发货？", "history": []}
).json()
emit("backend      = %s" % res.get("backend"))
emit("model        = %s" % res.get("model"))
emit("latency_ms   = %s   (实测，不是写死的常数)" % res.get("latency_ms"))
emit("trace 节点数 = %d" % len(res.get("trace", [])))
emit("reply 前 120 字 = %s" % res.get("reply", "")[:120].replace("\n", " "))

section("[4] POST /api/v1/guide/chat  自纠错链路（500 元券压力测试）")
res2 = client.post("/api/v1/guide/chat", json={"message": "有500元无门槛券吗", "history": []}).json()
emit("self_corrected = %s" % res2.get("self_corrected"))
for st in res2.get("trace", []):
    emit("  [%s] %s" % (st.get("status"), st.get("node")))

section("[5] POST /api/v1/marketing/generate  营销文案 + 合规质检")
mk = client.post(
    "/api/v1/marketing/generate",
    json={"product_name": "全网唯一顶级和田玉吊坠", "target_platform": "xiaohongshu", "keywords": "第一"},
).json()
emit("title       = %s" % mk.get("title"))
emit("compliance  = %s" % json.dumps(mk.get("compliance"), ensure_ascii=False))
emit("latency_ms  = %s" % mk.get("latency_ms"))

section("[6] POST /api/v1/analysis/query  Text-to-SQL")
for q in ["按品类统计销售额", "各渠道成交额", "近半年趋势"]:
    a = client.post("/api/v1/analysis/query", json={"query_text": q}).json()
    emit("Q: %s" % q)
    emit("   SQL   : %s" % a.get("sql"))
    emit("   chart : %s" % a.get("chart", {}).get("type"))
    emit("   耗时  : %s ms" % a.get("latency_ms"))

section("[7] POST /api/v1/gateway/simulate_failover  主备热切（仿真）")
fo = client.post("/api/v1/gateway/simulate_failover").json()
emit(json.dumps(fo, ensure_ascii=False, indent=2))


# ================================================================ 第 2 组：静态版（GitHub Pages 场景）
section("[8] docs/ 静态站 —— 模拟 GitHub Pages（后端不存在）")
for path, must in [
    ("/docs/", None),
    ("/docs/index.html", "OmniAgent"),
    ("/docs/static/omni-api.js", "OmniAPI"),
    ("/docs/static/vendor/tailwind.js", None),
    ("/docs/static/vendor/chart.umd.js", None),
    ("/docs/static/vendor/fontawesome/css/all.min.css", None),
    ("/docs/static/vendor/fontawesome/webfonts/fa-solid-900.woff2", None),
]:
    try:
        rr = static.get(path, follow_redirects=True)
        extra = ""
        if must:
            extra = "  含 '%s' = %s" % (must, must in rr.text)
        emit("HTTP %d  %8d B  %s%s" % (rr.status_code, len(rr.content), path, extra))
    except Exception as e:
        emit("ERR  %s : %s" % (path, e))

section("[9] 降级链路：模拟后端 404 时前端取数")
try:
    rr = static.get("/api/v1/overview/stats")
    emit(
        "静态站下 GET /api/v1/overview/stats -> HTTP %d（非 200 → 前端 omni-api.js 自动降级）"
        % rr.status_code
    )
except Exception as e:
    emit("ERR %s" % e)

section("[10] docs/index.html 静态化自检")
idx = os.path.join(DOCS_DIR, "index.html")
if os.path.exists(idx):
    html = open(idx, encoding="utf-8").read()
    emit("bytes                = %d" % len(html.encode("utf-8")))
    n_tpl = html.count("{{") + html.count("{%")
    emit("残留 Jinja2 标记     = %d  (应为 0)" % n_tpl)
    emit("残留绝对 /static/    = %d  (应为 0)" % html.count('"/static/'))
    emit("含静态演示角标逻辑   = %s" % ("静态演示模式" in html))
    emit(
        "含外部 CDN           = %s  (应为 False)"
        % any(
            k in html
            for k in (
                "cdn.tailwindcss.com",
                "cdn.jsdelivr.net",
                "cdnjs.cloudflare.com",
                "fonts.googleapis.com",
            )
        )
    )
else:
    emit("docs/index.html 不存在！")

section("[11] GET /api/v1/events/stream  中枢事件总线（SSE，真实端口探测驱动）")
sse_events = []
try:
    with client.stream(
        "GET", "/api/v1/events/stream", timeout=httpx.Timeout(30.0, connect=5.0, read=6.0)
    ) as st:
        emit("HTTP %d   content-type = %s" % (st.status_code, st.headers.get("content-type")))
        try:
            for line in st.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    sse_events.append(json.loads(line[5:].strip()))
                except Exception:
                    continue
                if len(sse_events) >= 9:
                    break
        except httpx.ReadTimeout:
            emit("(采集 %d 条后读取超时，符合预期：之后只推状态变化/心跳)" % len(sse_events))
    for ev in sse_events:
        emit("  [%s] [%-11s] (%s) %s" % (ev.get("ts"), ev.get("tag"), ev.get("level"), ev.get("msg")))
    emit("初始事件条数 = %d  (1 条接入说明 + 8 条服务就绪播报)" % len(sse_events))
except Exception as e:
    emit("ERR %s" % e)

# 事件总线已从「写死的六行文本」改为运行时拉取 —— 校验静态产物里不再有固定时间戳
if os.path.exists(idx):
    html_ev = open(idx, encoding="utf-8").read()
    emit("docs 残留写死时间戳 19:15:02 = %s  (应为 False)" % ("19:15:02" in html_ev))
    emit("docs 含 startEvents 接线     = %s  (应为 True)" % ("startEvents" in html_ev))
js_path = os.path.join(DOCS_DIR, "static", "omni-api.js")
if os.path.exists(js_path):
    js = open(js_path, encoding="utf-8").read()
    emit("docs 的 omni-api.js 含 EventSource = %s  (应为 True)" % ("EventSource" in js))
    emit("docs 的 omni-api.js 含示例降级      = %s  (应为 True)" % ("示例事件流" in js))


# ================================================================ 收尾
section("收尾")
emit("拓扑服务数 = %d" % len(SERVICES_META))
srv.should_exit = True
httpd.shutdown()
httpd.server_close()
client.close()
static.close()
time.sleep(0.6)
emit("两个服务已关闭，进程退出")

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines))

print("\n".join(lines))
print("\n[evidence] %s" % OUT_PATH)
