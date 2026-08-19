param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [Parameter(Mandatory=$true)][string]$Confirmation
)
$ErrorActionPreference = "Stop"
if ($Confirmation -ne "APPLY_FRESH_PRODUCTION_MIGRATIONS") {
    throw "Confirmation token mismatch. No database changes were made."
}
$root = [System.IO.Path]::GetFullPath($ProjectRoot)
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
$gate = Join-Path $root "ops\production-r38\production_gate.py"

Write-Host "============================================================"
Write-Host "Build360 R38 - FRESH PRODUCTION DATABASE MIGRATION"
Write-Host "This command refuses a DB that already contains Build360 data."
Write-Host "============================================================" -ForegroundColor Yellow

& $python $gate $root --mode migrate-fresh
exit $LASTEXITCODE
