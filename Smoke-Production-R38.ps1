param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot,
    [Parameter(Mandatory=$true)][string]$ApiBaseUrl,
    [Parameter(Mandatory=$true)][string]$FrontendBaseUrl
)
& (Join-Path $ProjectRoot "ops\production-r38\Smoke-Production.ps1") -ProjectRoot $ProjectRoot -ApiBaseUrl $ApiBaseUrl -FrontendBaseUrl $FrontendBaseUrl
exit $LASTEXITCODE
