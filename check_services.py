"""
check_services.py —— 7 个微服务的就绪检查（拓扑来源与主控台共用 services.yaml）

它**不启动**任何服务 —— 那 7 个服务是各自独立的仓库，不在本仓库内。
它只做一件事：按 services.yaml 登记的顺序逐个 TCP 探测端口，打印一张「谁在线」的表，
用于本地排障和 CI 里确认拓扑配置没被改坏。

跑法：
    .venv\\Scripts\\python.exe check_services.py
    .venv\\Scripts\\python.exe check_services.py --require-all   # 必须 7/7 才算通过

退出码：
    0 = 全部在线，或（默认模式下）至少 1 个在线
    1 = 一个都没在线；带 --require-all 时，非 7/7 一律返回 1
"""

import argparse
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import CONFIG_SOURCE, PROBE_TIMEOUT, SERVICES_META  # noqa: E402


def probe(port: int, timeout: float):
    """返回 (是否在线, 实测耗时毫秒)。"""
    t0 = time.perf_counter()
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        return True, (time.perf_counter() - t0) * 1000
    except OSError:
        return False, (time.perf_counter() - t0) * 1000
    finally:
        try:
            s.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="OmniAgent 微服务就绪检查")
    ap.add_argument("--require-all", action="store_true", help="只有 7/7 全部在线才返回 0")
    args = ap.parse_args()

    print("拓扑来源: %s    探测超时: %.2fs    IPv4 回环: 127.0.0.1" % (CONFIG_SOURCE, PROBE_TIMEOUT))
    print("-" * 74)
    print("%-10s %-6s %-9s %-11s %s" % ("状态", "端口", "耗时", "类型", "服务"))
    print("-" * 74)

    online = 0
    for s in SERVICES_META:
        up, ms = probe(s["port"], PROBE_TIMEOUT)
        online += 1 if up else 0
        print(
            "%-10s %-6d %-9s %-11s %s"
            % ("● 在线" if up else "○ 离线", s["port"], "%.1f ms" % ms, s["type"], s["name"])
        )

    total = len(SERVICES_META)
    print("-" * 74)
    print("在线 %d / %d" % (online, total))

    if online == total:
        print("全部就绪：控制台会亮起 %d 个绿点，导购链路走真上游。" % total)
        return 0
    if online == 0:
        print("一个都没起 —— 控制台自身仍可正常使用，只是会显式标注为「静态演示模式」。")
        return 1
    print("部分在线：控制台按实际在线数显示，不夸大也不隐瞒。")
    return 0 if not args.require_all else 1


if __name__ == "__main__":
    sys.exit(main())
