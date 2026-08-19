@echo off
setlocal
set "ROOT=%~dp0..\.."
cd /d "%ROOT%\backend"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" manage.py prune_stability_telemetry %*
) else (
  python manage.py prune_stability_telemetry %*
)
exit /b %errorlevel%
