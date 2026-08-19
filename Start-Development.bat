@echo off
setlocal
set "ROOT=%~1"
if not defined ROOT set "ROOT=%~dp0"
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
if not exist "%ROOT%\backend\.env.development" (echo [ERROR] backend\.env.development missing. Run Configure-Local-Environments.ps1 first.& exit /b 1)
set "PYTHON=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [ERROR] Build360 backend Python runtime is not installed.
  echo [NEXT] Run Setup-Backend-Runtime.bat "%ROOT%"
  exit /b 1
)
start "Build360 DEV Backend" cmd /k "cd /d ""%ROOT%\backend"" && set BUILD360_ENVIRONMENT=development && set APP_ENV=local && set APP_VERSION=1.0.0 && set DJANGO_ENV_FILE=backend\.env.development && ""%PYTHON%"" manage.py runserver 127.0.0.1:8000"
start "Build360 DEV Frontend" cmd /k "cd /d ""%ROOT%\frontend"" && set BUILD360_ENVIRONMENT=development && set APP_ENV=local && set APP_VERSION=1.0.0 && npm run dev"
echo [SUCCESS] DEVELOPMENT v1.0.0 started.
