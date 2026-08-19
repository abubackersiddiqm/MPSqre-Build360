@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Sustainability-Readiness.ps1" %*
exit /b %ERRORLEVEL%
