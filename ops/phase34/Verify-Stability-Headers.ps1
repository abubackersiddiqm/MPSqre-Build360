param(
    [string]$BackendUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$url = $BackendUrl.TrimEnd("/") + "/api/v1/health/live"
$response = Invoke-WebRequest -Uri $url -Method Get -UseBasicParsing -TimeoutSec 30
$timing = $response.Headers["Server-Timing"]
$responseTime = $response.Headers["X-Response-Time-Ms"]
$requestId = $response.Headers["X-Request-ID"]
if ([string]::IsNullOrWhiteSpace($timing)) { throw "Server-Timing header is missing." }
if ([string]::IsNullOrWhiteSpace($responseTime)) { throw "X-Response-Time-Ms header is missing." }
if ([string]::IsNullOrWhiteSpace($requestId)) { throw "X-Request-ID header is missing." }
Write-Host "[SUCCESS] Stability timing headers are active." -ForegroundColor Green
Write-Host "Server-Timing: $timing"
Write-Host "X-Response-Time-Ms: $responseTime"
Write-Host "X-Request-ID: $requestId"
