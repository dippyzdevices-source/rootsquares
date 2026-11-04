# What it is:   What waits for a person at rootsquares (W25-R33): one list for the admin application's "Needs attention" page, side bar badge and overview.
# What it does: Reads platform data only (squares and support tables); nothing from inside a square (ADR 038). An item goes by itself once handled.
# How to run:   `collect(db, now)` from the staff routes `GET /owner/overview` and `/owner/attention`; `for_owner(db, user_id)` from `GET /attention` (W25-R35).
# Read before:  docs/setup/34-admin-console.md section on "Needs attention".
# Read after:   `frontend/admin/src/features/OwnerAttentionView.vue`.
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform.models import Membership, MembershipRole, Square, SquareStatus, SupportGrant, SupportRequest, SupportSession
from app.platform.schemas import OwnerAttention, PortalAttention

STUCK_AFTER = dt.timedelta(minutes=15)


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def collect(db: Session, now: dt.datetime) -> list[OwnerAttention]:
    """Failed or stuck squares, Google sign-in not on yet, own sending domain asked for or help asked, support access granted and not used yet. Oldest first."""
    items: list[OwnerAttention] = []

    def add(kind: str, sq: Square, since: dt.datetime, detail: str | None = None) -> None:
        items.append(OwnerAttention(kind=kind, square_id=sq.id, name=sq.name, slug=sq.slug, detail=detail, since=_aware(since)))

    for sq in db.scalars(select(Square).where(Square.status != SquareStatus.READY).order_by(Square.created_at)):
        if sq.status == SquareStatus.FAILED:
            add("failed", sq, sq.created_at, sq.error)
        elif now - _aware(sq.created_at) > STUCK_AFTER:
            add("stuck", sq, sq.created_at)
    for sq in db.scalars(select(Square).order_by(Square.created_at)):
        if sq.status == SquareStatus.READY and sq.google_login != "enabled":
            add("google_requested", sq, sq.created_at)
        if sq.mail_domain_request:
            add("mail_domain_requested", sq, sq.mail_domain_requested_at or sq.created_at, sq.mail_domain_request)
        if sq.site_domain_help_at and (sq.site_domain or sq.site_domain_request):
            add("site_domain_help", sq, sq.site_domain_help_at, sq.site_domain or sq.site_domain_request)
        if sq.site_domain_request:
            add("site_domain_requested", sq, sq.site_domain_requested_at or sq.created_at, sq.site_domain_request)
        if sq.mail_domain_help_at and sq.mail_domain_status != "verified":
            add("mail_domain_help", sq, sq.mail_domain_help_at, sq.mail_domain)
    used = set(db.scalars(select(SupportSession.grant_id)))
    for grant in db.scalars(select(SupportGrant).where(SupportGrant.revoked_at.is_(None)).order_by(SupportGrant.created_at)):
        if grant.id in used or _aware(grant.expires_at) <= now:
            continue
        granted = db.get(Square, grant.square_id)
        if granted is not None:
            add("support_granted", granted, grant.created_at)
    return items


def for_owner(db: Session, user_id: uuid.UUID) -> list[PortalAttention]:
    """What waits for a square's owner (the customer app's "Needs your attention" strip and side bar count, W25-R35): the records of the own sending domain
    to add, a domain Resend gave up on, and staff asking for support access. Only squares of organisations the person owns. Oldest first."""
    org_ids = list(db.scalars(select(Membership.org_id).where(Membership.user_id == user_id, Membership.role == MembershipRole.OWNER)))
    if not org_ids:
        return []
    items: list[PortalAttention] = []

    def add(kind: str, sq: Square, since: dt.datetime, detail: str | None = None) -> None:
        items.append(PortalAttention(kind=kind, square_id=sq.id, name=sq.name, slug=sq.slug, detail=detail, since=_aware(since)))

    squares = {sq.id: sq for sq in db.scalars(select(Square).where(Square.org_id.in_(org_ids)).order_by(Square.created_at))}
    for sq in squares.values():
        if not (sq.mail_domain and sq.mail_domain_id) or sq.mail_domain_status == "verified":
            continue
        failed = sq.mail_domain_status in ("failed", "partially_failed")
        add("mail_domain_failed" if failed else "mail_domain_records", sq, sq.created_at, sq.mail_domain)
    for req in db.scalars(
        select(SupportRequest).where(SupportRequest.square_id.in_(list(squares)), SupportRequest.answered_at.is_(None)).order_by(SupportRequest.created_at)
    ):
        add("support_request", squares[req.square_id], req.created_at, req.note)
    items.sort(key=lambda i: i.since)
    return items
