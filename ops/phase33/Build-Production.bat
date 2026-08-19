@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build-Production.ps1" %*
exit /b %ERRORLEVEL%
