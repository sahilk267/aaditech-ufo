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
$VersionFile = Join-Path $AgentDir "version.py"
Set-Location $AgentDir

if ($Version -notmatch '^[A-Za-z0-9._-]{1,64}$') {
    throw "Invalid version '$Version'. Allowed: letters, numbers, dot, underscore, hyphen (1-64 chars)."
}

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "Installing PyInstaller..."
    python -m pip install --upgrade pip
    python -m pip install pyinstaller
}

Write-Host "Stamping agent/version.py with $Version"
$VersionFileBackup = "$VersionFile.bak"
Copy-Item $VersionFile $VersionFileBackup -Force
$VersionContent = @"
"""Single source of truth for the agent's running version.

This file is overwritten by scripts/build_agent_windows.ps1 at build time.
"""

AGENT_VERSION = "$Version"
"@
Set-Content -Path $VersionFile -Value $VersionContent -Encoding utf8

try {
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
}
finally {
    Write-Host "Restoring agent/version.py"
    Move-Item $VersionFileBackup $VersionFile -Force
}
