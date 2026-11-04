from datetime import datetime, timezone

from datetime import timedelta

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func, select

from app.auth.optional import optional_admin_user
from app.common.urls import frontend_base_url
from app.events.calendar import build_calendar
from app.events.models import Event
from app.lookups.service import all_values
from app.orders.service import allowed_payment_methods, cash_note_for_event
from app.payments.bank import bank_details
from app.settings.models import get_site_settings
from app.extensions import db
from app.storage.service import get_public_storage
from app.modules import module_enabled
from app.tickets.qr import generate_qr_data_url

events_bp = Blueprint("events", __name__, url_prefix="/api/events")

MAX_PER_PAGE = 50


def _serialize_event_summary(event: Event) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "slug": event.slug,
        "short_description": event.short_description,
        "description_style": event.description_style,
        "event_type": event.event_type,
        "start_datetime": event.start_datetime.isoformat(),
        "end_datetime": event.end_datetime.isoformat() if event.end_datetime else None,
        "venue": event.venue,
        "banner_image": event.banner_image,
        "published": event.published,
        "status": event.status,  # "cancelled" for an occurrence of a series that was ended after tickets had been sold
        "repeats": event.series_id is not None,
        # Ticket sales belong to the Tickets module (W8-R29): without it an event is never 'closed for sales' or 'not open yet'
        "sales_closed": event.sales_closed and module_enabled("tickets"),
        "sales_not_open": event.sales_not_open and module_enabled("tickets"),
        "sales_open_at": event.sales_open_at.isoformat() if event.sales_open_at and module_enabled("tickets") else None,
    }


@events_bp.get("")
def list_events():
    when = request.args.get("when", "upcoming")
    if when not in ("upcoming", "past"):
        return jsonify({"error": "when must be 'upcoming' or 'past'"}), 400

    event_type = request.args.get("type")
    if event_type is not None and event_type not in all_values("event_type"):
        return jsonify({"error": f"type must be one of {sorted(all_values('event_type'))}"}), 400

    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 9))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400

    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    now = datetime.now(timezone.utc)
    # An event without an end_datetime is treated as ending when it starts.
    effective_end = func.coalesce(Event.end_datetime, Event.start_datetime)

    # Unpublished/draft events are never shown to an anonymous or non-admin visitor. An admin's
    # own authenticated request (see _optional_admin_user) sees them too, unfiltered, so other
    # admins can review a draft's look and feel on the real listing/detail pages before it goes
    # live — the frontend renders a "Draft" pill off the published flag in the response above.
    stmt = select(Event)
    if optional_admin_user() is None:
        stmt = stmt.where(Event.published.is_(True))
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)

    if when == "upcoming":
        stmt = stmt.where(effective_end >= now).order_by(Event.start_datetime.asc())
    else:
        stmt = stmt.where(effective_end < now).order_by(Event.start_datetime.desc())

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_event_summary(event) for event in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


def _serialize_session(session) -> dict:
    return {
        "id": session.id,
        "day_label": session.day_label,
        "time": session.time.isoformat(timespec="minutes"),
        "title": session.title,
        "description": session.description,
        "sort_order": session.sort_order,
    }


def _serialize_event_detail(event: Event) -> dict:
    storage = get_public_storage()
    return {
        "id": event.id,
        "title": event.title,
        "sub_name": event.sub_name,
        "description_style": event.description_style,
        "payment_methods": sorted(allowed_payment_methods(event), reverse=True),
        "status": event.status,
        "repeats": event.series_id is not None,
        "ticket_layout": event.ticket_layout,
        "sales_close_at": event.sales_close_at.isoformat() if event.sales_close_at and module_enabled("tickets") else None,
        "sales_closed": event.sales_closed and module_enabled("tickets"),
        "sales_open_at": event.sales_open_at.isoformat() if event.sales_open_at and module_enabled("tickets") else None,
        "sales_not_open": event.sales_not_open and module_enabled("tickets"),
        "cash_note": cash_note_for_event(event) if "cash" in allowed_payment_methods(event) else "",
        "bank": bank_details(get_site_settings()) if "bank" in allowed_payment_methods(event) else None,
        "slug": event.slug,
        "short_description": event.short_description,
        "description": event.description,
        "event_type": event.event_type,
        "start_datetime": event.start_datetime.isoformat(),
        "end_datetime": event.end_datetime.isoformat() if event.end_datetime else None,
        "venue": event.venue,
        "address": event.address,
        "capacity": event.capacity,
        "banner_image": event.banner_image,
        "facebook_url": event.facebook_url,
        "instagram_url": event.instagram_url,
        "max_tickets_per_email": event.max_tickets_per_email,
        "coupon_max_adult": event.coupon_max_adult,
        "coupon_max_child": event.coupon_max_child,
        "banners": [
            {"id": b.id, "image_url": storage.url_for(b.storage_key), "sort_order": b.sort_order}
            for b in event.banners
        ],
        "status": event.status,
        "sessions": [_serialize_session(s) for s in event.sessions],
        "published": event.published,
    }


@events_bp.get("/<string:slug>")
def get_event(slug: str):
    # See the matching comment in list_events — an admin's own authenticated request can also
    # open a draft event's real detail page (to review look and feel before publishing);
    # anonymous/non-admin requests still 404 on anything unpublished.
    stmt = select(Event).where(Event.slug == slug)
    if optional_admin_user() is None:
        stmt = stmt.where(Event.published.is_(True))
    event = db.session.execute(stmt).scalar_one_or_none()
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(_serialize_event_detail(event))


def _ics_response(events, name: str | None = None) -> Response:
    body = build_calendar(events, name=name)
    return Response(
        body,
        mimetype="text/calendar",
        headers={"Content-Disposition": 'inline; filename="calendar.ics"', "Cache-Control": "public, max-age=300"},
    )


@events_bp.get("/calendar.ics")
def calendar_feed():
    """Every published, upcoming event as a calendar file to subscribe to (a phone or computer calendar re-reads it by itself). No personal data in it."""
    now = datetime.now(timezone.utc)
    effective_end = func.coalesce(Event.end_datetime, Event.start_datetime)
    stmt = (
        select(Event)
        .where(Event.published.is_(True), Event.status != "cancelled", effective_end >= now - timedelta(days=1), Event.start_datetime <= now + timedelta(days=400))
        .order_by(Event.start_datetime.asc())
        .limit(500)
    )
    return _ics_response(list(db.session.execute(stmt).scalars()))


@events_bp.get("/<string:slug>/calendar.ics")
def event_calendar_file(slug: str):
    """One event as a calendar file ("Add to my calendar")."""
    event = db.session.execute(select(Event).where(Event.slug == slug, Event.published.is_(True))).scalar_one_or_none()
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    return _ics_response([event], name=event.title)


@events_bp.get("/<string:slug>/qr")
def get_event_qr(slug: str):
    """QR code (PNG data URI) of the event's public page, for the Share button."""
    stmt = select(Event).where(Event.slug == slug)
    if optional_admin_user() is None:
        stmt = stmt.where(Event.published.is_(True))
    event = db.session.execute(stmt).scalar_one_or_none()
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    url = f"{frontend_base_url()}/events/{event.slug}"
    return jsonify({"url": url, "qr": generate_qr_data_url(url)})
