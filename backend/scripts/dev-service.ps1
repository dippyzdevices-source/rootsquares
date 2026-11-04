# What it is:   Starts ONE of the two platform services in development, connected as its own database role (ADR 084, guide 36).
# What it does: Reads the host, port, database and project reference from DATABASE_URL in .env.local (the owner's address; nothing is printed or changed), asks you for the
#               password of the service's role (typed hidden, never saved, never printed), sets API_SURFACE and DATABASE_URL for this window only, and serves the API.
#               customer = the customer API as role customer_app (port 5001); admin = the staff API as role admin_app (port 5011). Close the window and nothing is left behind.
# How to run:   powershell -NoProfile -ExecutionPolicy Bypass -File backend\scripts\dev-service.ps1 -Surface customer      (window A, after stopping dev.ps1)
#               powershell -NoProfile -ExecutionPolicy Bypass -File backend\scripts\dev-service.ps1 -Surface admin         (window B)
#               Optional: -Port 5011 to choose another port. The admin application then needs VITE_ADMIN_API_BASE_URL=http://localhost:<port> (guide 36 section 5).
# Read before:  docs/setup/36-database-roles.md sections 1 to 4 (the roles must exist and `db_roles_check.py` must say all rights are as expected).
# Read after:   docs/setup/36-database-roles.md section 5 (what to try and what to expect).
#
# This is NOT how the application is started every day: dev.ps1 does that, as the database owner, with API_SURFACE=all. This script only rehearses production.
param(
  [Parameter(Mandatory = $true)][ValidateSet("customer", "admin")][string]$Surface,
  [int]$Port = 0
)
$ErrorActionPreference = "Stop"
$backend = Split-Path $PSScriptRoot -Parent
Set-Location $backend
if (-not (Test-Path ".env.local")) { throw "No .env.local in backend (copy .env.example to .env.local, guide 01)." }
if (-not (Test-Path ".venv\Scripts\flask.exe")) { throw "No virtual environment in backend (guide 01)." }
if ($Port -eq 0) { $Port = if ($Surface -eq "customer") { 5001 } else { 5011 } }
$role = if ($Surface -eq "customer") { "customer_app" } else { "admin_app" }

# Where the platform database is: the owner's DATABASE_URL, taken apart without printing the password.
$line = Select-String -Path ".env.local" -Pattern '^DATABASE_URL=(.*)$' | Select-Object -First 1
if (-not $line) { throw "DATABASE_URL is not set in backend\.env.local." }
$url = $line.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
if ($url -notmatch '^[a-z+]+://([^:]+):([^@]*)@([^:/]+):(\d+)/([^?]+)(\?.*)?$') { throw "DATABASE_URL in backend\.env.local does not look like user:password@host:port/database." }
$ownerUser = $Matches[1]; $dbHost = $Matches[3]; $dbPort = $Matches[4]; $dbName = $Matches[5]
$query = if ($Matches[6]) { $Matches[6] } else { "" }
# Through Supabase's pooler a login is role.project-ref (the owner is postgres.<ref>); a direct or local connection has no suffix.
$suffix = if ($ownerUser.Contains(".")) { "." + $ownerUser.Split(".")[1] } else { "" }

$secure = Read-Host "Password of $role (typed hidden, not saved)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
if (-not $plain) { throw "No password typed." }

$env:API_SURFACE = $Surface
$env:DATABASE_URL = "postgresql+psycopg://$role${suffix}:" + [System.Net.WebUtility]::UrlEncode($plain) + "@${dbHost}:${dbPort}/${dbName}$query"
Write-Host "Starting the $Surface service as $role$suffix on ${dbHost}:${dbPort}/${dbName}, port $Port (Ctrl+C stops it; this window only)."
& ".venv\Scripts\flask.exe" --app app.main:create_app run --port $Port
