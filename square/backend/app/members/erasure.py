"""GDPR erase = anonymise (W14-R3). Rows are never deleted: counts, amounts and the accounting record stay.

Two triggers: a person asks (an admin records the request, 30 days grace, then `process_erase_requests`) and the
retention period ends (`anonymise_old_orders`: buyer fields of orders after DATA_RETENTION_YEARS full accounting years,
default 5; ADR 018, UNVERIFIED until an accountant confirms). Both are idempotent and carry no personal data in logs.
"""

import logging
import os

import requests
from datetime import datetime, timedelta, timezone

from flask import g
from sqlalchemy import func, or_

from app.auth.models import User
from app.donations.models import Donation
from app.extensions import db
from app.members.models import Member
from app.messages.models import MessageRecipient
from app.newsletter.models import Subscriber
from app.orders.models import Order

logger = logging.getLogger(__name__)

GRACE_DAYS = 30
ERASED_NAME = "Erased person"
ERASED_DOMAIN = "erased.invalid"


def retention_years() -> int:
    try:
        return max(1, int(os.environ.get("DATA_RETENTION_YEARS", "5")))
    except ValueError:
        return 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def request_erase(member: Member) -> None:
    """Start the grace period and block sign-in at once."""
    if member.erased_at is not None or member.erase_requested_at is not None:
        return
    member.erase_requested_at = _now()
    if member.user_id:
        user = db.session.get(User, member.user_id)
        if user is not None:
            user.disabled_at = _now()
    db.session.commit()


def cancel_erase(member: Member) -> bool:
    if member.erased_at is not None or member.erase_requested_at is None:
        return False
    member.erase_requested_at = None
    if member.user_id:
        user = db.session.get(User, member.user_id)
        if user is not None:
            user.disabled_at = None
    db.session.commit()
    return True


def _anonymise_order(order: Order) -> None:
    order.customer_name = ERASED_NAME
    order.customer_email = f"erased-order-{order.id}@{ERASED_DOMAIN}"
    order.customer_phone = None


def _anonymise_donation(donation: Donation) -> None:
    donation.donor_name = ERASED_NAME
    donation.donor_email = f"erased-donation-{donation.id}@{ERASED_DOMAIN}"
    donation.message = None


def delete_provider_account(auth_user_id: str, auth_provider: str) -> bool:
    """Removes the person's sign-in at the square's own sign-in project (W15-R8), so the e-mail or Google link is gone there too.

    Supabase only: its admin API with the square's service key. Neon Auth has no such call wired yet, so nothing happens there. Best effort: a failure is
    logged without personal data and never undoes the anonymisation. Off with ERASE_DELETE_PROVIDER_ACCOUNT=false. Returns True when the account is gone."""
    if os.environ.get("ERASE_DELETE_PROVIDER_ACCOUNT", "true").strip().lower() in ("0", "false", "no", "off"):
        return False
    tenant = g.get("tenant") if g else None
    if tenant is None or auth_provider != "supabase" or not tenant.auth_url or not tenant.storage_key or not auth_user_id:
        return False
    try:
        response = requests.delete(
            f"{tenant.auth_url}/auth/v1/admin/users/{auth_user_id}",
            headers={"apikey": tenant.storage_key, "Authorization": f"Bearer {tenant.storage_key}"},
            timeout=10,
        )
    except requests.RequestException:
        logger.warning("Could not reach the sign-in project to remove an erased account")
        return False
    if response.status_code in (200, 204, 404):  # 404 = already gone
        return True
    logger.warning("The sign-in project refused to remove an erased account (status %s)", response.status_code)
    return False


def anonymise_member(member: Member) -> None:
    """Strip every personal field of the person, their account, orders and newsletter rows; keep the rows."""
    user = db.session.get(User, member.user_id) if member.user_id else None
    emails = {e.strip().lower() for e in (member.email, user.email if user else None) if e}

    orders = Order.query.filter(
        or_(
            Order.user_id == user.id if user else False,
            func.lower(Order.customer_email).in_(emails) if emails else False,
        )
    ).all()
    for order in orders:
        _anonymise_order(order)
    if emails:
        for row in MessageRecipient.query.filter(func.lower(MessageRecipient.email).in_(emails)).all():
            row.email = f"erased-recipient-{row.id}@{ERASED_DOMAIN}"
            row.name = ""
            row.context = {}
    donations = Donation.query.filter(
        or_(
            Donation.user_id == user.id if user else False,
            func.lower(Donation.donor_email).in_(emails) if emails else False,
        )
    ).all()
    for donation in donations:
        _anonymise_donation(donation)
    if emails:
        for sub in Subscriber.query.filter(func.lower(Subscriber.email).in_(emails)).all():
            sub.email = f"erased-subscriber-{sub.id}@{ERASED_DOMAIN}"
            sub.status = "unsubscribed"
            sub.unsubscribed_at = sub.unsubscribed_at or _now()

    for family in member.family_members:
        family.name = ERASED_NAME
        family.age = None
    photo_url = member.photo_url
    member.name = ERASED_NAME
    member.email = None
    member.phone = None
    member.address = None
    member.photo_url = None
    member.family_info = None
    member.erased_at = _now()
    if user is not None:
        user.email = f"erased-user-{user.id}@{ERASED_DOMAIN}"
        user.phone = None
        user.disabled_at = user.disabled_at or _now()
    db.session.commit()

    if user is not None:
        delete_provider_account(user.auth_user_id, user.auth_provider)
    if photo_url:  # the file is personal data too; a storage failure must not undo the anonymisation
        try:
            from app.storage.service import get_public_storage

            storage = get_public_storage()
            key = storage.key_from_url(photo_url)
            if key:
                storage.delete(key)
        except Exception:  # noqa: BLE001
            logger.warning("Could not delete the photo of an erased member (id %s)", member.id)


def process_erase_requests() -> int:
    """Anonymise everyone whose grace period has ended. Returns how many."""
    due = _now() - timedelta(days=GRACE_DAYS)
    members = Member.query.filter(
        Member.erase_requested_at.isnot(None), Member.erased_at.is_(None), Member.erase_requested_at <= due
    ).all()
    for member in members:
        anonymise_member(member)
    return len(members)


def anonymise_old_orders() -> int:
    """Buyer fields of orders whose accounting year ended more than `retention_years()` years ago."""
    cutoff = datetime(_now().year - retention_years(), 1, 1, tzinfo=timezone.utc)
    orders = Order.query.filter(
        Order.created_at < cutoff, ~Order.customer_email.like(f"%@{ERASED_DOMAIN}")
    ).all()
    for order in orders:
        _anonymise_order(order)
    old_donations = Donation.query.filter(
        Donation.created_at < cutoff, ~Donation.donor_email.like(f"%@{ERASED_DOMAIN}")
    ).all()
    for donation in old_donations:
        _anonymise_donation(donation)
    db.session.commit()
    return len(orders) + len(old_donations)


def run_privacy_jobs() -> int:
    return process_erase_requests() + anonymise_old_orders()
