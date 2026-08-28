@echo off
chcp 65001 > nul

:: ===========================================================================
:: Uninstall Backend Windows Service
:: ===========================================================================

SETLOCAL

SET SERVICE_NAME=pdf_bot_backend

:: Check if NSSM is available
WHERE nssm > nul 2>&1
IF ERRORLEVEL 1 (
    echo NSSM is not installed.
    pause
    exit /b 1
)

:: Check if service exists
nssm dump %SERVICE_NAME% > nul 2>&1
IF ERRORLEVEL 1 (
    echo Service %SERVICE_NAME% does not exist.
    pause
    exit /b 0
)

:: Stop the service
nssm stop %SERVICE_NAME%
IF ERRORLEVEL 1 (
    echo Failed to stop service %SERVICE_NAME%
    pause
    exit /b 1
)

:: Wait for service to stop
echo Waiting for service to stop...
timeout /t 10 > nul

:: Remove the service
nssm remove %SERVICE_NAME% confirm
IF ERRORLEVEL 1 (
    echo Failed to remove service %SERVICE_NAME%
    pause
    exit /b 1
)

echo Service %SERVICE_NAME% uninstalled successfully.

ENDLOCAL
pause
