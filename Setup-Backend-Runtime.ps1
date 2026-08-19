param(
  [Parameter(Mandatory=$false, Position=0)]
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Root)) {
  $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$Root = [System.IO.Path]::GetFullPath($Root)
$Backend = Join-Path $Root "backend"
$Requirements = Join-Path $Backend "requirements-dev.txt"
if (-not (Test-Path -LiteralPath $Requirements -PathType Leaf)) {
  $Requirements = Join-Path $Backend "requirements.txt"
}
if (-not (Test-Path -LiteralPath $Requirements -PathType Leaf)) {
  throw "Build360 requirements file not found under $Backend"
}

Write-Host "[INFO] Build360 v1.0.0 backend runtime bootstrap..."
Write-Host "[INFO] Required Python: >=3.14,<3.15"

$launcher = $null
$launcherArgs = @()

$py = Get-Command py.exe -ErrorAction SilentlyContinue
if ($py) {
  & $py.Source -3.14 -c "import sys; assert sys.version_info[:2] == (3,14); print(sys.version.split()[0])" *> $null
  if ($LASTEXITCODE -eq 0) {
    $launcher = $py.Source
    $launcherArgs = @("-3.14")
  }
}

if (-not $launcher) {
  $python = Get-Command python.exe -ErrorAction SilentlyContinue
  if ($python) {
    & $python.Source -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,14) else 1)" *> $null
    if ($LASTEXITCODE -eq 0) {
      $launcher = $python.Source
      $launcherArgs = @()
    }
  }
}

if (-not $launcher) {
  Write-Host "[ERROR] Python 3.14 was not found."
  Write-Host "[NEXT] Install Python 3.14 x64, then run this setup again."
  exit 2
}

$Venv = Join-Path $Backend ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
  Write-Host "[INFO] Creating isolated backend virtual environment: backend\.venv"
  & $launcher @launcherArgs -m venv $Venv
  if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed." }
} else {
  Write-Host "[OK] backend\.venv already exists."
}

Write-Host "[INFO] Upgrading pip inside backend\.venv..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }

Write-Host "[INFO] Installing Build360 backend dependencies from $(Split-Path -Leaf $Requirements)..."
& $VenvPython -m pip install -r $Requirements
if ($LASTEXITCODE -ne 0) { throw "Build360 backend dependency installation failed." }

Write-Host "[INFO] Verifying Python and Django runtime..."
& $VenvPython -c "import sys, django; assert sys.version_info[:2] == (3,14); print('Python', sys.version.split()[0]); print('Django', django.get_version())"
if ($LASTEXITCODE -ne 0) { throw "Backend runtime verification failed." }

Write-Host "[SUCCESS] Build360 backend runtime is ready at backend\.venv."
Write-Host "[NEXT] Run Check-Environment.bat demo"
