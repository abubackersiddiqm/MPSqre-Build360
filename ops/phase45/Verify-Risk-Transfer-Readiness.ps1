param(
    [Parameter(Mandatory = $true)]
    [string]$TargetProject
)

$ErrorActionPreference = "Stop"
$backend = Join-Path ([System.IO.Path]::GetFullPath($TargetProject)) "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
Push-Location $backend
try {
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }
    & $python manage.py showmigrations risktransferops
    if ($LASTEXITCODE -ne 0) { throw "Risk-transfer migration state could not be read." }
    & $python manage.py shell -c "from modules.identity.models import Permission; assert Permission.objects.filter(code__startswith='risktransfer.').count() == 12; print('risk-transfer permission inventory: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Risk-transfer permission inventory is incomplete." }
    Write-Host "[SUCCESS] Phase 45 risk-transfer readiness checks passed." -ForegroundColor Green
} finally {
    Pop-Location
}
