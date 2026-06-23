@echo off
setlocal

set ROOT=%~dp0
set BACKEND_DIR=%ROOT%backend
set FRONTEND_DIR=%ROOT%frontend
set VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe

echo [BAI-Edge-Model] Checking environment...

where python >nul 2>nul
if errorlevel 1 (
    echo [Error] Python was not found in PATH.
    pause
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo [Error] npm was not found in PATH.
    pause
    exit /b 1
)

if not exist "%VENV_PYTHON%" (
    echo [Backend] Creating virtual environment...
    pushd "%BACKEND_DIR%"
    python -m venv .venv
    if errorlevel 1 (
        popd
        echo [Error] Failed to create backend virtual environment.
        pause
        exit /b 1
    )
    popd
)

echo [Backend] Installing Python dependencies...
pushd "%BACKEND_DIR%"
call "%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    popd
    echo [Error] Failed to install backend dependencies.
    pause
    exit /b 1
)
popd

if not exist "%FRONTEND_DIR%\node_modules" (
    echo [Frontend] Installing npm dependencies...
    pushd "%FRONTEND_DIR%"
    call npm install
    if errorlevel 1 (
        popd
        echo [Error] Failed to install frontend dependencies.
        pause
        exit /b 1
    )
    popd
)

echo [Backend] Starting server on http://127.0.0.1:8000
start "BAI Edge Backend" cmd /k "cd /d \"%BACKEND_DIR%\" & call .venv\Scripts\activate.bat & uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [Frontend] Starting server on http://127.0.0.1:5173
start "BAI Edge Frontend" cmd /k "cd /d \"%FRONTEND_DIR%\" & npm run dev -- --host 127.0.0.1 --port 5173"

timeout /t 3 >nul
start "" "http://127.0.0.1:5173"

echo [Done] Frontend and backend have been started.
echo [Info] Close the two opened terminal windows to stop the service.
pause