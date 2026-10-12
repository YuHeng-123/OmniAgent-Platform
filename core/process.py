"""
OmniAgent Platform - 企业级进程管控与服务起停中枢 (Core Process)
管理本地微服务子进程的拉起、按端口终止以及日志重定向。
"""

import os
import subprocess
from typing import Any, Dict, List

from core.config import DATA_DIR

WIN_DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def find_listener_pids(port: int) -> List[int]:
    """找出**本机**监听在 port 上的进程 PID 列表（psutil 缺失时返回空）。"""
    try:
        import psutil
    except ImportError:
        return []
    pids = set()
    try:
        for c in psutil.net_connections(kind="tcp"):
            if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port and c.pid:
                pids.add(c.pid)
    except Exception:  # noqa: BLE001
        pass
    return sorted(pids)


def stop_port_processes(port: int) -> Dict[str, Any]:
    """终止监听在 port 上的进程。按端口停服务的真实实现。"""
    pids = find_listener_pids(port)
    if not pids:
        return {
            "stopped": False,
            "reason": "no-listener",
            "detail": "端口 :%d 当前没有进程在监听（服务可能本就没在运行）。" % port,
        }
    import psutil

    stopped, survivors = [], []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            survivors.append(pid)
            continue
    _exit, alive = psutil.wait_procs([psutil.Process(p) for p in pids if p not in survivors], timeout=3)
    for p in alive:
        try:
            p.kill()
            stopped.append(p.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            survivors.append(p.pid)
    for pid in pids:
        if pid not in survivors and pid not in stopped:
            stopped.append(pid)
    if survivors:
        return {
            "stopped": False,
            "reason": "access-denied",
            "detail": ("进程 %s 无权限终止（可能属于其他用户，需管理员权限运行控制台）。" % survivors),
        }
    return {
        "stopped": True,
        "pids": stopped,
        "detail": "已终止监听 :%d 的进程 PID %s。" % (port, stopped),
    }


def start_service_process(meta: Dict[str, Any]) -> Dict[str, Any]:
    """按 start_cmd 拉起服务子进程（真实 Popen），输出重定向到 data/service-logs/。"""
    cmd = meta.get("start_cmd") or []
    if not cmd:
        return {
            "started": False,
            "reason": "not-configured",
            "detail": "services.yaml 未给该服务配置 start_cmd —— 控制台不知道它该怎么启动。",
        }
    cwd = meta.get("start_cwd") or ""
    if cwd and not os.path.isdir(cwd):
        return {
            "started": False,
            "reason": "bad-cwd",
            "detail": "start_cwd 不存在：%s" % cwd,
        }
    log_dir = os.path.join(DATA_DIR, "service-logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "%s.log" % meta["id"])
    try:
        log_f = open(log_path, "ab")
    except OSError as exc:
        return {"started": False, "reason": "log-open-failed", "detail": str(exc)}
    kwargs = {
        "cwd": cwd or None,
        "stdout": log_f,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = WIN_DETACHED
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        return {"started": False, "reason": "spawn-failed", "detail": str(exc)}
    return {
        "started": True,
        "pid": proc.pid,
        "log": log_path,
        "detail": "子进程已拉起（PID %d），巡检器将在下一轮探测到上线并推送事件。" % proc.pid,
    }
