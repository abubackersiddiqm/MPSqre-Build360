param(
    [Parameter(Mandatory = $true)]
    [string]$TargetProject,
    [string]$CompanyCode = "MPSQRE",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$backend = Join-Path $target "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $target ("evidence\support\" + (Get-Date -Format "yyyyMMdd_HHmmss"))
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$output = Join-Path $OutputDirectory "support-evidence.json"

Push-Location $backend
try {
    $script = @"
import json
from modules.tenant.models import Company
from modules.supportops.application.selectors import support_overview
company = Company.objects.get(code='$CompanyCode')
print(json.dumps(support_overview(company), default=str, indent=2))
"@
    & $python manage.py shell -c $script | Out-File -LiteralPath $output -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Support evidence export failed." }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash.ToLowerInvariant()
    Set-Content -LiteralPath (Join-Path $OutputDirectory "SHA256.txt") -Value "$hash  support-evidence.json" -Encoding ascii
    Write-Host "[SUCCESS] Support evidence exported: $output" -ForegroundColor Green
} finally {
    Pop-Location
}
