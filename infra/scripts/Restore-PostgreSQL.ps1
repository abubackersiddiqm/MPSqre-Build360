[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DatabaseUrl,
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [switch]$ConfirmRestore
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not $ConfirmRestore) {
    throw "Restore is destructive. Re-run with -ConfirmRestore after validating the target."
}
if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) {
    throw "Backup file does not exist: $BackupFile"
}
if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) {
    throw "pg_restore is not available on PATH."
}
$started = Get-Date
& pg_restore --dbname=$DatabaseUrl --clean --if-exists --no-owner --no-acl $BackupFile
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed with exit code $LASTEXITCODE" }
$elapsed = [math]::Round(((Get-Date) - $started).TotalSeconds, 2)
Write-Host "Restore completed in $elapsed seconds." -ForegroundColor Green
