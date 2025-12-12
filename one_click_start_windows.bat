@echo off
setlocal EnableDelayedExpansion

set "ENV_NAME=EMinder_service"
set "PYTHON_VERSION=3.12"
set "ROOT_DIR=%~dp0"
set "BACKEND_SCRIPT=%ROOT_DIR%backend\run.py"
set "FRONTEND_SCRIPT=%ROOT_DIR%frontend\run.py"
set "REQ_FILE=%ROOT_DIR%requirements.txt"

set "BACKEND_PORT=8421"
set "FRONTEND_PORT=10101"

title EMinder Launcher

echo.
echo ===================================================
echo       EMinder One-Click Launcher
echo ===================================================
echo.

call conda --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] 'conda' command not found.
    echo Please ensure Anaconda or Miniconda is installed and added to your PATH.
    echo.
    pause
    exit /b 1
)

:: ---------------------------------------------------------
:: 2. Check or Create Conda Environment
:: ---------------------------------------------------------
echo [INFO] Checking Conda environment '%ENV_NAME%'

call conda info --envs | findstr /C:"%ENV_NAME% " >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [INFO] Environment '%ENV_NAME%' found.
) else (
    echo [INFO] Environment not found. Creating '%ENV_NAME%' (Python %PYTHON_VERSION%.
    echo ---------------------------------------------------
    call conda create -n %ENV_NAME% python=%PYTHON_VERSION% -y

    echo ---------------------------------------------------
    echo [INFO] Environment created.
)

:: ---------------------------------------------------------
:: 3. Activate Environment (Current Session)
:: ---------------------------------------------------------
echo [INFO] Activating environment
call conda activate %ENV_NAME% 2>nul
if %ERRORLEVEL% NEQ 0 (
    call activate %ENV_NAME% 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Could not activate environment '%ENV_NAME%'.
        echo Please try running 'conda activate %ENV_NAME%' manually to debug.
        pause
        exit /b 1
    )
)

if exist "%REQ_FILE%" (
    echo [INFO] Checking dependencies - requirements.txt
    pip install -r "%REQ_FILE%"
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo [WARNING] requirements.txt not found, skipping installation.
)

:: ---------------------------------------------------------
:: 5. Launch Services
:: ---------------------------------------------------------
echo.
echo [INFO] Starting EMinder Services

:: Launch Backend
if exist "%BACKEND_SCRIPT%" (
    echo [1/2] Launching Backend - Port: %BACKEND_PORT%
    start "EMinder Backend Service" cmd /k "call conda activate %ENV_NAME% && python "%BACKEND_SCRIPT%" --port %BACKEND_PORT%"
)

:: Wait a moment for backend to initialize
timeout /t 3 /nobreak >nul

:: Launch Frontend
if exist "%FRONTEND_SCRIPT%" (
    echo [2/2] Launching Frontend (Port: %FRONTEND_PORT%)
    start "EMinder Frontend UI" cmd /k "call conda activate %ENV_NAME% && python "%FRONTEND_SCRIPT%" --port %FRONTEND_PORT% --bnport %BACKEND_PORT%"
)

echo.
echo ===================================================
echo       Launch Complete!
echo ===================================================
echo.
echo  [Backend API]  http://127.0.0.1:%BACKEND_PORT%/docs
echo  [Frontend UI]  http://127.0.0.1:%FRONTEND_PORT%
echo.
echo  Please do not close the two new popup windows.
echo  You can safely close this launcher window now.
echo.
pause