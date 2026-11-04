"""The trial-end job (W12-R9) and the day-6 reminder (W12-R14), docs/plans/pricing-strategy.md, guide 22 section 10: a launch package gets 7 days of
Live free; when the paid time has run out and nobody paid, the site goes to sleep (Keep; nothing is deleted) and wakes when the owner pays.
A period that was paid for gets the grace days first.
Only with BILLING_ENFORCE=true (otherwise Live is free and nothing is put to sleep). Dry run by default, like the Event pass job."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import billing, plans
from app.platform.models import AuditLog, Square, SquareStatus
from app.shared.config import Settings

REMINDER_ACTION = "billing.trial_reminder"
LAPSED_ACTION = "billing.lapsed"
ASLEEP_ACTION = "billing.asleep_notice"  # recorded once the owner was told, so a missing e-mail service is retried (W13-R30)
PLAN_ACTION = "billing.plan_applied"  # a downgrade the owner chose started (with a renewal, or with the daily job), W18-R34
PLAN_NOTICE_ACTION = "billing.plan_notice"  # the owner was told that Keep started; the entry is the id of the `billing.plan_applied` it answers
NOTICE_DAYS = 14  # a square put to sleep longer ago than this is no longer told


def _package_name(pkg: str) -> str:
    """The package as a customer reads it (the base package is called Root; its id stays `roots`)."""
    return {"roots": "Root"}.get(pkg, pkg.title())


def _usd(minor: int) -> str:
    return f"${minor / 100:,.2f}"


def _reminded(db: Session, sq: Square) -> bool:
    return db.scalar(select(AuditLog.id).where(AuditLog.action == REMINDER_ACTION, AuditLog.entity_id == str(sq.id)).limit(1)) is not None


def reminder_text(db: Session, settings: Settings, sq: Square) -> tuple[str, str]:
    """The subject and plain text of the reminder: when the trial ends, what the first payment is, what happens otherwise (only the square's name)."""
    pkg = sq.launch_package or ""
    package, month = (
        billing.price_or_none(db, f"launch.{pkg}"),
        billing.price_or_none(db, f"running.{plans.LIVE}.month"),
    )  # none = not set yet: the text then names no amount
    ends = _aware(sq.paid_until) if sq.paid_until else None
    when = ends.strftime("%d %b %Y") if ends else "soon"
    link = f"{settings.PLATFORM_FRONTEND_URL.rstrip('/')}/squares/{sq.id}/billing"
    subject = f"Your rootsquares trial for {sq.name} ends on {when}"
    lines = [
        f"Your free trial of {sq.name} ends on {when}.",
        "",
        (
            f"To keep the site live, pay the {_package_name(pkg)} launch package ({_usd(package)}) "
            f"and your first Live month ({_usd(month)}) on your Billing page:"
            if package is not None and month is not None
            else f"To keep the site live, pay the {_package_name(pkg)} launch package and your first Live month on your Billing page:"
        ),
        link,
        "",
        "If you do not pay, the site goes to sleep when the trial ends. Nothing is deleted, and it wakes up as soon as you pay.",
    ]
    body = "\n".join(lines) + "\n"
    return subject, body


def _aware(value: dt.datetime) -> dt.datetime:
    return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value


def run(
    db: Session,
    settings: Settings,
    now: dt.datetime | None = None,
    apply: bool = False,
    sleep: Callable[[Session, Square], None] | None = None,
    remind: Callable[[Session, Square], bool] | None = None,
    notify: Callable[[Session, Square, str], bool] | None = None,
    notify_keep: Callable[[Session, Square, str], bool] | None = None,
) -> list[dict[str, Any]]:
    """Squares whose Live time has ended without payment: one `sleep` action each (the caller puts the square to sleep and starts the provider pause).
    A trial with `BILLING_TRIAL_REMINDER_HOURS` or fewer left gets one `reminder` (`remind` returns True when the e-mail was sent; only then is it recorded).
    A square that was put to sleep gets one `asleep_notice` (`notify(db, square, reason)` returns True when sent; only then is it recorded, so it is retried
    until e-mail works, for `NOTICE_DAYS` days, and never for a square the owner has already woken)."""
    if not settings.BILLING_ENFORCE:
        return []
    now = now or dt.datetime.now(dt.UTC)
    actions: list[dict[str, Any]] = []
    rows = db.scalars(
        select(Square)
        .where(
            Square.launch_package.in_(billing.UPGRADE_ORDER),
            Square.running_plan == plans.LIVE,
            Square.status == SquareStatus.READY,
            Square.paid_until.is_not(None),
        )
        .order_by(Square.created_at)
    ).all()
    for sq in rows:
        if (sq.sleep_state or "awake") != "awake" or sq.paid_until is None:
            continue
        if sq.pending_running_plan == plans.KEEP and _aware(sq.paid_until) <= now:
            # A downgrade the owner chose (W18-R34): the paid time is over and no renewal brought it, so the square goes to Keep now, with no grace days
            # and no "lapsed" notice; the plan is Keep from here.
            actions.append({"slug": sq.slug, "action": "sleep", "reason": "plan_change"})
            if apply and sleep is not None:
                sq.running_plan = plans.KEEP
                sq.pending_running_plan = None
                sleep(db, sq)
                db.add(AuditLog(action="billing.plan_applied", entity="square", entity_id=str(sq.id), org_id=sq.org_id, data={"running_plan": plans.KEEP}))
            continue
        trial = billing.first_payment_due(db, sq)
        ends = _aware(sq.paid_until) + (dt.timedelta(0) if trial else dt.timedelta(days=settings.BILLING_GRACE_DAYS))
        if now < ends:
            if trial and ends - now <= dt.timedelta(hours=settings.BILLING_TRIAL_REMINDER_HOURS) and not _reminded(db, sq):
                actions.append({"slug": sq.slug, "action": "reminder"})
                if apply and remind is not None and remind(db, sq):
                    db.add(AuditLog(action=REMINDER_ACTION, entity="square", entity_id=str(sq.id), org_id=sq.org_id, data={}))
            continue
        actions.append({"slug": sq.slug, "action": "sleep", "reason": "trial_ended" if trial else "not_renewed"})
        if apply and sleep is not None:
            sleep(db, sq)
            db.add(AuditLog(action=LAPSED_ACTION, entity="square", entity_id=str(sq.id), org_id=sq.org_id, data={"reason": actions[-1]["reason"]}))
    if apply:
        db.flush()
        if notify is not None:
            actions += _send_asleep_notices(db, now, notify)
        if notify_keep is not None:
            actions += send_keep_notices(db, now, notify_keep)
    return actions


def _send_asleep_notices(db: Session, now: dt.datetime, notify: Callable[[Session, Square, str], bool]) -> list[dict[str, Any]]:
    """The owners of squares that were put to sleep for lack of payment (a `billing.lapsed` entry in the last NOTICE_DAYS days) and not told yet."""
    since = now - dt.timedelta(days=NOTICE_DAYS)
    lapsed = db.execute(select(AuditLog.entity_id, AuditLog.data).where(AuditLog.action == LAPSED_ACTION, AuditLog.at >= since.replace(tzinfo=None))).all()
    told = set(db.scalars(select(AuditLog.entity_id).where(AuditLog.action == ASLEEP_ACTION)))
    sent: list[dict[str, Any]] = []
    for entity_id, data in lapsed:
        if entity_id in told:
            continue
        sq = db.get(Square, uuid.UUID(entity_id))
        if sq is None or (sq.sleep_state or "awake") == "awake":
            continue  # gone, or the owner already woke it
        reason = str((data or {}).get("reason") or "not_renewed")
        if notify(db, sq, reason):
            db.add(AuditLog(action=ASLEEP_ACTION, entity="square", entity_id=entity_id, org_id=sq.org_id, data={"reason": reason}))
            sent.append({"slug": sq.slug, "action": "asleep_notice"})
    return sent


def send_keep_notices(db: Session, now: dt.datetime, notify: Callable[[Session, Square, str], bool]) -> list[dict[str, Any]]:
    """The owners of squares whose chosen downgrade has started (a `billing.plan_applied` entry for Keep in the last NOTICE_DAYS days), not told yet (W18-R34).
    `notify(db, square, reason)` returns True when the e-mail was sent; only then is it recorded, so it is retried until e-mail works, and never for a square
    that has gone back to Live."""
    since = now - dt.timedelta(days=NOTICE_DAYS)
    applied = db.execute(
        select(AuditLog.id, AuditLog.entity_id, AuditLog.data).where(AuditLog.action == PLAN_ACTION, AuditLog.at >= since.replace(tzinfo=None))
    ).all()
    told = set(db.scalars(select(AuditLog.entity_id).where(AuditLog.action == PLAN_NOTICE_ACTION)))
    sent: list[dict[str, Any]] = []
    for entry_id, entity_id, data in applied:
        if str(entry_id) in told or (data or {}).get("running_plan") != plans.KEEP:
            continue
        sq = db.get(Square, uuid.UUID(entity_id))
        if sq is None or sq.running_plan != plans.KEEP:
            continue  # gone, or the owner already went back to Live
        if notify(db, sq, "plan_change"):
            db.add(AuditLog(action=PLAN_NOTICE_ACTION, entity="audit", entity_id=str(entry_id), org_id=sq.org_id, data={}))
            sent.append({"slug": sq.slug, "action": "keep_notice"})
    return sent


def keep_started_text(db: Session, settings: Settings, sq: Square) -> tuple[str, str]:
    """The subject and plain text of the notice that the plan is now Keep (only the square's name and plain sentences; the price only when it is set)."""
    interval = billing.subscription_interval(db, sq)
    price = billing.price_or_none(db, f"running.{plans.KEEP}.{interval}")
    ends = _aware(sq.paid_until) if sq.paid_until else None
    when = ends.strftime("%d %b %Y") if ends else ""
    renews = bool(sq.stripe_subscription_id) and not sq.renewal_cancelled
    link = f"{settings.PLATFORM_FRONTEND_URL.rstrip('/')}/squares/{sq.id}/billing"
    lines = [
        f"The plan of {sq.name} is now Keep, as you chose.",
        "",
        "The site is asleep: visitors see a back-soon page with your contact details and nobody can sign in until it wakes. Nothing has been deleted.",
    ]
    if price is not None:
        lines += ["", f"Keep costs {_usd(price)} a {'year' if interval == 'year' else 'month'}" + (f" and renews on {when}." if renews and when else ".")]
    lines += [
        "",
        "To wake the site, choose Live on your Billing page. You then pay the Live price for the rest of the period, less the Keep time you have already paid:",
        link,
        "",
        "If you do nothing, Keep carries on.",
    ]
    return f"{sq.name} is now on Keep", "\n".join(lines) + "\n"


def asleep_text(settings: Settings, sq: Square, reason: str) -> tuple[str, str]:
    """The subject and plain text of the notice that a square is asleep (only the square's name and plain sentences)."""
    link = f"{settings.PLATFORM_FRONTEND_URL.rstrip('/')}/squares/{sq.id}/billing"
    first = (
        f"Your free trial of {sq.name} has ended and no payment was made, so the site is now asleep."
        if reason == "trial_ended"
        else f"The last payment for {sq.name} did not go through, so the site is now asleep."
    )
    lines = [
        first,
        "",
        "Visitors see a back-soon page and nobody can sign in until it wakes. Nothing has been deleted.",
        "",
        "To wake it up, pay on your Billing page:",
        link,
        "",
        "It wakes up as soon as the payment succeeds.",
    ]
    return f"{sq.name} is now asleep", "\n".join(lines) + "\n"
