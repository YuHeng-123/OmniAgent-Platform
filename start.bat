@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ===================================================
echo   OmniAgent Platform 2.0 - 企业级全域 AI 控制中枢
echo ===================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INIT] 正在创建 Python 虚拟环境...
    python -m venv .venv
)

echo [INIT] 激活虚拟环境...
call .venv\Scripts\activate

echo [DEPS] 检查依赖...
pip install -q fastapi uvicorn jinja2 httpx pydantic

echo.
echo [START] 正在启动 OmniAgent 2.0 统一主控中枢...
echo [TIP] 稍候将自动在浏览器中打开: http://127.0.0.1:8888
echo [TIP] 按 Ctrl+C 可停止主控服务
echo.

start "" powershell -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8888'"
python server.py
pause
