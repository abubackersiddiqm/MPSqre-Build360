@echo off
setlocal
if "%~1"=="" (echo Usage: Check-Environment.bat development^|testing^|demo^|production [project-root]& exit /b 2)
set "ENV=%~1"
set "ROOT=%~2"
if not defined ROOT set "ROOT=%~dp0"
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
if not exist "%ROOT%\backend\.env.%ENV%" (echo [ERROR] backend\.env.%ENV% missing.& exit /b 1)
set "PYTHON=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [ERROR] Build360 backend Python runtime is not installed.
  echo [NEXT] Run Setup-Backend-Runtime.bat "%ROOT%"
  exit /b 1
)
cd /d "%ROOT%\backend"
set "LEGACY_APP_ENV="
if /I "%ENV%"=="development" set "LEGACY_APP_ENV=local"
if /I "%ENV%"=="testing" set "LEGACY_APP_ENV=test"
if /I "%ENV%"=="demo" set "LEGACY_APP_ENV=demo"
if /I "%ENV%"=="production" set "LEGACY_APP_ENV=production"
if not defined LEGACY_APP_ENV (
  echo [ERROR] Unsupported environment "%ENV%".
  exit /b 2
)
set "BUILD360_ENVIRONMENT=%ENV%"
set "APP_ENV=%LEGACY_APP_ENV%"
set "APP_VERSION=1.0.0"
set "DJANGO_ENV_FILE=backend\.env.%ENV%"
"%PYTHON%" manage.py build360_environment_status --require %ENV%
