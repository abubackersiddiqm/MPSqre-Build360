param(
    [Parameter(Mandatory = $true)][string]$TargetProject,
    [Parameter(Mandatory = $true)][string]$CompanyCode
)
$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
$output = Join-Path $target "evidence\phase41"
New-Item -ItemType Directory -Path $output -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$file = Join-Path $output "property_lease_${CompanyCode}_$stamp.json"
$script = @"
import json
from pathlib import Path
from modules.tenant.models import Company
from modules.leaseops.application.selectors import property_lease_overview
company = Company.objects.get(code='$CompanyCode')
Path(r'$file').write_text(json.dumps(property_lease_overview(company), default=str, indent=2), encoding='utf-8')
print(r'$file')
"@
Push-Location $backend
try {
    & $python manage.py shell -c $script
    if ($LASTEXITCODE -ne 0) { throw "Phase 41 evidence export failed." }
    Write-Host "[SUCCESS] Property and lease evidence exported: $file" -ForegroundColor Green
} finally { Pop-Location }
