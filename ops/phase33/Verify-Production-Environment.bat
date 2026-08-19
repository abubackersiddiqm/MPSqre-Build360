@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Production-Environment.ps1" %*
exit /b %ERRORLEVEL%
