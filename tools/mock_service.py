"""
mock_service.py —— 演示用的「假监听」

它只做一件事：在指定端口上起一个真实的 HTTP 监听，好让控制台的
「服务起停」按钮和事件总线**有对象可演示**。

  为什么需要它：
  7 个微服务是各自独立的仓库，不在本仓库内。没起它们时，面板上 7 张卡片
  全是灰的，「点停止 → 看下线事件」这个最有说服力的演示就无从下手。
  本工具提供一个**明确标注为假**的监听目标，让整条链路（探测 → 状态翻转 →
  差异事件广播 → 事件回放）可以在本机完整跑通。

  它是什么、不是什么（避免误会）：
    · 是：一个真的 TCP 监听，控制台探到的「端口在线」是真的；
    · 不是：任何业务服务。它不会导购、不会生成文案、不接任何模型 ——
      `/` 会老老实实返回 {"mock": true}。

用法：
    python tools/mock_service.py 8002            # 占住 8002（素材工作台）
    python tools/mock_service.py 8002 --id coze-material-studio

两种演示方式：
    A. 手动：先跑上面这条命令，再去控制台点那张卡片的「停止」，
       约 3 秒后事件总线会推出红色的下线事件。
    B. 让「启动」按钮也能用：在 services.yaml 里给该服务加上
         start_cmd: ["python", "tools/mock_service.py", "8002"]
       （未配 start_cmd 的服务，启动按钮会如实返回 not-configured）

Ctrl+C 退出。
"""

import argparse
import json
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BANNER = "=" * 62


class Handler(BaseHTTPRequestHandler):
    port = 8002
    service_id = "mock"

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 —— BaseHTTPRequestHandler 的约定命名
        if self.path.rstrip("/") in ("/healthz", "/health"):
            self._send(200, {"status": "ok", "mock": True, "port": self.port})
            return
        self._send(
            200,
            {
                "mock": True,
                "service_id": self.service_id,
                "port": self.port,
                "note": "演示用假监听，不是真实业务服务。",
                "purpose": "让控制台的起停按钮与事件总线有可演示的对象。",
            },
        )

    def log_message(self, fmt, *args):  # 打一行精简日志，方便看 service-logs
        sys.stderr.write("[mock:%d] %s\n" % (self.port, fmt % args))


def pick_port(preferred: int) -> int:
    """优先用指定端口；被占用则报错退出（不要把别人的服务挤掉）。"""
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", preferred))
        return preferred
    except OSError as e:
        print(BANNER)
        print("  端口 %d 无法绑定：%s" % (preferred, e))
        print("  —— 说明已经有服务在跑（那就直接用它演示，不用起假监听了）。")
        print(BANNER)
        raise SystemExit(2) from e
    finally:
        s.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="演示用假监听（不是业务服务）")
    ap.add_argument("port", type=int, help="要占住的端口，例如 8002")
    ap.add_argument("--id", dest="service_id", default="mock", help="对应的服务 id（仅用于标识）")
    args = ap.parse_args()

    port = pick_port(args.port)
    Handler.port = port
    Handler.service_id = args.service_id

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(BANNER)
    print("  mock 监听已就绪 —— 演示用，不是真实业务服务")
    print("  地址: http://127.0.0.1:%d/   (GET / 或 /healthz)" % port)
    print("  服务 id: %s" % args.service_id)
    print("  现在去控制台点这张卡片的「停止」，约 3 秒后会看到下线事件。")
    print("  Ctrl+C 退出。")
    print(BANNER)
    sys.stdout.flush()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  收到 Ctrl+C，mock 监听退出。")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    # 让 Ctrl+C 在 Windows 上也能干脆退出
    time.sleep(0)
    raise SystemExit(main())
