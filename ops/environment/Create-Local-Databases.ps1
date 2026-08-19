param(
  [string]$AdminUser = "postgres",
  [string]$AppUser = "build360",
  [Parameter(Mandatory=$true)][string]$AppPassword,
  [string]$HostName = "localhost",
  [int]$Port = 5432,
  [string]$AdminPassword = "",
  [switch]$IncludeProduction
)
$ErrorActionPreference = "Stop"
if (-not (Get-Command psql -ErrorAction SilentlyContinue)) { throw "psql was not found in PATH." }
if ($AdminPassword) { $env:PGPASSWORD = $AdminPassword }
$roleLiteral = $AppUser.Replace("'", "''")
$passwordLiteral = $AppPassword.Replace("'", "''")
$dbs = @("build360_development", "build360_testing", "build360_demo")
if ($IncludeProduction) { $dbs += "build360_production" }
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', '$roleLiteral', '$passwordLiteral') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$roleLiteral')\gexec")
$lines.Add("SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', '$roleLiteral', '$passwordLiteral')\gexec")
foreach ($db in $dbs) {
  $dbLiteral = $db.Replace("'", "''")
  $lines.Add("SELECT format('CREATE DATABASE %I OWNER %I', '$dbLiteral', '$roleLiteral') WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$dbLiteral')\gexec")
}
$sql = ($lines -join "`n") + "`n"
$temp = Join-Path $env:TEMP ("build360-db-init-" + [Guid]::NewGuid().ToString("N") + ".sql")
try {
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($temp, $sql, $utf8NoBom)
  & psql -v ON_ERROR_STOP=1 -h $HostName -p $Port -U $AdminUser -d postgres -f $temp
  if ($LASTEXITCODE -ne 0) { throw "PostgreSQL database initialization failed." }
  Write-Host "[SUCCESS] Separate Build360 databases are ready: $($dbs -join ', ')"
} finally {
  Remove-Item $temp -Force -ErrorAction SilentlyContinue
  if ($AdminPassword) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
}
