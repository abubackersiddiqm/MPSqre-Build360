@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\production-r38\Validate-Production.ps1" -ProjectRoot "%~1"
exit /b %ERRORLEVEL%
