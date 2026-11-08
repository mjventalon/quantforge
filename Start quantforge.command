#!/bin/bash
# quantforge launcher for macOS (and Linux): double-click to start the app.
# First run: creates a private Python environment and installs quantforge (a few minutes).
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Get it from https://www.python.org/downloads/ and try again."
  read -r -p "Press Enter to close..."
  exit 1
fi

if [ ! -x ".venv/bin/quantforge-app" ]; then
  echo "First launch: installing quantforge (this happens only once)..."
  python3 -m venv .venv || { read -r -p "Could not create the environment. Press Enter..."; exit 1; }
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -e ".[all]" || { read -r -p "Install failed. Press Enter..."; exit 1; }
fi

echo "Starting quantforge on http://localhost:8501 (close this window to stop it)"
exec .venv/bin/quantforge-app
