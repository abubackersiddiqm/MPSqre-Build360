@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export-Facilities-Evidence.ps1" %*
exit /b %ERRORLEVEL%
