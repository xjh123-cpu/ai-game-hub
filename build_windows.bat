@echo off
chcp 65001 >nul
echo ============================================================
echo   AI 游戏乐园 - Windows 本地打包脚本
echo ============================================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10 或更高版本
    echo        下载地址：https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 安装依赖（pywebview / pyinstaller / pythonnet / openai）...
pip install pywebview pyinstaller pythonnet openai

echo.
echo [2/3] 开始打包（首次打包需几分钟，请耐心等待）...
pyinstaller build.spec --noconfirm

echo.
echo [3/3] 打包完成！
if exist "dist\AI游戏乐园.exe" (
    echo.
    echo ✅ 生成的可执行文件：dist\AI游戏乐园.exe
    echo    双击该文件即可运行，无需安装 Python
) else (
    echo.
    echo ❌ 未找到生成的 exe，请检查上方报错信息
)

echo.
pause
