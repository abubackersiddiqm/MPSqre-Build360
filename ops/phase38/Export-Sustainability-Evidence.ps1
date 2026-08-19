param(
    [Parameter(Mandatory = $true)][string]$TargetProject,
    [string]$CompanyCode = "MPSQRE"
)
$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$evidenceRoot = Join-Path $target "ops\phase38\evidence"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$output = Join-Path $evidenceRoot "sustainability_${CompanyCode}_$stamp.json"
Push-Location $backend
try {
    $command = "import json; from modules.tenant.models import Company; from modules.sustainabilityops.application.selectors import sustainability_overview; c=Company.objects.get(code='$CompanyCode'); print(json.dumps(sustainability_overview(c), default=str, indent=2))"
    & $python manage.py shell -c $command | Out-File -FilePath $output -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Sustainability evidence export failed." }
    $hash = (Get-FileHash -Algorithm SHA256 -Path $output).Hash.ToLowerInvariant()
    Write-Host "[SUCCESS] Sustainability evidence exported: $output" -ForegroundColor Green
    Write-Host "[SHA256] $hash"
} finally { Pop-Location }
