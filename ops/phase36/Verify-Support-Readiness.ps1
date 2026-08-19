param(
    [Parameter(Mandatory = $true)]
    [string]$TargetProject
)

$ErrorActionPreference = "Stop"
$target = [System.IO.Path]::GetFullPath($TargetProject)
$required = @(
    "backend\modules\supportops\models.py",
    "backend\modules\supportops\api\urls.py",
    "frontend\src\app\platform\support-operations\page.tsx",
    "frontend\src\app\platform\support-operations\support-operations-client.tsx"
)
$failed = $false
foreach ($item in $required) {
    $path = Join-Path $target $item
    if (Test-Path $path -PathType Leaf) {
        Write-Host "[PASS] $item" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $item" -ForegroundColor Red
        $failed = $true
    }
}
if ($failed) { exit 1 }
Write-Host "[SUCCESS] Phase 36 source readiness verified." -ForegroundColor Green
