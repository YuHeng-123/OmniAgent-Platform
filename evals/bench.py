"""
evals/bench.py —— 编排层实测基准（只测本仓库真正有的东西）

为什么是这些指标：本仓库没有模型调用链（网关 `:8000` 未接真实大模型，见 README「诚实边界」），
所以「召回率 / LLM-as-Judge / 首 token 延迟」这类评测在本仓库**没有测量对象**。
硬编一组数出来就是造假。这里测的是控制台/编排层自身能观测、能复现的六个量：

  1. cold_start_ms       进程启动 → 首次 /healthz 200
  2. healthz_ms          /healthz 往返（进程内 HTTP 开销基线）
  3. topology_scan_ms    /api/v1/overview/stats（8 端口并发 TCP 探测一轮）
  4. sse_first_frame_ms  SSE 连接建立 → 第一帧事件
  5. event_online_ms     端口开始监听 → 事件总线上出现「上线」差异事件
  6. event_offline_ms    端口监听终止 → 事件总线上出现「下线」差异事件

3 是「探针成本」，5/6 是「配置的巡检周期 + 探针成本」的端到端体现 ——
后者必然 ≥ 0，且受 services.yaml 的 interval_sec 支配，数字要和配置一起看。

约束（对应 README 的红线）：
- 不编数：拿不到的指标写 skipped 并说明原因，不用默认值凑。
- 不碰别人的服务：只挑空闲端口，被终止的进程是本脚本自己 spawn 的假监听。
- 可复现：环境指纹（版本 / Python / 平台 / commit / 采样数）随报告一起落盘。

跑法：
    .venv/Scripts/python evals/bench.py
    .venv/Scripts/python evals/bench.py --samples 30 --json evals/reports/latest.json
"""

from __future__ import annotations

import argparse
import json
import platform
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from core.config import APP_VERSION  # noqa: E402
from server import SERVICES_META, app  # noqa: E402


# --------------------------------------------------------------------------- #
# 采样与统计
# --------------------------------------------------------------------------- #
def percentile(samples: List[float], p: float) -> float:
    """线性插值分位（样本少时也不至于退化成「最大值」）。"""
    if not samples:
        raise ValueError("empty")
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def summarize(samples: List[float]) -> Dict[str, Any]:
    if not samples:
        return {"n": 0, "skipped": True}
    return {
        "n": len(samples),
        "min_ms": round(min(samples), 2),
        "p50_ms": round(percentile(samples, 0.50), 2),
        "p95_ms": round(percentile(samples, 0.95), 2),
        "max_ms": round(max(samples), 2),
    }


def free_port(start: int = 8951) -> int:
    for port in range(start, start + 200):
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
        finally:
            sock.close()
    raise RuntimeError("找不到空闲端口")


def port_is_bindable(port: int) -> bool:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def git_commit() -> Optional[str]:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        return None


def probe_config() -> Dict[str, Any]:
    try:
        import yaml

        cfg = yaml.safe_load((ROOT / "services.yaml").read_text(encoding="utf-8")) or {}
        return dict(cfg.get("probe") or {})
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# 被测对象：起一个真服务（走 lifespan，巡检器会跟着跑）
# --------------------------------------------------------------------------- #
class Console:
    def __init__(self) -> None:
        self.port = free_port()
        self.base = "http://127.0.0.1:%d" % self.port
        self._server: Optional[uvicorn.Server] = None
        self.cold_start_ms: Optional[float] = None

    def start(self, timeout_s: float = 40.0) -> None:
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error")
        server = uvicorn.Server(config)
        server.install_signal_handlers = lambda: None  # 线程里不能装信号处理器
        self._server = server
        began = time.perf_counter()
        threading.Thread(target=server.run, daemon=True).start()

        client = httpx.Client(trust_env=False, timeout=2.0)
        while time.perf_counter() - began < timeout_s:
            try:
                if client.get(self.base + "/healthz").status_code == 200:
                    self.cold_start_ms = (time.perf_counter() - began) * 1000
                    client.close()
                    return
            except Exception:
                time.sleep(0.05)
        client.close()
        raise RuntimeError("服务在 %.0fs 内没有就绪" % timeout_s)

    def client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base, trust_env=False, timeout=20.0)

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True


# --------------------------------------------------------------------------- #
# 六项测量
# --------------------------------------------------------------------------- #
def measure_http(cli: httpx.Client, path: str, samples: int) -> List[float]:
    out: List[float] = []
    for _ in range(samples):
        began = time.perf_counter()
        resp = cli.get(path)
        resp.raise_for_status()
        out.append((time.perf_counter() - began) * 1000)
    return out


def measure_sse_first_frame(base: str, rounds: int) -> List[float]:
    out: List[float] = []
    for _ in range(rounds):
        began = time.perf_counter()
        with httpx.stream(
            "GET",
            base + "/api/v1/events/stream",
            timeout=httpx.Timeout(20, read=20),
            trust_env=False,
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    out.append((time.perf_counter() - began) * 1000)
                    break  # 关连接，等价于客户端断开
    return out


class EventTap(threading.Thread):
    """一条常驻 SSE 订阅，给每条事件打上到达时刻（perf_counter）。"""

    def __init__(self, base: str) -> None:
        super().__init__(daemon=True)
        self.base = base
        self.events: List[Tuple[float, Dict[str, Any]]] = []
        self.dead = threading.Event()

    def run(self) -> None:
        try:
            with httpx.stream(
                "GET",
                self.base + "/api/v1/events/stream",
                timeout=httpx.Timeout(120, read=120),
                trust_env=False,
            ) as stream:
                for line in stream.iter_lines():
                    if self.dead.is_set():
                        return
                    if line.startswith("data:"):
                        try:
                            self.events.append((time.perf_counter(), json.loads(line[5:].strip())))
                        except Exception:
                            pass
        except Exception:
            return

    def wait_for(self, keyword: str, port: int, timeout_s: float) -> Optional[float]:
        began = time.perf_counter()
        while time.perf_counter() - began < timeout_s:
            for stamp, event in self.events:
                msg = str(event.get("msg", ""))
                if keyword in msg and str(port) in msg:
                    return stamp
            time.sleep(0.05)
        return None


def spawn_listener(port: int) -> subprocess.Popen:
    """真 TCP 监听（不是业务服务），用于制造一次状态翻转。"""
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import socket,time;"
            "s=socket.socket();"
            "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
            "s.bind(('127.0.0.1',%d));s.listen(1);time.sleep(120)" % port,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def pick_flippable_port(cli: httpx.Client) -> Optional[int]:
    """挑一个「当前离线且端口空闲」的拓扑端口 —— 不碰正在跑的服务。"""
    stats = cli.get("/api/v1/overview/stats").json()
    offline = {s["port"] for s in stats["services"] if s.get("status") != "online"}
    for meta in SERVICES_META:
        port = meta["port"]
        if port in offline and port_is_bindable(port):
            return port
    return None


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="编排层实测基准")
    parser.add_argument("--samples", type=int, default=20, help="HTTP 延迟采样数（默认 20）")
    parser.add_argument("--sse-rounds", type=int, default=3, help="SSE 首帧采样数（默认 3）")
    parser.add_argument("--json", default=None, help="报告落盘路径")
    args = parser.parse_args()

    console = Console()
    console.start()
    cli = console.client()

    metrics: Dict[str, Any] = {}
    notes: List[str] = []

    metrics["cold_start_ms"] = {
        "n": 1,
        "value_ms": round(console.cold_start_ms or 0.0, 2),
        "what": "进程启动 → 首次 /healthz 200",
    }
    metrics["healthz_ms"] = summarize(measure_http(cli, "/healthz", args.samples))
    metrics["healthz_ms"]["what"] = "/healthz 往返（该接口内部会做一轮 8 端口探测）"
    metrics["topology_scan_ms"] = summarize(measure_http(cli, "/api/v1/overview/stats", args.samples))
    metrics["topology_scan_ms"]["what"] = "8 端口并发 TCP 探测一轮（含 HTTP 层）"

    first_frames = measure_sse_first_frame(console.base, args.sse_rounds)
    metrics["sse_first_frame_ms"] = summarize(first_frames)
    metrics["sse_first_frame_ms"]["what"] = "SSE 建连 → 第一帧事件"

    # 事件检测时延：必须用同一条常驻流，否则「新连接只拿快照」会误判
    tap = EventTap(console.base)
    tap.start()
    time.sleep(1.5)  # 让订阅建立

    port = pick_flippable_port(cli)
    if port is None:
        metrics["event_online_ms"] = {"n": 0, "skipped": True}
        metrics["event_offline_ms"] = {"n": 0, "skipped": True}
        notes.append("8 个拓扑端口全部在线或不可 bind，跳过状态翻转测量（不编数）")
    else:
        metrics["target_port"] = port
        spawned_at = time.perf_counter()
        child = spawn_listener(port)
        up_at = tap.wait_for("上线", port, timeout_s=20)
        if up_at is None:
            metrics["event_online_ms"] = {"n": 0, "skipped": True}
            notes.append("端口 :%d 拉起后 20s 内未收到上线事件" % port)
        else:
            metrics["event_online_ms"] = {
                "n": 1,
                "value_ms": round((up_at - spawned_at) * 1000, 2),
                "what": "端口开始监听 → 事件总线上线事件（含巡检周期）",
            }

        kill_at = time.perf_counter()
        child.terminate()
        try:
            child.wait(timeout=10)
        except Exception:
            child.kill()
        down_at = tap.wait_for("下线", port, timeout_s=20)
        if down_at is None:
            metrics["event_offline_ms"] = {"n": 0, "skipped": True}
            notes.append("端口 :%d 终止后 20s 内未收到下线事件" % port)
        else:
            metrics["event_offline_ms"] = {
                "n": 1,
                "value_ms": round((down_at - kill_at) * 1000, 2),
                "what": "端口监听终止 → 事件总线下线事件（含巡检周期）",
            }

    tap.dead.set()
    cli.close()
    console.stop()

    report = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "version": APP_VERSION,
        "commit": git_commit(),
        "env": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": None,
        },
        "probe_config": probe_config(),
        "samples": {"http": args.samples, "sse": args.sse_rounds},
        "metrics": metrics,
        "notes": notes,
        "scope": ("只测本仓库真实存在的编排层能力；不含模型效果评测（本仓库无模型调用链）。"),
    }
    import os

    report["env"]["cpu_count"] = os.cpu_count()

    target = (
        Path(args.json)
        if args.json
        else (ROOT / "evals" / "reports" / ("bench-%s.json" % datetime.now().strftime("%Y%m%d-%H%M%S")))
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 控制台汇总 ----
    print("=" * 74)
    print("OmniAgent 编排层实测基准  ·  v%s  ·  commit %s" % (APP_VERSION, report["commit"]))
    print("=" * 74)
    print("%-22s %6s %10s %10s %10s" % ("指标", "样本", "p50", "p95", "max"))
    print("-" * 74)
    for name, item in metrics.items():
        if name in ("target_port",) or not isinstance(item, dict):
            continue
        if item.get("skipped"):
            print("%-22s %6s %s" % (name, 0, "skipped"))
            continue
        if "value_ms" in item:
            print("%-22s %6d %10.2f %10s %10s" % (name, 1, item["value_ms"], "-", "-"))
        else:
            print(
                "%-22s %6d %10.2f %10.2f %10.2f"
                % (name, item["n"], item["p50_ms"], item["p95_ms"], item["max_ms"])
            )
    print("-" * 74)
    cfg = report["probe_config"]
    print(
        "巡检配置：interval=%ss  timeout=%ss  heartbeat_every=%s"
        % (cfg.get("interval_sec"), cfg.get("timeout_sec"), cfg.get("heartbeat_every"))
    )
    if metrics.get("target_port"):
        print("状态翻转目标端口：:%d" % metrics["target_port"])
    for note in notes:
        print("! %s" % note)
    print("报告已写入 %s" % target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
