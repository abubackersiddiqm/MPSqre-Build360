@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export-Executive-Evidence.ps1" %*
