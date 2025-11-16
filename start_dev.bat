@echo off
REM ===================================================
REM == EMinder 应用一键启动脚本 (开发模式) ==
REM ===================================================

REM --- 配置区 ---
SET PYTHON_EXE="C:\Users\lenovo\.conda\envs\EMinder\python.exe"
SET PROJECT_DIR="D:\Desktop\Develop\SelfProject\EMinder"
SET BN_PORT=8421
REM Uvicorn 可执行文件通常在 Conda 环境的 Scripts 目录下
SET UVICORN_EXE="C:\Users\lenovo\.conda\envs\EMinder\Scripts\uvicorn.exe"

echo.
echo [EMinder] Running dev...
echo.

REM --- 启动后端服务 (使用 uvicorn --reload) ---
echo [1/2] Starting backend (dev)...
start "EMinder Backend (Dev)" /D %PROJECT_DIR%\backend %UVICORN_EXE% app.main:app --reload --port %BN_PORT%

REM --- 等待后端初始化 ---
echo [EMinder] 3 secs waiting
timeout /t 3 /nobreak > nul

REM --- 启动前端服务 ---
echo [2/2] Running frontend...
start "EMinder Frontend" /D %PROJECT_DIR% %PYTHON_EXE% frontend.py

echo.
echo [EMinder] All services started.
echo.

