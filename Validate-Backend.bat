@echo off
setlocal
set "ROOT=%~1"
if not defined ROOT set "ROOT=%~dp0"
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

set "PYTHON=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [ERROR] backend\.venv runtime missing. Run Setup-Backend-Runtime.bat first.
  exit /b 2
)
if not exist "%ROOT%\backend\.env.testing" (
  echo [ERROR] backend\.env.testing missing.
  exit /b 3
)

cd /d "%ROOT%\backend"
set "BUILD360_ENVIRONMENT=testing"
set "APP_ENV=test"
set "APP_VERSION=1.0.0"
set "DJANGO_ENV_FILE=backend\.env.testing"

echo ============================================================
echo Build360 v1.0.0 Backend Production Gate
echo ============================================================

echo.
echo [1/6] Environment guard...
"%PYTHON%" manage.py build360_environment_status --require testing || exit /b 11

echo.
echo [2/6] Django system checks...
"%PYTHON%" manage.py check || exit /b 12

echo.
echo [3/6] Migration drift check...
"%PYTHON%" manage.py makemigrations --check --dry-run || exit /b 13

echo.
echo [4/6] Ruff...
"%PYTHON%" -m ruff check build360 modules || exit /b 14

echo.
echo [5/6] Mypy...
"%PYTHON%" -m mypy build360 modules || exit /b 15

echo.
echo [6/6] Pytest with governed testing DB reuse...
echo [INFO] build360_testing is a disposable automated-testing environment database.
echo [INFO] PostgreSQL CREATEDB is intentionally NOT granted to the Build360 app role.
"%PYTHON%" -m pytest --reuse-db || exit /b 16

echo.
echo [SUCCESS] Build360 v1.0.0 backend production gate passed.
exit /b 0
