param(
  [Parameter(Mandatory=$true)][string]$Root,
  [string]$DbUser = "build360",
  [Parameter(Mandatory=$true)][string]$DbPassword,
  [string]$DbHost = "localhost",
  [int]$DbPort = 5432,
  [switch]$IncludeProductionRehearsal,
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $Root).Path
$Backend = Join-Path $Root "backend"
if (-not (Test-Path (Join-Path $Backend "manage.py"))) { throw "Build360 backend not found: $Backend" }

function Get-SecureRandomBytes([int]$Bytes) {
  $b = New-Object byte[] $Bytes
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $rng.GetBytes($b)
  } finally {
    $rng.Dispose()
  }
  return $b
}
function New-RandomHex([int]$Bytes) {
  $b = Get-SecureRandomBytes $Bytes
  return -join ($b | ForEach-Object { $_.ToString("x2") })
}
function New-FernetKey {
  $b = Get-SecureRandomBytes 32
  return [Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_') + '='
}
function Write-Environment([string]$Name, [string]$Legacy, [string]$DbName, [bool]$LocalNoDocker, [string]$EmailBackend, [bool]$LocalAdapters) {
  $Path = Join-Path $Backend ".env.$Name"
  if ((Test-Path $Path) -and -not $Force) {
    Write-Host "[SKIP] $Path already exists. Use -Force to replace it."
    return
  }
  $DbPassEncoded = [Uri]::EscapeDataString($DbPassword)
  $Secret = New-RandomHex 48
  $Jwt = New-RandomHex 48
  $Blind = New-RandomHex 32
  $Fernet = New-FernetKey
  $Callback = New-RandomHex 24
  $local = if ($LocalNoDocker) { "true" } else { "false" }
  $adapter = if ($LocalAdapters) { "true" } else { "false" }
  $sslmode = if ($Name -eq "production") { "require" } else { "prefer" }
  $redis = if ($LocalNoDocker) { "" } else { "redis://localhost:6379/0" }
  $broker = if ($LocalNoDocker) { "" } else { "redis://localhost:6379/1" }
  $result = if ($LocalNoDocker) { "" } else { "redis://localhost:6379/2" }
  $content = @"
BUILD360_ENVIRONMENT=$Name
APP_ENV=$Legacy
APP_VERSION=1.0.0
LOCAL_NO_DOCKER=$local
BUILD360_DATABASE_NAME_GUARD=$DbName
DJANGO_SECRET_KEY=$Secret
JWT_SIGNING_KEY=$Jwt
JWT_ISSUER=mpsqre-build360
JWT_AUDIENCE=mpsqre-build360-api
JWT_ACCESS_TTL_SECONDS=900
JWT_REFRESH_TTL_SECONDS=2592000
JWT_STEP_UP_TTL_SECONDS=300
PASSWORD_RESET_TIMEOUT=3600
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DATABASE_URL=postgresql://${DbUser}:${DbPassEncoded}@${DbHost}:${DbPort}/${DbName}
DATABASE_SSLMODE=$sslmode
REDIS_URL=$redis
CELERY_BROKER_URL=$broker
CELERY_RESULT_BACKEND=$result
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_PUBLIC_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=build360-$Name
OBJECT_STORAGE_REGION=auto
FILE_UPLOAD_MAX_BYTES=26214400
FILE_UPLOAD_URL_TTL_SECONDS=900
FILE_DOWNLOAD_URL_TTL_SECONDS=300
CRM_PROTECTED_DATA_KEYS=$Fernet
CRM_BLIND_INDEX_KEY=$Blind
CRM_CONTACT_REVEAL_THROTTLE_RATE=30/minute
COMMUNICATION_CALLBACK_KEYS_JSON={"local":"$Callback"}
COMMUNICATION_LOCAL_ADAPTER_ENABLED=$adapter
BUILD360_PUBLIC_WEB_URL=http://localhost:3000
BUILD360_TRANSACTIONAL_FROM_EMAIL=notifications@mpsqre.com
BUILD360_SUPPORT_EMAIL=
DJANGO_EMAIL_BACKEND=$EmailBackend
EMAIL_HOST=localhost
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
AI_LOCAL_ADAPTER_ENABLED=$adapter
AI_MAX_PROMPT_CHARACTERS=8000
AI_EXTRACTION_MAX_CHARACTERS=50000
INTEGRATION_LOCAL_SIMULATION_ENABLED=$adapter
INTEGRATION_WEBHOOK_MAX_ATTEMPTS=5
ADMINOPS_DEFAULT_REGION=local
ADMINOPS_HEALTH_RETENTION_DAYS=90
ADMINOPS_RELEASE_CHECKS_REQUIRED=true
CONTROLPLANE_SUPPORT_MAX_HOURS=24
CONTROLPLANE_USAGE_RETENTION_DAYS=400
COMPLIANCE_EXCEPTION_MAX_DAYS=90
COMPLIANCE_ASSESSMENT_RETENTION_DAYS=2555
CLOUDOPS_DEPLOYMENT_EVIDENCE_REQUIRED=true
CLOUDOPS_BACKUP_RETENTION_MIN_DAYS=30
CLOUDOPS_SECRET_ROTATION_WARNING_DAYS=14
SUCCESSOPS_RENEWAL_WARNING_DAYS=90
SUCCESSOPS_SUPPORT_RETENTION_DAYS=1095
PEOPLEOPS_PAYROLL_RETENTION_DAYS=2555
PEOPLEOPS_LEAVE_YEAR_START_MONTH=1
BUILD360_PLATFORM_DOMAIN_SUFFIX=build360.local
BUILD360_CUSTOM_DOMAIN_CNAME_TARGET=domains.build360.local
"@
  if ($Name -eq "demo") { $content += "`nBUILD360_DEMO_ADMIN_PASSWORD=Build360Demo@2026`n" }
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $content, $utf8NoBom)
  Write-Host "[CREATED] $Path"
}

Write-Environment "development" "local" "build360_development" $true "django.core.mail.backends.console.EmailBackend" $true
Write-Environment "testing" "test" "build360_testing" $true "django.core.mail.backends.locmem.EmailBackend" $true
Write-Environment "demo" "demo" "build360_demo" $true "django.core.mail.backends.console.EmailBackend" $true
if ($IncludeProductionRehearsal) {
  Write-Warning "Creating a LOCAL production-rehearsal file. Replace all infrastructure values before a real deployment."
  Write-Environment "production" "production" "build360_production" $false "django.core.mail.backends.smtp.EmailBackend" $false
}
Write-Host "[SUCCESS] Build360 local environment files are ready. Real .env.* files are ignored by Git."
