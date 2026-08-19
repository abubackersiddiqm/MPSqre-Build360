@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Property-Lease-Readiness.ps1" -TargetProject %*
exit /b %ERRORLEVEL%
