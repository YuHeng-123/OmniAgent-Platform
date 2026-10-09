"""
verify_event_bus.py —— 证明「中枢事件总线」是**差异驱动**的，而不是定时播报固定文本

为什么需要它：
  事件总线最有说服力的一句宣传是「你把一个服务停掉，面板上会真的出现下线事件」。
  但这句话不验证就只是自夸。本脚本用**注入式端口探测**做端到端验证：
    · 巡检器第 1 轮探测：取真实结果 → 期望 8 条初始事件（1 条接入说明 + 7 条就绪播报）
    · 巡检器第 2 轮探测：把 :7860 的在线状态**翻转** → 期望出现 1 条「状态变化」事件
    · 之后无变化 → 每 4 轮期望出现 1 条「巡检心跳」
  全程走真实 HTTP + 真实 SSE 流，唯一被替换的是底层单端口探测函数
  （否则就得真去关掉用户正在跑的服务，那不行）。

  2.2 起事件总线由共享巡检器（ServiceMonitor）驱动：无论有没有人开着 SSE 流，
  探测每 3 秒都在发生、事件都在落盘。所以本脚本的注入点是 probe_port()
  （巡检器逐端口探测用的函数），并等巡检器跑完第 1 轮后再开流取断言。

  断言只看「有没有因为差异而推事件」，不看「服务到底在不在线」——
  所以无论本机 7 个服务是开着还是没开，这个验证都能跑出确定结论。

跑法：
    .venv\\Scripts\\python.exe verify_event_bus.py [证据输出路径]
"""

import json
import os
import socket
import sys
import threading
import time

import httpx
import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import server  # noqa: E402

OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "evidence", "event-bus-diff.txt")

# ---------------------------------------------------------------- 注入式探测
REAL_PROBE = server.probe_port
FLIP_PORT = 7860  # 巡检器第 2 轮起把 FunClip 的在线状态翻转
_flip = {"calls": 0, "first": None, "online": 0}


async def fake_probe(port, timeout=0.35):
    """单端口探测注入。

    对 FLIP_PORT：第 1 次调用（巡检器第 1 轮）返回真实结果并记下；
    第 2 次起（后续轮次）把在线状态**翻转**。
    「翻转」而不是「置为离线」—— 脚本必须与运行环境无关：
      · 服务本来在线 → 翻成离线，验证「下线」事件
      · 服务本来没起 → 翻成上线，验证「上线」事件
    其他端口一律直通真实探测。
    """
    online, latency = await REAL_PROBE(port, timeout)
    if port != FLIP_PORT:
        return online, latency
    _flip["calls"] += 1
    if _flip["calls"] == 1:
        _flip["first"] = bool(online)
    else:
        online = not _flip["first"]
    return online, latency


server.probe_port = fake_probe


def free_port(start):
    p = start
    while True:
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            s.close()
            p += 1


PORT = free_port(8920)

cfg = uvicorn.Config(server.app, host="127.0.0.1", port=PORT, log_level="error")
srv = uvicorn.Server(cfg)
srv.install_signal_handlers = lambda: None
threading.Thread(target=srv.run, daemon=True).start()

lines = []
lines.append("=" * 72)
lines.append("== 事件总线「差异驱动」端到端验证  (注入点：probe_port，驱动源：共享巡检器)")
lines.append("=" * 72)
lines.append("服务端口        = %d" % PORT)
lines.append("注入规则        = 巡检器第 1 轮取真实结果；第 2 轮起把 :%d 的在线状态翻转" % FLIP_PORT)
lines.append("                  （所以本机服务开着或没开，都能验出结论）")
lines.append("")

# 等巡检器跑完第 1 轮（patch 已生效，第 1 轮的真实结果已被记录），
# 同时用 healthz 确认 monitor 真的活着 —— 这本身就是 2.2 架构的一次自检。
t_wait = time.time()
ready = False
for _ in range(200):
    try:
        r = httpx.get("http://127.0.0.1:%d/healthz" % PORT, timeout=1.0, trust_env=False).json()
        if r.get("monitor", {}).get("cycle", 0) >= 1 and _flip["calls"] >= 1:
            ready = True
            break
    except Exception:
        pass
    time.sleep(0.2)
lines.append(
    "巡检器状态      = %s (第 1 轮完成耗时 %.1fs, cycle=%s)"
    % (
        "READY" if ready else "TIMEOUT",
        time.time() - t_wait,
        r.get("monitor", {}).get("cycle") if ready else "-",
    )
)
if not ready:
    lines.append("结论: FAIL —— 共享巡检器未能在超时内完成第一轮探测")
    text = "\n".join(lines)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(text)
    sys.exit(1)

events = []
t0 = time.time()
# n1 必须在开流「前」取 —— MONITOR.states 此刻还是第 1 轮的真实快照；
# 开流后第 2 轮翻转就会把它覆盖掉。
n1 = sum(1 for p in server.ALL_PORTS if server.MONITOR.states.get(p))
total = len(server.ALL_PORTS)
try:
    with httpx.stream(
        "GET",
        "http://127.0.0.1:%d/api/v1/events/stream" % PORT,
        timeout=httpx.Timeout(60.0, connect=5.0, read=20.0),
        trust_env=False,
    ) as st:
        lines.append("HTTP %d   content-type = %s" % (st.status_code, st.headers.get("content-type")))
        lines.append("-" * 72)
        try:
            for line in st.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except Exception:
                    continue
                events.append(ev)
                lines.append(
                    "  T+%5.1fs  [%s] [%-11s] (%s) %s"
                    % (time.time() - t0, ev.get("ts"), ev.get("tag"), ev.get("level"), ev.get("msg"))
                )
                if len(events) >= 10:
                    break
        except httpx.ReadTimeout:
            lines.append("  (读取超时，已采集 %d 条)" % len(events))
except Exception as e:
    lines.append("ERR %s" % e)

lines.append("-" * 72)
initial = events[:8]
changed = [e for e in events if "状态变化" in e.get("msg", "") and "无状态变化" not in e.get("msg", "")]
# 注意排除「本轮无状态变化」这句心跳文案 —— 它含「状态变化」子串，
# 不排除的话心跳会被误算成一次状态变化（实测踩过）。
beat = [e for e in events if "巡检完成" in e.get("msg", "")]

# 巡检器第 1 轮的真实在线数 —— 初始播报里应该正好有这么多条 ok（开流前已取）
initial_ok = [e for e in initial[1:] if e.get("level") == "ok"]
flip_dir = "下线" if _flip["first"] else "上线"

lines.append("注入方向           = :%d 翻转为「%s」" % (FLIP_PORT, flip_dir))
lines.append("巡检器第 1 轮在线数= %d/%d" % (n1, total))
lines.append("初始事件条数       = %d  (期望 8)" % len(initial))
lines.append("初始 ok 条数       = %d  (应等于第 1 轮在线数 %d)" % (len(initial_ok), n1))
lines.append("接入说明在线数一致 = %s" % (("当前在线 %d/%d" % (n1, total)) in initial[0].get("msg", "")))
lines.append("捕获「状态变化」   = %d 条  (期望 >=1，且含 :%d)" % (len(changed), FLIP_PORT))
lines.append("捕获「巡检心跳」   = %d 条  (期望 >=1)" % len(beat))

ok = (
    len(initial) == 8
    and len(initial_ok) == n1
    and ("当前在线 %d/%d" % (n1, total)) in initial[0].get("msg", "")
    and len(changed) >= 1
    and any((":%d" % FLIP_PORT) in e.get("msg", "") for e in changed)
    and len(beat) >= 1
)
lines.append("")
lines.append("结论: %s" % ("PASS —— 事件由共享巡检器的状态差异驱动，非定时文本播报" if ok else "FAIL"))

srv.should_exit = True
time.sleep(0.5)

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
text = "\n".join(lines)
with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
print(text)
print("\n[evidence] %s" % OUT_PATH)
sys.exit(0 if ok else 1)
