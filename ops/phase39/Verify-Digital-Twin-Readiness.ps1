param([string]$TargetProject = "D:\MPSqre\MPSqre_Build360")
$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
Push-Location $backend
try {
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }
    & $python manage.py showmigrations digitaltwinops
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect digitaltwinops migrations." }
    & $python manage.py shell -c "from modules.digitaltwinops.models import BIMModel,BIMRevision,ClashRecord,IoTDevice,SmartAlert,HandoverAssetRecord; print({'models':BIMModel.objects.count(),'revisions':BIMRevision.objects.count(),'open_clashes':ClashRecord.objects.exclude(status_code__in=['CLOSED','CANCELLED']).count(),'devices':IoTDevice.objects.count(),'open_alerts':SmartAlert.objects.exclude(status_code__in=['CLOSED','SUPPRESSED']).count(),'assets':HandoverAssetRecord.objects.count()})"
    if ($LASTEXITCODE -ne 0) { throw "Digital twin readiness query failed." }
    Write-Host "[SUCCESS] Phase 39 digital twin readiness verification completed." -ForegroundColor Green
} finally { Pop-Location }
