@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export-Property-Lease-Evidence.ps1" -TargetProject "%~1" -CompanyCode "%~2"
exit /b %ERRORLEVEL%
