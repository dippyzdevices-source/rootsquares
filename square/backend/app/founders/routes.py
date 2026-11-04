from flask import Blueprint, jsonify
from sqlalchemy import select

from app.auth.optional import optional_admin_user
from app.extensions import db
from app.founders.models import Founder

founders_bp = Blueprint("founders", __name__, url_prefix="/api/founders")


def _serialize_founder(founder: Founder) -> dict:
    """Public-safe fields only — never expose is_active/created_at/updated_at here."""
    return {
        "id": founder.id,
        "name": founder.name,
        "sub_name": founder.sub_name,
        "role": founder.role,
        "quote": founder.quote,
        "portrait_url": founder.portrait_url,
        # False only ever appears for an admin previewing a hidden founder (see list below).
        "published": founder.is_active,
    }


@founders_bp.get("")
def list_founders():
    stmt = select(Founder).order_by(Founder.display_order.asc(), Founder.id.asc())
    # Admins also get hidden founders (published: false) to preview them before going live.
    if optional_admin_user() is None:
        stmt = stmt.where(Founder.is_active.is_(True))
    items = db.session.execute(stmt).scalars().all()
    return jsonify({"items": [_serialize_founder(f) for f in items]})
