"""Tests for event series (10 tests), e.g. weekly and monthly dates; repeat makes ordinary events with the same wall clock time ticket type; extend is idempotent and tops up as time passes."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app import create_app
from app.audit.models import AuditLog
from app.events import series as series_logic
from app.events.calendar import escape_text, fold
from app.events.models import Event, EventSeries, EventSession
from app.extensions import db
from app.orders.models import Order
from app.tickets.models import TicketType
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_orders_checkout import _add_event, _add_type

OSLO = ZoneInfo("Europe/Oslo")


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin(app, method, path, **kw):
    _, token = make_user_and_token(role="admin", email="admin@example.com")
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return getattr(app.test_client(), method)(path, headers=auth_header(token), **kw)


def _sunday_event(**kw):
    """A Sunday 18:00 (Oslo time) event, a few days from now."""
    today = date.today()
    day = today + timedelta(days=(6 - today.weekday()) % 7 + 7)  # the Sunday after next at the earliest
    start = datetime.combine(day, datetime.min.time().replace(hour=18), tzinfo=OSLO).astimezone(timezone.utc)
    return _add_event(start_datetime=start, end_datetime=start + timedelta(hours=2), published=True, slug="service", **kw)


def test_weekly_and_monthly_dates():
    _new_app()  # loads every model, so the mappers can be built
    weekly = EventSeries(frequency="weekly", interval_weeks=1)
    assert series_logic.rule_dates(weekly, date(2026, 11, 1), date(2026, 11, 29)) == [date(2026, 11, d) for d in (1, 8, 15, 22, 29)]
    fortnight = EventSeries(frequency="weekly", interval_weeks=2)
    assert series_logic.rule_dates(fortnight, date(2026, 11, 1), date(2026, 12, 6)) == [date(2026, 11, 1), date(2026, 11, 15), date(2026, 11, 29)]
    first_friday = EventSeries(frequency="monthly_weekday", nth=1)
    assert series_logic.rule_dates(first_friday, date(2026, 11, 6), date(2027, 1, 31)) == [date(2026, 11, 6), date(2026, 12, 4), date(2027, 1, 1)]
    last_sunday = EventSeries(frequency="monthly_weekday", nth=series_logic.LAST)
    assert series_logic.rule_dates(last_sunday, date(2026, 10, 25), date(2027, 1, 31)) == [date(2026, 10, 25), date(2026, 11, 29), date(2026, 12, 27), date(2027, 1, 31)]
    capped = EventSeries(frequency="weekly", interval_weeks=1, max_count=3)
    assert len(series_logic.bounded_dates(capped, date(2026, 11, 1), date(2027, 6, 1))) == 3
    until = EventSeries(frequency="weekly", interval_weeks=1, until_date=date(2026, 11, 15))
    assert series_logic.bounded_dates(until, date(2026, 11, 1), date(2027, 6, 1)) == [date(2026, 11, 1), date(2026, 11, 8), date(2026, 11, 15)]


def test_repeat_makes_ordinary_events_with_the_same_wall_clock_time_ticket_types_and_schedule():
    app = _new_app()
    with app.app_context():
        base = _sunday_event()
        _add_type(base.id, price=15000)
        db.session.add(EventSession(event_id=base.id, day_label="Sunday", time=datetime(2026, 1, 1, 18, 0).time(), title="Gathering", sort_order=0))
        db.session.commit()
        response = _admin(app, "post", f"/api/admin/events/{base.id}/repeat", json={"frequency": "weekly", "interval_weeks": 1})
        assert response.status_code == 201
        made = response.get_json()["created"]
        assert 15 <= made <= 19  # about 120 days ahead
        events = Event.query.order_by(Event.start_datetime).all()
        assert len(events) == made + 1 and all(e.series_id == events[0].series_id for e in events)
        for e in events:
            local = e.start_datetime.replace(tzinfo=timezone.utc).astimezone(OSLO)
            assert (local.hour, local.minute, local.weekday()) == (18, 0, 6)  # 18:00 on a Sunday, also across the autumn clock change
            assert (e.end_datetime - e.start_datetime) == timedelta(hours=2)
        assert len({e.slug for e in events}) == len(events) and events[1].slug.startswith("service-20")
        assert TicketType.query.filter_by(event_id=events[1].id).one().price == 15000
        assert EventSession.query.filter_by(event_id=events[1].id).count() == 1
        assert all(e.published for e in events)
        assert AuditLog.query.filter_by(action="event_repeated").count() == 1
        again = _admin(app, "post", f"/api/admin/events/{base.id}/repeat", json={"frequency": "weekly"})
        assert again.status_code == 409
        db.drop_all()


def test_extend_is_idempotent_and_tops_up_as_time_passes():
    app = _new_app()
    with app.app_context():
        base = _sunday_event()
        series = series_logic.create_series(base, frequency="weekly", interval_weeks=1, nth=None, until_date=None, max_count=None, user_id=None)
        count = Event.query.count()
        assert series_logic.extend(series) == 0
        later = date.today() + timedelta(days=60)
        assert series_logic.extend(series, today=later) > 0 and Event.query.count() > count
        assert series_logic.extend(series, today=later) == 0
        db.drop_all()


def test_a_deleted_middle_occurrence_stays_deleted_and_a_count_limits_the_series():
    app = _new_app()
    with app.app_context():
        base = _sunday_event()
        series = series_logic.create_series(base, frequency="weekly", interval_weeks=1, nth=None, until_date=None, max_count=4, user_id=None)
        events = Event.query.order_by(Event.start_datetime).all()
        assert len(events) == 4
        db.session.delete(events[1])
        db.session.commit()
        series_logic.extend(series, today=date.today() + timedelta(days=200))
        assert Event.query.count() == 3  # not made again, and the count of 4 is not exceeded
        db.drop_all()


def test_deleting_the_first_occurrence_does_not_move_the_count():
    app = _new_app()
    with app.app_context():
        base = _sunday_event()
        series = series_logic.create_series(base, frequency="weekly", interval_weeks=1, nth=None, until_date=None, max_count=4, user_id=None)
        events = Event.query.order_by(Event.start_datetime).all()
        assert len(events) == 4 and series.first_date == series_logic._local(events[0]).date()
        db.session.delete(events[0])
        db.session.commit()
        series_logic.extend(series, today=date.today() + timedelta(days=200))
        assert Event.query.count() == 3  # still 4 times counted from the deleted first one: nothing new is made
        db.drop_all()


def test_the_next_ones_follow_the_latest_occurrence():
    app = _new_app()
    with app.app_context():
        base = _sunday_event()
        series = series_logic.create_series(base, frequency="weekly", interval_weeks=1, nth=None, until_date=None, max_count=None, user_id=None)
        last = Event.query.order_by(Event.start_datetime.desc()).first()
        last.venue = "The new hall"
        db.session.commit()
        series_logic.extend(series, today=date.today() + timedelta(days=60))
        assert Event.query.order_by(Event.start_datetime.desc()).first().venue == "The new hall"
        db.drop_all()


def test_update_following_skips_events_with_orders_and_end_series_cancels_them():
    app = _new_app()
    with app.app_context():
        base = _sunday_event(venue="Old hall")
        _add_type(base.id, price=100)
        series_logic.create_series(base, frequency="weekly", interval_weeks=1, nth=None, until_date=None, max_count=6, user_id=None)
        events = Event.query.order_by(Event.start_datetime).all()
        db.session.add(Order(order_number="T-1", event_id=events[2].id, customer_name="A", customer_email="a@x.org", total_amount=100, payment_status="paid"))
        db.session.commit()
        events[0].venue = "New hall"
        events[0].title = "Sunday gathering"
        db.session.commit()
        done = _admin(app, "post", f"/api/admin/events/{events[0].id}/series/update-following")
        assert done.get_json() == {"updated": 4, "skipped_with_orders": 1}
        db.session.expire_all()
        assert [e.venue for e in Event.query.order_by(Event.start_datetime).all()] == ["New hall", "New hall", "Old hall", "New hall", "New hall", "New hall"]

        ended = _admin(app, "post", f"/api/admin/events/{events[1].id}/series/end")
        assert ended.get_json() == {"removed": 3, "cancelled": 1}
        # the removed occurrences took their copied ticket types with them (no rows left pointing at a missing event)
        assert {t.event_id for t in TicketType.query.all()} <= {e.id for e in Event.query.all()}
        remaining = Event.query.order_by(Event.start_datetime).all()
        assert len(remaining) == 3 and remaining[2].status == "cancelled"
        assert db.session.get(EventSeries, base.series_id).ended is True
        assert series_logic.extend(db.session.get(EventSeries, base.series_id), today=date.today() + timedelta(days=300)) == 0
        db.drop_all()


def test_repeat_validation_and_event_without_series():
    app = _new_app()
    with app.app_context():
        base = _sunday_event()
        bad = _admin(app, "post", f"/api/admin/events/{base.id}/repeat", json={"frequency": "daily"})
        assert bad.status_code == 400 and "frequency" in bad.get_json()["errors"]
        both = _admin(app, "post", f"/api/admin/events/{base.id}/repeat", json={"frequency": "weekly", "until_date": "2030-01-01", "max_count": 5})
        assert both.status_code == 400
        past = _admin(app, "post", f"/api/admin/events/{base.id}/repeat", json={"frequency": "weekly", "until_date": "2001-01-01"})
        assert past.status_code == 400
        assert _admin(app, "get", f"/api/admin/events/{base.id}/series").get_json() == {"series": None}
        assert _admin(app, "post", f"/api/admin/events/{base.id}/series/end").status_code == 409
        assert Event.query.count() == 1
        db.drop_all()


def test_public_feed_lists_only_published_upcoming_events_and_a_single_event_file():
    app = _new_app()
    with app.app_context():
        shown = _sunday_event(title="Sunday, with a comma; and more", venue="Main hall", address="1 Street")
        _add_event(slug="draft", published=False, title="Draft")
        client = app.test_client()
        feed = client.get("/api/events/calendar.ics")
        assert feed.status_code == 200 and feed.mimetype == "text/calendar"
        text = feed.get_data(as_text=True)
        assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
        assert text.count("BEGIN:VEVENT") == 1 and "Draft" not in text
        assert "SUMMARY:Sunday\\, with a comma\\; and more" in text and "LOCATION:Main hall\\, 1 Street" in text
        assert f"UID:event-{shown.id}@" in text and "DTSTART:" in text and "URL:" in text
        one = client.get("/api/events/service/calendar.ics")
        assert one.status_code == 200 and one.get_data(as_text=True).count("BEGIN:VEVENT") == 1
        assert client.get("/api/events/draft/calendar.ics").status_code == 404
        shown.status = "cancelled"
        db.session.commit()
        assert "BEGIN:VEVENT" not in client.get("/api/events/calendar.ics").get_data(as_text=True)
        db.drop_all()


def test_calendar_text_escaping_and_folding_follow_the_standard():
    assert escape_text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    long = "SUMMARY:" + "ø" * 60
    folded = fold(long)
    assert "\r\n " in folded
    for physical in folded.split("\r\n"):
        assert len(physical.encode("utf-8")) <= 75
    assert folded.replace("\r\n ", "") == long
