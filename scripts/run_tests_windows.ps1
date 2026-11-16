$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location "$root\backend"
& "$root\backend\.venv\Scripts\python.exe" -m pytest -q
