#Requires -Version 5.1
<#
    Menschheit Arena - Startskript (Windows).
    Legt .venv an, installiert das Paket, prueft die Konfiguration und startet den Server.
#>

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Erstelle virtuelle Umgebung (.venv) ..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "Installiere Paket ..." -ForegroundColor Cyan
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -e ".[dev]"

Write-Host "Pruefe Konfiguration ..." -ForegroundColor Cyan
& $venvPython -m menschheit.cli doctor
if ($LASTEXITCODE -ne 0) {
    Write-Host "doctor meldet Fehler. Behebe sie, bevor du startest." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starte Menschheit Arena ..." -ForegroundColor Green
Write-Host "Danach: http://127.0.0.1:8000" -ForegroundColor DarkGray
Write-Host ""

& $venvPython -m menschheit.cli serve @args