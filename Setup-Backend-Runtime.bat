@echo off
setlocal
set "ROOT=%~1"
if not defined ROOT set "ROOT=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-Backend-Runtime.ps1" "%ROOT%"
exit /b %ERRORLEVEL%
