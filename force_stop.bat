@echo off
title EMinder Process Killer

echo.
echo [EMinder Killer] Finding and terminating all EMinder-related processes...
echo.

rem Section 1: Kill processes by script name
echo ================================================================
echo  Finding Backend (backend\run.py) and Frontend (frontend.py)...
echo ================================================================
FOR /F "tokens=2 delims==;" %%P IN (
    'wmic process where "name='python.exe' and (commandline like '%%backend\\run.py%%' or commandline like '%%frontend.py%%')" get processid /value'
) DO (
    IF NOT "%%P"=="" (
        echo  - Found PID: %%P, force killing...
        taskkill /F /PID %%P
    )
)

rem Section 2: Kill processes by port
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
echo [EMinder Killer] All identified EMinder processes have been terminated.
echo.
pause