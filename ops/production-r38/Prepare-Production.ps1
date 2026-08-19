param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath($ProjectRoot)
$example = Join-Path $root "backend\.env.production.example"
$target = Join-Path $root "backend\.env.production"

Write-Host "============================================================"
Write-Host "Build360 R38 - Prepare Production Environment"
Write-Host "Target: $root"
Write-Host "============================================================"

if (!(Test-Path $example)) {
    throw "Missing backend\.env.production.example"
}

if (Test-Path $target) {
    Write-Host "[OK] backend\.env.production already exists." -ForegroundColor Green
} else {
    Copy-Item $example $target
    Write-Host "[CREATED] backend\.env.production from the controlled example." -ForegroundColor Green
}

Write-Host ""
Write-Host "IMPORTANT: Do not run production migration yet." -ForegroundColor Yellow
Write-Host "Edit this file first:"
Write-Host "  $target"
Write-Host ""
Write-Host "Required production infrastructure:"
Write-Host "  - HTTPS public domain"
Write-Host "  - Managed PostgreSQL database named build360_production with TLS"
Write-Host "  - Encrypted Redis / Celery broker (rediss://)"
Write-Host "  - Private HTTPS object storage"
Write-Host "  - Production SMTP"
Write-Host "  - Unique Django/JWT/CRM encryption secrets from your secret manager"
Write-Host ""
Write-Host "Then run:"
Write-Host "  Validate-Production-R38.bat `"$root`""
