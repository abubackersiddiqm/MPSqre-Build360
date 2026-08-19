@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Risk-Transfer-Readiness.ps1" %*
exit /b %errorlevel%
