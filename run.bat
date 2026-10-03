@echo off
setlocal

cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo Venv not found. Please run setup first.
    exit /b 1
)

call venv\Scripts\activate.bat

python -m uvicorn api.server:app --host 127.0.0.1 --port 8004
