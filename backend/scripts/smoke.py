r"""What it is:   The smoke test of the platform backend against a real local Postgres.
What it does: Signs up, logs in, creates two squares, asserts two separate databases exist and one organisation cannot read the other's squares, cleans up.
How to run:   From backend/: .venv\Scripts\python.exe scripts\smoke.py (needs Postgres on 5432 with role rs_admin, or SMOKE_ADMIN_URL).
Read before:  docs/setup/14-testing-and-checks.md.
Read after:   scripts/test-all.ps1 -Smoke runs it with the full suites.

Smoke test of the platform backend against a real local Postgres (no mocks): signup, login, create two squares, assert two separate
databases exist, and a user of organization A cannot read organization B's squares.

Run from backend/ with the venv:   python scripts/smoke.py
Needs a Postgres where the role can create databases: the local service on port 5432 (role rs_admin) (override with SMOKE_ADMIN_URL).
Override with SMOKE_ADMIN_URL (a postgresql+psycopg:// URL to the maintenance database). It creates its own throwaway platform database
and drops everything it created at the end."""

from __future__ import annotations

import os
import re
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.main import create_app  # noqa: E402
from app.platform import staff as staff_service  # noqa: E402
from app.platform.models import Square  # noqa: E402
from app.platform.provisioning import to_libpq  # noqa: E402
from app.shared.config import Settings  # noqa: E402
from app.shared.crypto import Encryptor  # noqa: E402
from app.shared.db import Base  # noqa: E402

ADMIN_URL = os.environ.get("SMOKE_ADMIN_URL", "postgresql+psycopg://rs_admin:rootsquares_local_dev@127.0.0.1:5432/postgres")
H = {"X-Requested-With": "rootsquares"}
failures: list[str] = []
# The names this script gives its databases (smoke.py makes rs_smoke_platform_<run> and squares one-, two-, bad- and b-<run>; the provisioner adds _<8 hex>).
# Only these exact shapes are ever dropped, so a square you made yourself can never match.
SMOKE_DB = re.compile(r"rs_sq_(one|two|bad|b)_[0-9a-f]{6}_[0-9a-f]{8}|rs_smoke_platform_[0-9a-f]{6}")


def sweep_smoke_databases(only_run: str | None = None) -> list[str]:
    """Drops the databases of earlier smoke runs (a crashed run leaves its square databases behind); with only_run, just that run's. Returns the names."""
    with psycopg.connect(to_libpq(ADMIN_URL), autocommit=True) as c:
        found = [r[0] for r in c.execute("select datname from pg_database where datname like 'rs\\_%'")]
        names = [n for n in found if SMOKE_DB.fullmatch(n) and (only_run is None or f"_{only_run}" in n)]
        for name in names:
            c.execute(f'drop database if exists "{name}" with (force)')
    return names


def check(ok: bool, label: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + label)
    if not ok:
        failures.append(label)


def wait_ready(client, square_id: str, timeout: float = 30.0) -> dict:  # type: ignore[no-untyped-def]
    end = time.time() + timeout
    while time.time() < end:
        body = client.get(f"/api/platform/v1/squares/{square_id}").get_json()
        if body["status"] != "provisioning":
            return body  # type: ignore[no-any-return]
        time.sleep(0.2)
    raise TimeoutError("square still provisioning")


def main() -> int:
    run = secrets.token_hex(3)
    stale = sweep_smoke_databases()
    print(f"swept {len(stale)} database(s) left by earlier smoke runs" if stale else "no leftovers from earlier smoke runs")
    platform_db = f"rs_smoke_platform_{run}"
    admin = make_url(ADMIN_URL)
    platform_url = admin.set(database=platform_db).render_as_string(hide_password=False)
    created: list[str] = [platform_db]
    app = None
    with psycopg.connect(to_libpq(ADMIN_URL), autocommit=True) as c:
        c.execute(f'create database "{platform_db}"')
    try:
        settings = Settings(
            _env_file=None,
            ENV="test",
            LOG_LEVEL="ERROR",
            DATABASE_URL=platform_url,
            SEED_ADMIN_EMAIL=f"admin-{run}@example.com",
            SEED_ADMIN_PASSWORD="staff-password-123",
            LOGIN_RATE_LIMIT=5,
        )  # type: ignore[call-arg]
        app = create_app(settings)
        Base.metadata.create_all(app.extensions["db_engine"]())
        enc = Encryptor(settings.fernet_key)

        # --- seed a staff account through the CLI (ADR 083)
        res = app.test_cli_runner().invoke(args=["seed-staff"])
        check(res.exit_code == 0 and "created" in res.output, "seed-staff CLI creates the staff account")

        a, b, adm = app.test_client(), app.test_client(), app.test_client()
        base = "/api/platform/v1"

        # --- A: signup, session, csrf, logout, login
        r = a.post(
            f"{base}/auth/signup",
            json={
                "email": f"a-{run}@example.com",
                "password": "correct-horse-1",
                "name": "Anna",
                "organization_name": f"Org A {run}",
            },
            headers=H,
        )
        check(r.status_code == 201, "A signs up (user + organization)")
        cookies = r.headers.getlist("Set-Cookie")
        check(any("rs_access" in c and "HttpOnly" in c for c in cookies), "access cookie is httpOnly")
        check(a.post(f"{base}/auth/logout").status_code == 403, "mutating request without the CSRF header is refused")
        check(a.get(f"{base}/auth/me").get_json()["organizations"][0]["role"] == "owner", "me: A is owner of the new organization")
        check(a.post(f"{base}/auth/refresh", headers=H).status_code == 200, "refresh issues a new session")
        a.post(f"{base}/auth/logout", headers=H)
        check(a.get(f"{base}/auth/me").status_code == 401, "after logout me is 401")
        check(
            a.post(f"{base}/auth/login", json={"email": f"a-{run}@example.com", "password": "wrong-password"}, headers=H).status_code == 401,
            "wrong password is 401",
        )
        check(
            a.post(f"{base}/auth/login", json={"email": f"a-{run}@example.com", "password": "correct-horse-1"}, headers=H).status_code == 200,
            "A logs in",
        )
        check(
            a.post(
                f"{base}/auth/signup",
                json={"email": f"a-{run}@example.com", "password": "correct-horse-1", "organization_name": "Dup"},
                headers=H,
            ).status_code
            == 409,
            "duplicate email is 409",
        )

        # --- A: two squares
        r1 = a.post(f"{base}/squares", json={"name": "Square One", "slug": f"one-{run}", "theme_id": "paper-brick"}, headers=H)
        r2 = a.post(f"{base}/squares", json={"name": "Square Two", "slug": f"two-{run}", "theme_id": "paper-brick"}, headers=H)
        check(r1.status_code == 202 and r1.get_json()["status"] == "provisioning", "create square answers 202 provisioning")
        check(
            a.post(f"{base}/squares", json={"name": "Bad theme", "slug": f"bad-{run}", "theme_id": "no-such-theme"}, headers=H).status_code == 422,
            "a theme that is not enabled is refused",
        )
        check(
            a.post(f"{base}/squares", json={"name": "Dup", "slug": f"one-{run}", "theme_id": "paper-brick"}, headers=H).status_code == 409,
            "duplicate slug is 409",
        )
        s1, s2 = wait_ready(a, r1.get_json()["id"]), wait_ready(a, r2.get_json()["id"])
        check(s1["status"] == "ready" and s2["status"] == "ready", "both squares become ready")
        check(
            s1["has_database"] and s2["has_database"] and "postgres" not in r1.get_data(as_text=True),
            "API reports a database but never the connection string",
        )
        check(s1["url"] == f"https://one-{run}.rootsquares.com", "square detail has its link and domain")

        # --- two separate databases
        with app.extensions["db_factory"]()() as db:
            rows = {s.slug: s for s in db.scalars(select(Square)).all()}
        urls = {slug: enc.decrypt(sq.db_connection or "") for slug, sq in rows.items()}
        names = {slug: make_url(u).database for slug, u in urls.items()}
        created += [n for n in names.values() if n]
        check(
            len(set(names.values())) == 2 and platform_db not in names.values(),
            f"two separate databases: {sorted(names.values())}",
        )
        with psycopg.connect(to_libpq(ADMIN_URL), autocommit=True) as c:
            exist = {x[0] for x in c.execute("select datname from pg_database").fetchall()}
        check(all(n in exist for n in names.values()), "both databases exist in Postgres")
        for slug, url in urls.items():
            with psycopg.connect(to_libpq(url)) as c:
                email = c.execute("select email from admins").fetchall()
                dbname = c.execute("select current_database()").fetchone()[0]
            check(
                email == [(f"a-{run}@example.com",)] and dbname == names[slug],
                f"{slug}: own database, first admin seeded for the owner",
            )

        # --- B cannot see A's squares
        check(
            b.post(
                f"{base}/auth/signup",
                json={"email": f"b-{run}@example.com", "password": "another-pass-22", "organization_name": f"Org B {run}"},
                headers=H,
            ).status_code
            == 201,
            "B signs up (organization B)",
        )
        check(b.get(f"{base}/squares").get_json()["items"] == [], "B sees none of A's squares")
        check(b.get(f"{base}/squares/{s1['id']}").status_code == 404, "B cannot read A's square (404)")
        rb = b.post(f"{base}/squares", json={"name": "Square B", "slug": f"b-{run}", "theme_id": "paper-brick"}, headers=H)
        wait_ready(b, rb.get_json()["id"])
        check(len(a.get(f"{base}/squares").get_json()["items"]) == 2, "A still sees only its two squares")
        check(a.get(f"{base}/owner/squares").status_code == 404, "the customer API does not serve /owner/squares")

        # --- staff sees all, through the staff API: password, then the second step (set up at the first sign-in)
        admin_base = "/api/admin/v1"
        HA = {"X-Requested-With": "rootsquares-admin"}
        check(
            adm.post(f"{admin_base}/auth/login", json={"email": settings.SEED_ADMIN_EMAIL, "password": "staff-password-123"}, headers=HA).status_code == 200,
            "staff signs in with the password",
        )
        secret = adm.post(f"{admin_base}/auth/enrol/start", headers=HA).get_json()["secret"]
        check(
            adm.post(f"{admin_base}/auth/enrol/confirm", json={"code": staff_service.totp_code(secret)}, headers=HA).status_code == 200,
            "staff sets up the second step and is signed in",
        )
        owner_items = adm.get(f"{admin_base}/squares").get_json()["items"]
        check(
            len(owner_items) == 3 and {i["owner_email"] for i in owner_items} == {f"a-{run}@example.com", f"b-{run}@example.com"},
            "staff sees all 3 squares with owners",
        )
        with app.extensions["db_factory"]()() as db:
            created += [make_url(enc.decrypt(s.db_connection or "")).database for s in db.scalars(select(Square)).all() if s.db_connection]

        # --- rate limit, reset stub, OpenAPI
        codes = [b.post(f"{base}/auth/login", json={"email": f"x-{run}@example.com", "password": "nope-nope-nope"}, headers=H).status_code for _ in range(6)]
        check(codes[:5] == [401] * 5 and codes[5] == 429, f"login is rate limited after 5 attempts ({codes})")
        check(
            b.post(f"{base}/auth/password-reset", json={"email": f"b-{run}@example.com"}, headers=H).status_code == 202,
            "password reset stub answers 202",
        )
        spec = a.get("/apidoc/openapi.json").get_json()
        check(f"{base}/squares" in spec["paths"] and f"{base}/auth/signup" in spec["paths"], "OpenAPI document lists the endpoints")
    finally:
        if app is not None:
            app.extensions["executor"].shutdown(wait=True)
            app.extensions["db_engine"]().dispose()
        with psycopg.connect(to_libpq(ADMIN_URL), autocommit=True) as c:
            for name in dict.fromkeys(n for n in created if n):
                c.execute(f'drop database if exists "{name}" with (force)')
        leftover = sweep_smoke_databases(only_run=run)  # the square databases of this run, even when the run stopped before it noted them
        print(f"cleaned up {len(set(created)) + len(leftover)} databases")
    print("SMOKE PASSED" if not failures else f"SMOKE FAILED ({len(failures)}): " + "; ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
