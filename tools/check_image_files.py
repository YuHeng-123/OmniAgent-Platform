# -*- coding: utf-8 -*-
"""check_image_files.py —— 没有 Docker 也能提前发现「镜像里缺文件」。

背景：Dockerfile 曾经只 COPY 了 server.py / templates / static，漏掉 core 与 routers。
镜像照样 build 成功，但容器一启动就 ModuleNotFoundError，compose 里看到的是 restart 循环。

做法：静态解析 Dockerfile 的 COPY 行，拿到镜像内会有的顶层条目；
再扫 server.py 的本地 import（core / routers …），逐个核对是否被 COPY 进去。
纯静态、不依赖 Docker，可以放进 CI 当门禁。

用法：
    .venv\\Scripts\\python.exe tools\\check_image_files.py
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_copies(dockerfile_path):
    """返回 (被 COPY 的顶层条目集合, 容器内工作目录)"""
    copied = set()
    with open(dockerfile_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.upper().startswith("COPY "):
                continue
            parts = line.split()[1:]
            # 忽略 --chown=... 之类的 flag
            parts = [p for p in parts if not p.startswith("--")]
            if len(parts) < 2:
                continue
            for src in parts[:-1]:
                copied.add(src.strip("./").split("/")[0])
    return copied


def local_imports(py_path):
    """扫顶层 import 语句里指向本仓库的模块名"""
    names = set()
    with open(py_path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"\s*(?:from|import)\s+([A-Za-z_][\w]*)", line)
            if m:
                names.add(m.group(1))
    return names


def main():
    df = os.path.join(BASE, "Dockerfile")
    copied = parse_copies(df)
    entry = os.path.join(BASE, "server.py")
    missing = []
    checked = []
    for name in sorted(local_imports(entry)):
        pkg = os.path.join(BASE, name)
        is_local = os.path.isdir(pkg) or os.path.exists(pkg + ".py")
        if not is_local:
            continue
        checked.append(name)
        if name not in copied and name + ".py" not in copied:
            missing.append(name)

    print("Dockerfile 已 COPY 的顶层条目 :", ", ".join(sorted(copied)))
    print("server.py 依赖的本地模块     :", ", ".join(checked))
    if missing:
        print("\n[FAIL] 镜像里会缺这些本地模块:", ", ".join(missing))
        print("       补一行 COPY <name>/ ./<name>/ 到 Dockerfile")
        return 1
    print("\n[OK] server.py 的本地依赖全部在镜像内")
    return 0


if __name__ == "__main__":
    sys.exit(main())
