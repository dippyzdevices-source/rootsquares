# ruff: noqa: E501
r"""What it is:   A read-only review of backend/.env.staging (or another backend env file) and of the connections it names.
What it does: Checks the file's form (duplicates, typos, <placeholders>, stray comments), the staging rules (ENV=local, https addresses, secret lengths, Fernet keys valid,
              secrets that must differ, nothing copied from .env.local), whether the backend's Settings accept it as the customer and as the admin service, and then makes
              READ-ONLY connections: the database (role, migration version), the sign-in project (key set), the storage buckets, the public storage address, the Neon API.
              Nothing is created or changed. It never prints a secret: only names, lengths, yes/no and the non-secret addresses.
How to run:   From backend\ (PowerShell):   .venv\Scripts\python.exe -I scripts\env_review.py [.env.staging]
              Exit code is not used; read the SUMMARY line (ok / warnings / failed). Run it again after every fix. It is made for staging files: on .env.local the staging rules
              (https addresses, secrets that must be set) show as failures, which is expected.
Read before:  backend/.env.example and docs/setup/41-deploy-to-render-staging.md.
Read after:   docs/setup/41-deploy-to-render-staging.md, the step you are on."""
import base64
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402
from dotenv import dotenv_values  # noqa: E402

from app.shared.config import Settings  # noqa: E402

SECRET_NAMES = {
    "DATABASE_URL", "JWT_SECRET", "STAFF_JWT_SECRET", "STAFF_FERNET_KEY", "FERNET_KEY", "SUPPORT_SESSION_KEY", "SQUARE_INTERNAL_KEY", "SITE_GATE_PASSWORD",
    "STORAGE_S3_ACCESS_KEY", "STORAGE_S3_SECRET_KEY", "NEON_API_KEY", "AUTH_ADMIN_KEY", "RESEND_API_KEY", "RESEND_DOMAINS_API_KEY", "RENDER_API_KEY",
    "GOOGLE_OAUTH_CLIENT_SECRET", "SUPABASE_ACCESS_TOKEN", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "SEED_ADMIN_PASSWORD",
}
SHOW = {
    "ENV", "ENV_LABEL", "API_SURFACE", "COOKIE_SECURE", "PROXY_HOPS", "CORS_ORIGINS", "ADMIN_ORIGINS", "PLATFORM_FRONTEND_URL", "SQUARE_SERVER_URL",
    "SQUARE_DOMAIN_SUFFIX", "PROVISIONER", "NEON_REGION", "AUTH_PROVIDER", "STORAGE_S3_REGION", "STORAGE_PUBLIC_BUCKET", "STORAGE_PRIVATE_BUCKET",
    "BILLING_PROVIDER", "EMAIL_PROVIDER", "STAFF_NOTICE_EMAIL", "LOG_LEVEL", "CUSTOM_DOMAIN_TARGET", "RENDER_SITE_SERVICE_ID",
}

NAME = sys.argv[1] if len(sys.argv) > 1 else ".env.staging"
path = BACKEND / NAME
VS_LOCAL = NAME != ".env.local"  # the comparisons with the local file mean nothing when the local file itself is reviewed
raw = path.read_text(encoding="utf-8")
vals = {k: (v if v is not None else "") for k, v in dotenv_values(path).items()}
local = {k: (v or "") for k, v in dotenv_values(BACKEND / ".env.local").items()}
secrets_seen = {v for k, v in vals.items() if k in SECRET_NAMES and len(v) >= 8}
counts = {"OK": 0, "WARN": 0, "FAIL": 0}


def red(text: str) -> str:
    for s in secrets_seen:
        text = text.replace(s, "***")
    return text


def say(level: str, msg: str) -> None:
    counts[level] += 1
    print(f"{level:4} {red(msg)}")


def has(name: str) -> bool:
    return bool(vals.get(name, "").strip())


print(f"Reviewing backend/{NAME} (read-only)\n\n=== 1. the file itself ===")
lines = [ln for ln in raw.splitlines() if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", ln)]
names = [ln.split("=", 1)[0] for ln in lines]
dups = sorted({n for n in names if names.count(n) > 1})
say("FAIL" if dups else "OK", f"duplicate names: {dups}" if dups else f"{len(names)} setting lines, no name twice")
known = set(Settings.model_fields)
unknown = sorted(n for n in set(names) if n not in known)
say("WARN" if unknown else "OK", f"names the backend does not know (typo?): {unknown}" if unknown else "every name is a setting the backend reads")
inline = [ln.split("=", 1)[0] for ln in lines if re.search(r"\s#", ln.split("=", 1)[1])]
say("FAIL" if inline else "OK", f"a comment after the value on: {inline} (it would become part of the value)" if inline else "no comment after a value")
spaces = [n for n in names if vals.get(n, "") != vals.get(n, "").strip() or re.match(r"^[A-Za-z_0-9]+\s+=", next(ln for ln in lines if ln.startswith(n + "=")))]
say("WARN" if spaces else "OK", f"spaces around a value or the = on: {spaces}" if spaces else "no stray spaces")
quoted = [n for n in names if re.match(r"^[A-Za-z_0-9]+=[\"']", next(ln for ln in lines if ln.startswith(n + "=")))]
say("WARN" if quoted else "OK", f"quoted values (usually not needed): {quoted}" if quoted else "no quoted values")
placeholders = sorted(n for n, v in vals.items() if re.search(r"<[^>]*>", v))
say("FAIL" if placeholders else "OK", f"still a <placeholder> in: {placeholders}" if placeholders else "no <placeholder> left")
empty = sorted(n for n in names if not has(n))
say("WARN" if empty else "OK", f"set but empty: {empty}" if empty else "no empty line")

print("\n=== 2. what the file sets (non-secret values shown, secrets only as yes/length) ===")
for n in sorted(set(names)):
    if n in SHOW:
        print(f"     {n} = {vals.get(n, '')}")
    elif n in SECRET_NAMES:
        print(f"     {n} = <secret, {len(vals.get(n, ''))} characters>")
    else:
        print(f"     {n} = <not shown>")

print("\n=== 3. rules for a staging copy (ENV=local, see guide 41) ===")
say("OK" if vals.get("ENV") == "local" else "FAIL", f"ENV is {vals.get('ENV')!r} (staging must be local)")
say("OK" if vals.get("ENV_LABEL") == "Staging" else "WARN", f"ENV_LABEL is {vals.get('ENV_LABEL')!r} (expected Staging)")
say("OK" if vals.get("COOKIE_SECURE", "").lower() == "true" else "FAIL", f"COOKIE_SECURE is {vals.get('COOKIE_SECURE')!r} (expected true on Render)")
say("OK" if vals.get("PROXY_HOPS") == "1" else "FAIL", f"PROXY_HOPS is {vals.get('PROXY_HOPS')!r} (expected 1 on Render)")
say("OK" if "STAFF_SECOND_STEP_REQUIRED" not in vals else "FAIL", "STAFF_SECOND_STEP_REQUIRED must not be set in staging")
say("OK" if vals.get("API_SURFACE") in ("customer", "admin") else "FAIL", f"API_SURFACE is {vals.get('API_SURFACE')!r} (customer or admin; one file holds one, the other service changes this line)")
for n, minimum in (("JWT_SECRET", 32), ("STAFF_JWT_SECRET", 32), ("SUPPORT_SESSION_KEY", 32), ("SITE_GATE_PASSWORD", 16), ("SQUARE_INTERNAL_KEY", 40)):
    if not has(n):
        say("FAIL", f"{n} is missing")
    else:
        say("OK" if len(vals[n]) >= minimum else "FAIL", f"{n} has {len(vals[n])} characters (needs {minimum}+)")
for n in ("FERNET_KEY", "STAFF_FERNET_KEY"):
    if not has(n):
        say("FAIL", f"{n} is missing")
        continue
    try:
        ok = len(base64.urlsafe_b64decode(vals[n])) == 32
    except Exception:  # noqa: BLE001
        ok = False
    say("OK" if ok else "FAIL", f"{n} is a valid Fernet key" if ok else f"{n} is NOT a valid Fernet key (44 characters, ends with =)")
pairs = [("JWT_SECRET", "STAFF_JWT_SECRET"), ("JWT_SECRET", "SUPPORT_SESSION_KEY"), ("STAFF_JWT_SECRET", "SUPPORT_SESSION_KEY"), ("FERNET_KEY", "STAFF_FERNET_KEY")]
for a, b in pairs:
    if has(a) and has(b):
        say("FAIL" if vals[a] == vals[b] else "OK", f"{a} and {b} " + ("are EQUAL (they must differ)" if vals[a] == vals[b] else "differ"))
same_local = [] if not VS_LOCAL else [n for n in sorted(SECRET_NAMES) if n in ("JWT_SECRET", "FERNET_KEY", "STORAGE_S3_SECRET_KEY") and has(n) and vals[n] == local.get(n)]
say("FAIL" if same_local else "OK", f"equal to the LOCAL file: {same_local} (staging needs its own)" if same_local else "no secret is copied from the local file")

print("\n=== 4. the addresses ===")
for n in ("CORS_ORIGINS", "ADMIN_ORIGINS", "PLATFORM_FRONTEND_URL", "SQUARE_SERVER_URL"):
    v = vals.get(n, "")
    if not v:
        say("WARN", f"{n} is empty" + (" (fill in after the square server exists, guide 41 Step 6)" if n == "SQUARE_SERVER_URL" else ""))
    elif not all(p.strip().startswith("https://") for p in v.split(",")):
        say("FAIL", f"{n} must be https:// on Render")
    else:
        say("OK", f"{n} is https")
cors = {p.strip() for p in vals.get("CORS_ORIGINS", "").split(",") if p.strip()}
adm = {p.strip() for p in vals.get("ADMIN_ORIGINS", "").split(",") if p.strip()}
say("FAIL" if cors & adm else "OK", "an origin is in both CORS_ORIGINS and ADMIN_ORIGINS" if cors & adm else "CORS_ORIGINS and ADMIN_ORIGINS share no origin")
say("OK" if not any(o.endswith("/") or "/" in o.removeprefix("https://") for o in cors | adm) else "WARN", "origins have no path or trailing /")

print("\n=== 5. does the backend accept it? (Settings validation, both services) ===")
for surface in ("customer", "admin"):
    try:
        Settings(_env_file=str(path), API_SURFACE=surface)  # type: ignore[call-arg]
        say("OK", f"as the {surface} service: valid")
    except Exception as exc:  # noqa: BLE001
        errs = getattr(exc, "errors", lambda: [])()
        msgs = [f"{'.'.join(str(x) for x in e.get('loc', ()))}: {e.get('msg', '')}" for e in errs] or [type(exc).__name__]
        say("FAIL", f"as the {surface} service: " + " | ".join(msgs))

print("\n=== 6. connections (read-only; nothing is created or changed) ===")
url = vals.get("DATABASE_URL", "")
parts = urlsplit(url.replace("postgresql+psycopg://", "postgresql://", 1)) if url else None
db_user = (parts.username or "") if parts else ""
db_ref = db_user.split(".", 1)[1] if "." in db_user else ""
auth_host = urlsplit(vals.get("AUTH_URL", "")).hostname or ""
auth_ref = auth_host.split(".")[0]
local_url = local.get("DATABASE_URL", "")
local_ref = (urlsplit(local_url.replace("postgresql+psycopg://", "postgresql://", 1)).username or "").split(".", 1)[-1] if local_url else ""
print(f"     database login role: {db_user.split('.')[0] or '-'}" + (f"; the database project differs from the local one: {'yes' if db_ref and db_ref != local_ref else 'NO' if db_ref else 'unknown'}" if VS_LOCAL else ""))
say("OK" if db_ref and db_ref == auth_ref else "FAIL", "the database project and AUTH_URL are the same Supabase project" if db_ref and db_ref == auth_ref else "the database project and AUTH_URL are NOT the same project (staging must use one project)")
if VS_LOCAL:
    say("OK" if auth_ref and auth_ref != (urlsplit(local.get("AUTH_URL", "")).hostname or "").split(".")[0] else "FAIL", "AUTH_URL is not the local project's" if auth_ref else "AUTH_URL is empty")

if url:
    try:
        import psycopg

        with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://", 1), connect_timeout=20) as conn:
            cur = conn.cursor()
            cur.execute("select current_user, current_database()")
            u, d = cur.fetchone()
            cur.execute("select count(*) from information_schema.tables where table_schema='public'")
            tables = cur.fetchone()[0]
            try:
                cur.execute("select version_num from alembic_version")
                ver = cur.fetchone()[0]
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                ver = f"not readable ({type(exc).__name__})"
        say("OK", f"database: connected as role {u} to {d}; {tables} tables in public; migration version {ver}")
        if ver == "not readable (InsufficientPrivilege)":
            print("     (a service role cannot read alembic_version: that is expected for customer_app and admin_app)")
    except Exception as exc:  # noqa: BLE001
        say("FAIL", f"database: {type(exc).__name__}: {str(exc)[:140]}")
else:
    say("FAIL", "database: DATABASE_URL is missing")

if has("AUTH_URL"):
    try:
        r = httpx.get(vals["AUTH_URL"].rstrip("/") + "/auth/v1/.well-known/jwks.json", timeout=20)
        keys = r.json().get("keys", []) if r.status_code == 200 else []
        say("OK" if keys and keys[0].get("alg") == "ES256" else "FAIL", f"sign-in project: HTTP {r.status_code}, key set " + (f"alg {keys[0].get('alg')}" if keys else "empty"))
    except Exception as exc:  # noqa: BLE001
        say("FAIL", f"sign-in project: {type(exc).__name__}")

ep, ak, sk = vals.get("STORAGE_S3_ENDPOINT_URL", ""), vals.get("STORAGE_S3_ACCESS_KEY", ""), vals.get("STORAGE_S3_SECRET_KEY", "")
if ep and ak and sk:
    try:
        import boto3
        from botocore.config import Config

        s3 = boto3.client("s3", endpoint_url=ep, aws_access_key_id=ak, aws_secret_access_key=sk, region_name=vals.get("STORAGE_S3_REGION") or "auto",
                          config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, connect_timeout=15, read_timeout=20, retries={"max_attempts": 1}))
        for label, key in (("public", "STORAGE_PUBLIC_BUCKET"), ("private", "STORAGE_PRIVATE_BUCKET")):
            b = vals.get(key, "")
            try:
                s3.head_bucket(Bucket=b)
                say("OK", f"storage: the {label} bucket '{b}' exists and the key may read it")
            except Exception as exc:  # noqa: BLE001
                code = getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)
                say("FAIL", f"storage: the {label} bucket '{b}': {code}")
    except Exception as exc:  # noqa: BLE001
        say("FAIL", f"storage: {type(exc).__name__}")
    base = vals.get("STORAGE_PUBLIC_BASE_URL", "")
    pb = vals.get("STORAGE_PUBLIC_BUCKET", "")
    say("OK" if base.rstrip("/").endswith("/" + pb) else "FAIL", "STORAGE_PUBLIC_BASE_URL ends with the public bucket name" if base.rstrip("/").endswith("/" + pb) else "STORAGE_PUBLIC_BASE_URL must END with the public bucket name")
    try:
        rr = httpx.get(base.rstrip("/") + "/_review_probe_does_not_exist", timeout=20)
        say("OK" if rr.status_code in (400, 404) else "WARN", f"storage public address answers HTTP {rr.status_code} for a missing file (400 or 404 is right)")
    except Exception as exc:  # noqa: BLE001
        say("FAIL", f"storage public address: {type(exc).__name__}")
else:
    say("FAIL", "storage: endpoint or keys missing")

if vals.get("PROVISIONER") == "neon":
    if has("NEON_API_KEY"):
        try:
            r = httpx.get("https://console.neon.tech/api/v2/projects", params={"limit": 10}, headers={"Authorization": "Bearer " + vals["NEON_API_KEY"], "Accept": "application/json"}, timeout=30)
            n = len(r.json().get("projects", [])) if r.status_code == 200 else "-"
            say("OK" if r.status_code == 200 else "FAIL", f"Neon API: HTTP {r.status_code}; projects visible: {n}")
        except Exception as exc:  # noqa: BLE001
            say("FAIL", f"Neon API: {type(exc).__name__}")
    else:
        say("FAIL", "PROVISIONER=neon but NEON_API_KEY is missing")

if vals.get("PROVISIONER") == "supabase":
    if has("SUPABASE_ACCESS_TOKEN") and has("SUPABASE_ORG_SLUG"):
        try:
            hdr = {"Authorization": "Bearer " + vals["SUPABASE_ACCESS_TOKEN"], "Accept": "application/json"}
            ro = httpx.get("https://api.supabase.com/v1/organizations", headers=hdr, timeout=30)
            orgs = ro.json() if ro.status_code == 200 else []
            slug = vals["SUPABASE_ORG_SLUG"]
            found = any(slug in (o.get("slug"), o.get("id")) for o in orgs if isinstance(o, dict))
            say("OK" if ro.status_code == 200 and found else "FAIL", f"Supabase Management API: HTTP {ro.status_code}; the organisation slug " + ("is one of this token's organisations" if found else "is NOT one of this token's organisations"))
            rp = httpx.get("https://api.supabase.com/v1/projects", headers=hdr, timeout=30)
            if rp.status_code == 200:
                projs = [p for p in rp.json() if isinstance(p, dict)]
                inorg = [p for p in projs if slug in (p.get("organization_slug"), p.get("organization_id"))]
                say("WARN" if len(projs) >= 2 else "OK", f"Supabase account of this token: {len(projs)} project(s), {len(inorg)} in that organisation (the free plan allows 2 active projects per person: each new square is one more)")
        except Exception as exc:  # noqa: BLE001
            say("FAIL", f"Supabase Management API: {type(exc).__name__}")
    else:
        say("FAIL", "PROVISIONER=supabase but SUPABASE_ACCESS_TOKEN or SUPABASE_ORG_SLUG is missing")

print(f"\nSUMMARY: {counts['OK']} ok, {counts['WARN']} warnings, {counts['FAIL']} failed")
