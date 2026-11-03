@echo off
REM One-click start for Windows: sets up (first run only), builds the page, starts the server, opens the browser.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [setup] Creating Python environment ^(first run only, takes a few minutes^)...
  python -m venv .venv || goto :nopython
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
)

if not exist "frontend\dist\index.html" (
  echo [setup] Building the web page ^(first run only^)...
  pushd frontend
  call npm install || goto :nonode
  call npm run build || goto :nonode
  popd
)

echo.
echo Starting the translator at http://localhost:8000
echo The first start loads the translation model (2.4 GB; downloaded once). The page shows when it is ready.
echo Keep this window open. Press Ctrl+C to stop.
echo.
start "" http://localhost:8000
cd backend
set NLLB_PRELOAD=1
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto :eof

:nopython
echo Python 3.11+ was not found. Install it from https://www.python.org and run start.bat again.
pause
goto :eof
:nonode
echo Node.js was not found or the build failed. Install Node.js 20+ from https://nodejs.org and run start.bat again.
pause
