@echo off
chcp 65001 >nul
echo ========================================
echo EVE-LMA 日志查看器
echo ========================================
echo.

set LOG_DIR=logs
if not exist "%LOG_DIR%" (
    echo [错误] 日志目录不存在: %LOG_DIR%
    echo 请确保程序已运行并启用了日志文件记录
    pause
    exit /b 1
)

set TODAY=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%
set LOG_FILE=%LOG_DIR%\eve-lma-%TODAY%.log

if not exist "%LOG_FILE%" (
    echo [错误] 今天的日志文件不存在: %LOG_FILE%
    echo.
    echo 可用的日志文件:
    dir /b "%LOG_DIR%\*.log" 2>nul || echo 无
    pause
    exit /b 1
)

echo 查看今天的日志: %LOG_FILE%
echo ========================================
echo.

:menu
echo.
echo 请选择操作:
echo 1. 显示所有报警记录
echo 2. 显示静默报警
echo 3. 显示 PVP 报警
echo 4. 显示 BOSS 报警
echo 5. 显示无畏报警
echo 6. 显示隐身报警
echo 7. 显示音量设置
echo 8. 显示分组操作
echo 9. 显示最近 50 条日志
echo 10. 显示完整日志
echo 0. 退出
echo.
set /p choice=请输入选择: 

if "%choice%"=="1" goto alerts
if "%choice%"=="2" goto silence
if "%choice%"=="3" goto pvp
if "%choice%"=="4" goto boss
if "%choice%"=="5" goto dread
if "%choice%"=="6" goto cloak
if "%choice%"=="7" goto volume
if "%choice%"=="8" goto group
if "%choice%"=="9" goto recent
if "%choice%"=="10" goto full
if "%choice%"=="0" goto end

echo 无效选择
goto menu

:alerts
echo.
echo ========================================
echo 所有报警记录
echo ========================================
findstr /C:"[Silence]" /C:"[PVP]" /C:"[BOSS]" /C:"[Dread]" /C:"[Cloak]" "%LOG_FILE%" || echo 无报警记录
goto menu

:silence
echo.
echo ========================================
echo 静默报警记录
echo ========================================
findstr /C:"[Silence]" "%LOG_FILE%" || echo 无静默报警
goto menu

:pvp
echo.
echo ========================================
echo PVP 报警记录
echo ========================================
findstr /C:"[PVP]" "%LOG_FILE%" || echo 无PVP报警
goto menu

:boss
echo.
echo ========================================
echo BOSS 报警记录
echo ========================================
findstr /C:"[BOSS]" "%LOG_FILE%" || echo 无BOSS报警
goto menu

:dread
echo.
echo ========================================
echo 无畏报警记录
echo ========================================
findstr /C:"[Dread]" "%LOG_FILE%" || echo 无畏报警
goto menu

:cloak
echo.
echo ========================================
echo 隐身报警记录
echo ========================================
findstr /C:"[Cloak]" "%LOG_FILE%" || echo 无隐身报警
goto menu

:volume
echo.
echo ========================================
echo 音量设置记录
echo ========================================
findstr /C:"[Volume]" "%LOG_FILE%" || echo 无音量设置记录
goto menu

:group
echo.
echo ========================================
echo 分组操作记录
echo ========================================
findstr /C:"[Group]" "%LOG_FILE%" || echo 无分组操作记录
goto menu

:recent
echo.
echo ========================================
echo 最近 50 条日志
echo ========================================
powershell -Command "Get-Content '%LOG_FILE%' -Tail 50"
goto menu

:full
echo.
echo ========================================
echo 完整日志 (按 q 退出)
echo ========================================
type "%LOG_FILE%" | more
goto menu

:end
echo 完成
