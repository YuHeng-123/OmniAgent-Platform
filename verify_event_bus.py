"""
verify_event_bus.py —— 证明「中枢事件总线」是**差异驱动**的，而不是定时播报固定文本

为什么需要它：
  事件总线最有说服力的一句宣传是「你把一个服务停掉，面板上会真的出现下线事件」。
  但这句话不验证就只是自夸。本脚本用**注入式端口探测**做端到端验证：
    · 第 1 轮探测：取真实结果 → 期望 8 条初始事件（1 条接入说明 + 7 条就绪）
    · 第 2 轮探测：把 :7860 的在线状态**翻转** → 期望出现 1 条「状态变化」事件
    · 之后无变化 → 每 4 轮期望出现 1 条「巡检心跳」
  全程走真实 HTTP + 真实 SSE 流，唯一被替换的是底层端口探测函数
  （否则就得真去关掉用户正在跑的服务，那不行）。

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
REAL_SCAN = server.scan_ports
FLIP_PORT = 7860          # 第 2 轮起把 FunClip 的在线状态翻转
_calls = {"n": 0}
_first = {}


async def fake_scan(ports):
    """第 1 轮返回真实探测结果；第 2 轮起把 FLIP_PORT 的状态**翻转**。

    注意是「翻转」而不是「置为离线」—— 脚本必须与运行环境无关：
      · 7 个服务本来就在线 → 翻成离线，验证「下线」事件
      · 服务本来就没起     → 翻成上线，验证「上线」事件
    两个方向都能证明事件由真实状态差异驱动；否则在「所有服务都没起」的机器上
    会永远等不到变化，把好好的代码验成 FAIL。
    """
    _calls["n"] += 1
    real = await REAL_SCAN(ports)
    if _calls["n"] == 1:
        _first[FLIP_PORT] = bool(real.get(FLIP_PORT, False))
        _first["online"] = sum(1 for v in real.values() if v)
    elif FLIP_PORT in real:
        real[FLIP_PORT] = not _first.get(FLIP_PORT, False)
    return real


server.scan_ports = fake_scan


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

for _ in range(120):
    try:
        httpx.get("http://127.0.0.1:%d/api/v1/overview/stats" % PORT,
                  timeout=1.0, trust_env=False)
        break
    except Exception:
        time.sleep(0.15)

lines = []
lines.append("=" * 72)
lines.append("== 事件总线「差异驱动」端到端验证  (注入点：scan_ports)")
lines.append("=" * 72)
lines.append("服务端口        = %d" % PORT)
lines.append("注入规则        = 第 1 轮取真实结果；第 2 轮起把 :%d 的在线状态翻转" % FLIP_PORT)
lines.append("                  （所以本机服务开着或没开，都能验出结论）")
lines.append("")

events = []
t0 = time.time()
_calls["n"] = 0   # 关键：从「流打开」这一刻开始计探测轮次
                  # （否则上面的启动探活已经把计数推到第 2 轮，第一帧就是离线态，永远等不到"变化"）
try:
    with httpx.stream("GET", "http://127.0.0.1:%d/api/v1/events/stream" % PORT,
                      timeout=httpx.Timeout(60.0, connect=5.0, read=18.0),
                      trust_env=False) as st:
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
                lines.append("  T+%5.1fs  [%s] [%-11s] (%s) %s"
                             % (time.time() - t0, ev.get("ts"), ev.get("tag"),
                                ev.get("level"), ev.get("msg")))
                if len(events) >= 10:
                    break
        except httpx.ReadTimeout:
            lines.append("  (读取超时，已采集 %d 条)" % len(events))
except Exception as e:
    lines.append("ERR %s" % e)

lines.append("-" * 72)
initial = events[:8]
changed = [e for e in events
           if "状态变化" in e.get("msg", "") and "无状态变化" not in e.get("msg", "")]
# 注意排除「本轮无状态变化」这句心跳文案 —— 它含「状态变化」子串，
# 不排除的话心跳会被误算成一次状态变化（实测踩过）。
beat = [e for e in events if "巡检完成" in e.get("msg", "")]

# 第 1 轮的真实在线数 —— 初始播报里应该正好有这么多条 ok
n1 = _first.get("online", 0)
total = len(server.ALL_PORTS)
initial_ok = [e for e in initial[1:] if e.get("level") == "ok"]
flip_dir = "下线" if _first.get(FLIP_PORT) else "上线"

lines.append("探测轮次           = %d" % _calls["n"])
lines.append("第 1 轮真实在线数  = %d/%d" % (n1, total))
lines.append("注入方向           = :%d 翻转为「%s」" % (FLIP_PORT, flip_dir))
lines.append("初始事件条数       = %d  (期望 8)" % len(initial))
lines.append("初始 ok 条数       = %d  (应等于第 1 轮在线数 %d)" % (len(initial_ok), n1))
lines.append("接入说明在线数一致 = %s" % (("当前在线 %d/%d" % (n1, total)) in initial[0].get("msg", "")))
lines.append("捕获「状态变化」   = %d 条  (期望 >=1，且含 :%d)" % (len(changed), FLIP_PORT))
lines.append("捕获「巡检心跳」   = %d 条  (期望 >=1)" % len(beat))

ok = (len(initial) == 8
      and len(initial_ok) == n1
      and ("当前在线 %d/%d" % (n1, total)) in initial[0].get("msg", "")
      and len(changed) >= 1
      and any((":%d" % FLIP_PORT) in e.get("msg", "") for e in changed)
      and len(beat) >= 1)
lines.append("")
lines.append("结论: %s" % ("PASS —— 事件确实由状态差异驱动，非定时文本播报" if ok else "FAIL"))

srv.should_exit = True
time.sleep(0.5)

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
text = "\n".join(lines)
with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
print(text)
print("\n[evidence] %s" % OUT_PATH)
sys.exit(0 if ok else 1)
