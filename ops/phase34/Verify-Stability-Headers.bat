@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Stability-Headers.ps1" %*
exit /b %errorlevel%
