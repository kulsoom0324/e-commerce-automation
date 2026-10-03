$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\Backend"
Write-Host "Starting PostgreSQL + Redis containers..." -ForegroundColor Cyan
docker compose up -d postgres redis
Write-Host "Starting FastAPI locally on http://127.0.0.1:8000" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
