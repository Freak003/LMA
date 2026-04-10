@echo off
chcp 65001 >nul
echo ============================================
echo   EVE-LMA 打包脚本 (PyInstaller) v3.7
echo ============================================
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+ 并添加到 PATH。
    pause
    exit /b 1
)

REM 检查 PyInstaller 是否已安装
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 PyInstaller，正在安装...
    pip install PyInstaller --quiet
    if %errorlevel% neq 0 (
        echo [错误] PyInstaller 安装失败。
        pause
        exit /b 1
    )
)

REM 检查依赖是否已安装
echo [1/5] 检查并安装依赖...
pip install -r requirements.txt --quiet --disable-pip-version-check 2>nul
if %errorlevel% neq 0 (
    echo [警告] 依赖安装失败，继续执行...
)

REM 清理旧的构建文件
echo.
echo [2/5] 清理旧的构建文件...
if exist "build" rmdir /S /Q "build"
if exist "dist\EVE-LMA" rmdir /S /Q "dist\EVE-LMA"

REM 备份用户文件
echo.
echo [3/5] 备份用户配置文件...
if not exist "_backup" mkdir "_backup"
if exist "dist\EVE-LMA\Settings.json" (
    copy /Y "dist\EVE-LMA\Settings.json" "_backup\" >nul 2>&1
    echo [备份] Settings.json
)
if exist "dist\EVE-LMA\BossConfig.txt" (
    copy /Y "dist\EVE-LMA\BossConfig.txt" "_backup\" >nul 2>&1
    echo [备份] BossConfig.txt
)

REM 使用 spec 文件打包
echo.
echo [4/5] 正在打包为 EXE (使用 EVE-LMA.spec)...
python -m PyInstaller --clean -y EVE-LMA.spec
if %errorlevel% neq 0 (
    echo.
    echo [错误] 打包失败，请检查上方输出。
    echo [提示] 如果 spec 文件不存在，将使用命令行参数打包...
    echo.
    
    REM spec 文件打包失败，回退到命令行方式
    echo [回退] 使用命令行参数打包...
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
)

echo.
echo [5/5] 复制项目资源到输出目录...
REM 检查输出目录是否存在
if not exist "dist\EVE-LMA" (
    echo [错误] 打包成功但未找到输出目录 dist\EVE-LMA
    pause
    exit /b 1
)

REM 复制配置文件和图标
copy /Y BossConfig.txt dist\EVE-LMA\ >nul 2>&1 && echo [复制] BossConfig.txt
copy /Y LMA.ico dist\EVE-LMA\ >nul 2>&1 && echo [复制] LMA.ico
copy /Y LMA.png dist\EVE-LMA\ >nul 2>&1 && echo [复制] LMA.png

REM 复制默认音频文件到 audio 子目录
if exist "audio" (
    if not exist "dist\EVE-LMA\audio" mkdir "dist\EVE-LMA\audio"
    copy /Y audio\*.mp3 dist\EVE-LMA\audio\ >nul 2>&1
    copy /Y audio\*.MP3 dist\EVE-LMA\audio\ >nul 2>&1
    copy /Y audio\*.wav dist\EVE-LMA\audio\ >nul 2>&1
    echo [复制] audio/* 音频文件
)

REM 恢复用户自定义配置（如果有备份）
if exist "_backup\Settings.json" (
    copy /Y "_backup\Settings.json" "dist\EVE-LMA\" >nul 2>&1
    echo [恢复] Settings.json
)
if exist "_backup\BossConfig.txt" (
    copy /Y "_backup\BossConfig.txt" "dist\EVE-LMA\" >nul 2>&1
    echo [恢复] BossConfig.txt
)
if exist "_backup" rmdir /S /Q "_backup" >nul 2>&1

REM 显示打包结果
echo.
echo ============================================
echo   打包完成！
echo ============================================
echo   输出目录：dist\EVE-LMA\
echo   可执行文件：dist\EVE-LMA\EVE-LMA.exe
echo   版本：v3.7
echo ============================================
echo.
echo [提示] 首次运行会自动生成 Settings.json
echo [提示] 音频文件和配置文件已自动复制
echo.

pause
