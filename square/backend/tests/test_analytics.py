"""Visit counting on the square server (rootsquares ADR 090, W23-R76): the privacy rules first (no cookie, a daily hash, Do Not Track, bots, caps, small numbers), then the numbers."""

import datetime as dt

import pytest

from app import create_app
from app.analytics import service
from app.analytics.models import AnalyticsDaily, AnalyticsPage, AnalyticsSeen, AnalyticsSource
from app.events.models import Event
from app.extensions import db
from app.orders.models import Order, OrderItem

SECRET = "s" * 40
UA = "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/128.0"
HOST = "club.example.org"
T0 = dt.datetime(2026, 10, 27, 10, 0, tzinfo=dt.timezone.utc)


@pytest.fixture()
def app():
    app = create_app("testing")
    app.config.update(ANALYTICS_SALT_SECRET=SECRET, ANALYTICS_ENABLED=True, PLATFORM_INTERNAL_KEY="internal-key")
    with app.app_context():
        db.create_all()
        service._PURGED.clear()
        yield app


def _hit(app, path="/", referrer="", ua=UA, ip="10.0.0.1", headers=None):
    return app.test_client().post(
        "/api/analytics/hit", json={"path": path, "referrer": referrer}, headers={"User-Agent": ua, "X-Forwarded-For": ip, **(headers or {})}, base_url=f"http://{HOST}"
    )


def _count(model):
    return db.session.query(model).count()


# ---- nothing is counted unless it is switched on ----------------------------------------------------------------------------------------
def test_nothing_is_counted_without_the_key_or_the_switch(app):
    app.config["ANALYTICS_ENABLED"] = False
    assert _hit(app).status_code == 204 and _count(AnalyticsDaily) == 0
    app.config.update(ANALYTICS_ENABLED=True, ANALYTICS_SALT_SECRET="")
    assert _hit(app).status_code == 204 and _count(AnalyticsDaily) == 0


def test_the_answer_is_the_same_whether_a_visit_was_counted_or_not(app):
    counted = _hit(app, "/events")
    refused = _hit(app, "/admin")
    assert counted.status_code == refused.status_code == 204 and counted.get_data() == refused.get_data() == b""


# ---- what is never counted ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("headers", [{"DNT": "1"}, {"Sec-GPC": "1"}])
def test_do_not_track_and_global_privacy_control_are_honoured(app, headers):
    assert _hit(app, "/events", headers=headers).status_code == 204
    assert _count(AnalyticsDaily) == 0 and _count(AnalyticsSeen) == 0


@pytest.mark.parametrize("ua", ["", "Googlebot/2.1 (+http://www.google.com/bot.html)", "curl/8.4.0", "Mozilla/5.0 HeadlessChrome/120", "python-requests/2.31"])
def test_bots_and_clients_without_a_browser_are_not_counted(app, ua):
    _hit(app, "/events", ua=ua)
    assert _count(AnalyticsDaily) == 0


@pytest.mark.parametrize("path", ["/admin", "/admin/events", "/api/events", "/login", "/register", "/support", "/x" * 200, "no-slash", "/a b", "/<script>", 42, None])
def test_the_admin_area_the_api_and_garbage_are_not_pages(app, path):
    _hit(app, path)
    assert _count(AnalyticsDaily) == 0


def test_the_path_is_stored_without_query_fragment_or_trailing_slash(app):
    _hit(app, "/events/autumn/?utm_source=mail&id=7#top")
    assert [p.path for p in db.session.query(AnalyticsPage)] == ["/events/autumn"]


# ---- the visitor is a pseudonym for one day --------------------------------------------------------------------------------------------
def test_the_visitor_hash_changes_every_day_and_is_stable_within_one(app):
    d = dt.date(2026, 10, 27)
    a = service.visitor_hash("10.0.0.1", UA, d)
    assert a == service.visitor_hash("10.0.0.1", UA, d) and len(a) == 32
    assert a != service.visitor_hash("10.0.0.1", UA, d + dt.timedelta(days=1))  # tomorrow the same person is someone else
    assert a != service.visitor_hash("10.0.0.2", UA, d) and a != service.visitor_hash("10.0.0.1", "Other/1.0", d)
    assert "10.0.0.1" not in a and UA not in a


def test_the_hash_depends_on_the_secret(app):
    d = dt.date(2026, 10, 27)
    a = service.visitor_hash("10.0.0.1", UA, d)
    app.config["ANALYTICS_SALT_SECRET"] = "t" * 40
    assert service.visitor_hash("10.0.0.1", UA, d) != a


def test_the_visitors_of_an_earlier_day_are_deleted_and_no_total_holds_a_hash(app):
    service.record_hit("/", "", UA, "10.0.0.1", HOST, now=T0)
    service.record_hit("/", "", UA, "10.0.0.2", HOST, now=T0)
    assert _count(AnalyticsSeen) == 2
    service.record_hit("/", "", UA, "10.0.0.1", HOST, now=T0 + dt.timedelta(days=1))  # the next day: yesterday's visitors go
    assert [s.day for s in db.session.query(AnalyticsSeen)] == [(T0 + dt.timedelta(days=1)).date()]
    for model in (AnalyticsDaily, AnalyticsPage, AnalyticsSource):  # the totals have no column that could hold a visitor
        assert not {c.name for c in model.__table__.columns} & {"visitor", "ip", "user_agent", "hash", "email", "name", "user_id"}


def test_totals_older_than_24_months_are_removed(app):
    old = (T0 - dt.timedelta(days=service.RETENTION_DAYS + 5)).date()
    db.session.add(AnalyticsDaily(day=old, visits=3, views=4, visitors=2))
    db.session.add(AnalyticsPage(day=old, path="/", views=4))
    db.session.commit()
    service.record_hit("/", "", UA, "10.0.0.1", HOST, now=T0)
    assert _count(AnalyticsPage) == 1 and db.session.get(AnalyticsDaily, (old,)) is None


# ---- the numbers ------------------------------------------------------------------------------------------------------------------------
def test_visits_views_and_visitors_are_counted_per_day(app):
    service.record_hit("/", "", UA, "10.0.0.1", HOST, now=T0)
    service.record_hit("/events", "", UA, "10.0.0.1", HOST, now=T0 + dt.timedelta(minutes=2))  # the same visit
    service.record_hit("/", "", UA, "10.0.0.2", HOST, now=T0 + dt.timedelta(minutes=3))  # another visitor
    d = db.session.get(AnalyticsDaily, (T0.date(),))
    assert (d.visits, d.views, d.visitors) == (2, 3, 2)


def test_after_half_an_hour_of_quiet_the_same_visitor_starts_a_new_visit_but_is_still_one_visitor(app):
    service.record_hit("/", "", UA, "10.0.0.1", HOST, now=T0)
    service.record_hit("/", "", UA, "10.0.0.1", HOST, now=T0 + dt.timedelta(minutes=31))
    d = db.session.get(AnalyticsDaily, (T0.date(),))
    assert (d.visits, d.views, d.visitors) == (2, 2, 1)


def test_a_source_is_the_referring_site_only_and_a_click_inside_the_site_is_no_source(app):
    service.record_hit("/", "https://www.google.com/search?q=secret+words", UA, "10.0.0.1", HOST, now=T0)
    service.record_hit("/events", f"https://{HOST}/", UA, "10.0.0.1", HOST, now=T0 + dt.timedelta(minutes=1))  # inside the same visit
    service.record_hit("/", "", UA, "10.0.0.2", HOST, now=T0)
    service.record_hit("/", "ftp://files.example.net/x", UA, "10.0.0.3", HOST, now=T0)
    assert {s.source: s.visits for s in db.session.query(AnalyticsSource)} == {"google.com": 1, "direct": 2}


def test_one_visitor_cannot_inflate_the_day(app):
    for i in range(service.MAX_HITS + 20):
        service.record_hit("/", "", UA, "10.0.0.1", HOST, now=T0 + dt.timedelta(seconds=i))
    assert db.session.get(AnalyticsDaily, (T0.date(),)).views == service.MAX_HITS


def test_paths_and_sources_are_capped_and_the_rest_is_other(app):
    for i in range(service.MAX_PATHS + 5):
        service.record_hit(f"/p{i}", "", UA, f"10.1.{i // 250}.{i % 250}", HOST, now=T0)
    assert _count(AnalyticsPage) == service.MAX_PATHS + 1 and db.session.get(AnalyticsPage, (T0.date(), "other")).views == 5
    for i in range(service.MAX_SOURCES + 3):
        service.record_hit("/", f"https://site{i}.example.net/", UA, f"10.2.0.{i}", HOST, now=T0 + dt.timedelta(hours=1))
    # "direct" (from the paths above) already holds one of the 50 places, so 49 sites are named and the other 4 are counted together
    assert db.session.get(AnalyticsSource, (T0.date(), "other")).visits == 4


# ---- what is reported -----------------------------------------------------------------------------------------------------------------
def test_a_figure_under_five_is_not_reported_but_the_daily_totals_are_exact(app):
    for i in range(3):
        service.record_hit("/rare", "", UA, f"10.0.1.{i}", HOST, now=T0)
    for i in range(5):
        service.record_hit("/common", "", UA, f"10.0.2.{i}", HOST, now=T0)
    r = service.report(7, now=T0 + dt.timedelta(hours=3))
    pages = {p["path"]: p for p in r["pages"]}
    assert pages["/rare"] == {"path": "/rare", "views": None, "few": True}
    assert pages["/common"] == {"path": "/common", "views": 5, "few": False}
    assert r["totals"] == {"visits": 8, "views": 8, "visitors": 8} and r["daily"][-1]["views"] == 8  # exact


def test_the_report_has_every_day_of_the_range_the_previous_period_and_the_top_ten(app):
    for i in range(12):
        for j in range(6 + i):
            service.record_hit(f"/page{i}", "", UA, f"10.3.{i}.{j}", HOST, now=T0)
    service.record_hit("/", "", UA, "10.9.9.9", HOST, now=T0 - dt.timedelta(days=8))  # in the period before a 7 day range
    r = service.report(7, now=T0)
    assert [d["day"] for d in r["daily"]][-1] == T0.date().isoformat() and len(r["daily"]) == 7
    assert len(r["pages"]) == service.TOP and r["pages"][0]["path"] == "/page11"  # the most viewed first
    assert r["previous"]["views"] == 1 and r["days"] == 7
    assert service.report(5, now=T0)["days"] == 30  # only 7, 30 and 90 are ranges


def test_the_events_funnel_counts_views_against_tickets_bought_and_hides_small_numbers(app):
    ev = Event(title="Autumn gathering", slug="autumn", event_type="cultural", start_datetime=T0)
    db.session.add(ev)
    db.session.flush()
    for i in range(2):  # two paid orders of three tickets each = 6; one unpaid is not counted
        o = Order(order_number=f"X-{i}", event_id=ev.id, customer_name="A", customer_email="a@example.org", total_amount=100, payment_status="paid")
        o.created_at = T0
        db.session.add(o)
        db.session.flush()
        db.session.add(OrderItem(order_id=o.id, ticket_type_id=1, quantity=3, unit_price=1, subtotal=3))
    pending = Order(order_number="X-9", event_id=ev.id, customer_name="A", customer_email="a@example.org", total_amount=100, payment_status="pending")
    pending.created_at = T0
    db.session.add(pending)
    db.session.flush()
    db.session.add(OrderItem(order_id=pending.id, ticket_type_id=1, quantity=9, unit_price=1, subtotal=9))
    db.session.commit()
    for i in range(12):
        service.record_hit("/events/autumn", "", UA, f"10.4.0.{i}", HOST, now=T0)
    service.record_hit("/events/autumn/tickets", "", UA, "10.4.1.1", HOST, now=T0)  # a sub page is not the event's page
    row = service.report(7, now=T0)["events"][0]
    assert row == {"slug": "autumn", "title": "Autumn gathering", "views": 12, "views_few": False, "tickets": 6, "tickets_few": False}
    db.session.query(OrderItem).delete()  # one ticket left over: hidden
    db.session.add(OrderItem(order_id=1, ticket_type_id=1, quantity=1, unit_price=1, subtotal=1))
    db.session.commit()
    row = service.report(7, now=T0)["events"][0]
    assert row["tickets"] is None and row["tickets_few"] is True and row["views"] == 12


# ---- the internal door ------------------------------------------------------------------------------------------------------------------
def test_the_aggregates_are_answered_only_with_the_platforms_key(app):
    c = app.test_client()
    assert c.get("/api/internal/analytics").status_code == 404
    assert c.get("/api/internal/analytics", headers={"X-Internal-Key": "wrong"}).status_code == 404
    ok = c.get("/api/internal/analytics?days=7", headers={"X-Internal-Key": "internal-key"})
    assert ok.status_code == 200 and ok.get_json()["days"] == 7 and ok.get_json()["enabled"] is True
    assert c.get("/api/internal/analytics?days=abc", headers={"X-Internal-Key": "internal-key"}).get_json()["days"] == 30


def test_the_internal_answer_holds_no_visitor_data(app):
    service.record_hit("/", "https://www.google.com/", UA, "10.0.0.77", HOST, now=T0)
    text = app.test_client().get("/api/internal/analytics", headers={"X-Internal-Key": "internal-key"}).get_data(as_text=True)
    assert "10.0.0.77" not in text and "Firefox" not in text and "visitor_hash" not in text
