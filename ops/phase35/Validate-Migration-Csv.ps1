param(
    [Parameter(Mandatory = $true)]
    [string]$CsvPath,
    [string]$RequiredHeaders = ""
)

$ErrorActionPreference = "Stop"
$path = [System.IO.Path]::GetFullPath($CsvPath)
if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    Write-Host "[ERROR] CSV file not found: $path" -ForegroundColor Red
    exit 1
}

try {
    $rows = @(Import-Csv -LiteralPath $path)
    $headerLine = Get-Content -LiteralPath $path -TotalCount 1
    $headers = @()
    if ($headerLine) { $headers = @($headerLine -split ',' | ForEach-Object { $_.Trim().Trim('"') }) }
    $required = @()
    if (-not [string]::IsNullOrWhiteSpace($RequiredHeaders)) {
        $required = @($RequiredHeaders -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
    $missing = @($required | Where-Object { $_ -notin $headers })
    if ($missing.Count -gt 0) {
        throw "Required headers are missing: $($missing -join ', ')"
    }
    $duplicateHeaders = @($headers | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name })
    if ($duplicateHeaders.Count -gt 0) {
        throw "Duplicate CSV headers detected: $($duplicateHeaders -join ', ')"
    }
    $emptyRows = 0
    foreach ($row in $rows) {
        $values = @($row.PSObject.Properties.Value | ForEach-Object { [string]$_ })
        if (($values | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count -eq 0) { $emptyRows += 1 }
    }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "[SUCCESS] CSV structure validated." -ForegroundColor Green
    Write-Host "Path: $path"
    Write-Host "Rows: $($rows.Count)"
    Write-Host "Headers: $($headers -join ', ')"
    Write-Host "Empty rows: $emptyRows"
    Write-Host "SHA-256: $hash"
} catch {
    Write-Host "[ERROR] CSV validation failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
