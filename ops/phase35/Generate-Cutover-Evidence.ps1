param(
    [Parameter(Mandatory = $true)]
    [string]$TargetProject,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $target ("ops\evidence\phase35-cutover-" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
}
$output = [System.IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Path (Split-Path -Parent $output) -Force | Out-Null

function File-HashOrEmpty([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return ""
}

$gitCommit = ""
if (Test-Path (Join-Path $target ".git") -PathType Container) {
    Push-Location $target
    try { $gitCommit = (git rev-parse HEAD 2>$null | Out-String).Trim() } finally { Pop-Location }
}

$evidence = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    target_project = $target
    machine = $env:COMPUTERNAME
    user = $env:USERNAME
    git_commit = $gitCommit
    backend_settings_sha256 = File-HashOrEmpty (Join-Path $target "backend\build360\settings.py")
    backend_urls_sha256 = File-HashOrEmpty (Join-Path $target "backend\build360\urls.py")
    frontend_package_lock_sha256 = File-HashOrEmpty (Join-Path $target "frontend\package-lock.json")
    environment = $env:BUILD360_GO_LIVE_ENVIRONMENT
    window_start = $env:BUILD360_GO_LIVE_WINDOW_START
    window_end = $env:BUILD360_GO_LIVE_WINDOW_END
}
[System.IO.File]::WriteAllText($output, ($evidence | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))
Write-Host "[SUCCESS] Cutover evidence generated." -ForegroundColor Green
Write-Host $output
