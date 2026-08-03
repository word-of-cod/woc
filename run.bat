@echo off
setlocal

cd /d "%~dp0"

if not exist .env (
    echo .env not found — copying from .env.template
    copy /y .env.template .env >nul
    echo Fill in .env with real values, then re-run this script.
    exit /b 1
)

docker compose up --build
