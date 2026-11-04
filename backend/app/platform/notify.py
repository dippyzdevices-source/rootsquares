"""Mail to the owner of a square from the platform (W12-R18). Best effort: no e-mail service or a refusal means nothing is sent and nothing breaks.
Only the square's name and plain sentences go in; never personal data of the square's members."""

from __future__ import annotations

import datetime as dt
from typing import Any

from flask import Flask
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import models
from app.platform.models import Square, User
from app.shared.config import Settings


def owner_email(db: Session, org_id: object) -> str | None:
    owner = db.scalar(
        select(User)
        .join(models.Membership, models.Membership.user_id == User.id)
        .where(models.Membership.org_id == org_id, models.Membership.role == models.MembershipRole.OWNER)
    )
    return owner.email if owner is not None else None


def send_to_owner(app: Flask, db: Session, sq: Square, subject: str, body: str, **branded: Any) -> bool:
    email = app.extensions["providers"].email
    to = owner_email(db, sq.org_id)
    if email is None or to is None:
        return False
    try:
        email.send(to, subject, body, **branded)
    except Exception:  # noqa: BLE001 - a refused mail must not break the payment webhook
        return False
    return True


def payment_failed_text(settings: Settings, sq: Square) -> tuple[str, str]:
    until = sq.paid_until
    grace = (until + dt.timedelta(days=settings.BILLING_GRACE_DAYS)).strftime("%d %b %Y") if until else "soon"
    link = f"{settings.PLATFORM_FRONTEND_URL.rstrip('/')}/squares/{sq.id}/payments"
    lines = [
        f"We could not take the payment for {sq.name}.",
        "",
        f"Your site stays live until {grace}. Please update your card so the payment can go through:",
        link,
        "",
        "If it is not put right by then, the site goes to sleep. Nothing is deleted, and it wakes up as soon as the payment succeeds.",
    ]
    return f"The payment for {sq.name} failed", "\n".join(lines) + "\n"
