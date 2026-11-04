"""Data side of the opex forecast (W16-R9 phase 2): the real revenue from billing orders, the owner's assumptions kept as platform settings."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import opex
from app.platform.models import BillingOrder, PlatformSetting, Square

CASH_KEY = "opex.cash"


def _key(scenario: str, field: str) -> str:
    return f"opex.{scenario}.{field}"


def observed(db: Session, now: dt.datetime | None = None) -> dict[str, int]:
    """What already renews: for every square whose running plan is paid up, the latest paid running order as a monthly amount."""
    now = now or dt.datetime.now(dt.UTC)
    total = 0
    squares = 0
    for sq in db.scalars(select(Square)):
        until = sq.paid_until
        if until is None or (until.replace(tzinfo=dt.UTC) if until.tzinfo is None else until) < now or sq.renewal_cancelled:
            continue
        order = db.scalars(
            select(BillingOrder)
            .where(BillingOrder.square_id == sq.id, BillingOrder.kind == "running", BillingOrder.status == "paid")
            .order_by(BillingOrder.paid_at.desc())
            .limit(1)
        ).first()
        if order is None:
            continue
        net = order.amount_minor - order.refunded_minor
        total += round(net / 12) if order.interval == "year" else net
        squares += 1
    return {"base_monthly": total, "squares": squares}


def actual_revenue(db: Session, year: int, month: int, back: int = 6) -> list[dict[str, Any]]:
    """Money really received (paid minus refunded) in each of the last `back` months before (year, month)."""
    first = opex.add_months(year, month, -back)
    start = dt.datetime(first[0], first[1], 1, tzinfo=dt.UTC)
    got = {opex.add_months(year, month, -n): 0 for n in range(back, 0, -1)}
    for o in db.scalars(select(BillingOrder).where(BillingOrder.paid_at.is_not(None), BillingOrder.paid_at >= start)):
        paid = o.paid_at
        if paid is None:
            continue
        k = (paid.year, paid.month)
        if k in got:
            got[k] += o.amount_minor - o.refunded_minor
    return [{"month": f"{y:04d}-{m:02d}", "revenue": v} for (y, m), v in got.items()]


def load_assumptions(db: Session) -> dict[str, Any]:
    rows = {r.key: r.value for r in db.scalars(select(PlatformSetting).where(PlatformSetting.key.like("opex.%")))}
    out: dict[str, Any] = {"opening_cash_minor": int(rows[CASH_KEY]) if CASH_KEY in rows else 0, "scenarios": {}}
    for name in opex.SCENARIOS:
        d = opex.DEFAULT_ASSUMPTIONS[name]
        arpu = rows.get(_key(name, "arpu"))
        out["scenarios"][name] = {
            "new_per_month": float(rows.get(_key(name, "new"), d["new"])),
            "churn_pct": float(rows.get(_key(name, "churn"), d["churn"])),
            "revenue_per_square_minor": int(arpu) if arpu not in (None, "") else None,  # None = the observed average
        }
    return out


def save_assumptions(db: Session, opening_cash_minor: int, scenarios: dict[str, dict[str, Any]]) -> None:
    values: dict[str, str] = {CASH_KEY: str(opening_cash_minor)}
    for name, s in scenarios.items():
        values[_key(name, "new")] = repr(float(s["new_per_month"]))
        values[_key(name, "churn")] = repr(float(s["churn_pct"]))
        values[_key(name, "arpu")] = "" if s.get("revenue_per_square_minor") is None else str(int(s["revenue_per_square_minor"]))
    for key, value in values.items():
        row = db.get(PlatformSetting, key)
        if row is None:
            db.add(PlatformSetting(key=key, value=value))
        else:
            row.value = value


def received_by_month(db: Session) -> tuple[dict[str, int], dict[str, int]]:
    """Money received (paid minus refunded) and the number of paid orders, per month ("YYYY-MM"), from every paid billing order."""
    revenue: dict[str, int] = {}
    orders: dict[str, int] = {}
    for o in db.scalars(select(BillingOrder).where(BillingOrder.paid_at.is_not(None))):
        paid = o.paid_at
        if paid is None:
            continue
        key = opex.month_key(paid.year, paid.month)
        revenue[key] = revenue.get(key, 0) + o.amount_minor - o.refunded_minor
        orders[key] = orders.get(key, 0) + 1
    return revenue, orders


def context(db: Session) -> opex.Context:
    from app.platform.models import OpexActual

    revenue, orders = received_by_month(db)
    actuals = {(a.item_id, a.month): a.amount_minor for a in db.scalars(select(OpexActual))}
    return opex.Context(revenue, orders, actuals)
