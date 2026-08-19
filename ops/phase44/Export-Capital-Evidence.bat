@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export-Capital-Evidence.ps1" %*
exit /b %errorlevel%
