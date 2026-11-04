"""Recurring events (wave 14 item 6, ADR 065).

A series is a rule ("every Sunday", "the first Friday of the month", "until ...") plus the events that follow it. Every occurrence is a NORMAL event with its
own page, tickets, orders, check-in and reminders, so nothing else in the app needs to know about series. The rule only decides on which days a copy is made.
Copies are made a few months ahead and topped up by a daily job, so a weekly service goes on without writing years of events.

The copy is made from the latest occurrence of the series ("the last one wins"): if you fixed the wording of next week's, the following weeks follow it.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select

from app.common.site import site_timezone
from app.events.models import Event, EventSeries, EventSession
from app.coupons.models import Coupon
from app.extensions import db
from app.features import feature_enabled
from app.gallery.models import Album
from app.orders.models import Order
from app.tickets.models import TicketType

FREQUENCIES = ("weekly", "monthly_weekday")
MAX_INTERVAL_WEEKS = 8
LAST = 5  # `nth` = 5 means "the last <weekday> of the month"
DEFAULT_HORIZON_DAYS = 120
MAX_OCCURRENCES_PER_RUN = 60  # one run never creates more than this many events
_DATE_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")

# What "update the following events" copies from one occurrence to the later ones. Dates are never copied: each keeps its own day.
CONTENT_FIELDS = (
    "title", "sub_name", "description_style", "short_description", "description", "event_type", "venue", "address", "capacity", "banner_image",
    "ticket_payment_methods", "ticket_layout", "cash_note", "max_tickets_per_email", "coupon_max_adult", "coupon_max_child", "facebook_url", "instagram_url",
)


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date | None:
    days = [d for d in range(1, calendar.monthrange(year, month)[1] + 1) if date(year, month, d).weekday() == weekday]
    if nth == LAST:
        return date(year, month, days[-1])
    return date(year, month, days[nth - 1]) if nth <= len(days) else None


def rule_dates(series: EventSeries, first: date, end: date) -> list[date]:
    """Every date of the rule from the first occurrence (inclusive) to `end` (inclusive), before the until date and the count are applied."""
    out: list[date] = []
    if series.frequency == "weekly":
        step = timedelta(weeks=max(1, series.interval_weeks))
        day = first
        while day <= end:
            out.append(day)
            day += step
    else:  # monthly_weekday: the same weekday as the first occurrence, in the nth week of each month
        weekday = first.weekday()
        year, month = first.year, first.month
        while True:
            day = _nth_weekday(year, month, weekday, series.nth or 1)
            if day is not None and day >= first:
                if day > end:
                    break
                out.append(day)
            elif date(year, month, 1) > end:
                break
            month += 1
            if month > 12:
                year, month = year + 1, 1
    return out


def bounded_dates(series: EventSeries, first: date, horizon_end: date) -> list[date]:
    """The dates that may exist: the rule, up to the horizon, the until date and the count."""
    end = min(horizon_end, series.until_date) if series.until_date else horizon_end
    dates = rule_dates(series, first, end)
    return dates[: series.max_count] if series.max_count else dates


def _local(event: Event) -> datetime:
    return event.start_datetime.astimezone(site_timezone()) if event.start_datetime.tzinfo else event.start_datetime.replace(tzinfo=timezone.utc).astimezone(site_timezone())


def _at(day: date, local_time: time) -> datetime:
    """The moment `day` at the square's local clock time, in UTC (DST-safe: 18:00 stays 18:00 on the wall)."""
    return datetime.combine(day, local_time, tzinfo=site_timezone()).astimezone(timezone.utc)


def _unique_slug(base: str) -> str:
    slug, n = base, 2
    while db.session.scalar(select(Event.id).where(Event.slug == slug)) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def copy_for_date(template: Event, day: date) -> Event:
    """A new, unsaved-to-the-session-yet occurrence of `template` on `day` (same local time and length, dates inside it shifted by the same distance)."""
    start = _at(day, _local(template).timetz().replace(tzinfo=None))
    delta = start - (template.start_datetime if template.start_datetime.tzinfo else template.start_datetime.replace(tzinfo=timezone.utc))
    copy = Event(
        slug=_unique_slug(f"{_DATE_SUFFIX.sub('', template.slug)}-{day.isoformat()}"),
        start_datetime=start,
        end_datetime=(template.end_datetime + delta) if template.end_datetime else None,
        sales_open_at=(template.sales_open_at + delta) if template.sales_open_at else None,
        sales_close_at=(template.sales_close_at + delta) if template.sales_close_at else None,
        status="scheduled",
        published=template.published,
        series_id=template.series_id,
        created_by=template.created_by,
        updated_by=template.updated_by,
        **{f: getattr(template, f) for f in CONTENT_FIELDS},
    )
    db.session.add(copy)
    db.session.flush()
    for s in template.sessions:
        db.session.add(EventSession(event_id=copy.id, day_label=s.day_label, time=s.time, title=s.title, description=s.description, sort_order=s.sort_order))
    for t in TicketType.query.filter_by(event_id=template.id).order_by(TicketType.sort_order).all():
        db.session.add(
            TicketType(
                event_id=copy.id, name=t.name, description=t.description, price=t.price, capacity=t.capacity,
                sale_start=(t.sale_start + delta) if t.sale_start else None, sale_end=(t.sale_end + delta) if t.sale_end else None,
                valid_on=(t.valid_on + timedelta(days=delta.days)) if t.valid_on else None, members_only=t.members_only,
                age_category=t.age_category, coupon_eligible=t.coupon_eligible, sort_order=t.sort_order,
            )
        )
    return copy


def occurrences(series: EventSeries) -> list[Event]:
    return Event.query.filter_by(series_id=series.id).order_by(Event.start_datetime).all()


def extend(series: EventSeries, today: date | None = None) -> int:
    """Make the occurrences that are missing up to the horizon. Returns how many were made. Idempotent: an existing date is never made twice."""
    if series.ended:
        return 0
    events = occurrences(series)
    if not events:
        return 0
    today = today or datetime.now(timezone.utc).astimezone(site_timezone()).date()
    first = series.first_date or _local(events[0]).date()
    have = {_local(e).date() for e in events}
    live = [e for e in events if e.status != "cancelled"]
    template = (live or events)[-1]
    wanted = bounded_dates(series, first, today + timedelta(days=series.horizon_days))
    made = 0
    for day in wanted:
        if day in have or day <= _local(events[-1]).date():
            continue
        if made >= MAX_OCCURRENCES_PER_RUN:
            break
        copy_for_date(template, day)
        made += 1
    db.session.commit()
    return made


def create_series(base: Event, *, frequency: str, interval_weeks: int, nth: int | None, until_date: date | None, max_count: int | None, user_id: int | None) -> EventSeries:
    series = EventSeries(first_date=_local(base).date(), frequency=frequency, interval_weeks=interval_weeks, nth=nth, until_date=until_date, max_count=max_count, horizon_days=DEFAULT_HORIZON_DAYS, created_by=user_id)
    db.session.add(series)
    db.session.flush()
    base.series_id = series.id
    db.session.commit()
    extend(series)
    return series


def extend_all() -> int:
    """The hourly top-up: every running series gets its next occurrences. A square whose package has no repeating events (W14-R25) is skipped: its series stay as they are."""
    if not feature_enabled("repeating_events"):
        return 0
    return sum(extend(s) for s in EventSeries.query.filter_by(ended=False).all())


def has_orders(event: Event) -> bool:
    return bool(db.session.scalar(select(func.count(Order.id)).where(Order.event_id == event.id)))


def update_following(source: Event) -> tuple[int, int]:
    """Copy the wording, place, limits and clock time of `source` to the LATER occurrences of its series. An occurrence that already has orders is left alone.
    Returns (updated, skipped because of orders). Ticket types are not changed here (they may already be sold)."""
    updated = skipped = 0
    local_time = _local(source).timetz().replace(tzinfo=None)
    length = (source.end_datetime - source.start_datetime) if source.end_datetime else None
    for event in occurrences(db.session.get(EventSeries, source.series_id)):
        if event.id == source.id or event.start_datetime <= source.start_datetime:
            continue
        if has_orders(event):
            skipped += 1
            continue
        for f in CONTENT_FIELDS:
            setattr(event, f, getattr(source, f))
        event.start_datetime = _at(_local(event).date(), local_time)
        event.end_datetime = (event.start_datetime + length) if length else None
        updated += 1
    db.session.commit()
    return updated, skipped


def end_here(source: Event) -> tuple[int, int]:
    """Stop the series at `source`: later occurrences without orders are removed, later ones with orders are marked cancelled (the buyers are not forgotten),
    and no more are made. Returns (removed, cancelled)."""
    series = db.session.get(EventSeries, source.series_id)
    removed = cancelled = 0
    for event in occurrences(series):
        if event.start_datetime <= source.start_datetime:
            continue
        if has_orders(event):
            event.status = "cancelled"
            cancelled += 1
        else:
            # Same as deleting one event by hand: ticket types and coupons have no cascade, an album is only unlinked.
            TicketType.query.filter_by(event_id=event.id).delete()
            Coupon.query.filter_by(event_id=event.id).delete()
            Album.query.filter_by(event_id=event.id).update({"event_id": None})
            db.session.delete(event)
            removed += 1
    series.ended = True
    series.until_date = _local(source).date()
    db.session.commit()
    return removed, cancelled
