#!/usr/bin/env bash
# One-click start for Linux/macOS: sets up (first run only), builds the page, starts the server.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "[setup] Creating Python environment (first run only, takes a few minutes)..."
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  if [ "$(uname)" = "Darwin" ]; then .venv/bin/python -m pip install torch
  else .venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu; fi
  .venv/bin/python -m pip install -r backend/requirements.txt
fi
if [ ! -f frontend/dist/index.html ]; then
  echo "[setup] Building the web page (first run only)..."
  (cd frontend && npm install && npm run build)
fi
echo
echo "Starting the translator at http://localhost:8000"
echo "The first start loads the translation model (2.4 GB; downloaded once). The page shows when it is ready."
echo "Press Ctrl+C to stop."
cd backend
NLLB_PRELOAD=1 exec ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
