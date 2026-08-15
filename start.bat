@echo off
setlocal EnableDelayedExpansion
title Chirag Clone - Startup
color 0A

echo ============================================================
echo    Chirag Clone - Local-First AI Digital Twin
echo    One-Click Setup ^& Launch
echo ============================================================
echo.

:: ============= Check Python =============
echo [1/7] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Please install Python 3.11+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo    Found Python %PYVER%

:: ============= Check Node.js =============
echo [2/7] Checking Node.js...
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Node.js not found. Please install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do set NODEVER=%%v
echo    Found Node.js %NODEVER%

:: ============= Setup .env =============
echo [3/7] Checking .env configuration...
if not exist ".env" (
    echo    .env not found, creating from .env.example...
    copy ".env.example" ".env" >nul
    echo    Created .env — edit it later to customize settings.
) else (
    echo    .env already exists.
)

:: ============= Create Python Virtual Environment =============
echo [4/7] Setting up Python virtual environment...
if not exist ".venv\Scripts\python.exe" (
    echo    Creating virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo    Virtual environment created.
) else (
    echo    Virtual environment already exists.
)

:: ============= Install Backend Dependencies =============
echo [5/7] Installing backend dependencies...
:: Check if key packages are already installed
.venv\Scripts\python.exe -c "import fastapi; import sentence_transformers" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo    Installing Python packages (this may take a few minutes on first run)...
    .venv\Scripts\pip.exe install --quiet --disable-pip-version-check -r requirements.txt 2>nul
    if %ERRORLEVEL% neq 0 (
        echo    Some packages may have failed. Trying essential packages only...
        .venv\Scripts\pip.exe install --quiet fastapi uvicorn python-dotenv requests pydantic sentence-transformers orjson 2>nul
    )
    echo    Backend dependencies installed.
) else (
    echo    Backend dependencies already installed.
)

:: ============= Install Frontend Dependencies =============
echo [6/7] Installing frontend dependencies...
if not exist "frontend-react\node_modules" (
    echo    Installing npm packages (this may take a minute on first run)...
    pushd frontend-react
    call npm.cmd install --silent 2>nul
    popd
    echo    Frontend dependencies installed.
) else (
    echo    Frontend dependencies already installed.
)

:: ============= Create Context Directory =============
if not exist "backend\data\context" (
    mkdir "backend\data\context" 2>nul
)

:: Copy chiragcontext.txt if it exists at root and not yet in context dir
if exist "chiragcontext.txt" (
    if not exist "backend\data\context\chirag_identity.txt" (
        copy "chiragcontext.txt" "backend\data\context\chirag_identity.txt" >nul
        echo    Copied chiragcontext.txt to context directory.
    )
)

:: ============= Launch Services =============
echo [7/7] Starting services...
echo.
echo ============================================================
echo    Starting Backend (FastAPI) and Frontend (Vite)...
echo ============================================================
echo.

:: Check LM Studio
echo Checking LM Studio connection...
.venv\Scripts\python.exe -c "import requests; r=requests.get('http://localhost:1234/v1/models', timeout=3); models=r.json().get('data',[]); print(f'  LM Studio: {len(models)} model(s) loaded') if models else print('  LM Studio: running but no model loaded')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo    LM Studio not detected at localhost:1234
    echo    The clone will run in RAG-only mode (context files).
    echo    Start LM Studio and load a model for full AI responses.
)
echo.

:: Start backend in background
echo Starting backend on http://localhost:8000 ...
start "Chirag Clone Backend" /min cmd /c "cd /d %~dp0 && .venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload 2>&1"

:: Wait for backend to start
echo Waiting for backend to be ready...
timeout /t 3 /nobreak >nul

:: Start frontend in background
echo Starting frontend on http://localhost:5173 ...
start "Chirag Clone Frontend" /min cmd /c "cd /d %~dp0\frontend-react && npm.cmd run dev 2>&1"

:: Wait for frontend to start
timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo    Chirag Clone is running!
echo ============================================================
echo.
echo    Frontend:  http://localhost:5173
echo    Backend:   http://localhost:8000
echo    API Docs:  http://localhost:8000/docs
echo.
echo    To stop: Close the "Chirag Clone Backend" and
echo             "Chirag Clone Frontend" terminal windows.
echo.
echo    Press any key to open the app in your browser...
pause >nul

:: Open in default browser
start http://localhost:5173

echo.
echo App opened in browser. This window can be closed.
echo To stop the services, close the Backend and Frontend windows.
pause
