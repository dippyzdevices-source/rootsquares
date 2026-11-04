"""Membership period generation — the only place MembershipPeriod rows are created. Called
from app/memberships/admin_routes.py whenever a Membership becomes active (see that file's
admin_create_membership and admin_update_membership).
"""

import calendar
from datetime import date, datetime, timezone

from sqlalchemy import func

from app.common.site import site_currency
from app.auth.models import User
from app.extensions import db
from app.members.models import FamilyMember, Member
from app.memberships.emails import send_membership_active_email
from app.memberships.models import Membership, MembershipPeriod, MembershipType, MembershipTypeChange
from app.payments.fees import snapshot_processing_fee
from app.payments.models import Payment, PaymentAllocation


CHILD_TYPE = "child"


def find_member_by_email(email: str) -> Member | None:
    """Reuses an existing roster entry instead of creating a duplicate — mirrors
    find_my_member's own linked-vs-unlinked preference (app/members/routes.py): prefer a member
    already linked to a real User whose current email matches (covers someone whose account
    email changed since they were imported or last signed up), falling back to an unlinked
    profile's own stored email column.
    """
    normalized = email.strip().lower()
    linked = (
        Member.query.join(User, Member.user_id == User.id)
        .filter(func.lower(User.email) == normalized)
        .first()
    )
    if linked is not None:
        return linked
    return Member.query.filter(
        Member.user_id.is_(None), func.lower(Member.email) == normalized
    ).first()


def _add_family_entry(owner: Member, name: str, relationship_type: str) -> None:
    exists = any(
        f.relationship_type == relationship_type and f.name.strip().lower() == name.strip().lower()
        for f in owner.family_members
    )
    if not exists:
        db.session.add(
            FamilyMember(
                member_id=owner.id,
                name=name,
                relationship_type=relationship_type,
                sort_order=len(owner.family_members),
            )
        )


def ensure_family_entry_for_child(child: Member) -> None:
    """Mirror the parent/child link both ways in the family-members lists: the parent gets a
    `child` entry and the child gets a `parent` entry (names only), unless already present.
    Caller commits."""
    parent = child.parent
    if parent is None:
        return
    _add_family_entry(parent, child.name, "child")
    _add_family_entry(child, parent.name, "parent")


def is_child_type(name: str | None) -> bool:
    """Type names are admin-entered, so compare case-insensitively ("Child" == "child")."""
    return (name or "").strip().lower() == CHILD_TYPE


def parent_adult_error(parent: Member | None) -> str | None:
    """A child's parent must hold an active, non-child membership (adult, or a legacy/internal
    type such as individual/family — not only the literal `adult` type, so members still on an
    older type can enrol children). None means OK."""
    if parent is None:
        return "No member found with this email."
    active_types = [
        m.membership_type
        for m in Membership.query.filter_by(member_id=parent.id, status="active").all()
    ]
    if not any(not is_child_type(t) for t in active_types):
        return "This parent has no active (adult) membership."
    return None


def child_membership_error(member: Member) -> str | None:
    """Rule for creating/activating a `child` membership: the member must be linked to a parent
    (Member.parent_member_id) who holds an active adult membership. None means OK."""
    if member.parent_member_id is None:
        return "A child membership needs a parent — set the member's parent email first."
    return parent_adult_error(db.session.get(Member, member.parent_member_id))


def expire_other_active_memberships(membership: Membership) -> None:
    """A member has at most one active membership: when `membership` is (or becomes) active,
    every other active one on the same member is moved to history — status `expired`, with
    `end_date` set to this one's start date if it had none. Call after the commit that made
    `membership` active.
    """
    others = Membership.query.filter(
        Membership.member_id == membership.member_id,
        Membership.status == "active",
        Membership.id != membership.id,
    ).all()
    for other in others:
        other.status = "expired"
        if other.end_date is None:
            other.end_date = membership.start_date
    if others:
        db.session.commit()


def membership_rule_error(member: Member, type_name: str) -> str | None:
    """Type-specific rules a membership must satisfy before it is created or activated for
    `member` (today: a child needs a parent with an active membership). None means OK."""
    return child_membership_error(member) if is_child_type(type_name) else None


def activate_membership(membership: Membership) -> None:
    """The one place "this membership is now active" side effects live: the member's other
    active memberships move to history, and this membership's billing periods are generated.
    Call after the commit that made it active (admin create/update, drive signup)."""
    expire_other_active_memberships(membership)
    generate_periods_for_membership(membership)


# --- Self-service requests: pay first, then active -------------------------------------------
# A member's own request creates a `pending` Membership with its periods already generated; the
# member pays the CURRENT period straight away, and the membership activates by itself once that
# payment is confirmed (admin confirm of a manual Vipps payment, or Vipps itself for Vipps App).
# Until then it is an "awaiting payment" request and stays out of the admin's approval lists.

# A payment in these states means the member has actually started/completed paying, so the
# request can no longer be swapped or dropped. (cancelled / failed attempts changed nothing.)
LIVE_PAYMENT_STATUSES = ("pending", "initiated", "paid", "refunded")


def awaiting_payment_clause():
    """SQL clause over `Membership`: a pending request that has periods to pay but no manual
    payment waiting for an admin (or already paid). Vipps App payments in flight ("initiated")
    count as still awaiting — Vipps confirms those automatically, nobody needs to review them.
    Pending rows with NO periods (older requests, or a contact-for-price type) are not covered
    on purpose: they still need an admin's approval and stay visible."""
    from sqlalchemy import and_

    has_periods = db.session.query(MembershipPeriod.id).filter(
        MembershipPeriod.membership_id == Membership.id
    ).exists()
    reported = (
        db.session.query(PaymentAllocation.id)
        .join(MembershipPeriod, PaymentAllocation.membership_period_id == MembershipPeriod.id)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(MembershipPeriod.membership_id == Membership.id, Payment.status.in_(("pending", "paid")))
        .exists()
    )
    return and_(Membership.status == "pending", has_periods, ~reported)


def is_awaiting_payment(membership: Membership) -> bool:
    """Python twin of awaiting_payment_clause() for a single, already-loaded membership."""
    if membership.status != "pending":
        return False
    periods = MembershipPeriod.query.filter_by(membership_id=membership.id).all()
    if not periods:
        return False
    reported = (
        db.session.query(PaymentAllocation.id)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(
            PaymentAllocation.membership_period_id.in_([p.id for p in periods]),
            Payment.status.in_(("pending", "paid")),
        )
        .first()
    )
    return reported is None


def has_live_payment(membership: Membership) -> bool:
    return (
        db.session.query(PaymentAllocation.id)
        .join(MembershipPeriod, PaymentAllocation.membership_period_id == MembershipPeriod.id)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .filter(
            MembershipPeriod.membership_id == membership.id,
            Payment.status.in_(LIVE_PAYMENT_STATUSES),
        )
        .first()
        is not None
    )


def discard_pending_request(membership: Membership) -> None:
    """Removes a pending request (and its periods) the member is replacing. Only call when
    has_live_payment() is False. Allocations left by cancelled/failed attempts go with it; the
    Payment rows themselves stay as history. Caller commits."""
    period_ids = [p.id for p in MembershipPeriod.query.filter_by(membership_id=membership.id).all()]
    if period_ids:
        PaymentAllocation.query.filter(PaymentAllocation.membership_period_id.in_(period_ids)).delete(
            synchronize_session=False
        )
        MembershipPeriod.query.filter(MembershipPeriod.id.in_(period_ids)).delete(synchronize_session=False)
    MembershipTypeChange.query.filter_by(membership_id=membership.id).delete(synchronize_session=False)
    db.session.delete(membership)


def activate_pending_memberships_after_payment(periods: list[MembershipPeriod]) -> list[Membership]:
    """Call after the commit that marked `periods` paid. A `pending` membership whose period was
    just paid becomes `active` through the normal activate_membership() path (other active
    memberships expire, the rest of the year's periods exist). While pending, only the current
    period can be paid (see payment_routes.start_my_payment), so any paid period means the member
    has paid up front. Returns the memberships that were activated."""
    activated = []
    for membership_id in {p.membership_id for p in periods}:
        membership = db.session.get(Membership, membership_id)
        if membership is not None and membership.status == "pending":
            membership.status = "active"
            db.session.commit()
            activate_membership(membership)
            send_membership_active_email(membership)
            activated.append(membership)
    return activated


def due_periods(membership: Membership, today: date | None = None) -> list[MembershipPeriod]:
    """Unpaid periods an admin may chase for an active membership: they have started, they didn't
    end before the membership did (periods are generated for the whole calendar year, so a member
    who joined in October is not "overdue" for January), and no manual payment for them is already
    waiting for confirmation. Oldest first."""
    today = today or date.today()
    reported = {
        period_id
        for (period_id,) in db.session.query(PaymentAllocation.membership_period_id)
        .join(Payment, PaymentAllocation.payment_id == Payment.id)
        .join(MembershipPeriod, PaymentAllocation.membership_period_id == MembershipPeriod.id)
        .filter(MembershipPeriod.membership_id == membership.id, Payment.status == "pending")
        .all()
    }
    return (
        MembershipPeriod.query.filter(
            MembershipPeriod.membership_id == membership.id,
            MembershipPeriod.status == "unpaid",
            MembershipPeriod.period_start <= today,
            MembershipPeriod.period_end >= membership.start_date,
            MembershipPeriod.id.notin_(reported) if reported else True,
        )
        .order_by(MembershipPeriod.period_start)
        .all()
    )


def _month_label(year: int, month: int) -> str:
    return date(year, month, 1).strftime("%B %Y")


def _monthly_periods(year: int, amount: int) -> list[dict]:
    periods = []
    for month in range(1, 13):
        last_day = calendar.monthrange(year, month)[1]
        periods.append(
            {
                "period_start": date(year, month, 1),
                "period_end": date(year, month, last_day),
                "label": _month_label(year, month),
                "amount": amount,
            }
        )
    return periods


def _quarterly_periods(year: int, amount: int) -> list[dict]:
    quarters = [(1, 3), (4, 6), (7, 9), (10, 12)]
    periods = []
    for index, (start_month, end_month) in enumerate(quarters, start=1):
        last_day = calendar.monthrange(year, end_month)[1]
        periods.append(
            {
                "period_start": date(year, start_month, 1),
                "period_end": date(year, end_month, last_day),
                "label": f"Q{index} {year}",
                "amount": amount,
            }
        )
    return periods


def _yearly_periods(year: int, amount: int) -> list[dict]:
    return [
        {
            "period_start": date(year, 1, 1),
            "period_end": date(year, 12, 31),
            "label": str(year),
            "amount": amount,
        }
    ]


def generate_periods_for_membership(membership: Membership) -> list[MembershipPeriod]:
    """Idempotent: safe to call more than once for the same membership. Never duplicates,
    never alters, an already-existing period's status or amount — even if the membership
    type's price has since changed. Returns only the newly created periods (empty list if
    nothing new was needed, including for a contact_for_price type, which never gets periods).
    """
    membership_type = db.session.get(MembershipType, membership.membership_type)
    if membership_type is None or membership_type.contact_for_price:
        return []

    year = membership.start_date.year
    amount = membership_type.price * 100  # whole NOK -> øre, once, at generation time

    if membership_type.billing_frequency == "yearly":
        specs = _yearly_periods(year, amount)
    elif membership_type.billing_frequency == "quarterly":
        specs = _quarterly_periods(year, amount)
    else:
        specs = _monthly_periods(year, amount)

    existing_starts = {
        p.period_start
        for p in MembershipPeriod.query.filter_by(membership_id=membership.id).all()
    }

    created = []
    for spec in specs:
        if spec["period_start"] in existing_starts:
            continue
        period = MembershipPeriod(membership_id=membership.id, **spec)
        db.session.add(period)
        created.append(period)

    if created:
        db.session.commit()

    return created


def resync_periods_after_type_change(membership: Membership, old_type: str | None) -> None:
    """Drops this membership's unpaid periods that no payment (pending or paid) touches — they
    belong to the old type's billing shape and would otherwise sit around as bogus "unpaid" rows
    (and block same-start-date periods of the new type) — then regenerates for the current type.
    Periods with any payment allocation are kept. Records a MembershipTypeChange when the type
    really changed. Also self-heals a membership already left in a mixed state (call with
    old_type == membership.membership_type: no history note is written).
    """
    allocated = db.session.query(PaymentAllocation.membership_period_id)
    stale = MembershipPeriod.query.filter(
        MembershipPeriod.membership_id == membership.id,
        MembershipPeriod.status == "unpaid",
        ~MembershipPeriod.id.in_(allocated),
    ).all()
    for period in stale:
        db.session.delete(period)
    if old_type and old_type != membership.membership_type:
        db.session.add(
            MembershipTypeChange(
                membership_id=membership.id, from_type=old_type, to_type=membership.membership_type
            )
        )
    db.session.commit()
    if membership.status == "active":
        generate_periods_for_membership(membership)


def current_period_for_date(membership: Membership, on: date) -> MembershipPeriod | None:
    """The single MembershipPeriod (of the membership's full generated set) whose date range
    covers `on` — e.g. "this month" for a monthly type, "this quarter" for quarterly, "this
    year" for yearly. None for a contact_for_price type (no periods exist at all).
    """
    return (
        MembershipPeriod.query.filter(
            MembershipPeriod.membership_id == membership.id,
            MembershipPeriod.period_start <= on,
            MembershipPeriod.period_end >= on,
        )
        .first()
    )


def complete_membership_payment_immediately(
    periods: list[MembershipPeriod], *, provider: str
) -> Payment | None:
    """Marks every given period paid via one new, already-`paid` Payment row — no external
    provider call, no pending/webhook wait. Shared by FakeOnlinePaymentProvider (Phase 1 tests,
    which stand in for a real Vipps/Stripe completion) and the membership drive's volunteer-
    confirmed "mark as paid" action (real production use, a manual-approval method such as "vipps_qr" — the volunteer's
    own tap IS the confirmation, same philosophy as the ticket side's ManualPaymentProvider).
    Returns None if `periods` is empty (nothing to charge — e.g. a contact_for_price type).
    """
    if not periods:
        return None

    total = sum(p.amount for p in periods)
    paid_at = datetime.now(timezone.utc)
    payment = Payment(
        payment_type="membership", provider=provider, amount=total, currency=site_currency(),
        status="paid", paid_at=paid_at,
    )
    snapshot_processing_fee(payment)
    db.session.add(payment)
    db.session.flush()
    payment.payment_reference = f"PAY-{payment.created_at.year}-{payment.id:06d}"

    for period in periods:
        db.session.add(
            PaymentAllocation(
                payment_id=payment.id, membership_period_id=period.id, amount=period.amount
            )
        )
        period.status = "paid"
        period.paid_at = paid_at

    db.session.commit()
    return payment
