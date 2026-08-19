param([Parameter(Mandatory = $true)][string]$TargetProject)
$ErrorActionPreference = "Stop"
$backend = Join-Path ([System.IO.Path]::GetFullPath($TargetProject)) "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
Push-Location $backend
try {
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }
    & $python manage.py shell -c "from modules.landops.models import LandPolicyVersion, LandParcel, OwnershipInterest, DueDiligenceCase, FeasibilityScenario, AcquisitionOpportunity, CommercialOffer, StatutoryApproval, LandRisk, AcquisitionEvent; print({'policies': LandPolicyVersion.objects.count(), 'parcels': LandParcel.objects.count(), 'owners': OwnershipInterest.objects.count(), 'diligence': DueDiligenceCase.objects.count(), 'feasibilities': FeasibilityScenario.objects.count(), 'opportunities': AcquisitionOpportunity.objects.count(), 'offers': CommercialOffer.objects.count(), 'approvals': StatutoryApproval.objects.count(), 'risks': LandRisk.objects.count(), 'events': AcquisitionEvent.objects.count()})"
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect Phase 43 records." }
    Write-Host "[SUCCESS] Phase 43 land acquisition readiness verified." -ForegroundColor Green
} finally { Pop-Location }
