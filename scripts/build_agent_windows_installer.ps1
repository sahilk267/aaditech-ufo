# Build the AADITECH UFO Agent Windows installer end-to-end.
# Usage:  pwsh ./scripts/build_agent_windows_installer.ps1 -Version 1.2.3
# Output: agent/AaditechUfoAgentSetup-<Version>.exe

param(
  [Parameter(Mandatory=$false)]
  [string]$Version = "0.0.0",
  [Parameter(Mandatory=$false)]
  [string]$NsisPath = "C:\Program Files (x86)\NSIS\makensis.exe"
)

$ErrorActionPreference = 'Stop'

Write-Host "==> Verifying prerequisites" -ForegroundColor Cyan
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python is not on PATH." }
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
  Write-Host "PyInstaller not found, installing..." -ForegroundColor Yellow
  python -m pip install --upgrade pip pyinstaller | Out-Null
}
if (-not (Test-Path $NsisPath)) { throw "NSIS not found at $NsisPath. Install from https://nsis.sourceforge.io/" }

Write-Host "==> Building agent .exe with PyInstaller (version $Version)" -ForegroundColor Cyan
pyinstaller --noconfirm --onefile --name aaditech-agent agent/agent.py
if (-not (Test-Path "dist/aaditech-agent.exe")) { throw "PyInstaller build failed: dist/aaditech-agent.exe missing." }

Write-Host "==> Building NSIS installer" -ForegroundColor Cyan
& $NsisPath "/DAGENT_VERSION=$Version" "/DAGENT_EXE_PATH=$PWD\dist\aaditech-agent.exe" "agent\installer.nsi"

$installer = "agent\AaditechUfoAgentSetup-$Version.exe"
if (-not (Test-Path $installer)) { throw "NSIS build failed: $installer missing." }

Write-Host "==> Done. Installer ready at: $installer" -ForegroundColor Green
Get-Item $installer | Select-Object Name, Length, LastWriteTime
