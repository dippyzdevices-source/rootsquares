r"""What it is:   A one-off script for demo members.
What it does: Creates real Supabase Auth accounts for seeded demo members that have no login yet, so you can sign in as one of them. Does not touch Member.user_id.
How to run:   From square/backend: .venv\Scripts\python.exe -m scripts.create_supabase_auth_users (needs SUPABASE_SERVICE_ROLE_KEY in .env; never commit it).
Read before:  docs/setup/30-demo-data.md.
Read after:   Sign in as the member; docs/hand-tests/demo-data-test-guide.md.

One-off script to create real Supabase Auth accounts for the seeded demo Members that have
no login yet (Member.user_id IS NULL) — e.g. so you can actually log in as one of them to test
things like the Admin Volunteers search, which only lists people who have authenticated at
least once (see MEMORY.md's Members/Excel-import note: a Member can exist on the roster before
ever logging in, and only auto-links to a User the first time its email matches a real login).

This does NOT touch Member.user_id itself — that auto-link happens naturally, in the app's own
existing code, the first time someone actually logs in with a matching email. This script only
creates the Supabase Auth account so that first login becomes possible.

Requires a SUPABASE_SERVICE_ROLE_KEY in backend/.env (NOT the anon key already used elsewhere
in this project) — get it from the Supabase Dashboard: Project Settings -> API -> "service_role"
secret key. This key bypasses all Supabase security rules — never commit it, never expose it to
the frontend, and only ever use it from a trusted server-side script like this one.

Run once from backend/: .venv/Scripts/python.exe -m scripts.create_supabase_auth_users
(the -m form is required so the `app` package resolves — a direct path invocation fails with
ModuleNotFoundError: No module named 'app').
"""

import json
import os
import urllib.error
import urllib.request

from pathlib import Path

from dotenv import load_dotenv

# The settings file (W26-R51): .env.local in square/backend; ENV_FILE names another one.
load_dotenv(Path(__file__).resolve().parents[1] / (os.environ.get("ENV_FILE", "").strip() or ".env.local"))

from app import create_app  # noqa: E402
from app.members.models import Member  # noqa: E402

TEST_PASSWORD = "BcaOslo2026!"


def create_auth_user(supabase_url: str, service_role_key: str, email: str, full_name: str) -> str:
    """Returns 'created', 'already_exists', or raises for any other failure."""
    request = urllib.request.Request(
        url=f"{supabase_url}/auth/v1/admin/users",
        method="POST",
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "email": email,
                "password": TEST_PASSWORD,
                # Skips Supabase's confirmation email — these are fake @example.com addresses
                # that can't receive one anyway, and this is test data, not a real signup.
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            }
        ).encode(),
    )
    try:
        urllib.request.urlopen(request)
        return "created"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        if exc.code in (400, 422) and "already been registered" in body:
            return "already_exists"
        raise RuntimeError(f"Supabase Admin API returned {exc.code}: {body}") from exc


def main() -> None:
    if os.environ.get("AUTH_PROVIDER", "").strip().lower() != "supabase":
        raise SystemExit("AUTH_PROVIDER must be 'supabase' in backend/.env to run this script.")
    supabase_url = os.environ.get("AUTH_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise SystemExit(
            "AUTH_URL (the Supabase project URL) and SUPABASE_SERVICE_ROLE_KEY must both be set in "
            "backend/.env (the service role key is in the Supabase Dashboard under Project Settings -> API)."
        )

    app = create_app()
    with app.app_context():
        members = (
            Member.query.filter(Member.user_id.is_(None))
            .filter(Member.email.isnot(None))
            .order_by(Member.id)
            .all()
        )

        created, already_existed, failed = 0, 0, 0
        for member in members:
            try:
                result = create_auth_user(supabase_url, service_role_key, member.email, member.name)
            except RuntimeError as exc:
                print(f"  FAILED  {member.email}: {exc}")
                failed += 1
                continue
            if result == "created":
                print(f"  created {member.email}")
                created += 1
            else:
                already_existed += 1

        print()
        print(f"{created} account(s) created, {already_existed} already existed, {failed} failed.")
        if created:
            print(f"Test password for every created account: {TEST_PASSWORD}")
            print(
                "Each account auto-links to its Member row the first time it logs in, exactly "
                "like a real member's first login — no other setup needed."
            )


if __name__ == "__main__":
    main()
