"""
pytest 公共设施 —— 一个「跑得起来」的本地后端。

为什么不用 fastapi.testclient.TestClient：
  本仓库有一条 **SSE 长连接**（/api/v1/events/stream）。Starlette 的 TestClient 在
  读到无限流时会一直等，实测在本机（Windows + httpx 传输层）会直接卡住不返回。
  所以这里改成在后台线程里真起一个 uvicorn，用 httpx 打真实 HTTP —— 跟
  selftest_omni.py 走的是同一条路，行为最接近线上。

对 127.0.0.1 的请求一律 trust_env=False：否则 httpx 会把本机请求丢给系统代理，
  在开了代理的机器上会假报连不上。
"""
import os
import socket
import sys
import threading
import time

import httpx
import pytest
import uvicorn

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from server import app  # noqa: E402


def _port_free(port: int) -> bool:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _pick_port(start: int = 8901) -> int:
    port = start
    while not _port_free(port):
        port += 1
    return port


@pytest.fixture(scope="session")
def base_url():
    """后台线程起一个真 uvicorn，返回 http://127.0.0.1:<port>。"""
    port = _pick_port()
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    srv = uvicorn.Server(cfg)
    srv.install_signal_handlers = lambda: None      # 非主线程装信号处理器会抛错
    threading.Thread(target=srv.run, daemon=True).start()

    url = "http://127.0.0.1:%d" % port
    deadline = time.time() + 20
    ready = False
    with httpx.Client(trust_env=False, timeout=2.0) as probe:
        while time.time() < deadline:
            try:
                if probe.get(url + "/api/v1/overview/stats").status_code == 200:
                    ready = True
                    break
            except Exception:
                time.sleep(0.15)
    if not ready:
        srv.should_exit = True
        pytest.fail("测试用 uvicorn 未能在 20s 内就绪")

    yield url

    srv.should_exit = True
    time.sleep(0.4)


@pytest.fixture(scope="session")
def client(base_url):
    with httpx.Client(base_url=base_url, trust_env=False, timeout=30.0) as c:
        yield c
