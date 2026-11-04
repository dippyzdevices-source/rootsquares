# ruff: noqa: F811
"""Shared helpers of the billing test suite: a square owned by a fake user, checkout calls, the clock, the trial job."""

from __future__ import annotations

import datetime as dt

from flask import Flask
from sqlalchemy import select

from app.platform import trial
from app.platform.models import BillingOrder, Square
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)

NOW = dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.UTC)


def _square(api: Flask, who: str, package: str = "roots", country: str | None = None):
    """A signed-in fake user `who` with an organisation and one square `sq-<who>`; returns (client, headers, square json)."""
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": f"Bearer fake:u-{who}:{who}@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": f"Club {who}"}, headers=h).status_code == 201
    body = {"name": f"Sq {who}", "slug": f"sq-{who}", "theme_id": "paper-brick", "launch_package": package, "billing_country": country}
    sq = c.post(f"{PREFIX}/squares", json=body, headers=h).json
    return c, h, sq


def _checkout(c, h, sq, **body):
    return c.post(f"{PREFIX}/squares/{sq['id']}/billing/checkout", json=body, headers=h)


def _run(api: Flask, enforce: bool = True, apply: bool = False, slept: list[str] | None = None):
    """One pass of the trial job at NOW."""
    settings = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": enforce})
    db = api.extensions["db_factory"]()()
    try:
        return trial.run(db, settings, now=NOW, apply=apply, sleep=lambda _s, sq: slept.append(sq.slug) if slept is not None else None)
    finally:
        db.rollback()
        db.close()


def _set(api: Flask, slug: str, paid_until: dt.datetime, paid_first: bool = False) -> None:
    """Put a square's paid time where a test needs it (and, with `paid_first`, give it a paid first payment)."""
    db = api.extensions["db_factory"]()()
    sq = db.scalar(select(Square).where(Square.slug == slug))
    sq.paid_until = paid_until
    sq.status = "ready"
    if paid_first:
        db.add(BillingOrder(square_id=sq.id, kind="first", amount_minor=1, status="paid", provider="fake", launch_package="roots", running_plan="live"))
    db.commit()
    db.close()
