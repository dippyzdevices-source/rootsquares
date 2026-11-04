"""Vouchers: a code that lowers the price of one payment (W14-R27, docs/reference/prices-and-vouchers.md).

A voucher lowers a launch package (first payment, upgrade, upgrade from an Event pass) or a new Event pass, once. It never lowers a running period on its
own, and never the Live period inside a first payment (that is the renewing subscription's price). A use is a paid order that carries the voucher, so the
counts are always read from `billing_orders`; nothing is stored twice. `amount_minor` of the order stays what is charged.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.platform import plans
from app.platform.models import BillingOrder, BillingOrderVoucher, PlatformSetting, Square, Voucher
from app.shared.errors import ConflictError

CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,39}$")
KINDS = ("percent", "fixed")
APPLIES_TO = ("all", "launch", "event_pass")
LAUNCH_PACKAGES = (plans.ROOTS, plans.SQUARE, plans.GROVE)
# which scope of voucher a payment kind belongs to; a running period alone has none
KIND_SCOPE = {"first": "launch", "upgrade": "launch", "event_upgrade": "launch", "event_pass": "event_pass"}


class VoucherRejected(ConflictError):
    """The code cannot be used for this payment. `code` says why (voucher_unknown, voucher_expired, ...); the message is for the customer."""


def normalize_code(raw: str | None) -> str:
    return re.sub(r"\s+", "", (raw or "")).upper()


@dataclass(frozen=True)
class Applied:
    voucher: Voucher
    list_minor: int  # the whole price of the payment before the voucher
    discount_minor: int
    payable_minor: int  # what is charged


def base_minor(kind: str, list_minor: int, launch_minor: int) -> int:
    """The part of a payment a voucher may lower.

    The package part of a first payment, the whole of an upgrade or an Event pass, nothing for a running period.
    """
    if kind == "first":
        return min(launch_minor, list_minor)
    if kind in ("upgrade", "event_upgrade", "event_pass"):
        return list_minor
    return 0


def discount_for(voucher: Voucher, base: int) -> int:
    if base <= 0:
        return 0
    raw = (base * voucher.value + 50) // 100 if voucher.kind == "percent" else voucher.value
    return max(0, min(raw, base))


def used_by(voucher_id: uuid.UUID) -> ColumnElement[bool]:
    """The orders that used a voucher, as main or stacked one (orders from before stacking only have `voucher_id`)."""
    stacked = select(BillingOrderVoucher.order_id).where(BillingOrderVoucher.voucher_id == voucher_id)
    return or_(BillingOrder.voucher_id == voucher_id, BillingOrder.id.in_(stacked))


def voucher_orders_stmt(voucher_id: uuid.UUID) -> Any:
    """Paid orders that used a voucher, each with the discount THIS voucher gave (an order with two vouchers splits its discount)."""
    own = BillingOrderVoucher
    return (
        select(BillingOrder, func.coalesce(own.discount_minor, BillingOrder.discount_minor).label("given"))
        .outerjoin(own, and_(own.order_id == BillingOrder.id, own.voucher_id == voucher_id))
        .where(used_by(voucher_id), BillingOrder.status == "paid")
    )


def paid_uses(db: Session, voucher_id: uuid.UUID) -> int:
    return int(db.scalar(select(func.count(BillingOrder.id)).where(used_by(voucher_id), BillingOrder.status == "paid")) or 0)


def _org_paid_orders(db: Session, org_id: uuid.UUID, voucher_id: uuid.UUID | None = None) -> int:
    stmt = select(func.count(BillingOrder.id)).join(Square, Square.id == BillingOrder.square_id).where(Square.org_id == org_id, BillingOrder.status == "paid")
    stmt = stmt.where(used_by(voucher_id)) if voucher_id else stmt.where(BillingOrder.amount_minor > 0)
    return int(db.scalar(stmt) or 0)


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=dt.UTC)


def find(db: Session, code: str) -> Voucher | None:
    return db.scalar(select(Voucher).where(Voucher.code == normalize_code(code)))


def evaluate(
    db: Session, code: str, *, kind: str, package: str | None, org_id: uuid.UUID, list_minor: int, launch_minor: int = 0, now: dt.datetime | None = None
) -> Applied:
    """The discount a code gives to this payment, or VoucherRejected. Nothing is written."""
    now = now or dt.datetime.now(dt.UTC)
    voucher = find(db, code)
    if voucher is None:
        raise VoucherRejected("This code is not valid.", code="voucher_unknown")
    if not voucher.active:
        raise VoucherRejected("This code is not valid any more.", code="voucher_inactive")
    if (start := _aware(voucher.valid_from)) is not None and now < start:
        raise VoucherRejected("This code cannot be used yet.", code="voucher_not_started")
    if (end := _aware(voucher.valid_until)) is not None and now > end:
        raise VoucherRejected("This code has expired.", code="voucher_expired")
    scope = KIND_SCOPE.get(kind)
    if scope is None:
        raise VoucherRejected(
            "A voucher cannot be used for a monthly or yearly plan on its own. It lowers a launch package or an Event pass.", code="voucher_not_for_running"
        )
    if voucher.applies_to not in ("all", scope):
        raise VoucherRejected("This code is not for this kind of payment.", code="voucher_not_for_this")
    if scope == "launch" and voucher.packages and package not in voucher.packages:
        raise VoucherRejected("This code is not for this package.", code="voucher_not_for_this")
    if voucher.max_uses is not None and paid_uses(db, voucher.id) >= voucher.max_uses:
        raise VoucherRejected("This code has been used up.", code="voucher_used_up")
    if voucher.once_per_org and _org_paid_orders(db, org_id, voucher.id) > 0:
        raise VoucherRejected("Your organisation has already used this code.", code="voucher_already_used")
    if voucher.new_customers_only and _org_paid_orders(db, org_id) > 0:
        raise VoucherRejected("This code is for new customers only.", code="voucher_new_customers_only")
    base = base_minor(kind, list_minor, launch_minor)
    discount = discount_for(voucher, base)
    if discount <= 0:
        raise VoucherRejected("This code gives nothing off this payment.", code="voucher_nothing_to_discount")
    return Applied(voucher=voucher, list_minor=list_minor, discount_minor=discount, payable_minor=list_minor - discount)


def apply_to_order(db: Session, order: BillingOrder, code: str, org_id: uuid.UUID, launch_minor: int = 0) -> Applied:
    """Lower an order that was just made (not paid yet): the order keeps the price before, the discount and the code; `amount_minor` becomes what is charged."""
    applied = evaluate(db, code, kind=order.kind, package=order.launch_package, org_id=org_id, list_minor=order.amount_minor, launch_minor=launch_minor)
    order.list_minor = applied.list_minor
    order.discount_minor = applied.discount_minor
    order.amount_minor = applied.payable_minor
    order.voucher_id = applied.voucher.id
    order.voucher_code = applied.voucher.code
    return applied


# ---- several codes on one payment (W15-R19) ------------------------------------------------------------------------------------
# How codes combine is data on the platform (`platform_settings`, owner console Vouchers): `best` = several codes may be typed but only the one that
# lowers the price most is used (the default); `sequential` = codes marked "can be combined" apply one after the other, each on what is left;
# `additive` = they apply to the same price and add up. `voucher_max_codes` caps how many may be typed. Nothing is stored twice: the order keeps
# its main voucher in `voucher_id` and one `billing_order_vouchers` row per voucher used.
STACK_BEST, STACK_SEQUENTIAL, STACK_ADDITIVE = "best", "sequential", "additive"
STACKING_MODES = (STACK_BEST, STACK_SEQUENTIAL, STACK_ADDITIVE)
SETTING_MODE, SETTING_MAX = "voucher_stacking", "voucher_max_codes"
DEFAULT_MODE, DEFAULT_MAX, MAX_CODES_LIMIT = STACK_BEST, 2, 5


def get_stacking(db: Session) -> tuple[str, int]:
    """(mode, most codes on one payment) as set by a platform admin; the defaults when nothing was set or a stored value is not understood."""
    rows = {r.key: r.value for r in db.scalars(select(PlatformSetting).where(PlatformSetting.key.in_((SETTING_MODE, SETTING_MAX))))}
    mode = rows.get(SETTING_MODE, DEFAULT_MODE)
    try:
        most = int(rows.get(SETTING_MAX, DEFAULT_MAX))
    except ValueError:
        most = DEFAULT_MAX
    return (mode if mode in STACKING_MODES else DEFAULT_MODE), max(1, min(most, MAX_CODES_LIMIT))


def set_stacking(db: Session, mode: str, most: int) -> None:
    for key, value in ((SETTING_MODE, mode), (SETTING_MAX, str(most))):
        row = db.get(PlatformSetting, key)
        if row is None:
            db.add(PlatformSetting(key=key, value=value))
        else:
            row.value = value


def split_codes(raw: str | None) -> list[str]:
    """The codes in what was typed (separated by spaces, commas, semicolons or plus signs), upper case, each once, in the order typed."""
    return list(dict.fromkeys(c for c in re.split(r"[\s,;+]+", (raw or "").upper()) if c))


@dataclass(frozen=True)
class AppliedMany:
    applied: list[Applied]  # the vouchers used, each with the discount it gave
    ignored: list[tuple[str, str]]  # (code, why) typed but not used
    list_minor: int
    discount_minor: int
    payable_minor: int
    mode: str

    @property
    def voucher(self) -> Voucher:
        """The main voucher: the first one of a partner when there is one (the partner is credited), else the first used."""
        return next((a.voucher for a in self.applied if a.voucher.partner_id), self.applied[0].voucher)

    @property
    def codes(self) -> str:
        return " ".join(a.voucher.code for a in self.applied)


def evaluate_codes(
    db: Session, raw: str, *, kind: str, package: str | None, org_id: uuid.UUID, list_minor: int, launch_minor: int = 0, now: dt.datetime | None = None
) -> AppliedMany:
    """What the typed code or codes take off this payment, or VoucherRejected. Every typed code must be valid; nothing is written."""
    codes = split_codes(raw)
    if not codes:
        raise VoucherRejected("Enter a code.", code="voucher_unknown")
    mode, most = get_stacking(db)
    if len(codes) > most:
        raise VoucherRejected(f"At most {most} code{'s' if most != 1 else ''} can be used on one payment.", code="voucher_too_many")
    each = [evaluate(db, c, kind=kind, package=package, org_id=org_id, list_minor=list_minor, launch_minor=launch_minor, now=now) for c in codes]
    if len(each) == 1:
        one = each[0]
        return AppliedMany([one], [], one.list_minor, one.discount_minor, one.payable_minor, mode)
    if mode == STACK_BEST:
        best = max(each, key=lambda a: a.discount_minor)  # the first one typed wins a tie
        others = [(a.voucher.code, "Not used: another code takes more off.") for a in each if a is not best]
        return AppliedMany([best], others, best.list_minor, best.discount_minor, best.payable_minor, mode)
    blocked = [a.voucher.code for a in each if not a.voucher.stackable]
    if blocked:
        raise VoucherRejected(f"{', '.join(blocked)} cannot be combined with another code.", code="voucher_not_stackable")
    base = base_minor(kind, list_minor, launch_minor)
    used: list[Applied] = []
    ignored: list[tuple[str, str]] = []
    left = base  # what the codes may still take off
    for a in each:
        wanted = discount_for(a.voucher, left if mode == STACK_SEQUENTIAL else base)
        given = min(wanted, left)
        if given <= 0:
            ignored.append((a.voucher.code, "Not used: nothing is left to take off."))
            continue
        left -= given
        used.append(Applied(voucher=a.voucher, list_minor=list_minor, discount_minor=given, payable_minor=list_minor - given))
    total = sum(a.discount_minor for a in used)
    return AppliedMany(used, ignored, list_minor, total, list_minor - total, mode)


def apply_codes_to_order(db: Session, order: BillingOrder, raw: str, org_id: uuid.UUID, launch_minor: int = 0) -> AppliedMany:
    """Like `apply_to_order` for one or more codes: the order keeps the price before, the discount, every code, and one row per voucher used."""
    result = evaluate_codes(db, raw, kind=order.kind, package=order.launch_package, org_id=org_id, list_minor=order.amount_minor, launch_minor=launch_minor)
    order.list_minor = result.list_minor
    order.discount_minor = result.discount_minor
    order.amount_minor = result.payable_minor
    order.voucher_id = result.voucher.id
    order.voucher_code = result.codes
    db.flush()
    for position, a in enumerate(result.applied):
        db.add(BillingOrderVoucher(order_id=order.id, voucher_id=a.voucher.id, code=a.voucher.code, discount_minor=a.discount_minor, position=position))
    return result
