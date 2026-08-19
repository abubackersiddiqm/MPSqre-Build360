param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [Parameter(Mandatory=$true)][string]$ApiBaseUrl,
    [Parameter(Mandatory=$true)][string]$FrontendBaseUrl
)
$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath($ProjectRoot)
$smoke = Join-Path $root "infra\scripts\Test-Production-Smoke.ps1"
if (!(Test-Path $smoke)) { throw "Existing Build360 production smoke script is missing." }
& $smoke -ApiBaseUrl $ApiBaseUrl -FrontendBaseUrl $FrontendBaseUrl
exit $LASTEXITCODE
