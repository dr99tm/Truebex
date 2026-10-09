@echo off
REM LOCAL USE ONLY since PF14: production runs on the VM (infra/, CUTOVER.md).
REM Starts the API on :8001 against server\auth.db. Never point the tunnel's
REM api.truebex.com at it again: a second API with its own database would take
REM writes nobody sees. Creates the venv + .env on first run.
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
