@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Land-Acquisition-Readiness.ps1" -TargetProject %*
exit /b %ERRORLEVEL%
