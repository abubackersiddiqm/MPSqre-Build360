param([string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$ErrorActionPreference = "Stop"
$project = [System.IO.Path]::GetFullPath($ProjectRoot)
$backend = Join-Path $project "backend"
$frontend = Join-Path $project "frontend"
$failures = 0
function Check([string]$Name, [bool]$Passed, [string]$Detail) {
    if ($Passed) { Write-Host "[PASS] $Name - $Detail" -ForegroundColor Green }
    else { Write-Host "[FAIL] $Name - $Detail" -ForegroundColor Red; $script:failures += 1 }
}
Check "Backend" (Test-Path (Join-Path $backend "manage.py")) "Django project present"
Check "Frontend" (Test-Path (Join-Path $frontend "package.json")) "Next.js project present"
$required = @("SECRET_KEY", "ALLOWED_HOSTS", "DATABASE_URL", "CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS")
foreach ($name in $required) { Check "Environment $name" (-not [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name))) "Required production variable" }
$debug = [Environment]::GetEnvironmentVariable("DEBUG")
Check "DEBUG disabled" ($debug -notin @("1", "true", "True", "TRUE")) "Production must not expose debug output"
if (Test-Path (Join-Path $backend "venv\Scripts\activate.ps1")) { . (Join-Path $backend "venv\Scripts\activate.ps1") }
Push-Location $backend
python manage.py check --deploy
if ($LASTEXITCODE -ne 0) { $failures += 1 }
python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { $failures += 1 }
Pop-Location
if ($failures -gt 0) { Write-Host "[ERROR] Production environment has $failures blocking issue(s)." -ForegroundColor Red; exit 1 }
Write-Host "[SUCCESS] Production environment verification passed." -ForegroundColor Green
