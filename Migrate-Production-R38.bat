@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\production-r38\Migrate-Production.ps1" -ProjectRoot "%~1" -Confirmation "%~2"
exit /b %ERRORLEVEL%
