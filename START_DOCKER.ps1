$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\Backend"
Write-Host "Starting Digital FTE Docker stack..." -ForegroundColor Cyan
docker compose up --build
