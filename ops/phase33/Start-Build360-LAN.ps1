param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [int]$FrontendPort = 3000,
    [int]$BackendPort = 8000
)
$ErrorActionPreference = "Stop"
$project = [System.IO.Path]::GetFullPath($ProjectRoot)
$backend = Join-Path $project "backend"
$frontend = Join-Path $project "frontend"
if (-not (Test-Path (Join-Path $backend "manage.py"))) { throw "backend\manage.py was not found." }
if (-not (Test-Path (Join-Path $frontend "package.json"))) { throw "frontend\package.json was not found." }
$ip = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" -and $_.AddressState -eq "Preferred"
} | Select-Object -First 1 -ExpandProperty IPAddress
if (-not $ip) { $ip = "YOUR-LAN-IP" }
$backendCommand = "cd /d `"$backend`" && call venv\Scripts\activate.bat && python manage.py runserver 0.0.0.0:$BackendPort"
$frontendCommand = "cd /d `"$frontend`" && npm run dev -- --hostname 0.0.0.0 --port $FrontendPort"
Start-Process cmd.exe -ArgumentList "/k", $backendCommand
Start-Sleep -Seconds 2
Start-Process cmd.exe -ArgumentList "/k", $frontendCommand
Write-Host "[SUCCESS] Build360 LAN development services started." -ForegroundColor Green
Write-Host "[OPEN] http://${ip}:$FrontendPort"
Write-Host "[API]  http://${ip}:$BackendPort/api/v1/health/ready"
Write-Host "Ensure ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS include this LAN address."
