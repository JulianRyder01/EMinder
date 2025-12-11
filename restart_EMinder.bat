@echo off
title EMinder - Restarting

echo.
echo [EMinder Restart] Finding and terminating all EMinder-related processes...
echo.

REM Kill processes by port
REM The port 8421 is the backend of EMinder and the frontend is 10101
echo.
echo ================================================================
echo  Finding processes stuck on ports 8421 and 10101...
echo ================================================================
for %%p in (8421 10101) do (
    echo  - Checking for process on port %%p...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%%p ^| findstr LISTENING') do (
        if not "%%a"=="0" (
            echo  - Found PID: %%a on port %%p, force killing...
            taskkill /F /PID %%a
        )
    )
)

echo.
echo [EMinder] All identified EMinder processes have been terminated.
echo.

@echo off
title EMinder - Service is running

echo [EMinder] Activating Conda Environment ...
echo [EMinder] To close all servers, press Ctrl+C

REM 激活 Conda 环境 (这是确保 honcho 能被找到的关键)
call conda activate EMinder

REM 切换到脚本所在的目录
cd /d "%~dp0"

REM 使用 honcho 启动 Procfile 中定义的所有服务
honcho start -f Procfile

echo [EMinder] Honcho Monitor has been terminated...
title EMinder - Stopped
pause