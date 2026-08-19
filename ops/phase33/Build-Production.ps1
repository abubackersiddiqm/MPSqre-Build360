param([string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$ErrorActionPreference = "Stop"
$project = [System.IO.Path]::GetFullPath($ProjectRoot)
$backend = Join-Path $project "backend"
$frontend = Join-Path $project "frontend"
if (Test-Path (Join-Path $backend "venv\Scripts\activate.ps1")) { . (Join-Path $backend "venv\Scripts\activate.ps1") }
Push-Location $backend
python manage.py check --deploy
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
python manage.py collectstatic --noinput
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
Pop-Location
Push-Location $frontend
npm ci
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
npm run typecheck --if-present
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
npm run lint --if-present
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
npm run build
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { exit $code }
Write-Host "[SUCCESS] Build360 production build completed." -ForegroundColor Green
