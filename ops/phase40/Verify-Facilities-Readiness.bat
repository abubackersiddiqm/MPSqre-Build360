@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Facilities-Readiness.ps1" %*
exit /b %ERRORLEVEL%
