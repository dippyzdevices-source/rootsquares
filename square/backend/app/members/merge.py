"""Finding and merging duplicate Member records (admin-only, see admin_routes.py).

A duplicate is two Member rows for one person — the same effective email, or the same name +
phone. The merge keeps one record and moves everything attached to the other onto it.
"""

import re

from app.events.models import EventTaskAssignment
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership
from app.memberships.service import expire_other_active_memberships


def _effective_email(member: Member) -> str:
    return ((member.user.email if member.user else member.email) or "").strip().lower()


def _effective_phone(member: Member) -> str:
    raw = (member.user.phone if member.user else member.phone) or ""
    digits = re.sub(r"\D", "", raw)
    return digits[-8:] if len(digits) >= 8 else digits


def find_duplicate_groups() -> list[dict]:
    """Groups of 2+ members sharing an email, or a name + phone. Each group is
    {"reason": "email" | "name_phone", "members": [Member, ...]}."""
    members = Member.query.order_by(Member.id).all()
    by_email: dict[str, list[Member]] = {}
    by_name_phone: dict[tuple[str, str], list[Member]] = {}
    for m in members:
        email = _effective_email(m)
        if email:
            by_email.setdefault(email, []).append(m)
        phone = _effective_phone(m)
        if phone and m.name:
            by_name_phone.setdefault((m.name.strip().lower(), phone), []).append(m)

    groups, seen = [], set()
    for reason, buckets in (("email", by_email), ("name_phone", by_name_phone)):
        for bucket in buckets.values():
            ids = frozenset(m.id for m in bucket)
            if len(bucket) > 1 and ids not in seen:
                seen.add(ids)
                groups.append({"reason": reason, "members": bucket})
    return groups


def merge_error(keep: Member, merge: Member) -> str | None:
    """Why `merge` can't be folded into `keep`, or None if it can."""
    if keep.id == merge.id:
        return "Choose two different members."
    if keep.user_id is not None and merge.user_id is not None:
        return "Both records are linked to a login account — they can't be merged."
    if merge.parent_member_id == keep.id or keep.parent_member_id == merge.id:
        return "These members are parent and child — they can't be merged."
    return None


def merge_members(keep: Member, merge: Member) -> None:
    """Move everything from `merge` onto `keep`, then delete `merge`. Caller validates with
    merge_error() first and commits."""
    # Login link: unique on Member.user_id, so release it before handing it over.
    if keep.user_id is None and merge.user_id is not None:
        user_id = merge.user_id
        merge.user_id = None
        db.session.flush()
        keep.user_id = user_id

    for field in ("email", "phone", "address", "photo_url", "family_info"):
        if not getattr(keep, field) and getattr(merge, field):
            setattr(keep, field, getattr(merge, field))
    if keep.parent_member_id is None and merge.parent_member_id is not None:
        keep.parent_member_id = merge.parent_member_id

    Membership.query.filter_by(member_id=merge.id).update({"member_id": keep.id})
    EventTaskAssignment.query.filter_by(member_id=merge.id).update({"member_id": keep.id})
    Member.query.filter_by(parent_member_id=merge.id).update({"parent_member_id": keep.id})

    existing = {(f.relationship_type, f.name.strip().lower()) for f in keep.family_members}
    for family in list(merge.family_members):
        key = (family.relationship_type, family.name.strip().lower())
        if key in existing:
            db.session.delete(family)
        else:
            family.member_id = keep.id
            existing.add(key)

    db.session.flush()
    db.session.expire(keep)
    db.session.expire(merge)
    db.session.delete(merge)
    db.session.flush()

    # Two actives may now sit on one member: keep the newest, move the rest to history.
    keep_active = (
        Membership.query.filter_by(member_id=keep.id, status="active")
        .order_by(Membership.start_date.desc(), Membership.id.desc())
        .first()
    )
    if keep_active is not None:
        expire_other_active_memberships(keep_active)
