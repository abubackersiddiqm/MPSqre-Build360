@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Benchmark-Core-Routes.ps1" %*
exit /b %errorlevel%
