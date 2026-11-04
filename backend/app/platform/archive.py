"""Archive of an abandoned sleeping square (W13-R48, ADR 059, docs/plans/pricing-strategy.md section 6): a square asleep with nothing paid
for `SLEEP_ARCHIVE_DAYS` (360 = 12 months of 30 days) is archived. Three reminders first: at 9 months, at 11 months and 7 days before the archive date.
Then, only when `SLEEP_ARCHIVE_PURGE` is on, the square's own project (database, sign-in, files) is deleted at the provider and the platform row is kept with
`archived_at`: the square is not served, cannot be woken, and the owner can delete it or make a new one. Nothing else is touched.
Counted from the later of `asleep_since` and `paid_until`, so a Keep square that is still paid for is never archived. Event passes have their own life
(event_pass.py). The platform cannot read a square's data (ADR 038), so it cannot export it: the reminders tell the owner to wake the square and
download it from its own admin first. A square is archived only after all three reminders were sent (so a missing e-mail service never ends in a
deletion) and the last one is at least `GAP_DAYS` old. Only with BILLING_ENFORCE=true. Dry run by default, like the other daily jobs (called by `trial-run`)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import plans
from app.platform.models import AuditLog, Square, SquareStatus
from app.shared.config import Settings

NOTICE_ACTION = "billing.archive_notice"  # data {"n": 1..3}; recorded once the owner was told, so a missing e-mail service is retried
ARCHIVED_ACTION = "square.archived"
FAILED_ACTION = "square.archive_failed"
GAP_DAYS = 7  # the last reminder must be at least this old before the archive runs


def _aware(value: dt.datetime) -> dt.datetime:
    return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value


def unpaid_since(sq: Square) -> dt.datetime | None:
    """The day the square began to be asleep with nothing paid: the later of when it fell asleep and when its paid time ended."""
    marks = [_aware(m) for m in (sq.asleep_since, sq.paid_until) if m is not None]
    return max(marks) if marks else None


def thresholds(settings: Settings) -> tuple[int, int, int]:
    """Days unpaid at which reminder 1, 2 and 3 go out (9 months, 11 months and 7 days before the archive date for the default 360)."""
    a = settings.SLEEP_ARCHIVE_DAYS
    return a * 3 // 4, a * 11 // 12, a - GAP_DAYS


def archive_date(sq: Square, settings: Settings, now: dt.datetime) -> dt.datetime:
    since = unpaid_since(sq) or now
    return max(since + dt.timedelta(days=settings.SLEEP_ARCHIVE_DAYS), now + dt.timedelta(days=GAP_DAYS))


def notice_text(sq: Square, n: int, delete_on: dt.datetime, billing_url: str) -> tuple[str, str]:
    """The subject and plain text of reminder `n` (only the square's name and plain sentences)."""
    on = delete_on.strftime("%d %b %Y")
    first = {
        1: f"Your square {sq.name} has been asleep for about nine months and nothing has been paid for it.",
        2: f"Your square {sq.name} has been asleep for about eleven months and nothing has been paid for it.",
        3: f"Your square {sq.name} will be archived in one week.",
    }[n]
    lines = [
        first,
        "",
        f"On {on} it is archived: its database and files are deleted for good and the site cannot be woken again. Nothing is deleted before then.",
        "",
        "To keep it, pay for a Keep or Live period on your Billing page:",
        billing_url,
        "",
        "To keep a copy of your data first, wake the square (a Live period) and download it from the admin of your site, before that date.",
    ]
    return f"{sq.name}: archived on {on} unless you pay", "\n".join(lines) + "\n"


def run(
    db: Session,
    settings: Settings,
    now: dt.datetime | None = None,
    apply: bool = False,
    remind: Callable[[Session, Square, int, dt.datetime], bool] | None = None,
    archive: Callable[[Session, Square], None] | None = None,
) -> list[dict[str, Any]]:
    """One `reminder` (the next one due) or one `archive` per abandoned sleeping square. `remind(db, square, n, archive_date)` returns True when the e-mail
    was sent (only then is it recorded); `archive(db, square)` deletes the project at the provider (it raises when that fails, and the next run tries again).
    The archive step runs only with SLEEP_ARCHIVE_PURGE."""
    if not settings.BILLING_ENFORCE:
        return []
    now = now or dt.datetime.now(dt.UTC)
    actions: list[dict[str, Any]] = []
    rows = db.scalars(
        select(Square).where(
            Square.status == SquareStatus.READY,
            Square.sleep_state == "sleeping",
            Square.archived_at.is_(None),
            Square.running_plan != plans.EVENT_RUN,
        )
    ).all()
    t1, t2, t3 = thresholds(settings)
    for sq in rows:
        since = unpaid_since(sq)
        if since is None or (sq.paid_until is not None and _aware(sq.paid_until) > now):
            continue  # a paid period is running: not abandoned
        unpaid = (now - since).days
        notices = db.execute(select(AuditLog.at, AuditLog.data).where(AuditLog.action == NOTICE_ACTION, AuditLog.entity_id == str(sq.id)))
        sent = {int((d or {}).get("n", 0)): at for at, d in notices}
        nxt = next((n for n, t in ((1, t1), (2, t2), (3, t3)) if n not in sent and unpaid >= t), None)
        if nxt is not None:
            actions.append({"slug": sq.slug, "action": "reminder", "n": nxt})
            if apply and remind is not None and remind(db, sq, nxt, archive_date(sq, settings, now)):
                db.add(AuditLog(action=NOTICE_ACTION, entity="square", entity_id=str(sq.id), org_id=sq.org_id, data={"n": nxt}))
            continue
        last = sent.get(3)
        if unpaid >= settings.SLEEP_ARCHIVE_DAYS and last is not None and now - _aware(last) >= dt.timedelta(days=GAP_DAYS):
            actions.append({"slug": sq.slug, "action": "archive", "enabled": settings.SLEEP_ARCHIVE_PURGE})
            if apply and settings.SLEEP_ARCHIVE_PURGE and archive is not None:
                try:
                    archive(db, sq)
                except Exception as exc:  # noqa: BLE001 - audited by type only; the next run tries again
                    db.add(AuditLog(action=FAILED_ACTION, entity="square", entity_id=str(sq.id), org_id=sq.org_id, data={"error_type": type(exc).__name__}))
                    continue
                sq.archived_at = now
                db.add(AuditLog(action=ARCHIVED_ACTION, entity="square", entity_id=str(sq.id), org_id=sq.org_id, data={"slug": sq.slug}))
    if apply:
        db.flush()
    return actions
