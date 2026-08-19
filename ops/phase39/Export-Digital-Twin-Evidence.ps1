param(
    [string]$TargetProject = "D:\MPSqre\MPSqre_Build360",
    [string]$CompanyCode = "MPSQRE"
)
$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
$evidenceRoot = Join-Path $target ("evidence\phase39_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
$out = Join-Path $evidenceRoot "digital-twin-summary.json"
Push-Location $backend
try {
    $command = "import json; from modules.tenant.models import Company; from modules.digitaltwinops.application.selectors import digital_twin_overview; c=Company.objects.get(code='$CompanyCode'); print(json.dumps(digital_twin_overview(c), default=str, indent=2))"
    & $python manage.py shell -c $command | Out-File -FilePath $out -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Digital twin evidence export failed." }
    $hash = (Get-FileHash -Algorithm SHA256 $out).Hash.ToLowerInvariant()
    Set-Content -Path (Join-Path $evidenceRoot "SHA256.txt") -Value "$hash  digital-twin-summary.json" -Encoding ASCII
    Write-Host "[SUCCESS] Phase 39 evidence exported: $evidenceRoot" -ForegroundColor Green
} finally { Pop-Location }
