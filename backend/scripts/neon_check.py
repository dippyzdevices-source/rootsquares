r"""What it is:   The automated check of a new square on Neon.
What it does: Walks the steps of creating a square against the real Neon API with one throwaway project, prints PASS/FAIL for each, always deletes it.
How to run:   From backend/: .venv\Scripts\python.exe scripts\neon_check.py [--region aws-us-east-2] [--keep]
Read before:  docs/setup/31-neon-squares.md and NEON_API_KEY in backend/.env.
Read after:   backend/scripts/neon_state.py to see what is left; docs/setup/31-neon-squares.md for the hand test.

Walks the steps a new square needs on Neon, against the REAL Neon API, and prints PASS/FAIL for each (rootsquares W17-R14).

Run from backend/ with the venv:   python scripts/neon_check.py [--region aws-us-east-2] [--keep]

It reads NEON_API_KEY (and NEON_REGION) from backend/.env.local or the environment, creates ONE throwaway Neon project named `rootsquares-neoncheck-<hex>`,
exercises it, and ALWAYS deletes it again at the end (unless --keep). It never prints a key, a password or a connection string: only statuses and the
NAMES of fields in an answer. It uses the platform's own code (`NeonProvisioner`, `seed_square`, `template_command`) wherever there is any, so a PASS means
the real provisioning path works, and the steps that have no code yet (Neon Auth, storage buckets) are marked PROBE: they show what Neon answers.

Steps: key works -> create the project, Neon Auth, trusted address, buckets and storage credential (NeonProvisioner) -> connect -> square tables built
(SQUARE_TEMPLATE_CMD = square_db.py upgrade-env) -> suspend -> start -> reconnect -> owner, real sign-in and JWT check, storage upload and reads
(using only the returned secrets) -> delete the project.
"""

from __future__ import annotations

import os
import secrets
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402
import psycopg  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from app.shared.config import ENV_FILE  # noqa: E402

load_dotenv(BACKEND / ENV_FILE)

from app.platform.provisioning import (  # noqa: E402
    NeonApiError,
    NeonProvisioner,
    Owner,
    ProvisionResult,
    mail_sender,
    seed_square,
    template_command,
    to_libpq,
    verify_neon_owner,
)
from app.shared.config import Settings  # noqa: E402

API = "https://console.neon.tech/api/v2"
failures: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    print(("PASS   " if ok else "FAIL   ") + label + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(label)
    return ok


def probe(label: str, detail: str) -> None:
    print(f"PROBE  {label}  [{detail}]")


def short(r: httpx.Response) -> str:
    """Status and the API's own message, never a secret: only the error text or the names of the fields."""
    try:
        body = r.json()
    except ValueError:
        return f"HTTP {r.status_code}"
    if r.is_success and isinstance(body, dict):
        return f"HTTP {r.status_code}, fields: {', '.join(sorted(body))}"
    msg = body.get("message") if isinstance(body, dict) else None
    return f"HTTP {r.status_code}: {str(msg or body)[:200]}"


def connect(url: str):  # type: ignore[no-untyped-def]
    return psycopg.connect(to_libpq(url), autocommit=True, prepare_threshold=None, connect_timeout=60)


def wait_connect(url: str, seconds: float = 90.0) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        try:
            with connect(url) as c:
                c.execute("select 1")
            return True
        except Exception:  # noqa: BLE001  (the compute may still be starting)
            time.sleep(3)
    return False


def integration_checks(prov: NeonProvisioner, result: ProvisionResult, slug: str, run: str) -> None:
    """What the servers do with a new Neon square, using ONLY what the provisioner returned (its secrets): the owner, a real sign-in and the storage."""
    import boto3
    from botocore.config import Config

    from app.providers.auth import NeonAuthProvider

    sec = result.secrets or {}
    names = ("auth_provider", "project_url", "auth_url", "neon_branch_id", "s3_endpoint", "s3_region", "s3_access_key", "s3_secret_key")
    complete = all(sec.get(k) for k in names) and sec["auth_provider"] == "neon"
    check(complete, "the provisioner returns the sign-in address, the branch and the storage credential")
    check(bool(result.branch_id) and sec.get("neon_branch_id") == result.branch_id, "the result carries the branch id")
    site = f"https://{slug}.rootsquares.com"
    auth_url = sec["project_url"]

    # --- the owner and a real sign-in
    try:
        owner = Owner(email=f"owner-{run}@example.com", name="Neon Check Owner", password_hash=None)
        owner_id = prov.create_auth_user(result, owner)
        check(bool(owner_id), "the owner is created in the square's Neon Auth")
        verify_neon_owner(result.connection_url, owner_id)
        with connect(result.connection_url) as c:
            verified = c.execute('select "emailVerified" from neon_auth."user" where id::text = %s', (owner_id,)).fetchone()
        check(bool(verified and verified[0]), "the owner's e-mail is marked verified (so a Google sign-in can link to the owner)")
    except Exception as exc:  # noqa: BLE001
        check(False, "the owner is created in the square's Neon Auth", f"{type(exc).__name__}: {str(exc)[:160]}")
    email, password = f"tester-{run}@example.com", "Neon-check-pass-123!"
    web = {"Origin": site, "Content-Type": "application/json", "Accept": "application/json"}
    with httpx.Client(timeout=60.0, headers=web) as browser:  # a browser keeps the session cookie; the square's frontend does the same
        r = browser.post(f"{auth_url}/sign-up/email", json={"email": email, "password": password, "name": "Neon Check"})
        check(r.is_success, "a person can sign up at the square's Neon Auth from the square's address", short(r))
        signed_up_id = str(r.json().get("user", {}).get("id", "")) if r.is_success and isinstance(r.json(), dict) else ""
        r = browser.get(f"{auth_url}/token")
        token = r.json().get("token") if r.is_success and isinstance(r.json(), dict) else None
    check(bool(token), "the session cookie is exchanged for a JWT at <auth address>/token")
    if token:
        try:
            who = NeonAuthProvider(auth_url).verify(token)
            check(who["email"] == email, "the JWT passes the verification both servers use (EdDSA, issuer, audience)")
            # the owner is linked to the square by the id Neon returns when it creates the user; a later sign-in must carry that same id as `sub`
            check(bool(signed_up_id) and who["sub"] == signed_up_id, "the JWT's sub is the user id Neon Auth returns for that user (what links the owner)")
        except Exception as exc:  # noqa: BLE001
            check(False, "the JWT passes the verification both servers use", f"{type(exc).__name__}: {str(exc)[:160]}")

    # --- the storage, as the square server's S3 client uses it (path style, public base <endpoint>/<bucket>)
    endpoint = sec["s3_endpoint"]
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=sec["s3_access_key"],
        aws_secret_access_key=sec["s3_secret_key"],
        region_name=sec["s3_region"],
        config=Config(s3={"addressing_style": "path"}),
    )
    try:
        s3.put_object(Bucket="public", Key="check/hello.txt", Body=b"hello", ContentType="text/plain")
        s3.put_object(Bucket="private", Key="check/secret.txt", Body=b"secret", ContentType="text/plain")
        check(True, "upload to the public and the private bucket with the returned credential")
    except Exception as exc:  # noqa: BLE001
        check(False, "upload to the public and the private bucket with the returned credential", f"{type(exc).__name__}: {str(exc)[:200]}")
        return
    anon = httpx.get(f"{endpoint}/public/check/hello.txt", timeout=60.0)
    public_ok = anon.status_code == 200 and anon.content == b"hello"
    check(public_ok, "a public object is readable without a key at <endpoint>/public/<key>", f"HTTP {anon.status_code}")
    anon_private = httpx.get(f"{endpoint}/private/check/secret.txt", timeout=60.0)
    check(anon_private.status_code in (401, 403), "a private object is NOT readable without a key", f"HTTP {anon_private.status_code}")
    signed = s3.generate_presigned_url("get_object", Params={"Bucket": "private", "Key": "check/secret.txt"}, ExpiresIn=300)
    check(httpx.get(signed, timeout=60.0).content == b"secret", "a presigned URL reads the private object")


def real_settings():  # type: ignore[no-untyped-def]
    """The platform's real settings from backend/.env.local (or ENV_FILE; for the Resend sender), or None when they cannot be read."""
    try:
        return Settings(_env_file=str(BACKEND / ENV_FILE))  # type: ignore[call-arg]
    except Exception:  # noqa: BLE001
        return None


def google_and_mail_checks(  # type: ignore[no-untyped-def]
    prov: NeonProvisioner, client: httpx.Client, headers: dict[str, str], result: ProvisionResult, slug: str, settings, test_email: str
) -> None:
    pid, bid = str(result.neon_project_id), str(result.branch_id)
    base = f"/projects/{pid}/branches/{bid}/auth"

    def providers() -> list[str]:
        r = client.get(f"{base}/oauth_providers", headers=headers)
        body = r.json() if r.is_success else {}
        items = body.get("oauth_providers") or body.get("providers") or (body if isinstance(body, list) else [])
        return [str(i.get("id")) for i in items if isinstance(i, dict)]

    # Google with Neon's shared development credentials (no client id or secret), on, on again, off
    try:
        prov.set_google_login(pid, bid, "", "", True)
        check("google" in providers(), "Google sign-in switched on (Neon's shared development credentials)")
        prov.set_google_login(pid, bid, "", "", True)
        check("google" in providers(), "switching Google on again is fine")
        prov.set_google_login(pid, bid, "", "", False)
        check("google" not in providers(), "Google sign-in switched off")
        prov.set_google_login(pid, bid, "", "", False)
        check(True, "switching Google off again is fine")
    except NeonApiError as exc:
        check(False, "Google sign-in on and off", str(exc)[:200])

    # trusted addresses: adding the same one again
    try:
        address = f"https://{slug}.rootsquares.com"
        prov.set_redirects(pid, bid, [address, address, "http://" + slug + ".localhost:5274"])
        check(True, "trusted addresses can be set again without an error")
    except NeonApiError as exc:
        check(False, "trusted addresses can be set again without an error", str(exc)[:200])

    # the sign-in e-mail sender: the platform's Resend settings through Neon's SMTP option
    sender = mail_sender(settings) if settings is not None else None
    if sender is None:
        print("NOTE   Resend is not set in .env.local (EMAIL_PROVIDER=resend, RESEND_API_KEY, EMAIL_FROM): trying placeholder SMTP, nothing is sent")
        sender = {"host": "smtp.example.com", "port": 465, "username": "placeholder", "password": "not-a-real-password", "sender_email": "no-reply@example.com"}
    try:
        prov.set_email(pid, bid, sender_name="Neon Check", **sender)
        check(True, "the square's sign-in e-mails are sent through Resend's SMTP (setting accepted)")
    except NeonApiError as exc:
        check(False, "the square's sign-in e-mails are sent through Resend's SMTP (setting accepted)", str(exc)[:200])
        return
    r = client.get(f"{base}/email_provider", headers=headers)
    probe("read the e-mail provider back", short(r) if r.is_success else f"HTTP {r.status_code}")
    if test_email:
        try:
            prov.send_test_email(pid, bid, test_email)
            check(True, "a test e-mail is sent through the square's sender")
        except NeonApiError as exc:
            check(False, "a test e-mail is sent through the square's sender", str(exc)[:200])
    else:
        print("SKIP   test e-mail (add --test-email <your address> to send one)")


def main(argv: list[str]) -> int:
    key = os.environ.get("NEON_API_KEY", "")
    if not key:
        print("NEON_API_KEY is not set (backend/.env.local)")
        return 1
    region = os.environ.get("NEON_REGION", "aws-eu-central-1")
    if "--region" in argv:
        region = argv[argv.index("--region") + 1]
    keep = "--keep" in argv
    test_email = argv[argv.index("--test-email") + 1] if "--test-email" in argv else ""
    run = secrets.token_hex(3)
    slug = f"neoncheck-{run}"
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"}
    client = httpx.Client(base_url=API, timeout=60.0)
    prov = NeonProvisioner(key, region, client=client, site_suffix="rootsquares.com", extra_redirects=("http://{slug}.localhost:5274/**",))
    project_id: str | None = None
    print(f"Neon check, region {region}, project name rootsquares-{slug}")
    try:
        # 1. the key works
        r = client.get("/projects", headers=headers, params={"limit": 1})
        if not check(r.is_success, "the API key is accepted", short(r)):
            return 1

        # 2. create the project with the platform's own provisioner
        try:
            result = prov.create_database(slug)
            project_id = result.neon_project_id
            check(bool(project_id and result.connection_url), "NeonProvisioner creates a project and returns a connection URI")
        except Exception as exc:  # noqa: BLE001
            check(False, "NeonProvisioner creates a project and returns a connection URI", f"{type(exc).__name__}: {str(exc)[:200]}")
            return 1
        url = result.connection_url
        check(url.startswith("postgres"), "the connection URI is a postgres address")

        # 3. connect
        ok = wait_connect(url)
        check(ok, "the database accepts a connection")
        if not ok:
            return 1
        with connect(url) as c:
            version = c.execute("show server_version").fetchone()[0]  # type: ignore[index]
        check(True, "Postgres version", str(version))

        # 4. the platform's own seeding path: admins table + the square app's tables (square_db.py upgrade-env)
        settings = Settings(_env_file=None, ENV="test", PROVISIONER="neon", NEON_API_KEY=key, NEON_REGION=region)  # type: ignore[call-arg]
        cmd = template_command(settings)
        check(bool(cmd), "the square app's table command is found (square/backend venv)")
        owner = Owner(email=f"owner-{run}@example.com", name="Neon Check Owner", password_hash=None)
        started = time.time()
        try:
            seed_square(url, slug, owner, cmd)
            check(True, "seed_square: admins table, owner and all square migrations ran", f"{time.time() - started:.0f} s")
        except Exception as exc:  # noqa: BLE001
            check(False, "seed_square: admins table, owner and all square migrations ran", f"{type(exc).__name__}: {str(exc)[:200]}")
        with connect(url) as c:
            tables = {row[0] for row in c.execute("select tablename from pg_tables where schemaname = 'public'")}
            rls_off = [row[0] for row in c.execute("select tablename from pg_tables where schemaname = 'public' and not rowsecurity")]
            version_row = c.execute("select version_num from alembic_version").fetchone() if "alembic_version" in tables else None
        check({"events", "orders", "members", "admins"} <= tables, "the square tables exist", f"{len(tables)} tables")
        check(version_row is not None, "the square migration version is recorded")
        check(not rls_off, "row level security is on for every table", f"{len(rls_off)} without" if rls_off else "")

        # 5. sleep and wake (Keep plan)
        try:
            prov.suspend_project(project_id)  # type: ignore[arg-type]
            check(True, "suspend_project (sleep)")
        except Exception as exc:  # noqa: BLE001
            check(False, "suspend_project (sleep)", f"{type(exc).__name__}: {str(exc)[:200]}")
        try:
            prov.start_project(project_id)  # type: ignore[arg-type]
            check(True, "start_project (wake)")
        except Exception as exc:  # noqa: BLE001
            check(False, "start_project (wake)", f"{type(exc).__name__}: {str(exc)[:200]}")
        check(wait_connect(url), "the database answers again after sleep and wake")

        # 6. sign-in and storage, from what the provisioner returned
        integration_checks(prov, result, slug, run)

        # 7. Google sign-in, trusted addresses and the sign-in e-mail sender (the platform's own methods, as the CLI and the owner console call them)
        settings_real = real_settings()
        google_and_mail_checks(prov, client, headers, result, slug, settings_real, test_email)
    finally:
        if project_id and not keep:
            try:
                gone = prov.destroy_project(project_id)
                check(gone, "the throwaway project is deleted again")
            except Exception as exc:  # noqa: BLE001
                detail = f"{type(exc).__name__}: {str(exc)[:200]} (delete rootsquares-{slug} in the Neon console)"
                check(False, "the throwaway project is deleted again", detail)
        elif project_id:
            print(f"KEPT   project rootsquares-{slug} ({project_id}); delete it in the Neon console")
    print("NEON CHECK PASSED (probes are information, not pass/fail)" if not failures else f"NEON CHECK FAILED ({len(failures)}): " + "; ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
