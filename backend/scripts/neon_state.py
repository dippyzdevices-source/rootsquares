r"""What it is:   A read-only report on the Neon squares.
What it does: Prints what Neon says (compute state, operations) next to what the platform recorded (plan, sleep state, audit entries); changes nothing.
How to run:   From backend/: .venv\Scripts\python.exe scripts\neon_state.py
Read before:  docs/setup/31-neon-squares.md section 12 and NEON_API_KEY in backend/.env.local.
Read after:   backend/scripts/neon_check.py for the full check.

Read-only view of the Neon squares: what Neon says and what the platform says (rootsquares W17-R26; guide 31 section 12).

Run from backend/ with the venv:   .venv\Scripts\python.exe scripts\neon_state.py

Prints, for every project named `rootsquares-*` at Neon: the compute state (`active` or `idle` = suspended), when it was last active, and Neon's own log of
recent compute operations (`start_compute`, `suspend_compute`); then, for every square the platform made at Neon: its running plan, sleep state and the
latest `square.*` audit entries (for example `square.paused`, `square.woke`). It changes nothing and never prints a key, a password or a connection string.
Projects that are not named `rootsquares-*` are listed only by count and are never touched."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from app.shared.config import ENV_FILE  # noqa: E402

load_dotenv(BACKEND / ENV_FILE)

from sqlalchemy import select  # noqa: E402

from app.main import create_app  # noqa: E402
from app.platform.models import AuditLog, Square  # noqa: E402


def neon_side() -> None:
    key = os.environ.get("NEON_API_KEY", "")
    if not key:
        print("NEON_API_KEY is not set (backend/.env.local): skipping the Neon side")
        return
    client = httpx.Client(base_url="https://console.neon.tech/api/v2", headers={"Authorization": f"Bearer {key}", "Accept": "application/json"}, timeout=60.0)
    projects = client.get("/projects", params={"limit": 100}).json().get("projects", [])
    mine = [p for p in projects if str(p.get("name", "")).startswith("rootsquares-")]
    print(f"NEON: {len(mine)} rootsquares project(s) of {len(projects)} in the account")
    for p in mine:
        for e in client.get(f"/projects/{p['id']}/endpoints").json().get("endpoints", []):
            print(f"  {p['name']}: compute {e.get('current_state')}, last active {e.get('last_active')}")
        for o in client.get(f"/projects/{p['id']}/operations", params={"limit": 12}).json().get("operations", []):
            if o.get("action") in ("start_compute", "suspend_compute"):
                print(f"      {o.get('created_at')}  {o.get('action')}  {o.get('status')}")


def platform_side() -> None:
    app = create_app()
    db = app.extensions["db_factory"]()()
    settings = app.extensions["settings"]
    print(f"PLATFORM: PROVISIONER={settings.PROVISIONER} PROVIDER_SLEEP={settings.PROVIDER_SLEEP} BILLING_ENFORCE={settings.BILLING_ENFORCE}")
    for sq in db.scalars(select(Square).where(Square.neon_project_id.is_not(None)).order_by(Square.created_at.desc())):
        print(f"  {sq.slug}: package={sq.launch_package} running_plan={sq.running_plan} sleep_state={sq.sleep_state} asleep_since={sq.asleep_since}")
        where = (AuditLog.entity == "square", AuditLog.entity_id == str(sq.id), AuditLog.action.like("square.%"))
        stmt = select(AuditLog).where(*where).order_by(AuditLog.at.desc()).limit(6)
        for a in db.scalars(stmt):
            print(f"      {a.at}  {a.action}  {a.data}")


if __name__ == "__main__":
    neon_side()
    platform_side()
