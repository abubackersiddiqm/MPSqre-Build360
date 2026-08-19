param(
    [Parameter(Mandatory = $true)][string]$FrontendUrl,
    [Parameter(Mandatory = $true)][string]$BackendUrl
)
$ErrorActionPreference = "Stop"
$failures = 0
function Probe([string]$Name, [string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -UseBasicParsing -TimeoutSec 25
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { Write-Host "[PASS] $Name $($response.StatusCode) - $Url" -ForegroundColor Green }
        else { Write-Host "[FAIL] $Name $($response.StatusCode) - $Url" -ForegroundColor Red; $script:failures += 1 }
    } catch { Write-Host "[FAIL] $Name - $($_.Exception.Message)" -ForegroundColor Red; $script:failures += 1 }
}
$front = $FrontendUrl.TrimEnd("/")
$back = $BackendUrl.TrimEnd("/")
Probe "Frontend" $front
Probe "Sign in" "$front/sign-in"
Probe "Live health" "$back/api/v1/health/live"
Probe "Ready health" "$back/api/v1/health/ready"
if ($failures -gt 0) { Write-Host "[ERROR] Smoke test completed with $failures failure(s)." -ForegroundColor Red; exit 1 }
Write-Host "[SUCCESS] Production smoke test passed." -ForegroundColor Green
