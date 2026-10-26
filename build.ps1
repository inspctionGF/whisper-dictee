# Construit le dossier Windows dist\DicteeLocale, sans modèle Whisper.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "L'environnement .venv est introuvable."
}

& $python -m pip install pyinstaller
& $python -m PyInstaller --noconfirm DicteeLocale.spec

$iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    throw "Inno Setup 6 est introuvable. Installez-le, puis relancez ce script."
}
& $iscc (Join-Path $PSScriptRoot "installer.iss")

Write-Host ""
Write-Host "Installateur prêt : dist\DicteeLocale-Setup.exe"
Write-Host "Il pose l'icône Dictée locale sur le Bureau."
Write-Host "Le modèle Whisper n'est pas inclus. Il se télécharge au premier lancement, selon la carte graphique."
