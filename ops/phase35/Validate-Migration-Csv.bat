@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Validate-Migration-Csv.ps1" -CsvPath "%~1" -RequiredHeaders "%~2"
exit /b %errorlevel%
