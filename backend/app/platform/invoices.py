"""The invoice of a paid order (W19-R16): one printable document per payment, built from what billing already stores.

What it is:   the seller's details (platform settings kept as data), the invoice number, and the period of a payment.
What it does: nothing is stored per invoice. The number counts the paid orders of the year in the order they were paid, so it never changes for a paid order;
              whether our own number series is required is for the accountant (docs/LEGAL_TODO.md), this is provisional.
How to use:   `app.platform.invoice_routes` serves it; the page is `frontend/platform/src/features/portal/InvoicePage.vue`.
Read before:  docs/reference/billing-and-payments.md, app/platform/billing.py (`tax_split`).
Read after:   app/platform/invoice_routes.py.
"""

from __future__ import annotations

import calendar
import datetime as dt

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.platform.models import BillingOrder, PlatformSetting

SELLER_FIELDS = ("name", "org_no", "address", "email", "prefix", "footer")
DEFAULT_PREFIX = "RS"
KEY = "invoice.{}"
INVOICED = ("paid", "refunded")  # a refunded payment keeps its invoice, with the refund shown


def get_seller(db: Session) -> dict[str, str]:
    """The seller's details as a platform admin set them; an empty value is not shown on the invoice (the prefix falls back to RS)."""
    rows = {r.key: r.value for r in db.scalars(select(PlatformSetting).where(PlatformSetting.key.like("invoice.%")))}
    out = {f: rows.get(KEY.format(f), "") for f in SELLER_FIELDS}
    out["prefix"] = out["prefix"] or DEFAULT_PREFIX
    return out


def set_seller(db: Session, values: dict[str, str]) -> None:
    for field in SELLER_FIELDS:
        key, value = KEY.format(field), (values.get(field) or "").strip()
        row = db.get(PlatformSetting, key)
        if row is None:
            db.add(PlatformSetting(key=key, value=value))
        else:
            row.value = value


def invoice_number(db: Session, order: BillingOrder, prefix: str) -> str:
    """`RS-2026-0007`: the 7th payment of 2026 (paid or refunded), counted in the order they were paid."""
    paid = order.paid_at or order.created_at
    year = paid.year
    start, end = dt.datetime(year, 1, 1, tzinfo=dt.UTC), dt.datetime(year + 1, 1, 1, tzinfo=dt.UTC)
    when = func.coalesce(BillingOrder.paid_at, BillingOrder.created_at)
    rank = db.scalar(
        select(func.count()).select_from(BillingOrder).where(
            BillingOrder.status.in_(INVOICED), when >= start, when < end,
            or_(when < paid, and_(when == paid, BillingOrder.id <= order.id)),
        )
    )  # fmt: skip
    return f"{prefix}-{year}-{int(rank or 1):04d}"


def period(order: BillingOrder) -> tuple[dt.date, dt.date] | None:
    """The first and last day a running payment pays for, counted from the day it was paid; None for a payment that is not for a period."""
    if order.interval not in ("month", "year") or order.paid_at is None:
        return None
    first = order.paid_at.date()
    months = 12 if order.interval == "year" else 1
    m = first.month - 1 + months
    y, m = first.year + m // 12, m % 12 + 1
    nxt = dt.date(y, m, min(first.day, calendar.monthrange(y, m)[1]))
    return first, nxt - dt.timedelta(days=1)
