param([string]$TargetProject = "D:\MPSqre\MPSqre_Build360")
$ErrorActionPreference = "Stop"
$backend = Join-Path ([System.IO.Path]::GetFullPath($TargetProject)) "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
Push-Location $backend
try {
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }
    & $python manage.py shell -c "from modules.facilityops.models import FacilityPolicyVersion, Facility, OperationalAsset, FacilityWorkOrder, ServiceRequest; print({'policies': FacilityPolicyVersion.objects.count(), 'facilities': Facility.objects.count(), 'assets': OperationalAsset.objects.count(), 'work_orders': FacilityWorkOrder.objects.count(), 'service_requests': ServiceRequest.objects.count()})"
    if ($LASTEXITCODE -ne 0) { throw "Facilities readiness query failed." }
    Write-Host "[SUCCESS] Facilities readiness verification completed." -ForegroundColor Green
} finally { Pop-Location }
