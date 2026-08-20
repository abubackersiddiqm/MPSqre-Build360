@echo off
setlocal
set "ROOT=%~1"
if not defined ROOT set "ROOT=%~dp0"
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
if not exist "%ROOT%\backend\.env.demo" (echo [ERROR] backend\.env.demo missing.& exit /b 1)
set "PYTHON=%ROOT%\backend\venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [ERROR] Build360 backend Python runtime is not installed.
  echo [NEXT] Run Setup-Backend-Runtime.bat "%ROOT%"
  exit /b 1
)
cd /d "%ROOT%\backend"
set "BUILD360_ENVIRONMENT=demo"
set "APP_ENV=demo"
set "APP_VERSION=1.0.0"
set "DJANGO_ENV_FILE=backend\.env.demo"
"%PYTHON%" manage.py build360_environment_status --require demo || exit /b 1
"%PYTHON%" manage.py migrate || exit /b 1
"%PYTHON%" manage.py seed_build360_demo || exit /b 1
"%PYTHON%" manage.py seed_crm_automation_demo || exit /b 1
echo [SUCCESS] Demo data is ready.
