from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.auth.optional import optional_admin_user
from app.extensions import db
from app.testimonials.models import Testimonial

testimonials_bp = Blueprint("testimonials", __name__, url_prefix="/api/testimonials")

# Generous but bounded — this is a public, unauthenticated endpoint, so length limits are the
# one real guardrail against abuse (there is no CAPTCHA/rate-limit infra in this app; every
# submission also lands as "pending" and is invisible on the site until an admin approves it,
# which is the actual anti-abuse mechanism — a spammer can submit garbage, but it never
# becomes visible without a human choosing to publish it).
MAX_QUOTE_LENGTH = 1000
MAX_NAME_LENGTH = 200
MAX_CONTEXT_LENGTH = 200
MAX_PHOTO_URL_LENGTH = 500


def _serialize_testimonial(testimonial: Testimonial) -> dict:
    return {
        "id": testimonial.id,
        "quote": testimonial.quote,
        "author_name": testimonial.author_name,
        "author_context": testimonial.author_context,
        "photo_url": testimonial.photo_url,
        # False only ever appears for an admin previewing a pending/rejected/hidden testimonial.
        "published": testimonial.status == "approved" and testimonial.is_active,
    }


@testimonials_bp.get("")
def list_testimonials():
    # Unpaginated on purpose — this is a short homepage card row, not a browsable list.
    # Requires BOTH approved (reviewed) and active (currently shown) — see the model docstring.
    stmt = select(Testimonial).order_by(Testimonial.sort_order.asc())
    # Admins also get pending/rejected/hidden testimonials (published: false) to preview.
    if optional_admin_user() is None:
        stmt = stmt.where(Testimonial.status == "approved", Testimonial.is_active.is_(True))
    items = db.session.execute(stmt).scalars().all()
    return jsonify({"items": [_serialize_testimonial(t) for t in items]})


def _validate_submission(data: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    quote = data.get("quote")
    if not isinstance(quote, str) or not quote.strip():
        errors["quote"] = "This field is required."
    elif len(quote.strip()) > MAX_QUOTE_LENGTH:
        errors["quote"] = f"Must be at most {MAX_QUOTE_LENGTH} characters."
    else:
        cleaned["quote"] = quote.strip()

    author_name = data.get("author_name")
    if not isinstance(author_name, str) or not author_name.strip():
        errors["author_name"] = "This field is required."
    elif len(author_name.strip()) > MAX_NAME_LENGTH:
        errors["author_name"] = f"Must be at most {MAX_NAME_LENGTH} characters."
    else:
        cleaned["author_name"] = author_name.strip()

    author_context = data.get("author_context")
    if author_context is not None:
        if not isinstance(author_context, str) or not author_context.strip():
            errors["author_context"] = "Must be a non-empty string or left blank."
        elif len(author_context.strip()) > MAX_CONTEXT_LENGTH:
            errors["author_context"] = f"Must be at most {MAX_CONTEXT_LENGTH} characters."
        else:
            cleaned["author_context"] = author_context.strip()
    else:
        cleaned["author_context"] = None

    photo_url = data.get("photo_url")
    if photo_url is not None:
        if not isinstance(photo_url, str) or not photo_url.strip():
            errors["photo_url"] = "Must be a non-empty string or left blank."
        elif len(photo_url.strip()) > MAX_PHOTO_URL_LENGTH:
            errors["photo_url"] = f"Must be at most {MAX_PHOTO_URL_LENGTH} characters."
        else:
            cleaned["photo_url"] = photo_url.strip()
    else:
        cleaned["photo_url"] = None

    return cleaned, errors


@testimonials_bp.post("")
def submit_testimonial():
    """Public, unauthenticated submission — anyone may share a testimonial. It is never shown
    on the site until an admin reviews and approves it (see the model docstring)."""
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_submission(data)
    if errors:
        return jsonify({"errors": errors}), 400

    testimonial = Testimonial(
        quote=cleaned["quote"],
        author_name=cleaned["author_name"],
        author_context=cleaned["author_context"],
        photo_url=cleaned["photo_url"],
        status="pending",
        is_active=False,
    )
    db.session.add(testimonial)
    db.session.commit()

    return jsonify({"id": testimonial.id, "status": testimonial.status}), 201
