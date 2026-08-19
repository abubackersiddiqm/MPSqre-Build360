param([Parameter(Mandatory = $true)][string]$TargetProject)
$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
Push-Location $backend
try {
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "Django check failed." }
    & $python manage.py showmigrations insightops
    if ($LASTEXITCODE -ne 0) { throw "Could not read insightops migrations." }
    & $python manage.py shell -c "from modules.identity.models import Permission; assert Permission.objects.filter(code__startswith='insights.').count() == 10; print('Phase 37 permission inventory: 10')"
    if ($LASTEXITCODE -ne 0) { throw "Phase 37 permission inventory is incomplete." }
    Write-Host "[SUCCESS] Phase 37 executive readiness checks passed." -ForegroundColor Green
} finally { Pop-Location }
