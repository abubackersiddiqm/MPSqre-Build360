param(
    [string]$BaseUrl = "http://localhost:3000",
    [string]$OutputPath = "",
    [int]$Iterations = 3
)

$ErrorActionPreference = "Continue"
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $PSScriptRoot ("phase34-benchmark-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".json")
}
$routes = @(
    "/platform",
    "/platform/release-readiness",
    "/platform/stability-operations"
)
$results = @()
foreach ($route in $routes) {
    for ($index = 1; $index -le $Iterations; $index++) {
        $url = $BaseUrl.TrimEnd("/") + $route
        $watch = [System.Diagnostics.Stopwatch]::StartNew()
        $status = 0
        $errorText = ""
        try {
            $response = Invoke-WebRequest -Uri $url -Method Get -MaximumRedirection 5 -UseBasicParsing -TimeoutSec 60
            $status = [int]$response.StatusCode
        } catch {
            if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
            $errorText = $_.Exception.Message
        } finally {
            $watch.Stop()
        }
        $results += [pscustomobject]@{
            route = $route
            iteration = $index
            status = $status
            duration_ms = [math]::Round($watch.Elapsed.TotalMilliseconds, 2)
            captured_at = (Get-Date).ToString("o")
            error = $errorText
        }
        Write-Host ("{0} #{1}: {2} ms status={3}" -f $route, $index, [math]::Round($watch.Elapsed.TotalMilliseconds, 2), $status)
    }
}
$results | ConvertTo-Json -Depth 4 | Set-Content -Path $OutputPath -Encoding UTF8
Write-Host "[SUCCESS] Benchmark evidence written to $OutputPath" -ForegroundColor Green
