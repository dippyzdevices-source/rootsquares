from flask import Blueprint, jsonify
from sqlalchemy import select

from app.auth.optional import optional_admin_user
from app.extensions import db
from app.sponsors.models import Sponsor

sponsors_bp = Blueprint("sponsors", __name__, url_prefix="/api/sponsors")


def _serialize_sponsor(sponsor: Sponsor) -> dict:
    """Public-safe fields only."""
    return {
        "id": sponsor.id,
        "name": sponsor.name,
        "logo_url": sponsor.logo_url,
        "website_url": sponsor.website_url,
        # False only ever appears for an admin previewing a hidden sponsor.
        "published": sponsor.is_active,
    }


@sponsors_bp.get("")
def list_sponsors():
    stmt = select(Sponsor).order_by(Sponsor.display_order.asc(), Sponsor.id.asc())
    if optional_admin_user() is None:
        stmt = stmt.where(Sponsor.is_active.is_(True))
    items = db.session.execute(stmt).scalars().all()
    return jsonify({"items": [_serialize_sponsor(s) for s in items]})
