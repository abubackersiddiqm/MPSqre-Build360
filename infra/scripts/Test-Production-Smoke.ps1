[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ApiBaseUrl,
    [Parameter(Mandatory = $true)][string]$FrontendBaseUrl
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$api = $ApiBaseUrl.TrimEnd("/")
$web = $FrontendBaseUrl.TrimEnd("/")
$live = Invoke-RestMethod -Method Get -Uri "$api/health/live" -TimeoutSec 30
if ($live.status -ne "ok") { throw "API liveness failed." }
$ready = Invoke-RestMethod -Method Get -Uri "$api/health/ready" -TimeoutSec 30
if ($ready.status -ne "ok") { throw "API readiness failed." }
$response = Invoke-WebRequest -Method Get -Uri $web -TimeoutSec 30 -UseBasicParsing
if ($response.StatusCode -ne 200) { throw "Frontend health failed." }
Write-Host "Production smoke checks passed." -ForegroundColor Green
