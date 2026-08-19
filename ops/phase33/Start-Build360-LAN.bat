@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Build360-LAN.ps1" %*
exit /b %ERRORLEVEL%
