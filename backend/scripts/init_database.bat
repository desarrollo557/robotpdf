@echo off
chcp 65001 > nul

:: ===========================================================================
:: Initialize Database and Run Migrations
:: ===========================================================================

SETLOCAL

:: Check if Python is available
python --version > nul 2>&1
IF ERRORLEVEL 1 (
    echo Python is not installed or not in PATH
    pause
    exit /b 1
)

:: Check if venv exists and use it
IF EXIST "%~dp0..\venv\Scripts\python.exe" (
    SET PYTHON=%~dp0..\venv\Scripts\python.exe
) ELSE (
    SET PYTHON=python
)

:: Check if alembic is installed
"%PYTHON%" -c "import alembic" > nul 2>&1
IF ERRORLEVEL 1 (
    echo Alembic is not installed.
    echo Installing dependencies...
    "%PYTHON%" -m pip install -r requirements.txt --quiet
    IF ERRORLEVEL 1 (
        echo Failed to install dependencies
        pause
        exit /b 1
    )
)

:: Run database migrations
echo Running database migrations...
cd /d "%~dp0.."
"%PYTHON%" -m alembic upgrade head
IF ERRORLEVEL 1 (
    echo Failed to run migrations
    pause
    exit /b 1
)

echo Database initialized successfully.

ENDLOCAL
pause
