@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\production-r38\Build-Production.ps1" -ProjectRoot "%~1"
exit /b %ERRORLEVEL%
