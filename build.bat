@echo off
chcp 65001 >nul
echo ============================================
echo   EVE-LMA 打包脚本 (PyInstaller)
echo ============================================
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+ 并添加到 PATH。
    pause
    exit /b 1
)

REM 检查依赖是否已安装（跳过已满足的情况）
echo [1/4] 检查依赖...
pip install -r requirements.txt --quiet --disable-pip-version-check 2>nul
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败。
    pause
    exit /b 1
)

REM 备份用户文件（防止 PyInstaller --noconfirm 清空 dist 目录）
echo.
echo [2/4] 备份用户文件...
if not exist "_backup" mkdir "_backup"
if exist "dist\EVE-LMA\Settings.json" copy /Y "dist\EVE-LMA\Settings.json" "_backup\" >nul 2>&1
if exist "dist\EVE-LMA\BossConfig.txt" copy /Y "dist\EVE-LMA\BossConfig.txt" "_backup\" >nul 2>&1

echo.
echo [3/4] 正在打包为 EXE...
pyinstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "EVE-LMA" ^
    --add-data "BossConfig.txt;." ^
    --add-data "LMA.png;." ^
    --hidden-import "pygame" ^
    --hidden-import "watchdog" ^
    --icon "LMA.ico" ^
    main.py

if %errorlevel% neq 0 (
    echo [错误] 打包失败，请检查上方输出。
    pause
    exit /b 1
)

echo.
echo [4/4] 复制项目资源到输出目录...
REM 复制配置文件和图标
copy /Y BossConfig.txt dist\EVE-LMA\ >nul 2>&1
copy /Y LMA.ico dist\EVE-LMA\ >nul 2>&1
copy /Y LMA.png dist\EVE-LMA\ >nul 2>&1

REM 复制默认音频文件到 audio 子目录
if exist "audio" (
    if not exist "dist\EVE-LMA\audio" mkdir "dist\EVE-LMA\audio"
    copy /Y audio\*.mp3 dist\EVE-LMA\audio\ >nul 2>&1
    copy /Y audio\*.MP3 dist\EVE-LMA\audio\ >nul 2>&1
    copy /Y audio\*.wav dist\EVE-LMA\audio\ >nul 2>&1
)

REM 恢复用户自定义配置（如果有备份）
if exist "_backup\Settings.json" copy /Y "_backup\Settings.json" "dist\EVE-LMA\" >nul 2>&1
if exist "_backup\BossConfig.txt" copy /Y "_backup\BossConfig.txt" "dist\EVE-LMA\" >nul 2>&1
if exist "_backup" rmdir /S /Q "_backup" >nul 2>&1

echo.
echo ============================================
echo   打包完成！
echo   输出目录: dist\EVE-LMA\
echo   运行: dist\EVE-LMA\EVE-LMA.exe
echo ============================================
echo.
echo 注意: 首次运行 EXE 会自动生成 Settings.json
echo       音频文件和 BossConfig.txt 已自动复制到 EXE 同级目录
pause
