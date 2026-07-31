@echo off
chcp 65001 >nul
echo =============================================
echo   摄影采集 - 图片采集工具 一键打包脚本
echo =============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 安装依赖包...
pip install -r requirements.txt --break-system-packages >nul 2>&1
if %errorlevel% neq 0 (
    pip install -r requirements.txt
)

echo [2/4] 安装 PyInstaller...
pip install pyinstaller --break-system-packages >nul 2>&1
if %errorlevel% neq 0 (
    pip install pyinstaller
)

echo [3/4] 正在打包为 exe (可能需要几分钟)...
pyinstaller --onefile --windowed ^
    --name "摄影采集" ^
    --add-data "scrapers.py;." ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "bs4" ^
    --hidden-import "requests" ^
    --hidden-import "json" ^
    --hidden-import "hashlib" ^
    --hidden-import "threading" ^
    --hidden-import "os" ^
    --hidden-import "re" ^
    --hidden-import "time" ^
    --hidden-import "datetime" ^
    --hidden-import "webbrowser" ^
    --clean ^
    --noconsole ^
    main.py

if %errorlevel% neq 0 (
    echo.
    echo [错误] 打包失败! 请检查上方错误信息。
    pause
    exit /b 1
)

echo.
echo [4/4] 清理临时文件...
rmdir /s /q build 2>nul
del /q "摄影采集.spec" 2>nul

echo.
echo =============================================
echo   打包完成!
echo   程序位置: dist\摄影采集.exe
echo   直接双击运行即可!
echo =============================================
echo.

REM 复制配置文件到 dist 目录
copy requirements.txt dist\README.txt >nul 2>&1

echo [提示] 首次运行会自动在系统图片文件夹下创建"摄影采集"目录。
echo.

pause
