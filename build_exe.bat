@echo off
chcp 65001 >nul
title 摄影采集 — 一键打包
echo.
echo  ╔══════════════════════════════════════╗
echo  ║    ?? 摄影采集 — 一键打包工具      ║
echo  ╚══════════════════════════════════════╝
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [?] 未检测到 Python
    echo     请先安装 Python 3.8+: https://www.python.org/downloads/
    pause & exit /b 1
)

echo [1/4] 安装依赖...
pip install -r requirements.txt -q 2>nul
if %errorlevel% neq 0 (
    pip install -r requirements.txt
)

echo [2/4] 清理旧构建...
rmdir /s /q build dist 2>nul
del /q "摄影采集.spec" 2>nul

echo [3/4] 打包为 EXE (约 2-5 分钟，请稍候)...
pyinstaller --onefile --windowed ^
    --name "PhotoScraper" ^
    --add-data "photo_scraper.py;." ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "bs4" ^
    --hidden-import "requests" ^
    --hidden-import "json" ^
    --hidden-import "hashlib" ^
    --hidden-import "threading" ^
    --hidden-import "re" ^
    --hidden-import "time" ^
    --hidden-import "datetime" ^
    --hidden-import "webbrowser" ^
    --hidden-import "os" ^
    --clean ^
    --noconsole ^
    main.py

if %errorlevel% neq 0 (
    echo.
    echo [?] 打包失败
    pause & exit /b 1
)

echo [4/4] 清理临时文件...
rmdir /s /q build 2>nul
del /q "PhotoScraper.spec" 2>nul

echo.
echo  ╔══════════════════════════════════════╗
echo  ║     ? 打包完成!                    ║
echo  ║     程序: dist\PhotoScraper.exe      ║
echo  ╚══════════════════════════════════════╝
echo.
echo  直接双击运行即可，首次打开会自动在
echo  "图片\PhotoScraper" 目录下创建文件夹。
echo.
pause
