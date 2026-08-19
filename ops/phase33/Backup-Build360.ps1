param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$OutputRoot = ""
)
$ErrorActionPreference = "Stop"
$project = [System.IO.Path]::GetFullPath($ProjectRoot)
$backend = Join-Path $project "backend"
if (-not $OutputRoot) { $OutputRoot = Join-Path $project "_release_backups" }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$destination = Join-Path $OutputRoot "build360_$stamp"
New-Item -ItemType Directory -Path $destination -Force | Out-Null
if (Test-Path (Join-Path $backend "venv\Scripts\activate.ps1")) { . (Join-Path $backend "venv\Scripts\activate.ps1") }
Push-Location $backend
python manage.py dumpdata --natural-foreign --natural-primary --exclude contenttypes --exclude auth.permission --indent 2 --output (Join-Path $destination "database.json")
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Database export failed." }
Pop-Location
$sourceArchive = Join-Path $destination "source.zip"
Compress-Archive -Path (Join-Path $project "backend"), (Join-Path $project "frontend"), (Join-Path $project "ops") -DestinationPath $sourceArchive -CompressionLevel Optimal
Get-ChildItem $destination -File | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $($_.Path | Split-Path -Leaf)" } | Set-Content -Encoding ascii (Join-Path $destination "SHA256SUMS.txt")
Write-Host "[SUCCESS] Backup evidence created: $destination" -ForegroundColor Green
Write-Host "Register this reference in /platform/release-readiness after performing a restore drill."
