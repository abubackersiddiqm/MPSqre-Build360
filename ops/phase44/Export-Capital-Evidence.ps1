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
$outputRoot = Join-Path $target "evidence\phase44"
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$output = Join-Path $outputRoot ("capital_" + $CompanyCode + "_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
$script = "import json; from modules.tenant.models import Company; from modules.capitalops.application.selectors import capital_overview; c=Company.objects.get(code='$CompanyCode'); print(json.dumps(capital_overview(c), default=str, indent=2))"
Push-Location $backend
try {
    & $python manage.py shell -c $script | Out-File -FilePath $output -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Capital evidence export failed." }
} finally {
    Pop-Location
}
Write-Host "[SUCCESS] Capital evidence exported: $output" -ForegroundColor Green
