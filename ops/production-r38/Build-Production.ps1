param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath($ProjectRoot)
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
$gate = Join-Path $root "ops\production-r38\production_gate.py"

& $python $gate $root --mode validate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:BUILD360_ENVIRONMENT = "production"
$env:APP_ENV = "production"
$env:DJANGO_ENV_FILE = "backend\.env.production"

Write-Host "[BUILD] Django collectstatic" -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
try {
    & $python manage.py collectstatic --noinput
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

Write-Host "[BUILD] Frontend quality + production build" -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm run lint
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

Write-Host "[SUCCESS] Build360 production release build passed." -ForegroundColor Green
