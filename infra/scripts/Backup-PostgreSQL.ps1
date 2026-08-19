[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$DatabaseUrl,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$Label = "manual"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) {
    throw "pg_dump is not available on PATH."
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$file = Join-Path $OutputDirectory "build360-$Label-$timestamp.backup"
& pg_dump --dbname=$DatabaseUrl --format=custom --no-owner --no-acl --file=$file
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed with exit code $LASTEXITCODE" }
$hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
$evidence = [pscustomobject]@{
    file = $file
    sha256 = $hash
    size_bytes = (Get-Item -LiteralPath $file).Length
    created_at = (Get-Date).ToUniversalTime().ToString("o")
}
$evidence | ConvertTo-Json | Set-Content -LiteralPath "$file.evidence.json" -Encoding UTF8
Write-Host "Backup completed: $file" -ForegroundColor Green
Write-Host "SHA-256: $hash"
