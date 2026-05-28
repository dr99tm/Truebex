@echo off
REM Start the Truebex auth API. Creates a venv + .env on first run.
cd /d "%~dp0\server"

if not exist ".venv\" (
    echo Creating virtual environment...
    py -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

if not exist ".env" (
    echo No .env found - copying from .env.example. Edit it to set SECRET_KEY.
    copy .env.example .env
)

python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
pause
