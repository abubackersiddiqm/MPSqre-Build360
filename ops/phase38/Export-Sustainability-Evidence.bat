@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export-Sustainability-Evidence.ps1" %*
exit /b %ERRORLEVEL%
