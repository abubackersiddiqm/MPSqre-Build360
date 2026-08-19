@echo off
setlocal EnableExtensions
if "%~1"=="" goto :usage
set "PROJECT=%~1"
if not exist "%PROJECT%\ops\phase33\Backup-Build360.bat" (
  echo [ERROR] Build360 backup script is missing under ops\phase33.
  exit /b 2
)
call "%PROJECT%\ops\phase33\Backup-Build360.bat" -ProjectRoot "%PROJECT%"
exit /b %ERRORLEVEL%
:usage
echo Usage:
echo   Create-CRM-PreDeploy-Backup.bat "D:\MPSqre\MPSqre_Build360"
exit /b 1
