@echo off
REM Local development server on :8000 with auto-reload. Creates the venv on
REM first run. Production uses ..\start-server.bat (port 8001) instead.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment with Python 3.12...
    if exist ".venv\" rmdir /s /q .venv
    py -3.12 -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
)

if not exist ".env" (
    echo No .env found - copying from .env.example. Edit it to set SECRET_KEY.
    copy .env.example .env
)

.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
