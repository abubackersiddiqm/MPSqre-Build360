param(
    [Parameter(Mandatory = $true)][string]$TargetProject,
    [string]$CompanyCode = "MPSQRE"
)
$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
Push-Location $backend
try {
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }
    & $python manage.py shell -c "from modules.tenant.models import Company; from modules.sustainabilityops.models import SustainabilityPolicyVersion, EmissionFactor; c=Company.objects.get(code='$CompanyCode'); print({'company': c.code, 'policy_versions': SustainabilityPolicyVersion.objects.filter(company=c).count(), 'active_factors': EmissionFactor.objects.filter(company=c, active=True).count()})"
    if ($LASTEXITCODE -ne 0) { throw "Sustainability readiness query failed." }
    Write-Host "[SUCCESS] Phase 38 sustainability readiness verification completed." -ForegroundColor Green
} finally { Pop-Location }
