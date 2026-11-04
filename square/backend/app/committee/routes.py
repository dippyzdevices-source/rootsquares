from flask import Blueprint, jsonify
from sqlalchemy import select

from app.auth.optional import optional_admin_user
from app.committee.models import CommitteeMember
from app.extensions import db

committee_bp = Blueprint("committee", __name__, url_prefix="/api/committee")


def _serialize_committee_member(member: CommitteeMember) -> dict:
    """Public-safe fields only — never expose is_active/created_at/updated_at here."""
    return {
        "id": member.id,
        "name": member.name,
        "sub_name": member.sub_name,
        "role": member.role,
        "portrait_url": member.portrait_url,
        "address": member.address,
        "email": member.email,
        "phone": member.phone,
        "member_since": member.member_since,
        "quote": member.quote,
        # False only ever appears for an admin previewing a hidden member (see list below).
        "published": member.is_active,
    }


@committee_bp.get("")
def list_committee_members():
    stmt = select(CommitteeMember).order_by(CommitteeMember.display_order.asc())
    # An admin's own authenticated request also gets hidden members (tagged published: false)
    # so they can review the page before switching "Active" on; everyone else sees active only.
    if optional_admin_user() is None:
        stmt = stmt.where(CommitteeMember.is_active.is_(True))
    items = db.session.execute(stmt).scalars().all()
    return jsonify({"items": [_serialize_committee_member(m) for m in items]})
