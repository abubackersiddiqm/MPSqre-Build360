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
    & $python manage.py showmigrations capitalops
    if ($LASTEXITCODE -ne 0) { throw "Capital migration state could not be read." }
    & $python manage.py shell -c "from modules.identity.models import Permission; assert Permission.objects.filter(code__startswith='capital.').count() == 12; print('capital permission inventory: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Capital permission inventory is incomplete." }
    Write-Host "[SUCCESS] Phase 44 capital readiness checks passed." -ForegroundColor Green
} finally {
    Pop-Location
}
