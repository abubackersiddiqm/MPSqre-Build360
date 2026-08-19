param(
    [Parameter(Mandatory = $true)][string]$TargetProject,
    [Parameter(Mandatory = $true)][string]$CompanyCode,
    [string]$OutputFolder = ""
)
$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
if (-not $OutputFolder) { $OutputFolder = Join-Path $target "evidence\phase37" }
New-Item -ItemType Directory -Path $OutputFolder -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$output = Join-Path $OutputFolder "executive_intelligence_${CompanyCode}_$stamp.json"
Push-Location $backend
try {
    $script = "import json; from modules.tenant.models import Company; from modules.insightops.application.selectors import insight_overview; c=Company.objects.get(code='$CompanyCode'); print(json.dumps(insight_overview(c), default=str, indent=2))"
    & $python manage.py shell -c $script | Set-Content -Path $output -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw "Executive evidence export failed." }
    Write-Host "[SUCCESS] Executive evidence exported: $output" -ForegroundColor Green
} finally { Pop-Location }
