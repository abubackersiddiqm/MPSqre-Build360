@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Digital-Twin-Readiness.ps1" %*
exit /b %ERRORLEVEL%
