param(
    [Parameter(Mandatory = $true)]
    [string]$TargetProject,
    [Parameter(Mandatory = $true)]
    [string]$CompanyCode
)

$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
$outputRoot = Join-Path $target "evidence\phase45"
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$output = Join-Path $outputRoot ("risk_transfer_" + $CompanyCode + "_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
$script = "import json; from modules.tenant.models import Company; from modules.risktransferops.application.selectors import risk_transfer_overview; c=Company.objects.get(code='$CompanyCode'); print(json.dumps(risk_transfer_overview(c), default=str, indent=2))"
Push-Location $backend
try {
    & $python manage.py shell -c $script | Out-File -FilePath $output -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Risk-transfer evidence export failed." }
} finally {
    Pop-Location
}
Write-Host "[SUCCESS] Risk-transfer evidence exported: $output" -ForegroundColor Green
