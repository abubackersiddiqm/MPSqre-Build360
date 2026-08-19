@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Capital-Readiness.ps1" %*
exit /b %errorlevel%
