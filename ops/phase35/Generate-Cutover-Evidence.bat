@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Generate-Cutover-Evidence.ps1" -TargetProject "%~1" -OutputPath "%~2"
exit /b %errorlevel%
