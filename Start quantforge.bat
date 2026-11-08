@echo off
REM quantforge launcher for Windows: double-click to start the app.
REM First run: creates a private Python environment and installs quantforge (a few minutes).
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://www.python.org/downloads/ and tick "Add Python to PATH".
  pause
  exit /b 1
)
if not exist ".venv\Scripts\quantforge-app.exe" (
  echo First launch: installing quantforge ^(this happens only once^)...
  python -m venv .venv || goto :fail
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -e ".[all]" || goto :fail
)
echo Starting quantforge on http://localhost:8501 (close this window to stop it)
".venv\Scripts\quantforge-app.exe"
exit /b 0
:fail
echo Installation failed. See the messages above.
pause
exit /b 1
