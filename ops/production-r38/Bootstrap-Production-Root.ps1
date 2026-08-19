param(
    [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath($ProjectRoot)
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
$script = Join-Path $root "ops\production-r38\bootstrap_root_operator.py"
if (!(Test-Path $python)) { throw "Backend runtime missing." }
if (!(Test-Path $script)) { throw "R38 ROOT_OPERATOR bootstrap script missing." }
& $python $script $root
exit $LASTEXITCODE
