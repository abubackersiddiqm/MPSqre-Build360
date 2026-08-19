param(
    [Parameter(Mandatory = $true)][string]$TargetProject,
    [Parameter(Mandatory = $true)][string]$CompanyCode,
    [string]$OutputDirectory = ""
)
$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $target "evidence\phase40" }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$output = Join-Path $OutputDirectory ("facilities_evidence_{0}_{1}.json" -f $CompanyCode, (Get-Date -Format "yyyyMMdd_HHmmss"))
Push-Location $backend
try {
    $script = "import json; from modules.tenant.models import Company; from modules.facilityops.application.selectors import facility_overview; c=Company.objects.get(code='$CompanyCode'); print(json.dumps(facility_overview(c), default=str))"
    & $python manage.py shell -c $script | Out-File -FilePath $output -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Facilities evidence export failed." }
    Write-Host "[SUCCESS] Facilities evidence exported: $output" -ForegroundColor Green
} finally { Pop-Location }
