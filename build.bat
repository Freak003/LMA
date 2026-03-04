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

REM 安装依赖
echo [1/3] 正在安装依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败。
    pause
    exit /b 1
)

echo.
echo [2/3] 正在打包为 EXE...
pyinstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "EVE-LMA" ^
    --add-data "BossConfig.txt;." ^
    --hidden-import "pygame" ^
    --icon NONE ^
    main.py

if %errorlevel% neq 0 (
    echo [错误] 打包失败，请检查上方输出。
    pause
    exit /b 1
)

echo.
echo [3/3] 复制配置文件到输出目录...
copy /Y BossConfig.txt dist\EVE-LMA\ >nul 2>&1

echo.
echo ============================================
echo   打包完成！
echo   输出目录: dist\EVE-LMA\
echo   运行: dist\EVE-LMA\EVE-LMA.exe
echo ============================================
echo.
echo 注意: 首次运行 EXE 会自动生成 Settings.json
echo       请将 BossConfig.txt 放在 EXE 同级目录
pause
