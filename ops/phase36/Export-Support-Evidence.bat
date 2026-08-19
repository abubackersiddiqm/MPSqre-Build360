@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export-Support-Evidence.ps1" %*
