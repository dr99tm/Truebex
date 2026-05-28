@echo off
REM Start the Truebex auth server. Creates a venv on first run.
cd /d "%~dp0"

if not exist ".venv\" (
    echo Creating virtual environment...
    py -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

if not exist ".env" (
    echo No .env found - copying from .env.example. Edit it to set SECRET_KEY.
    copy .env.example .env
)

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
