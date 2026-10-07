@echo off
REM Start the Truebex API on :8001 (the port the cloudflared tunnel forwards
REM api.truebex.com to). Creates the venv + .env on first run.
cd /d "%~dp0\server"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment with Python 3.12...
    if exist ".venv\" rmdir /s /q .venv
    py -3.12 -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)

if not exist ".env" (
    echo No .env found - copying from .env.example. Edit it to set SECRET_KEY.
    copy .env.example .env
)

.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --proxy-headers
pause
