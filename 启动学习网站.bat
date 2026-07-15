@echo off
chcp 65001 >nul 2>&1
title 智能体学习档案
cd /d "%~dp0web_demo"

echo ============================================
echo        智能体学习档案 - 个人学习网站
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python。
    echo 请先安装 Python 3.9 或更高版本，并勾选 Add Python to PATH。
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 版本过低，需要 Python 3.9 或更高版本。
    pause
    exit /b 1
)

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [错误] 端口 5000 已被其他程序占用。
    echo 请关闭占用端口的程序后重新启动。
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [准备] 正在创建独立运行环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 无法创建独立运行环境。
        pause
        exit /b 1
    )
)

set "SITE_PYTHON=.venv\Scripts\python.exe"
"%SITE_PYTHON%" -c "from importlib.metadata import version; assert version('Flask') == '3.1.3'" >nul 2>&1
if errorlevel 1 (
    echo [准备] 首次运行需要联网安装网站依赖...
    "%SITE_PYTHON%" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络或代理设置后重试。
        pause
        exit /b 1
    )
)

echo [就绪] 浏览器将打开 http://localhost:5000
echo [提示] 关闭此窗口即可停止网站。
echo.
start "" powershell -NoProfile -WindowStyle Hidden -Command "$deadline=(Get-Date).AddSeconds(30); while((Get-Date) -lt $deadline){ try { $r=Invoke-RestMethod 'http://127.0.0.1:5000/api/health' -TimeoutSec 1; if($r.success){ Start-Process 'http://127.0.0.1:5000'; break } } catch {}; Start-Sleep -Milliseconds 500 }"
"%SITE_PYTHON%" app.py

pause
