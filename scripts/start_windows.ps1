# Starts the backend (port 8000) and frontend (port 5173) in two windows.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Run scripts\setup_windows.ps1 first." -ForegroundColor Red; exit 1 }

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; & '$py' -m uvicorn app.main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; npm run dev"
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"
Write-Host "Backend: http://localhost:8000/docs   Frontend: http://localhost:5173"
