param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath($ProjectRoot)
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
$gate = Join-Path $root "ops\production-r38\production_gate.py"

if (!(Test-Path $python)) { throw "Backend .venv Python runtime is missing." }
if (!(Test-Path $gate)) { throw "R38 production_gate.py is missing." }

& $python $gate $root --mode migration-plan
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[TEST] Frontend typecheck" -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm run lint
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

Write-Host "[SUCCESS] Production pre-migration validation passed." -ForegroundColor Green
