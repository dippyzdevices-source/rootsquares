"""Admin side of recurring events: make an event repeat, see its series, update the following events, end the series. Admin only (the blueprint's guard)."""

from __future__ import annotations

from datetime import date, datetime

from flask import g, jsonify, request

from app.audit.service import log_action
from app.event_pass import is_event_pass
from app.events import series as series_logic
from app.events.admin_routes import admin_events_bp
from app.events.models import Event, EventSeries
from app.extensions import db
from app.features import locked


def _describe(series: EventSeries, first: date | None = None) -> str:
    if series.frequency == "weekly":
        base = "Every week" if series.interval_weeks == 1 else f"Every {series.interval_weeks} weeks"
        if first:
            base += f" on {first.strftime('%A')}"
    else:
        ordinal = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "last"}.get(series.nth or 1, "first")
        base = f"The {ordinal} {first.strftime('%A') if first else 'weekday'} of every month"
    if series.until_date:
        base += f", until {series.until_date.isoformat()}"
    elif series.max_count:
        base += f", {series.max_count} times"
    return base


def serialize_series(series: EventSeries) -> dict:
    events = series_logic.occurrences(series)
    first = series.first_date or (series_logic._local(events[0]).date() if events else None)
    return {
        "id": series.id,
        "frequency": series.frequency,
        "interval_weeks": series.interval_weeks,
        "nth": series.nth,
        "until_date": series.until_date.isoformat() if series.until_date else None,
        "max_count": series.max_count,
        "ended": series.ended,
        "label": _describe(series, first),
        "occurrences": [
            {"id": e.id, "slug": e.slug, "title": e.title, "start_datetime": e.start_datetime.isoformat(), "status": e.status, "published": e.published, "has_orders": series_logic.has_orders(e)}
            for e in events
        ],
    }


def _clean_rule(data: dict) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    frequency = data.get("frequency")
    if frequency not in series_logic.FREQUENCIES:
        errors["frequency"] = "Choose weekly or monthly."
    interval = data.get("interval_weeks", 1)
    if frequency == "weekly" and (not isinstance(interval, int) or isinstance(interval, bool) or not 1 <= interval <= series_logic.MAX_INTERVAL_WEEKS):
        errors["interval_weeks"] = f"Every 1 to {series_logic.MAX_INTERVAL_WEEKS} weeks."
    nth = data.get("nth")
    if frequency == "monthly_weekday" and (not isinstance(nth, int) or isinstance(nth, bool) or not 1 <= nth <= series_logic.LAST):
        errors["nth"] = "Choose the first, second, third, fourth or last."
    until = None
    if data.get("until_date") not in (None, ""):
        try:
            until = date.fromisoformat(str(data["until_date"]))
        except ValueError:
            errors["until_date"] = "Not a valid date."
    count = data.get("max_count")
    if count in (None, ""):
        count = None
    elif not isinstance(count, int) or isinstance(count, bool) or not 2 <= count <= 520:
        errors["max_count"] = "A number from 2 to 520."
    if until is not None and count is not None:
        errors["until_date"] = "End on a date or after a number of times, not both."
    return {"frequency": frequency, "interval_weeks": interval if frequency == "weekly" else 1, "nth": nth if frequency == "monthly_weekday" else None, "until_date": until, "max_count": count}, errors


@admin_events_bp.post("/<int:event_id>/repeat")
def repeat_event(event_id: int):
    if is_event_pass():
        return jsonify({"error": "An Event pass holds one event; it cannot repeat.", "code": "event_pass_limit"}), 409
    if (refused := locked("repeating_events")) is not None:
        return refused
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    if event.series_id:
        return jsonify({"error": "This event already repeats."}), 409
    rule, errors = _clean_rule(request.get_json(silent=True) or {})
    if not errors and rule["until_date"] and rule["until_date"] <= series_logic._local(event).date():
        errors["until_date"] = "Choose a date after this event."
    if errors:
        return jsonify({"errors": errors}), 400
    series = series_logic.create_series(event, user_id=g.current_user.id, **rule)
    made = Event.query.filter_by(series_id=series.id).count() - 1
    log_action(g.current_user, "event_repeated", f"Made event #{event.id} repeat ({_describe(series)}): {made} more created", target_type="event", target_id=event.id)
    return jsonify({"series": serialize_series(series), "created": made}), 201


@admin_events_bp.get("/<int:event_id>/series")
def get_series(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return jsonify({"error": "Event not found"}), 404
    if not event.series_id:
        return jsonify({"series": None})
    return jsonify({"series": serialize_series(db.session.get(EventSeries, event.series_id))})


def _in_series(event_id: int):
    event = db.session.get(Event, event_id)
    if event is None:
        return None, (jsonify({"error": "Event not found"}), 404)
    if not event.series_id:
        return None, (jsonify({"error": "This event does not repeat."}), 409)
    return event, None


@admin_events_bp.post("/<int:event_id>/series/update-following")
def update_following(event_id: int):
    if (refused := locked("repeating_events")) is not None:
        return refused
    event, error = _in_series(event_id)
    if error:
        return error
    updated, skipped = series_logic.update_following(event)
    log_action(g.current_user, "series_updated", f"Copied event #{event.id} to {updated} following event(s); {skipped} skipped (orders)", target_type="event", target_id=event.id)
    return jsonify({"updated": updated, "skipped_with_orders": skipped})


@admin_events_bp.post("/<int:event_id>/series/end")
def end_series(event_id: int):
    if (refused := locked("repeating_events")) is not None:
        return refused
    event, error = _in_series(event_id)
    if error:
        return error
    removed, cancelled = series_logic.end_here(event)
    log_action(g.current_user, "series_ended", f"Ended the series at event #{event.id}: {removed} removed, {cancelled} cancelled (orders)", target_type="event", target_id=event.id)
    return jsonify({"removed": removed, "cancelled": cancelled})
