@echo off
title EMinder Supervisor

echo [EMinder] Activating Conda Environment ...
echo [EMinder] To close all servers, press Ctrl+C

REM 激活 Conda 环境 (这是确保 honcho 能被找到的关键)
call conda activate EMinder

REM 切换到脚本所在的目录
cd /d "%~dp0"

REM 使用 honcho 启动 Procfile 中定义的所有服务
honcho start -f Procfile

echo [EMinder] Honcho Monitor has been terminated...
pause