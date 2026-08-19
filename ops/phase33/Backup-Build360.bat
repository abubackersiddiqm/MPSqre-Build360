@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Backup-Build360.ps1" %*
exit /b %ERRORLEVEL%
