@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   OmniAgent Platform 2.0 - 本地一键启动
echo ============================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/2] 首次运行：创建虚拟环境并安装依赖...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请确认已安装 Python 3.10+ 并加入 PATH。
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络或 pip 源。
        pause
        exit /b 1
    )
) else (
    echo [1/2] 检测到已有虚拟环境，跳过依赖安装。
)

echo [2/2] 启动控制台...
echo       浏览器访问 http://127.0.0.1:8888
echo       依赖已全部本地化，断网也能正常渲染。
echo.
".venv\Scripts\python.exe" server.py
pause
