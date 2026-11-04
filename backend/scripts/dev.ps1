# What it is:   The one command that starts the platform backend in development.
# What it does: Checks the database, runs the Alembic migrations, seeds the platform admin and serves the API on http://localhost:5001.
# How to run:   powershell -NoProfile -ExecutionPolicy Bypass -File backend\scripts\dev.ps1 (restart it after any change of .env.local or code).
# Read before:  docs/setup/01-local-machine.md and docs/setup/13-environment-variables.md.
# Read after:   docs/setup/18-commands.md (start the frontend and the square app).
#
# One command for the backend in development: checks the platform database is reachable (only when it is the local Postgres service on 5432), creates
# the database migrations (Alembic; a database made by the old init-db is adopted once), seeds the first staff account from .env.local (skipped with a message when SEED_ADMIN_* is empty), and runs the API on
# http://localhost:5001. Restart it after any change of .env.local or of the code (it does not reload by itself).
# First time only: python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt ; copy .env.example .env.local
# Usage (from anywhere):  powershell -NoProfile -ExecutionPolicy Bypass -File C:\diPpY_devLocal\Digital\Master_RootSquares\rootsquares\backend\scripts\dev.ps1
$ErrorActionPreference = "Stop"
$backend = Split-Path $PSScriptRoot -Parent
Set-Location $backend
if (-not (Test-Path ".env.local")) { throw "No .env.local in backend. Copy .env.example to .env.local and fill it in (the top of .env.example says how; guide 01)." }
if (-not (Test-Path ".venv\Scripts\flask.exe")) { throw "No virtual environment. Run: python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt" }

# Host of DATABASE_URL (never printed with its password)
$dbLine = Select-String -Path ".env.local" -Pattern '^DATABASE_URL=(.*)$' | Select-Object -First 1
$dbHost = ""
if ($dbLine -and ($dbLine.Matches[0].Groups[1].Value -match '@([^:/@?]+)')) { $dbHost = $Matches[1] }
if ($dbHost -in @("127.0.0.1", "localhost")) {
  $pgbin = if ($env:PG_BIN) { $env:PG_BIN } else { "C:\Program Files\PostgreSQL\18\bin" }
  & "$pgbin\pg_isready.exe" -h 127.0.0.1 -p 5432 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "DATABASE_URL points at the local Postgres but nothing answers on 127.0.0.1:5432. Start the PostgreSQL service." }
} else {
  Write-Host "Platform database is hosted ($dbHost): local Postgres check skipped"
}

& ".venv\Scripts\flask.exe" --app app.main:create_app db upgrade
$seed = Select-String -Path ".env.local" -Pattern '^SEED_ADMIN_EMAIL=(\S+)' | Select-Object -First 1
if ($seed) { & ".venv\Scripts\flask.exe" --app app.main:create_app seed-staff } else { Write-Host "SEED_ADMIN_EMAIL is empty: no staff account seeded (create one with: flask staff-create <email>)" }
Write-Host "API on http://localhost:5001  (docs: http://localhost:5001/apidoc/swagger/)  admin: see SEED_ADMIN_EMAIL in .env.local"
& ".venv\Scripts\flask.exe" --app app.main:create_app run --port 5001
