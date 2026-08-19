@echo off
setlocal EnableExtensions
if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
set "PROJECT=%~1"
set "COMPANY_CODE=%~2"
set "BACKEND=%PROJECT%\backend"
if not exist "%BACKEND%\manage.py" (
  echo [ERROR] Invalid Build360 project root: "%PROJECT%"
  exit /b 2
)
if not exist "%BACKEND%\venv\Scripts\activate.bat" (
  echo [ERROR] Backend venv is missing: "%BACKEND%\venv"
  exit /b 2
)
pushd "%BACKEND%"
call venv\Scripts\activate.bat || goto :fail
python manage.py verify_crm_production_readiness --company-code "%COMPANY_CODE%"
if errorlevel 1 goto :fail
popd
echo.
echo [SUCCESS] CRM technical production-readiness gate passed for %COMPANY_CODE%.
echo [MANUAL] Complete CRM-UAT-CHECKLIST.md and create backup evidence before deployment approval.
exit /b 0
:fail
set "RC=%ERRORLEVEL%"
popd
echo [ERROR] CRM technical production-readiness gate failed.
exit /b %RC%
:usage
echo Usage:
echo   Verify-CRM-Production-Readiness.bat "D:\MPSqre\MPSqre_Build360" COMPANY_CODE
exit /b 1
