@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-Smoke-Test.ps1" %*
exit /b %ERRORLEVEL%
