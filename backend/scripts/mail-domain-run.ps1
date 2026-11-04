# What it is:   The platform's hourly job of the own sending domains (ADR 095).
# What it does: Runs mail-domain-run (dry run unless -Apply): asks Resend about every registered sending domain, keeps its status, e-mails the owner once when it is verified and once when it failed. Logs every line to backend\logs\mail-domain-run.log.
# How to run:   powershell -NoProfile -ExecutionPolicy Bypass -File backend\scripts\mail-domain-run.ps1 [-Apply]; schedule it every hour.
# Read before:  docs/setup/25-platform-email.md section 11.
# Read after:   backend\logs\mail-domain-run.log (the result of each run).
#
# Needs RESEND_DOMAINS_API_KEY in backend\.env.local (a full access Resend key). Without -Apply it only prints what it would do.
param([switch]$Apply)
$ErrorActionPreference = "Stop"
$backend = Split-Path $PSScriptRoot -Parent
Set-Location $backend
if (-not (Test-Path ".venv\Scripts\flask.exe")) { throw "No virtual environment in $backend (see docs/setup/01-local-machine.md)" }
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$log = Join-Path $backend "logs\mail-domain-run.log"
function Say($text) { $line = "{0:u} {1}" -f (Get-Date), $text; Write-Host $line; Add-Content -Path $log -Value $line }
$extra = @()
if ($Apply) { $extra = @("--apply") }
Say ("run: flask mail-domain-run " + ($extra -join " "))
$ErrorActionPreference = "Continue"  # a native program may write a warning to stderr; only its exit code decides
$out = & (Join-Path $backend ".venv\Scripts\flask.exe") --app app.main:create_app mail-domain-run @extra 2>&1
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
foreach ($row in $out) { Say ("  " + $row) }
if ($code -ne 0) { Say "FAILED: mail-domain-run exited with $code"; exit $code }
Say "done"
