"""The owner console's Subscriptions page (W12-R20): money and plan state of every square, read from the platform's own tables only (orders, plans, dates).
Nothing here comes from a square's content (ADR 038). USD, integer minor units."""

from __future__ import annotations

import dataclasses
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import billing, plans
from app.platform.models import BillingOrder, Square

PACKAGES = (plans.ROOTS, plans.SQUARE, plans.GROVE, plans.EVENT)
RUNNING = (plans.LIVE, plans.KEEP)


@dataclasses.dataclass
class Upcoming:
    square_id: str
    name: str
    slug: str
    state: str  # trial | unpaid | renewing | ending | failed | asleep | paid | expired
    paid_until: dt.datetime | None
    next_minor: int  # what the next payment will be (0 when none is expected)
    package: str


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    return value.replace(tzinfo=dt.UTC) if value is not None and value.tzinfo is None else value


def overview(db: Session, now: dt.datetime | None = None) -> dict[str, object]:
    now = now or dt.datetime.now(dt.UTC)
    prices = {p.key: p.amount_minor for p in billing.list_prices(db)}
    squares = list(db.scalars(select(Square).where(Square.launch_package.is_not(None)).order_by(Square.created_at)))
    orders = list(db.scalars(select(BillingOrder).where(BillingOrder.status == "paid")))
    first_paid = {o.square_id for o in orders if o.kind == "first"}
    paid_30d = sum(o.amount_minor for o in orders if (_aware(o.paid_at) or now) >= now - dt.timedelta(days=30))

    rows: list[Upcoming] = []
    mrr = 0
    counts: dict[str, int] = {"paying": 0, "trial": 0, "failed": 0, "asleep": 0}
    for sq in squares:
        pkg = sq.launch_package or ""
        if pkg == plans.EVENT:
            continue
        until = _aware(sq.paid_until)
        live = until is not None and until > now
        interval = sq.billing_interval or "month"
        per_period = prices.get(f"running.{sq.running_plan}.{interval}", 0)
        due = sq.id not in first_paid and pkg in billing.UPGRADE_ORDER
        if sq.payment_failed_at is not None:
            state = "failed"
        elif (sq.sleep_state or "awake") != "awake" or sq.running_plan == plans.KEEP:
            state = "asleep"
        elif due and live:
            state = "trial"
        elif due:
            state = "unpaid"
        elif sq.stripe_subscription_id and sq.renewal_cancelled:
            state = "ending"
        elif sq.stripe_subscription_id:
            state = "renewing"
        else:
            state = "paid" if live else "expired"
        next_minor = prices.get(f"launch.{pkg}", 0) + prices.get(f"running.live.{interval}", 0) if due else (0 if state == "ending" else per_period)
        if state in ("renewing", "failed") and sq.stripe_subscription_id:
            monthly = per_period / 12 if interval == "year" else per_period
            mrr += int(monthly)
        if state in ("renewing", "ending", "paid", "failed"):
            counts["paying"] += 1
        counts["trial"] += state == "trial"
        counts["failed"] += state == "failed"
        counts["asleep"] += state == "asleep"
        rows.append(Upcoming(str(sq.id), sq.name, sq.slug, state, until, next_minor, pkg))

    package_rows = [{"key": k, "count": sum(1 for s in squares if s.launch_package == k), "price_minor": prices.get(f"launch.{k}", 0)} for k in PACKAGES]
    running_rows = [
        {
            "key": k,
            "count": sum(1 for s in squares if s.running_plan == k and s.launch_package != plans.EVENT),
            "price_minor": prices.get(f"running.{k}.month", 0),
        }
        for k in RUNNING
    ]
    upcoming = sorted((r for r in rows if r.paid_until is not None), key=lambda r: r.paid_until or now)
    return {
        "mrr_minor": mrr,
        "paid_30d_minor": paid_30d,
        "paying": counts["paying"],
        "trial": counts["trial"],
        "failed": counts["failed"],
        "asleep": counts["asleep"],
        "packages": package_rows,
        "running": running_rows,
        "upcoming": [dataclasses.asdict(r) for r in upcoming[:12]],
    }
