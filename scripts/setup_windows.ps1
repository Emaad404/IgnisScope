# Run from the project root:  powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Write-Host "Missing: $cmd. $hint" -ForegroundColor Red; exit 1 }
}
Need "python" "Install Python 3.11 or newer from python.org and tick 'Add to PATH'."
Need "node"   "Install Node.js 18 or newer (LTS) from nodejs.org."

$v = python -c "import sys; print(sys.version_info.major*100+sys.version_info.minor)"
if ([int]$v -lt 311) { Write-Host "Python 3.11+ is required (found $v)." -ForegroundColor Red; exit 1 }

if (-not (Test-Path "backend\.venv")) { python -m venv backend\.venv }
& backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

Set-Location $root
npm install

if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
Write-Host "Setup finished. Start the app with: powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1" -ForegroundColor Green
