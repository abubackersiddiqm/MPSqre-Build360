@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Development-Sales-Readiness.ps1" -TargetProject %*
exit /b %ERRORLEVEL%
