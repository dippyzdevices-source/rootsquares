"""The square's health, for its owner (rootsquares W10-R19, ADR 038).

Plain checks, each with a state (`ok`, `warn`, `fail`, `off`) and one sentence. NO numbers of rows, no names, no content: only whether the database answers,
storage and email are set up, the background jobs ran and the payment setup is complete. The platform asks over the protected call
`GET /api/internal/health` (module_status.py) and adds the facts it holds itself (logo, domain, reachable).
"""

from __future__ import annotations

import os
import time
from typing import Any

from flask import current_app, g
from sqlalchemy import text

from app.extensions import db
from app.jobs import heartbeat
from app.modules import module_enabled

JOB_STALE = {"messages": 10 * 60, "vipps_sweep": 30 * 60, "keep_alive": 40 * 60}  # seconds after which a quiet job is called late


def _check(key: str, state: str, sentence: str, group: str) -> dict[str, str]:
    return {"key": key, "group": group, "state": state, "text": sentence}


def _database() -> dict[str, str]:
    try:
        db.session.execute(text("SELECT 1"))
        return _check("database", "ok", "The database answers.", "system")
    except Exception:  # noqa: BLE001 - any failure is a failing database for the owner
        db.session.rollback()
        return _check("database", "fail", "The database does not answer.", "system")


def _storage() -> dict[str, str]:
    c = current_app.config
    ok = bool(c.get("STORAGE_S3_ENDPOINT_URL") and c.get("STORAGE_S3_ACCESS_KEY")) or current_app.extensions.get("tenancy") is not None
    return _check("storage", "ok" if ok else "warn", "Storage for pictures and files is set up." if ok else "Storage for pictures and files is not set up.", "system")


def _job(job: str, label: str, module: str | None) -> dict[str, str] | None:
    if module and not module_enabled(module):
        return None
    beat = heartbeat.last(job)
    if beat is None:
        return _check(f"job_{job}", "ok", f"{label}: has not run yet since the server started.", "jobs")
    if not beat["ok"]:
        return _check(f"job_{job}", "fail", f"{label}: the last run failed.", "jobs")
    if time.time() - beat["at"] > JOB_STALE[job]:
        return _check(f"job_{job}", "warn", f"{label}: has not run for a while.", "jobs")
    return _check(f"job_{job}", "ok", f"{label}: running.", "jobs")


def _setup() -> list[dict[str, str]]:
    c = current_app.config
    out = []
    mail = bool(c.get("RESEND_API_KEY") and c.get("EMAIL_FROM"))
    out.append(_check("setup_email", "ok" if mail else "warn", "Email sending is set up." if mail else "Email sending is not set up, so no emails go out.", "setup"))
    if module_enabled("payments"):
        from app.payments.vipps import is_enabled
        from app.settings.models import get_site_settings

        try:
            number = bool((get_site_settings().vipps_number or "").strip())
        except Exception:  # noqa: BLE001
            db.session.rollback()
            number = False
        paid = is_enabled() or number
        out.append(_check("setup_payments", "ok" if paid else "warn", "Payment is set up." if paid else "Payments are on but no way to pay is set up yet.", "setup"))
    return out


def health_report() -> dict[str, Any]:
    tenant = g.get("tenant")
    if tenant is not None and tenant.sleeping:  # asleep: its project may be paused, so nothing of the square is read
        return {"version": os.environ.get("APP_VERSION", ""), "checks": [_check("sleeping", "off", "The site is asleep (Keep): its project is paused and visitors see a back-soon page.", "system")]}
    checks = [_database(), _storage()]
    for job, label, module in (("messages", "Messages scheduler", "messages"), ("vipps_sweep", "Payment check", "payments"), ("keep_alive", "Keep-alive", None)):
        if job == "keep_alive" and not current_app.config.get("KEEP_ALIVE_URL"):
            continue
        c = _job(job, label, module)
        if c:
            checks.append(c)
    checks += _setup()
    return {"version": os.environ.get("APP_VERSION", ""), "checks": checks}
