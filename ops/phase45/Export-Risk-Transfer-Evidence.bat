@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export-Risk-Transfer-Evidence.ps1" %*
exit /b %errorlevel%
