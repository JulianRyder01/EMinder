@echo off
REM 检测是否已经带参数运行，如果没有，则以最小化模式重新启动自己
if "%1" == "min" goto :run
start "" /min cmd /c "%~dpnx0" min
exit

:run
title EMinder Supervisor

echo [EMinder] Activating Conda Environment ...
echo [EMinder] To close all servers, press Ctrl+C

REM 激活 Conda 环境
call conda activate EMinder

REM 切换到脚本所在的目录
cd /d "%~dp0"

REM 使用 honcho 启动 Procfile 中定义的所有服务
honcho start -f Procfile

echo [EMinder] Honcho Monitor has been terminated...
pause