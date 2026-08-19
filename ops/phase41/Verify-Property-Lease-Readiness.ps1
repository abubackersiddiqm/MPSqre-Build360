param([Parameter(Mandatory = $true)][string]$TargetProject)
$ErrorActionPreference = "Stop"
$backend = Join-Path ([System.IO.Path]::GetFullPath($TargetProject)) "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
Push-Location $backend
try {
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }
    & $python manage.py shell -c "from modules.leaseops.models import PropertyPolicyVersion, ManagedProperty, LeaseableUnit, LeaseAgreement, RentInvoice, TenantExperienceCase; print({'policies': PropertyPolicyVersion.objects.count(), 'properties': ManagedProperty.objects.count(), 'units': LeaseableUnit.objects.count(), 'leases': LeaseAgreement.objects.count(), 'invoices': RentInvoice.objects.count(), 'cases': TenantExperienceCase.objects.count()})"
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect Phase 41 records." }
    Write-Host "[SUCCESS] Phase 41 property and lease readiness verified." -ForegroundColor Green
} finally { Pop-Location }
