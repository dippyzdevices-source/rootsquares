"""Admin CRUD for events.

Protected by role-based auth (added in EPIC 5) — every route in this blueprint requires the
"admin" role via the before_request hook below. See app/auth/decorators.py for require_role.
"""

import uuid
from datetime import datetime, time, timezone

import bleach
from flask import Blueprint, g, jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.auth.models import User
from app.coupons.models import Coupon
from app.events.models import Event, EventBanner, EventSession, EventTaskAssignment
from app.events.routes import MAX_PER_PAGE, _serialize_session
from app.lookups.service import active_values
from app.extensions import db
from app.gallery.media_processing import MediaValidationError, process_upload
from app.gallery.models import Album
from app.modules import module_enabled
from app.members.models import Member
from app.orders.models import Order
from app.storage.service import get_public_storage
from app.tickets.models import TicketType
from app.orders.service import canonical_event_methods
from app.settings.admin_routes import DESCRIPTION_STYLES

admin_events_bp = Blueprint("admin_events", __name__, url_prefix="/api/admin/events")
admin_events_bp.before_request(require_role("admin"))


TICKET_LAYOUTS = ("sections", "tabs")
REQUIRED_FIELDS = ("title", "slug", "event_type", "start_datetime")
STRING_FIELDS = {
    "title": 200,
    "sub_name": 200,
    "description_style": 20,
    "ticket_payment_methods": 30,
    "ticket_layout": 10,
    "cash_note": 1000,
    "slug": 220,
    "short_description": 500,
    "venue": 200,
    "address": 300,
    "banner_image": 500,
    "facebook_url": 500,
    "instagram_url": 500,
    "status": 50,
}
TICKET_LIMIT_FIELDS = ("max_tickets_per_email", "coupon_max_adult", "coupon_max_child")
NULLABLE_STRING_FIELDS = {"cash_note", "sub_name", "description_style", "short_description", "venue", "address", "banner_image", "facebook_url", "instagram_url"}
TEXT_FIELDS = ("description",)

# Matches the rich-text editor's own toolbar scope exactly (bold/italic, headings, lists,
# links) — kept modest on purpose, same as News. Sanitized server-side too, never trusting the
# editor alone: an admin API call bypassing the editor is still a vector.
ALLOWED_DESCRIPTION_TAGS = ["p", "br", "strong", "em", "h2", "h3", "ul", "ol", "li", "a"]
ALLOWED_DESCRIPTION_ATTRIBUTES = {"a": ["href", "rel", "target"]}


def sanitize_event_description(html: str) -> str:
    return bleach.clean(
        html,
        tags=ALLOWED_DESCRIPTION_TAGS,
        attributes=ALLOWED_DESCRIPTION_ATTRIBUTES,
        protocols=["http", "https", "mailto"],
        strip=True,
    )


def _user_email(user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    return user.email if user else None


def _serialize_banner(banner: EventBanner) -> dict:
    return {
        "id": banner.id,
        "image_url": get_public_storage().url_for(banner.storage_key),
        "sort_order": banner.sort_order,
    }


def _serialize_event_admin(event: Event) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "sub_name": event.sub_name,
        "description_style": event.description_style,
        "ticket_payment_methods": event.ticket_payment_methods,
        "ticket_layout": event.ticket_layout,
        "cash_note": event.cash_note,
        "series_id": event.series_id,
        "slug": event.slug,
        "short_description": event.short_description,
        "description": event.description,
        "event_type": event.event_type,
        "start_datetime": event.start_datetime.isoformat(),
        "end_datetime": event.end_datetime.isoformat() if event.end_datetime else None,
        "sales_close_at": event.sales_close_at.isoformat() if event.sales_close_at else None,
        "sales_closed": event.sales_closed,
        "sales_open_at": event.sales_open_at.isoformat() if event.sales_open_at else None,
        "sales_not_open": event.sales_not_open,
        "venue": event.venue,
        "address": event.address,
        "capacity": event.capacity,
        "banner_image": event.banner_image,
        "facebook_url": event.facebook_url,
        "instagram_url": event.instagram_url,
        "max_tickets_per_email": event.max_tickets_per_email,
        "coupon_max_adult": event.coupon_max_adult,
        "coupon_max_child": event.coupon_max_child,
        "banners": [_serialize_banner(b) for b in event.banners],
        "status": event.status,
        "published": event.published,
        "created_by_email": _user_email(event.created_by),
        "updated_by_email": _user_email(event.updated_by),
        "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(),
        "sessions": [_serialize_session(s) for s in event.sessions],
        "task_assignments": [_serialize_task_assignment(a) for a in event.task_assignments] if module_enabled("volunteering") else [],
    }


def _serialize_task_assignment(assignment: EventTaskAssignment) -> dict:
    member = assignment.member
    return {
        "id": assignment.id,
        "member_id": assignment.member_id,
        "member_name": member.name,
        "member_email": member.user.email if member.user else member.email,
        "category": assignment.category,
    }


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _validate_event_payload(data: dict, existing: Event | None) -> tuple[dict, dict]:
    """Validate and clean a create/update payload.

    Required fields are only enforced when `existing` is None (create).
    Returns (cleaned_fields, errors) — apply cleaned_fields only if errors is empty.
    """
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                errors[field] = "This field is required."

    for field, max_length in STRING_FIELDS.items():
        if field not in data:
            continue
        value = data[field]
        if value is None and field in NULLABLE_STRING_FIELDS:
            cleaned[field] = None
            continue
        if not isinstance(value, str) or not value.strip():
            errors[field] = "Must be a non-empty string."
            continue
        if len(value) > max_length:
            errors[field] = f"Must be at most {max_length} characters."
            continue
        cleaned[field] = value.strip()

    if "ticket_payment_methods" in cleaned:
        canonical = canonical_event_methods(cleaned["ticket_payment_methods"])
        if canonical is None:
            errors["ticket_payment_methods"] = "Choose at least one of: qr, app, bank, cash, card."
            del cleaned["ticket_payment_methods"]
        else:
            cleaned["ticket_payment_methods"] = canonical

    if "ticket_layout" in cleaned and cleaned["ticket_layout"] not in TICKET_LAYOUTS:
        errors["ticket_layout"] = f"Must be one of: {', '.join(TICKET_LAYOUTS)}."
        del cleaned["ticket_layout"]

    if cleaned.get("description_style") and cleaned["description_style"] not in DESCRIPTION_STYLES:
        errors["description_style"] = f"Must be one of: {', '.join(DESCRIPTION_STYLES)}, or empty for the site default."
        del cleaned["description_style"]

    for field in ("facebook_url", "instagram_url"):
        value = cleaned.get(field)
        if value and not value.lower().startswith(("http://", "https://")):
            errors[field] = "Must start with http:// or https://."
            del cleaned[field]

    for field in TEXT_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if value is not None and not isinstance(value, str):
            errors[field] = "Must be a string."
        elif value is None:
            cleaned[field] = None
        elif field == "description":
            cleaned[field] = sanitize_event_description(value)
        else:
            cleaned[field] = value

    if "event_type" in data:
        event_type = data["event_type"]
        # A hidden type is refused for new choices, but an event may keep the one it already has.
        if event_type not in active_values("event_type") and not (existing and existing.event_type == event_type):
            errors["event_type"] = f"Must be one of {sorted(active_values('event_type'))}."
        else:
            cleaned["event_type"] = event_type

    for field in ("start_datetime", "end_datetime", "sales_close_at", "sales_open_at"):
        if field not in data:
            continue
        value = data[field]
        if value is None:
            cleaned[field] = None
            continue
        try:
            cleaned[field] = _parse_datetime(value)
        except (ValueError, TypeError):
            errors[field] = "Must be a valid ISO 8601 datetime."

    start = cleaned.get("start_datetime", existing.start_datetime if existing else None)
    end = cleaned.get("end_datetime", existing.end_datetime if existing else None)
    if start and end and end < start:
        errors["end_datetime"] = "End date/time must not be before the start date/time."
    opens = cleaned.get("sales_open_at", existing.sales_open_at if existing else None)
    closes = cleaned.get("sales_close_at", existing.sales_close_at if existing else None)
    if opens and closes and closes <= opens:
        errors["sales_close_at"] = "Sales must close after they open."

    if "capacity" in data:
        value = data["capacity"]
        if value is None:
            cleaned["capacity"] = None
        elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors["capacity"] = "Must be a non-negative integer."
        else:
            cleaned["capacity"] = value

    for field in TICKET_LIMIT_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if value is None:
            cleaned[field] = None
        elif isinstance(value, bool) or not isinstance(value, int) or value < 1:
            errors[field] = "Must be a whole number of at least 1, or empty for no limit."
        else:
            cleaned[field] = value

    if "published" in data:
        value = data["published"]
        if not isinstance(value, bool):
            errors["published"] = "Must be a boolean."
        else:
            cleaned["published"] = value

    return cleaned, errors


@admin_events_bp.get("")
def admin_list_events():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    # Unlike the public endpoint, this lists every event regardless of published status.
    stmt = select(Event).order_by(Event.start_datetime.desc())
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_event_admin(event) for event in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_events_bp.post("")
def admin_create_event():
    from app.event_pass import one_event_refusal

    refused = one_event_refusal()  # an Event pass holds one event (ADR 044)
    if refused is not None:
        return refused
    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_event_payload(data, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    event = Event(
        title=cleaned["title"],
        sub_name=cleaned.get("sub_name"),
        description_style=cleaned.get("description_style"),
        ticket_payment_methods=cleaned.get("ticket_payment_methods", "qr,app"),
        ticket_layout=cleaned.get("ticket_layout", "sections"),
        cash_note=cleaned.get("cash_note"),
        slug=cleaned["slug"],
        event_type=cleaned["event_type"],
        start_datetime=cleaned["start_datetime"],
        short_description=cleaned.get("short_description"),
        description=cleaned.get("description"),
        end_datetime=cleaned.get("end_datetime"),
        sales_close_at=cleaned.get("sales_close_at"),
        sales_open_at=cleaned.get("sales_open_at"),
        venue=cleaned.get("venue"),
        address=cleaned.get("address"),
        capacity=cleaned.get("capacity"),
        max_tickets_per_email=cleaned.get("max_tickets_per_email"),
        coupon_max_adult=cleaned.get("coupon_max_adult"),
        coupon_max_child=cleaned.get("coupon_max_child"),
        banner_image=cleaned.get("banner_image"),
        facebook_url=cleaned.get("facebook_url"),
        instagram_url=cleaned.get("instagram_url"),
        status=cleaned.get("status", "scheduled"),
        published=cleaned.get("published", False),
        created_by=g.current_user.id,
        updated_by=g.current_user.id,
    )
    db.session.add(event)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"errors": {"slug": "An event with this slug already exists."}}), 409

    log_action(
        g.current_user,
        "event_created",
        f'Created event "{event.title}"',
        target_type="event",
        target_id=event.id,
    )

    return jsonify(_serialize_event_admin(event)), 201


@admin_events_bp.get("/<int:event_id>")
def admin_get_event(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(_serialize_event_admin(event))


@admin_events_bp.post("/<int:event_id>/banner")
def admin_upload_event_banner(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_public_storage()
    old_key = storage.key_from_url(event.banner_image) if event.banner_image else None

    unique_id = uuid.uuid4().hex
    safe_name = secure_filename(file.filename) or "banner"
    storage_key = f"events/{event_id}/banner-{unique_id}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    if old_key:
        storage.delete(old_key)

    event.banner_image = storage.url_for(storage_key)
    event.updated_by = g.current_user.id
    db.session.commit()

    return jsonify(_serialize_event_admin(event))


@admin_events_bp.post("/<int:event_id>/banners")
def admin_add_event_banner(event_id: int):
    """Appends a new banner to the event's slider (see EventBanner) — unlike the single
    `/banner` upload above, this never replaces an existing image."""
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_public_storage()
    unique_id = uuid.uuid4().hex
    safe_name = secure_filename(file.filename) or "banner"
    storage_key = f"events/{event_id}/banner-{unique_id}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)

    next_sort_order = max((b.sort_order for b in event.banners), default=-1) + 1
    db.session.add(EventBanner(event_id=event_id, storage_key=storage_key, sort_order=next_sort_order))
    db.session.commit()

    return jsonify(_serialize_event_admin(event)), 201


@admin_events_bp.delete("/<int:event_id>/banners/<int:banner_id>")
def admin_delete_event_banner(event_id: int, banner_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    banner = db.session.get(EventBanner, banner_id)
    if banner is None or banner.event_id != event_id:
        return jsonify({"error": "Banner not found"}), 404

    get_public_storage().delete(banner.storage_key)
    db.session.delete(banner)
    db.session.commit()

    return jsonify(_serialize_event_admin(event))


@admin_events_bp.patch("/<int:event_id>")
def admin_update_event(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_event_payload(data, existing=event)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(event, field, value)
    event.updated_by = g.current_user.id

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"errors": {"slug": "An event with this slug already exists."}}), 409

    log_action(
        g.current_user,
        "event_updated",
        f'Updated event "{event.title}"',
        target_type="event",
        target_id=event.id,
    )

    return jsonify(_serialize_event_admin(event))


@admin_events_bp.delete("/<int:event_id>")
def admin_delete_event(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    if Order.query.filter_by(event_id=event_id).first() is not None:
        return jsonify({"error": "Cannot delete an event with existing ticket orders."}), 409

    # Sessions/task-assignments cascade via the ORM relationship (see Event.sessions/
    # task_assignments), but TicketType, Coupon, and Album have no cascade declared —
    # TicketType/Coupon are safe to remove outright once we've confirmed above there are no
    # Orders (and therefore no Tickets, and no Order ever referencing one of this event's
    # coupons) referencing it; Album.event_id is just a loose, nullable link, so we unlink
    # rather than delete someone's photos.
    TicketType.query.filter_by(event_id=event_id).delete()
    Coupon.query.filter_by(event_id=event_id).delete()
    Album.query.filter_by(event_id=event_id).update({"event_id": None})

    event_title = event.title
    db.session.delete(event)
    db.session.commit()

    log_action(
        g.current_user,
        "event_deleted",
        f'Deleted event "{event_title}"',
        target_type="event",
        target_id=event_id,
    )

    return "", 204


def _unique_copy_slug(source_slug: str) -> str:
    """`durga-puja-2026` -> `durga-puja-2026-copy`, `-copy-2`, `-copy-3`, ... as needed."""
    base = f"{source_slug}-copy"
    slug = base
    suffix = 2
    while db.session.execute(select(Event).where(Event.slug == slug)).scalar_one_or_none():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


@admin_events_bp.post("/<int:event_id>/duplicate")
def admin_duplicate_event(event_id: int):
    from app.event_pass import one_event_refusal

    refused = one_event_refusal()  # a copy would be a second event (ADR 044)
    if refused is not None:
        return refused
    source = db.session.get(Event, event_id)
    if source is None:
        return jsonify({"error": "Event not found"}), 404

    # Dates and content carry over as-is — admin adjusts them (e.g. bumps the
    # year) via the edit form afterwards. status/published reset to draft
    # since a straight copy is never ready to go live immediately.
    duplicate = Event(
        title=source.title,
        sub_name=source.sub_name,
        description_style=source.description_style,
        ticket_payment_methods=source.ticket_payment_methods,
        ticket_layout=source.ticket_layout,
        cash_note=source.cash_note,
        slug=_unique_copy_slug(source.slug),
        short_description=source.short_description,
        description=source.description,
        event_type=source.event_type,
        start_datetime=source.start_datetime,
        end_datetime=source.end_datetime,
        venue=source.venue,
        address=source.address,
        capacity=source.capacity,
        max_tickets_per_email=source.max_tickets_per_email,
        coupon_max_adult=source.coupon_max_adult,
        coupon_max_child=source.coupon_max_child,
        banner_image=source.banner_image,
        facebook_url=source.facebook_url,
        instagram_url=source.instagram_url,
        status="scheduled",
        published=False,
        created_by=g.current_user.id,
        updated_by=g.current_user.id,
    )
    db.session.add(duplicate)
    db.session.flush()  # assign duplicate.id before copying sessions

    for session in source.sessions:
        db.session.add(
            EventSession(
                event_id=duplicate.id,
                day_label=session.day_label,
                time=session.time,
                title=session.title,
                description=session.description,
                sort_order=session.sort_order,
            )
        )

    db.session.commit()
    return jsonify(_serialize_event_admin(duplicate)), 201


def _validate_session_payload(data: dict, existing: EventSession | None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        for field in ("day_label", "time", "title"):
            if not data.get(field):
                errors[field] = "This field is required."

    if "day_label" in data:
        value = data["day_label"]
        if not isinstance(value, str) or not value.strip():
            errors["day_label"] = "Must be a non-empty string."
        elif len(value) > 50:
            errors["day_label"] = "Must be at most 50 characters."
        else:
            cleaned["day_label"] = value.strip()

    if "title" in data:
        value = data["title"]
        if not isinstance(value, str) or not value.strip():
            errors["title"] = "Must be a non-empty string."
        elif len(value) > 200:
            errors["title"] = "Must be at most 200 characters."
        else:
            cleaned["title"] = value.strip()

    if "time" in data:
        value = data["time"]
        try:
            cleaned["time"] = time.fromisoformat(value)
        except (ValueError, TypeError):
            errors["time"] = "Must be a valid time in HH:MM format."

    if "description" in data:
        value = data["description"]
        if value is None:
            cleaned["description"] = None
        elif not isinstance(value, str):
            errors["description"] = "Must be a string or null."
        elif len(value) > 2000:
            errors["description"] = "Must be at most 2000 characters."
        else:
            cleaned["description"] = value.strip() or None

    if "sort_order" in data:
        value = data["sort_order"]
        if isinstance(value, bool) or not isinstance(value, int):
            errors["sort_order"] = "Must be an integer."
        else:
            cleaned["sort_order"] = value

    return cleaned, errors


@admin_events_bp.post("/<int:event_id>/sessions")
def admin_create_session(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_session_payload(data, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    session = EventSession(
        event_id=event.id,
        day_label=cleaned["day_label"],
        time=cleaned["time"],
        title=cleaned["title"],
        description=cleaned.get("description"),
        sort_order=cleaned.get("sort_order", 0),
    )
    db.session.add(session)
    db.session.commit()

    return jsonify(_serialize_session(session)), 201


@admin_events_bp.patch("/<int:event_id>/sessions/<int:session_id>")
def admin_update_session(event_id: int, session_id: int):
    session = db.session.get(EventSession, session_id)
    if session is None or session.event_id != event_id:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_session_payload(data, existing=session)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(session, field, value)

    db.session.commit()
    return jsonify(_serialize_session(session))


@admin_events_bp.delete("/<int:event_id>/sessions/<int:session_id>")
def admin_delete_session(event_id: int, session_id: int):
    session = db.session.get(EventSession, session_id)
    if session is None or session.event_id != event_id:
        return jsonify({"error": "Session not found"}), 404

    db.session.delete(session)
    db.session.commit()
    return "", 204


def _validate_task_assignment_payload(data: dict, existing: EventTaskAssignment | None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        for field in ("member_id", "category"):
            if not data.get(field):
                errors[field] = "This field is required."

    if "member_id" in data:
        value = data["member_id"]
        if isinstance(value, bool) or not isinstance(value, int):
            errors["member_id"] = "Must be an integer."
        elif db.session.get(Member, value) is None:
            errors["member_id"] = "No member exists with this id."
        else:
            cleaned["member_id"] = value

    if "category" in data:
        value = data["category"]
        # A hidden category is refused for new choices, but an assignment may keep its current one.
        if value not in active_values("task_category") and not (existing and existing.category == value):
            errors["category"] = f"Must be one of {sorted(active_values('task_category'))}."
        else:
            cleaned["category"] = value

    return cleaned, errors


@admin_events_bp.post("/<int:event_id>/task-assignments")
def admin_create_task_assignment(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_task_assignment_payload(data, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    assignment = EventTaskAssignment(
        event_id=event.id, member_id=cleaned["member_id"], category=cleaned["category"]
    )
    db.session.add(assignment)
    db.session.commit()

    return jsonify(_serialize_task_assignment(assignment)), 201


@admin_events_bp.patch("/<int:event_id>/task-assignments/<int:assignment_id>")
def admin_update_task_assignment(event_id: int, assignment_id: int):
    assignment = db.session.get(EventTaskAssignment, assignment_id)
    if assignment is None or assignment.event_id != event_id:
        return jsonify({"error": "Volunteer assignment not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_task_assignment_payload(data, existing=assignment)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(assignment, field, value)

    db.session.commit()
    return jsonify(_serialize_task_assignment(assignment))


@admin_events_bp.delete("/<int:event_id>/task-assignments/<int:assignment_id>")
def admin_delete_task_assignment(event_id: int, assignment_id: int):
    assignment = db.session.get(EventTaskAssignment, assignment_id)
    if assignment is None or assignment.event_id != event_id:
        return jsonify({"error": "Volunteer assignment not found"}), 404

    db.session.delete(assignment)
    db.session.commit()
    return "", 204
