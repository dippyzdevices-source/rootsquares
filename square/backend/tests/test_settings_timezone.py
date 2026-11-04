"""Tests for settings timezone (3 tests), e.g. timezone defaults to oslo and an admin can change it to a real zone on; site timezone follows the setting and falls back to utc; refund cut off uses the squares own day."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.payments.admin_routes import _refund_block_reason
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def test_timezone_defaults_to_oslo_and_an_admin_can_change_it_to_a_real_zone_only():
    """rootsquares W6-R54: a square has its own time zone (bca-oslo hardcoded Europe/Oslo)."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        assert client.get("/api/settings").get_json()["timezone"] == "Europe/Oslo"
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            ok = client.patch("/api/admin/settings", json={"timezone": " Asia/Dhaka "}, headers=headers)
            bad = [client.patch("/api/admin/settings", json={"timezone": v}, headers=headers).status_code for v in ("Mars/Base", "", 5)]
        assert ok.status_code == 200 and ok.get_json()["timezone"] == "Asia/Dhaka"
        assert bad == [400, 400, 400]
        assert client.get("/api/settings").get_json()["timezone"] == "Asia/Dhaka"
        db.drop_all()


def test_site_timezone_follows_the_setting_and_falls_back_to_utc():
    from app.common.site import site_timezone
    from app.settings.models import get_site_settings

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        assert str(site_timezone()) == "Europe/Oslo"
        settings = get_site_settings()
        settings.timezone = "America/New_York"
        assert str(site_timezone()) == "America/New_York"
        settings.timezone = "Nowhere/None"
        assert str(site_timezone()) == "UTC"
        db.drop_all()


def test_refund_cut_off_uses_the_squares_own_day():
    """An event that ended 20:00 UTC on 1 Oct: at 23:40 UTC it is still 1 Oct in New York (event day) but already 2 Oct in Oslo."""
    from app.settings.models import get_site_settings

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 1, 23, 40, tzinfo=timezone.utc).astimezone(tz)

    app = create_app("testing")
    with app.app_context():
        db.create_all()
        from app.events.models import Event
        from app.orders.models import Order
        from app.payments.models import Payment

        ended = datetime(2026, 10, 1, 20, 0, tzinfo=timezone.utc)
        event = Event(title="E", slug="e", event_type="cultural", start_datetime=ended - timedelta(hours=2), end_datetime=ended, status="published")
        db.session.add(event)
        db.session.flush()
        order = Order(order_number="X-1", event_id=event.id, customer_name="n", customer_email="e@x.org", total_amount=100)
        db.session.add(order)
        db.session.flush()
        payment = Payment(order_id=order.id, payment_type="event_ticket", provider="cash", amount=100)
        with patch("app.payments.admin_routes.datetime", Frozen):
            get_site_settings().timezone = "Europe/Oslo"  # now = 2 Oct 01:40 in Oslo, the event was on 1 Oct: closed
            assert _refund_block_reason(payment) == "Refunds are not allowed after the event day."
            get_site_settings().timezone = "America/New_York"  # now = 1 Oct 19:40 in New York, still the event day: open
            assert _refund_block_reason(payment) is None
        db.session.rollback()
        db.drop_all()
