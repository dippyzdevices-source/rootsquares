# What it is:   The platform's daily billing job runner.
# What it does: Runs trial-run and event-pass-run one after the other (dry run unless -Apply) and logs every line to backend\logs\billing-daily.log.
# How to run:   powershell -NoProfile -ExecutionPolicy Bypass -File backend\scripts\billing-daily.ps1 [-Apply]; schedule it once a day.
# Read before:  docs/setup/22-stripe-billing.md section 6 and docs/setup/23-event-pass.md.
# Read after:   backend\logs\billing-daily.log (the result of each run); docs/setup/22-stripe-billing.md for troubleshooting.
#
# The two daily jobs of the platform, one after the other: trial-run (trial ends, lapsed payments go to sleep, the day-6 reminder) and event-pass-run
# (Event pass reminders, removal at day 90, purge only with EVENT_PASS_PURGE=true). DRY RUN unless -Apply is given: it then only prints what it would do.
# Schedule it once a day (docs/setup/22-stripe-billing.md section 6). Every line it prints is also written to backend\logs\billing-daily.log.
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File backend\scripts\billing-daily.ps1 [-Apply]
param([switch]$Apply)
$ErrorActionPreference = "Stop"
$backend = Split-Path $PSScriptRoot -Parent
Set-Location $backend
if (-not (Test-Path ".venv\Scripts\flask.exe")) { throw "No virtual environment in $backend (see docs/setup/01-local-machine.md)" }
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
$log = Join-Path $backend "logs\billing-daily.log"
function Say($text) { $line = "{0:u} {1}" -f (Get-Date), $text; Write-Host $line; Add-Content -Path $log -Value $line }
$flask = Join-Path $backend ".venv\Scripts\flask.exe"
foreach ($command in @("trial-run", "event-pass-run")) {
  $extra = @()
  if ($Apply) { $extra = @("--apply") }
  Say ("run: flask $command " + ($extra -join " "))
  $ErrorActionPreference = "Continue"  # a native program may write a warning to stderr; only its exit code decides
  $out = & $flask --app app.main:create_app $command @extra 2>&1
  $code = $LASTEXITCODE
  $ErrorActionPreference = "Stop"
  foreach ($row in $out) { Say ("  " + $row) }
  if ($code -ne 0) { Say "FAILED: $command exited with $code"; exit $code }
}
Say "done"
