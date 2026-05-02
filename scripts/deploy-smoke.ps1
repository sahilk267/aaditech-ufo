<#
deploy-smoke.ps1

Performs basic smoke checks against the gateway after starting the staging/prod gateway.

Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\deploy-smoke.ps1

Environment expectations:
  - Gateway running on http://localhost:9773
  - `frontend/dist/index.html` present and mounted into gateway
#>

param(
    [string]$GatewayUrl = 'http://localhost:9773'
)

function ExitWithError($msg) {
    Write-Error $msg
    exit 1
}

Write-Host "Checking SPA index at $GatewayUrl/app/ ..."
try {
    $r = Invoke-WebRequest -Uri "$GatewayUrl/app/" -UseBasicParsing -TimeoutSec 30
} catch {
    ExitWithError "Failed to fetch $GatewayUrl/app/: $_"
}

if ($r.StatusCode -ne 200) { ExitWithError "Non-200 response for /app/: $($r.StatusCode)" }

$html = $r.Content
if (-not ($html -match '<title')) { ExitWithError "Returned HTML does not contain <title> — SPA index may be wrong" }
Write-Host "SPA index fetched and looks valid."

Write-Host "Checking API proxy at $GatewayUrl/api/status ..."
try {
    $api = Invoke-RestMethod -Uri "$GatewayUrl/api/status" -TimeoutSec 15 -ErrorAction Stop
    Write-Host "API response (parsed):" -NoNewline; Write-Host ($api | ConvertTo-Json -Depth 2)
} catch {
    Write-Warning "API call failed or returned an auth error — this may be expected if auth required. Error: $_"
}

Write-Host "Smoke checks passed (index found). If API requires auth, verify expected auth flows separately." 

exit 0
