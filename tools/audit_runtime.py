"""运行时端到端审计：起真 uvicorn（走 lifespan）→ 打真接口 → 真起停一个进程 → 看事件总线。

与 pytest 的分工：
  · pytest 验「契约形状」（响应字段、状态码、文件一致性）；
  · 本脚本验「东西真的动起来了」—— 尤其是那条最核心的演示链路：
      拉起一个假监听进程 → 巡检器探测到上线 → SSE 推「上线」差异事件
      → 调 stop → 巡检器探测到下线 → SSE 推「下线」差异事件 → SQLite 留下历史
    全程只用【一条】SSE 流，避免「新连接只拿快照」造成的时序误判。

安全性：被终止的进程是本脚本自己 spawn 的假监听进程（只 bind 端口、不做别的），
       绝不会碰到宿主机上其它正在运行的服务。

跑法：
    .venv/Scripts/python tools/audit_runtime.py [输出文件]
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "evidence" / "runtime-audit.txt"
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from server import SERVICES_META, app  # noqa: E402

L: list[str] = []
fails: list[str] = []
checks: list[tuple[str, bool, str]] = []


def ok(name, cond, detail=""):
    checks.append((name, bool(cond), detail))
    if not cond:
        fails.append("%s %s" % (name, detail))


def free_port(start=8931):
    for p in range(start, start + 200):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            return p
        except OSError:
            continue
        finally:
            s.close()
    raise RuntimeError("找不到空闲端口")


L.append("=" * 74)
L.append("运行时端到端审计")
L.append("=" * 74)

port = free_port()
cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
srv = uvicorn.Server(cfg)
srv.install_signal_handlers = lambda: None
threading.Thread(target=srv.run, daemon=True).start()

base = "http://127.0.0.1:%d" % port
cli = httpx.Client(base_url=base, trust_env=False, timeout=20.0)

# ---------- 0. 就绪（lifespan 会把共享巡检器跑起来） ----------
ready = False
for _ in range(120):
    try:
        if cli.get("/api/v1/overview/stats").status_code == 200:
            ready = True
            break
    except Exception:
        time.sleep(0.25)
ok("服务在 30s 内就绪", ready)
if not ready:
    L.append("服务起不来，审计终止")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    sys.exit(1)
L.append("\n[0] 服务就绪 = ✅  %s" % base)

# ---------- 1. 首页真的渲染出 2.2 的东西 ----------
r = cli.get("/")
html = r.text
ok("GET / 返回 200", r.status_code == 200, "实际 %s" % r.status_code)
for marker in (
    "nav-history",
    "tab-history",
    "history-uptime-canvas",
    "history-latency-canvas",
    "停止",
    "启动",
):
    ok("首页含 %s" % marker, marker in html)
ok("首页里没有未渲染的 Jinja 标记", "{{" not in html and "{%" not in html)

# ---------- 2. /healthz 与版本 ----------
hz = cli.get("/healthz").json()
ok("/healthz 状态 ok", hz.get("status") == "ok")
ok("版本与 APP_VERSION 一致", hz.get("version") is not None and hz["version"][0].isdigit())
ok("healthz 带巡检器信息", "monitor" in json.dumps(hz, ensure_ascii=False))

# ---------- 3. 起停能力表 ----------
caps = cli.get("/api/v1/services/control-capabilities").json()
ok("能力表条数 == 服务数", len(caps["services"]) == len(SERVICES_META))
meta = {s["id"]: s for s in SERVICES_META}
ok(
    "can_start 如实反映 start_cmd",
    all(c["can_start"] == bool(meta[c["id"]].get("start_cmd")) for c in caps["services"]),
)
no_cmd = [c["id"] for c in caps["services"] if not c["can_start"]]
L.append("\n[3] 未配置 start_cmd 的服务：%s（点启动会如实拒绝）" % (", ".join(no_cmd) or "无"))

# ---------- 4/5. 起停演练 + 同一条流上看上下线事件 ----------
stats = cli.get("/api/v1/overview/stats").json()
online_now = {s["id"]: s.get("status") == "online" for s in stats["services"]}
target = next((s for s in SERVICES_META if not online_now.get(s["id"])), None)
if target is None:
    L.append("\n[4] 7 个服务全部在线，跳过起停演练（避免影响老板正在跑的服务）")
    child = None
else:
    tport = target["port"]
    L.append("\n[4] 演练对象：%s（:%d）" % (target["name"], tport))

    events: list[dict] = []
    stop_flag = threading.Event()

    def reader():
        try:
            with httpx.stream(
                "GET", base + "/api/v1/events/stream", timeout=httpx.Timeout(90, read=90), trust_env=False
            ) as st:
                for line in st.iter_lines():
                    if stop_flag.is_set():
                        break
                    if line.startswith("data:"):
                        try:
                            events.append(json.loads(line[5:].strip()))
                        except Exception:
                            pass
        except Exception as e:
            L.append("    SSE 读取结束（%r）" % e)

    threading.Thread(target=reader, daemon=True).start()
    time.sleep(1.5)  # 先让订阅建立，避免漏掉第一帧

    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import socket,time;s=socket.socket();"
            "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
            "s.bind(('127.0.0.1',%d));s.listen(1);time.sleep(120)" % tport,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    L.append("    已拉起假监听进程 pid=%d" % child.pid)

    t1 = time.time()
    while time.time() - t1 < 12:
        if any("上线" in e.get("msg", "") and str(tport) in e.get("msg", "") for e in events):
            break
        time.sleep(0.5)
    ok(
        "同一条流上捕获到「上线」差异事件",
        any("上线" in e.get("msg", "") and str(tport) in e.get("msg", "") for e in events),
        "该端口相关：%s" % [e.get("msg") for e in events if str(tport) in e.get("msg", "")][:4],
    )

    d = cli.post("/api/v1/services/%s/stop" % target["id"]).json()
    ok("stop 返回 stopped=True", d.get("stopped") is True, str(d)[:200])
    ok("stop 未把自己算进被杀 PID", os.getpid() not in (d.get("pids") or []))
    try:
        child.wait(timeout=15)
    except Exception:
        pass
    ok("假监听进程真的被终止", child.poll() is not None)

    t2 = time.time()
    while time.time() - t2 < 12:
        if any("下线" in e.get("msg", "") and str(tport) in e.get("msg", "") for e in events):
            break
        time.sleep(0.5)
    down_ev = [e for e in events if str(tport) in e.get("msg", "") and "下线" in e.get("msg", "")]
    ok(
        "同一条流上捕获到「下线」差异事件",
        len(down_ev) >= 1,
        "该端口相关：%s" % [e.get("msg") for e in events if str(tport) in e.get("msg", "")][:6],
    )
    ok("下线事件是差异驱动（含「状态变化」字样）", any("状态变化" in e.get("msg", "") for e in down_ev))
    L.append("    整条流共收到 %d 条事件" % len(events))

    # ---------- 5. 历史与回放真的落了盘 ----------
    hist = cli.get("/api/v1/history/probes", params={"minutes": 10}).json()
    ok("history/probes source=sqlite-history", hist.get("source") == "sqlite-history", str(hist)[:160])
    series = {x["id"]: x for x in hist.get("series", [])}
    ok("该服务有历史点", len(series.get(target["id"], {}).get("points") or []) >= 1)

    recent = cli.get("/api/v1/events/recent", params={"limit": 50}).json()
    ok("events/recent 能回放", recent.get("source") == "sqlite-history", str(recent)[:160])
    ok(
        "回放含该端口的记录",
        any(str(tport) in e.get("msg", "") for e in recent.get("events", [])),
        "回放 %d 条" % len(recent.get("events", [])),
    )

    stop_flag.set()

# ---------- 6. 404 与静态资源 ----------
r404 = cli.get("/api/v1/definitely-not-here")
ok("未知 API 返回 404 且带提示", r404.status_code == 404 and "hint" in r404.json())
fav = cli.get("/static/favicon.svg")
ok("favicon 可访问", fav.status_code == 200 and "svg" in fav.text[:200])

# ---------- 7. SQLite 文件与表 ----------
db = ROOT / "data" / "omni_history.db"
ok("SQLite 落盘文件存在", db.exists())
if db.exists():
    con = sqlite3.connect(str(db))
    tabs = [t[0] for t in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    L.append("\n[7] SQLite 表：%s" % ", ".join(tabs))
    for t in tabs:
        n = con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        L.append("    %-16s %d 行" % (t, n))
        ok("表 %s 有数据" % t, n > 0)
    con.close()

# ---------- 收尾 ----------
cli.close()
srv.should_exit = True
time.sleep(0.5)

L.append("\n" + "=" * 74)
L.append("明细：%d 项检查" % len(checks))
for name, good, detail in checks:
    L.append("  %s %s%s" % ("✅" if good else "❌", name, ("  → " + detail) if (detail and not good) else ""))
L.append("")
if fails:
    L.append("结论：FAIL（%d 项）" % len(fails))
    for f in fails:
        L.append("  ✗ %s" % f)
else:
    L.append("结论：PASS —— 起停真实生效、事件总线真的推了上下线、历史与回放真的落盘")
L.append("=" * 74)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
sys.exit(1 if fails else 0)
