#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  OmniAgent Platform 2.0 - 本地一键启动"
echo "============================================"

PY=python3
command -v $PY >/dev/null 2>&1 || PY=python

if [ ! -x ".venv/bin/python" ]; then
  echo "[1/2] 首次运行：创建虚拟环境并安装依赖..."
  $PY -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip -q
  ./.venv/bin/python -m pip install -r requirements.txt -q
else
  echo "[1/2] 检测到已有虚拟环境，跳过依赖安装。"
fi

echo "[2/2] 启动控制台: http://127.0.0.1:8888"
echo "      依赖已全部本地化，断网也能正常渲染。"
exec ./.venv/bin/python server.py
