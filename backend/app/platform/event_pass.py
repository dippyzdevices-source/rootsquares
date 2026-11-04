"""The life of an Event pass (rootsquares W11, ADR 044, docs/plans/pricing-strategy.md).

An Event pass is a one-off page for a single event, not an association. Its life, counted from the day it is paid:
  live      days 0 to 45   public page, ticket sales, the event;
  archive   days 45 to 90  the public page says the event is over, only the owner can sign in, read-only: to download the accounting report, the
                           attendee and order list and the people list (the square server enforces this from `event_live_until` / `event_archive_until`);
  removed   day 90         the square is removed from service (soft delete: not served, nothing deleted yet);
  purged    day 104        (90 + 14 days) its project at the provider and its row are deleted for good. Only when EVENT_PASS_PURGE is on.
Reminders are due on days 40, 60, 80 and 85 and recorded on the square (shown on the portal, written to the audit log, e-mailed once an e-mail provider
is wired). The dates are written to the square when the pass starts, so changing a setting later never moves a pass that is already running.
The upgrade to a launch package plus Live (the $25 credited) clears the lifecycle (see billing.py).
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import plans
from app.platform.models import AuditLog, Square, SquareStatus
from app.shared.config import Settings

log = structlog.get_logger("app.event_pass")

LIVE, ARCHIVE, REMOVED = "live", "archive", "removed"
REMINDER_DAYS: tuple[int, ...] = (40, 60, 80, 85)  # days since the pass started


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    """Some databases give back a time without its zone; it is always UTC here."""
    return value.replace(tzinfo=dt.UTC) if value is not None and value.tzinfo is None else value


def is_event_pass(sq: Square) -> bool:
    return sq.launch_package == plans.EVENT and sq.event_live_until is not None


def awaiting_payment(sq: Square) -> bool:
    """An Event pass made while payment is required (W12-R6): nothing is provisioned and no clock runs until the $25 is paid."""
    return sq.launch_package == plans.EVENT and sq.event_live_until is None and str(sq.status) == "provisioning"


def start(sq: Square, settings: Settings, now: dt.datetime | None = None) -> None:
    """Start the clock of a new Event pass (from payment; until Stripe is on, the moment the square is created)."""
    now = now or dt.datetime.now(dt.UTC)
    sq.event_started_at = now
    sq.event_live_until = now + dt.timedelta(days=settings.EVENT_PASS_LIVE_DAYS)
    sq.event_archive_until = sq.event_live_until + dt.timedelta(days=settings.EVENT_PASS_ARCHIVE_DAYS)
    sq.event_deleted_at = None
    sq.event_reminders = None


def end_now(sq: Square, archive_days: int, now: dt.datetime | None = None) -> None:
    """A refunded Event pass ends at once: the live days stop now and the normal archive starts
    (the owner can still sign in to export, then it is removed on schedule)."""
    now = now or dt.datetime.now(dt.UTC)
    sq.event_live_until = now
    sq.event_archive_until = now + dt.timedelta(days=archive_days)


def clear(sq: Square) -> None:
    """The pass became a normal square (upgrade): no live end, no archive, no deletion."""
    sq.event_started_at = sq.event_live_until = sq.event_archive_until = sq.event_deleted_at = None
    sq.event_export_confirmed_at = None
    sq.event_reminders = None


def phase(sq: Square, now: dt.datetime | None = None) -> str | None:
    """live | archive | removed for an Event pass; None for every other square."""
    if not is_event_pass(sq):
        return None
    now = now or dt.datetime.now(dt.UTC)
    if sq.event_deleted_at is not None:
        return REMOVED
    live_until = _aware(sq.event_live_until)
    archive_until = _aware(sq.event_archive_until)
    if live_until is not None and now < live_until:
        return LIVE
    if archive_until is not None and now < archive_until:
        return ARCHIVE
    return REMOVED


def sent_reminders(sq: Square) -> list[int]:
    try:
        data = json.loads(sq.event_reminders or "[]")
    except ValueError:
        return []
    return [int(d) for d in data if isinstance(d, int)] if isinstance(data, list) else []


def due_reminders(sq: Square, now: dt.datetime | None = None) -> list[int]:
    """The reminder days that have come and were not recorded yet (days since the start)."""
    if not is_event_pass(sq) or sq.event_started_at is None or sq.event_deleted_at is not None:
        return []
    now = now or dt.datetime.now(dt.UTC)
    age = (now - (_aware(sq.event_started_at) or now)).days
    done = set(sent_reminders(sq))
    return [d for d in REMINDER_DAYS if age >= d and d not in done]


def summary(sq: Square, settings: Settings, now: dt.datetime | None = None) -> dict[str, Any] | None:
    """What the owner sees: the phase, the dates and the days left until the next change (None for a square that is not an Event pass)."""
    if not is_event_pass(sq):
        return None
    now = now or dt.datetime.now(dt.UTC)
    ph = phase(sq, now)
    live_until = _aware(sq.event_live_until)
    archive_until = _aware(sq.event_archive_until)
    purge_at = (_aware(sq.event_deleted_at) or archive_until or now) + dt.timedelta(days=settings.EVENT_PASS_SOFT_DELETE_DAYS) if ph == REMOVED else None
    target = {LIVE: live_until, ARCHIVE: archive_until, REMOVED: purge_at}[ph or LIVE]
    days_left = max(0, (target - now).days + (1 if (target - now).seconds else 0)) if target else 0
    return {
        "phase": ph,
        "started_at": _aware(sq.event_started_at),
        "live_until": live_until,
        "archive_until": archive_until,
        "purge_at": purge_at,
        "days_left": days_left,  # days until the next change: live to archive, archive to removal, removal to the final purge
        "export_confirmed_at": _aware(sq.event_export_confirmed_at),
        "reminders_sent": sent_reminders(sq),
    }


def confirm_export(sq: Square, now: dt.datetime | None = None) -> None:
    """The owner says the reports are saved (a plain yes, nothing about their content is learned: ADR 038)."""
    sq.event_export_confirmed_at = now or dt.datetime.now(dt.UTC)


def _audit(db: Session, action: str, sq: Square, **data: Any) -> None:
    db.add(AuditLog(action=action, entity="square", entity_id=str(sq.id), org_id=sq.org_id, actor_user_id=None, data={"slug": sq.slug, **data}))


def run(
    db: Session,
    settings: Settings,
    now: dt.datetime | None = None,
    apply: bool = False,
    notify: Callable[[Square, int], None] | None = None,
    purge: Callable[[Session, Square], None] | None = None,
) -> list[dict[str, Any]]:
    """One pass of the daily job. Returns what was (or, without `apply`, would be) done, one entry per action:
    reminder (a reminder day came), remove (the square leaves service), purge (the square is deleted for good; only with EVENT_PASS_PURGE).
    Without `apply` nothing is written: a dry run (the default of the command line)."""
    now = now or dt.datetime.now(dt.UTC)
    actions: list[dict[str, Any]] = []
    squares = db.scalars(select(Square).where(Square.launch_package == plans.EVENT, Square.event_live_until.is_not(None)).order_by(Square.created_at)).all()
    for sq in squares:
        if sq.status == SquareStatus.PROVISIONING:
            continue
        for day in due_reminders(sq, now):
            actions.append({"slug": sq.slug, "action": "reminder", "day": day})
            if apply:
                sent = sent_reminders(sq) + [day]
                sq.event_reminders = json.dumps(sorted(sent))
                _audit(db, "event_pass.reminder", sq, day=day)
                if notify is not None:
                    notify(sq, day)
        ph = phase(sq, now)
        if ph == REMOVED and sq.event_deleted_at is None:
            actions.append({"slug": sq.slug, "action": "remove"})
            if apply:
                sq.event_deleted_at = now
                sq.suspended_at = sq.suspended_at or now  # no longer served; its data is still there until the purge
                _audit(db, "event_pass.removed", sq)
        elif ph == REMOVED and sq.event_deleted_at is not None:
            removed_at = _aware(sq.event_deleted_at) or now
            if now >= removed_at + dt.timedelta(days=settings.EVENT_PASS_SOFT_DELETE_DAYS):
                actions.append({"slug": sq.slug, "action": "purge", "enabled": settings.EVENT_PASS_PURGE})
                if apply and settings.EVENT_PASS_PURGE and purge is not None:
                    purge(db, sq)
    if apply:
        db.flush()
    return actions
