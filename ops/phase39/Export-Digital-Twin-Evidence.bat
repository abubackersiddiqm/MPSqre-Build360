@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export-Digital-Twin-Evidence.ps1" %*
exit /b %ERRORLEVEL%
