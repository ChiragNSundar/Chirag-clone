@echo off
setlocal EnableDelayedExpansion
title Chirag Clone - Startup
color 0A

echo ============================================================
echo    Chirag Clone - Local-First AI Digital Twin
echo    One-Click Setup ^& Launch
echo ============================================================
echo.

:: Set PYTHONPATH so python imports backend files cleanly
set "PYTHONPATH=%~dp0backend;%~dp0;%PYTHONPATH%"

:: ============= Check Python =============
echo [1/6] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Please install Python 3.11+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo    Found Python %PYVER%

:: Determine Python executable to use
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
    set "PIP_CMD=.venv\Scripts\pip.exe"
) else (
    set "PY_CMD=python"
    set "PIP_CMD=pip"
)

:: ============= Check Node.js =============
echo [2/6] Checking Node.js...
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Node.js not found. Please install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do set NODEVER=%%v
echo    Found Node.js %NODEVER%

:: ============= Setup .env =============
echo [3/6] Checking .env configuration...
if not exist ".env" (
    echo    .env not found, creating from .env.example...
    copy ".env.example" ".env" >nul
    echo    Created .env — edit it later to customize settings.
) else (
    echo    .env already exists.
)

:: ============= Install Backend Dependencies =============
echo [4/6] Checking backend dependencies...
%PY_CMD% -c "import fastapi; import sqlmodel; import requests; import orjson" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo    Installing Python packages...
    %PIP_CMD% install -r requirements.txt
) else (
    echo    Backend dependencies verified.
)

:: ============= Install Frontend Dependencies =============
echo [5/6] Checking frontend dependencies...
if not exist "frontend-react\node_modules" (
    echo    Installing npm packages...
    pushd frontend-react
    call npm.cmd install --ignore-scripts
    popd
    echo    Frontend dependencies installed.
) else (
    echo    Frontend dependencies verified.
)

:: ============= Create Context Directory =============
if not exist "backend\data\context" (
    mkdir "backend\data\context" 2>nul
)

if exist "chiragcontext.txt" (
    if not exist "backend\data\context\chirag_identity.txt" (
        copy "chiragcontext.txt" "backend\data\context\chirag_identity.txt" >nul
        echo    Copied chiragcontext.txt to context directory.
    )
)

:: ============= Launch Services =============
echo [6/6] Launching Chirag Clone...
echo.

:: Check LM Studio
echo Checking LM Studio connection...
%PY_CMD% -c "import requests; r=requests.get('http://localhost:1234/v1/models', timeout=3); models=r.json().get('data',[]); print(f'  LM Studio: {len(models)} model(s) loaded') if models else print('  LM Studio: running but no model loaded')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo    LM Studio not detected at http://localhost:1234
    echo    The clone will run in RAG-only mode (context files).
    echo    Start LM Studio and load a model for full AI responses.
)
echo.

:: Start backend in separate persistent window
echo Starting backend server (http://localhost:8000)...
start "Chirag Clone Backend" cmd /k "cd /d %~dp0 && set PYTHONPATH=%~dp0backend;%~dp0 && %PY_CMD% -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait 3s for backend startup
timeout /t 3 /nobreak >nul

:: Start frontend in separate persistent window
echo Starting frontend server (http://localhost:5173)...
start "Chirag Clone Frontend" cmd /k "cd /d %~dp0\frontend-react && npm.cmd run dev"

timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo    Chirag Clone is RUNNING!
echo ============================================================
echo.
echo    Frontend UI: http://localhost:5173
echo    Backend API: http://localhost:8000
echo    API Docs:    http://localhost:8000/docs
echo.
echo    Opening browser...
echo.

start http://localhost:5173

echo.
echo Press any key to exit this installer window.
echo (The Backend and Frontend windows will remain running.)
pause >nul
