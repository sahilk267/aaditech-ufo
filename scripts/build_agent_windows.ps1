# Build Aaditech Windows agent executable on a Windows build server.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scripts\build_agent_windows.ps1 -Version 1.0.0

param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$AgentDir = Join-Path $RepoRoot "agent"
Set-Location $AgentDir

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "Installing PyInstaller..."
    python -m pip install --upgrade pip
    python -m pip install pyinstaller
}

Write-Host "Building aaditech-agent executable..."
pyinstaller build.spec --clean --noconfirm

$BuiltExe = Join-Path $AgentDir "dist\aaditech-agent.exe"
if (-not (Test-Path $BuiltExe)) {
    throw "Build failed: $BuiltExe not found"
}

$VersionedExe = Join-Path $AgentDir "dist\aaditech-agent-$Version.exe"
Copy-Item $BuiltExe $VersionedExe -Force

Write-Host "Build complete: $VersionedExe"
Write-Host "Next: publish with scripts/publish_agent_release.sh (or copy into instance/agent_releases)."
