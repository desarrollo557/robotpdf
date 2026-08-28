@echo off
setlocal enabledelayedexpansion
title Robot Project - Launcher de Servicios
color 0A

set "BACKEND_DIR=C:\Users\desarrollo.SIAR\Desktop\robot-project\backend"
set "FRONTEND_DIR=C:\Users\desarrollo.SIAR\Desktop\robot-project\frontend"

echo ============================================================
echo   Robot Project - Arranque de servicios
echo ============================================================
echo.

REM ---------------------------------------------------------------------------
REM [1/4] Validar puertos ocupados y limpiar servicios previos
REM ---------------------------------------------------------------------------
echo [1/4] Validando puertos y limpiando servicios previos...

set "PUERTOS=8000 5173"
for %%P in (%PUERTOS%) do (
    set "ENCONTRADO=0"
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr /c:":%%P " ^| findstr "LISTENING"') do (
        set "ENCONTRADO=1"
        echo   - Puerto %%P ocupado por PID %%a. Matando...
        taskkill /PID %%a /F >nul 2>&1
        if !errorlevel! == 0 (
            echo     PID %%a terminado.
        ) else (
            echo     No se pudo terminar PID %%a (quizas ya cerro).
        )
    )
    if !ENCONTRADO! == 0 (
        echo   - Puerto %%P libre.
    )
)

echo   Esperando liberacion de puertos...
timeout /t 2 >nul
echo.

REM ---------------------------------------------------------------------------
REM [2/4] Iniciar Backend (FastAPI :8000 + Prometheus :9090)
REM ---------------------------------------------------------------------------
echo [2/4] Iniciando Backend (API :8000 + Prometheus :9090)...
if not exist "%BACKEND_DIR%\venv\Scripts\activate" (
    echo   ERROR: no se encontro el venv en %BACKEND_DIR%\venv
    goto :fin
)
start "RobotBackend" cmd /k "cd /d "%BACKEND_DIR%" && set PYTHONPATH=%BACKEND_DIR% && call venv\Scripts\activate && python app/main.py"
echo   Ventana 'RobotBackend' abierta.
echo.

REM ---------------------------------------------------------------------------
REM [3/4] Iniciar Frontend dev (Vite :5173)
REM ---------------------------------------------------------------------------
echo [3/4] Iniciando Frontend dev (:5173)...
if not exist "%FRONTEND_DIR%\package.json" (
    echo   ERROR: no se encontro el frontend en %FRONTEND_DIR%
    goto :fin
)
start "RobotFrontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"
echo   Ventana 'RobotFrontend' abierta.
echo.

REM ---------------------------------------------------------------------------
REM [4/4] Resumen
REM ---------------------------------------------------------------------------
echo [4/4] Servicios iniciados en ventanas separadas.
echo.
echo   Backend  : http://localhost:8000   (docs: /docs, health: /health)
echo   Frontend : http://localhost:5173
echo   Prometheus: http://localhost:9090/metrics
echo.
echo   Cierra las ventanas para detener cada servicio.
echo   (El frontend de produccion ya se sirve desde :8000/)
echo.

:fin
pause
