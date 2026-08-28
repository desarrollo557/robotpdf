@echo off
chcp 65001 > nul

:: ===========================================================================
:: Install Backend as Windows Service using NSSM
:: ===========================================================================

SETLOCAL

:: Configuration
SET SERVICE_NAME=pdf_bot_backend
SET DISPLAY_NAME=PDF Resolution Bot Backend
SET DESCRIPTION=Backend service for PDF Resolution Segmentation Bot
SET PYTHON_EXE=python
SET SCRIPT_PATH=%~dp0..\app\main.py
SET VENV_PATH=%~dp0..\venv\Scripts\python.exe

:: Check if NSSM is available
WHERE nssm > nul 2>&1
IF ERRORLEVEL 1 (
    echo NSSM is not installed. Please download from https://nssm.cc/download
    echo and install it to a directory in your PATH, or place nssm.exe in this directory.
    pause
    exit /b 1
)

:: Check if Python virtual environment exists
IF NOT EXIST "%VENV_PATH%" (
    echo Python virtual environment not found at: %VENV_PATH%
    echo Please create it first by running: python -m venv venv
    pause
    exit /b 1
)

:: Check if uvicorn is installed
"%VENV_PATH%" -c "import uvicorn" > nul 2>&1
IF ERRORLEVEL 1 (
    echo uvicorn is not installed in the virtual environment.
    echo Please install dependencies first: venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: Check if service already exists
nssm dump %SERVICE_NAME% > nul 2>&1
IF ERRORLEVEL 0 (
    echo Service %SERVICE_NAME% already exists.
    nssm status %SERVICE_NAME%
    goto :CONFIG_SERVICE
)

:: Install the service
nssm install %SERVICE_NAME% "%VENV_PATH%"
IF ERRORLEVEL 1 (
    echo Failed to install service
    pause
    exit /b 1
)

:: Configure the service
:CONFIG_SERVICE
nssm set %SERVICE_NAME% AppDirectory "%~dp0.."
nssm set %SERVICE_NAME% AppParameters "-m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"
nssm set %SERVICE_NAME% AppStdout "%~dp0..\logs\backend_stdout.log"
nssm set %SERVICE_NAME% AppStderr "%~dp0..\logs\backend_stderr.log"
nssm set %SERVICE_NAME% AppStdoutCreationDisposition 4
nssm set %SERVICE_NAME% AppStderrCreationDisposition 4
nssm set %SERVICE_NAME% DisplayName "%DISPLAY_NAME%"
nssm set %SERVICE_NAME% Description "%DESCRIPTION%"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% Type SERVICE_INTERACTIVE_PROCESS
nssm set %SERVICE_NAME% ObjectName LocalSystem
nssm set %SERVICE_NAME% Restart OnExit 5000

:: Set environment variable for the service
nssm set %SERVICE_NAME% AppEnvironmentExtra PYTHONUNBUFFERED=1

:: Create logs directory if it doesn't exist
IF NOT EXIST "%~dp0..\logs" mkdir "%~dp0..\logs"

:: Start the service
nssm start %SERVICE_NAME%
IF ERRORLEVEL 1 (
    echo Failed to start service
    echo Checking service status...
    nssm dump %SERVICE_NAME%
    pause
    exit /b 1
)

echo Service %SERVICE_NAME% installed and started successfully.
echo You can check the status with: nssm status %SERVICE_NAME%
echo View logs with: type %~dp0..\logs\backend_stdout.log

ENDLOCAL
pause
