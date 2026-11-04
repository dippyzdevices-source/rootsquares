"""Admin donations and sponsorships for an event's accounting — recorded like expenses, but they
are money IN: paid ones are added to the event's Collection (see _build_event_summary)."""

import re
from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from app.accounting.models import EventContribution
from app.auth.decorators import require_role
from app.auth.models import User
from app.common.query_params import csv_arg
from app.events.models import Event
from app.extensions import db

admin_contributions_bp = Blueprint(
    "admin_contributions", __name__, url_prefix="/api/admin/accounting"
)
admin_contributions_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 50
ANONYMOUS = "Anonymous"
# What an admin may set by hand (failed / refunded come from the payment itself).
ADMIN_STATUSES = ("pending", "paid")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def serialize_contribution(c: EventContribution) -> dict:
    creator = db.session.get(User, c.created_by) if c.created_by else None
    return {
        "id": c.id,
        "event_id": c.event_id,
        "kind": c.kind,
        "name": c.name,
        "email": c.email,
        "amount": c.amount,
        "contact_name": c.contact_name,
        "phone": c.phone,
        "website": c.website,
        "requirements": c.requirements,
        "date": c.date.isoformat(),
        "payment_method": c.payment_method,
        "notes": c.notes,
        "status": c.status,
        "created_by": creator.email if creator else None,
        "created_at": c.created_at.isoformat(),
    }


def _validate(
    data: dict, *, is_create: bool, current_kind: str | None = None, current_amount: int | None = None
) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}
    if is_create:
        for field in ("kind", "amount", "date"):
            if data.get(field) in (None, ""):
                errors[field] = "This field is required."

    if "kind" in data and "kind" not in errors:
        if data["kind"] not in EventContribution.KINDS:
            errors["kind"] = f"Must be one of {list(EventContribution.KINDS)}."
        else:
            cleaned["kind"] = data["kind"]
    blank_name = not isinstance(data.get("name"), str) or not data["name"].strip()
    if "name" in data or is_create:
        value = data.get("name")
        if blank_name:
            # A donor may stay anonymous; a sponsor must be named.
            if cleaned.get("kind", current_kind) == "sponsorship":
                errors["name"] = "This field is required."
            else:
                cleaned["name"] = ANONYMOUS
        elif len(value) > 200:
            errors["name"] = "Must be at most 200 characters."
        else:
            cleaned["name"] = value.strip()
    if "email" in data:
        value = data["email"]
        if value in (None, ""):
            cleaned["email"] = None
        elif not isinstance(value, str) or not EMAIL_RE.match(value.strip()) or len(value) > 255:
            errors["email"] = "Enter a valid email address."
        else:
            cleaned["email"] = value.strip()
    if "amount" in data and "amount" not in errors:
        value = data["amount"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            errors["amount"] = "Must be a number greater than zero."
        else:
            cleaned["amount"] = int(value)
    if "date" in data and "date" not in errors:
        try:
            cleaned["date"] = datetime.strptime(data["date"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            errors["date"] = "Must be a valid date (YYYY-MM-DD)."
    for field, limit in (("contact_name", 200), ("phone", 30), ("website", 300), ("requirements", 2000)):
        if field in data:
            value = data[field]
            if value in (None, ""):
                cleaned[field] = None
            elif not isinstance(value, str) or len(value.strip()) > limit:
                errors[field] = f"Must be at most {limit} characters."
            else:
                cleaned[field] = value.strip()
    if "status" in data:
        if data["status"] not in ADMIN_STATUSES:
            errors["status"] = f"Must be one of {list(ADMIN_STATUSES)}."
        else:
            cleaned["status"] = data["status"]
    if cleaned.get("status") == "paid" and cleaned.get("amount", current_amount) is None:
        errors["amount"] = "Set the amount before marking it received."
    if "payment_method" in data:
        value = data["payment_method"]
        if value in (None, ""):
            cleaned["payment_method"] = None
        elif not isinstance(value, str) or len(value) > 30:
            errors["payment_method"] = "Must be at most 30 characters."
        else:
            cleaned["payment_method"] = value.strip()
    if "notes" in data:
        value = data["notes"]
        if value is None:
            cleaned["notes"] = None
        elif not isinstance(value, str):
            errors["notes"] = "Must be a string or null."
        else:
            cleaned["notes"] = value.strip() or None
    return cleaned, errors


def filtered_contributions_stmt(event_id: int):
    """An event's contributions narrowed by ?kind= (csv) and ?q= (unordered); shared with exports."""
    stmt = select(EventContribution).where(EventContribution.event_id == event_id)
    kinds = csv_arg("kind")
    if kinds:
        stmt = stmt.where(EventContribution.kind.in_(kinds))
    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(db.or_(EventContribution.name.ilike(like), EventContribution.email.ilike(like)))
    return stmt


@admin_contributions_bp.get("/events/<int:event_id>/contributions")
def list_contributions(event_id: int):
    if db.session.get(Event, event_id) is None:
        return jsonify({"error": "Event not found"}), 404
    stmt = filtered_contributions_stmt(event_id).order_by(
        EventContribution.date.desc(), EventContribution.id.desc()
    )
    # Small per-event lists: returned whole (the page pages them client-side like the other lists).
    items = db.session.scalars(stmt).all()
    return jsonify({"items": [serialize_contribution(c) for c in items], "total": len(items)})


@admin_contributions_bp.post("/events/<int:event_id>/contributions")
def create_contribution(event_id: int):
    if db.session.get(Event, event_id) is None:
        return jsonify({"error": "Event not found"}), 404
    cleaned, errors = _validate(request.get_json(silent=True) or {}, is_create=True)
    if errors:
        return jsonify({"errors": errors}), 400
    contribution = EventContribution(
        **{"status": "paid", **cleaned}, event_id=event_id, created_by=g.current_user.id
    )
    db.session.add(contribution)
    db.session.commit()
    return jsonify(serialize_contribution(contribution)), 201


@admin_contributions_bp.patch("/contributions/<int:contribution_id>")
def update_contribution(contribution_id: int):
    contribution = db.session.get(EventContribution, contribution_id)
    if contribution is None:
        return jsonify({"error": "Contribution not found"}), 404
    cleaned, errors = _validate(request.get_json(silent=True) or {}, is_create=False, current_kind=contribution.kind, current_amount=contribution.amount)
    if errors:
        return jsonify({"errors": errors}), 400
    for field, value in cleaned.items():
        setattr(contribution, field, value)
    db.session.commit()
    return jsonify(serialize_contribution(contribution))


@admin_contributions_bp.delete("/contributions/<int:contribution_id>")
def delete_contribution(contribution_id: int):
    contribution = db.session.get(EventContribution, contribution_id)
    if contribution is None:
        return jsonify({"error": "Contribution not found"}), 404
    db.session.delete(contribution)
    db.session.commit()
    return "", 204
