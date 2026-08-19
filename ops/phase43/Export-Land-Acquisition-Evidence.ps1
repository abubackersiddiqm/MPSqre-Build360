param(
    [Parameter(Mandatory = $true)][string]$TargetProject,
    [Parameter(Mandatory = $true)][string]$CompanyCode
)
$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
$output = Join-Path $target "evidence\phase43"
New-Item -ItemType Directory -Path $output -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$file = Join-Path $output "land_acquisition_${CompanyCode}_$stamp.json"
$script = @"
import json
from pathlib import Path
from modules.tenant.models import Company
from modules.landops.application.selectors import land_acquisition_overview
company = Company.objects.get(code='$CompanyCode')
Path(r'$file').write_text(json.dumps(land_acquisition_overview(company), default=str, indent=2), encoding='utf-8')
print(r'$file')
"@
Push-Location $backend
try {
    & $python manage.py shell -c $script
    if ($LASTEXITCODE -ne 0) { throw "Phase 43 evidence export failed." }
    Write-Host "[SUCCESS] Land acquisition evidence exported: $file" -ForegroundColor Green
} finally { Pop-Location }
