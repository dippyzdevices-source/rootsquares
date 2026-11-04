"""Tests for sales close (7 tests), e.g. event without a cut off sells as before; a future cut off keeps selling and a past one stops it while the event; admin sets clears and validates the cut off."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_orders_checkout import _add_event, _add_type, _valid_payload

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_event_without_a_cut_off_sells_as_before():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        tt = _add_type(event.id)
        client = app.test_client()
        assert client.get(f"/api/tickets/types?event_id={event.id}").get_json()["items"][0]["status"] == "on_sale"
        detail = client.get(f"/api/events/{event.slug}").get_json()
        assert detail["sales_closed"] is False and detail["sales_close_at"] is None
        with patch("app.orders.routes.send_order_received_email"):
            assert client.post("/api/orders", json=_valid_payload(event.id, tt.id)).status_code == 201
        db.drop_all()


def test_a_future_cut_off_keeps_selling_and_a_past_one_stops_it_while_the_event_stays_live():
    app = _new_app()
    with app.app_context():
        event = _add_event(sales_close_at=NOW + timedelta(days=1))
        tt = _add_type(event.id)
        client = app.test_client()
        assert client.get(f"/api/tickets/types?event_id={event.id}").get_json()["items"][0]["status"] == "on_sale"
        assert client.get(f"/api/events/{event.slug}").get_json()["sales_closed"] is False

        event.sales_close_at = NOW - timedelta(minutes=1)
        db.session.commit()
        assert client.get(f"/api/tickets/types?event_id={event.id}").get_json()["items"][0]["status"] == "ended"
        body = client.get(f"/api/events/{event.slug}").get_json()
        assert body["sales_closed"] is True and body["sales_close_at"]
        # still live and still on the upcoming list
        assert [e["slug"] for e in client.get("/api/events").get_json()["items"]] == [event.slug]
        assert client.get("/api/events").get_json()["items"][0]["sales_closed"] is True

        refused = client.post("/api/orders", json=_valid_payload(event.id, tt.id))
        assert refused.status_code == 400
        assert refused.get_json()["errors"]["items"] == "Ticket sales for this event have closed."
        db.drop_all()


def test_admin_sets_clears_and_validates_the_cut_off():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        h = auth_header(make_user_and_token(role="admin")[1])
        client = app.test_client()
        created = client.post(
            "/api/admin/events", headers=h,
            json={"title": "Puja", "slug": "puja", "event_type": "festival", "start_datetime": "2027-10-09T10:00:00Z",
                  "sales_close_at": "2027-10-07T18:00:00Z"},
        ).get_json()
        assert created["sales_close_at"].startswith("2027-10-07T18:00") and created["sales_closed"] is False
        assert client.patch(f"/api/admin/events/{created['id']}", headers=h, json={"sales_close_at": "not a date"}).status_code == 400
        cleared = client.patch(f"/api/admin/events/{created['id']}", headers=h, json={"sales_close_at": None}).get_json()
        assert cleared["sales_close_at"] is None
        # a duplicated event does not inherit the old cut-off (dates belong to one event)
        client.patch(f"/api/admin/events/{created['id']}", headers=h, json={"sales_close_at": "2027-10-07T18:00:00Z"})
        copy = client.post(f"/api/admin/events/{created['id']}/duplicate", headers=h).get_json()
        assert copy["sales_close_at"] is None
        db.drop_all()


def test_one_ticket_type_can_be_closed_while_the_others_and_the_event_stay_open():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        dinner = _add_type(event.id, name="Dinner", sale_end=NOW - timedelta(hours=1))
        adult = _add_type(event.id, name="Adult")
        client = app.test_client()

        status = {t["name"]: t["status"] for t in client.get(f"/api/tickets/types?event_id={event.id}").get_json()["items"]}
        assert status == {"Dinner": "ended", "Adult": "on_sale"}
        assert client.get(f"/api/events/{event.slug}").get_json()["sales_closed"] is False  # the event itself is still selling

        refused = client.post("/api/orders", json=_valid_payload(event.id, dinner.id))
        assert refused.status_code == 400 and "not currently on sale" in refused.get_json()["errors"]["items"]
        with patch("app.orders.routes.send_order_received_email"):
            assert client.post("/api/orders", json=_valid_payload(event.id, adult.id)).status_code == 201
        db.drop_all()


def test_the_earlier_of_the_type_window_and_the_event_cut_off_wins_and_a_start_in_the_future_waits():
    app = _new_app()
    with app.app_context():
        # the event cut-off has passed even though this type's own window is still open
        event = _add_event(sales_close_at=NOW - timedelta(minutes=5))
        _add_type(event.id, sale_end=NOW + timedelta(days=2))
        later = _add_event(slug="later", sales_close_at=NOW + timedelta(days=1))
        _add_type(later.id, sale_start=NOW + timedelta(hours=3))
        client = app.test_client()
        assert client.get(f"/api/tickets/types?event_id={event.id}").get_json()["items"][0]["status"] == "ended"
        assert client.get(f"/api/tickets/types?event_id={later.id}").get_json()["items"][0]["status"] == "upcoming"
        db.drop_all()


def test_admin_sets_and_clears_a_ticket_type_sales_window():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        h = auth_header(make_user_and_token(role="admin")[1])
        event = _add_event()
        client = app.test_client()
        created = client.post(
            f"/api/admin/events/{event.id}/ticket-types", headers=h,
            json={"age_category": "other", "name": "Dinner", "price": 20000, "sale_end": "2027-10-07T18:00:00Z"},
        ).get_json()
        assert created["sale_end"].startswith("2027-10-07T18:00")
        cleared = client.patch(f"/api/admin/ticket-types/{created['id']}", headers=h, json={"sale_end": None}).get_json()
        assert cleared["sale_end"] is None
        assert client.patch(f"/api/admin/ticket-types/{created['id']}", headers=h, json={"sale_end": "tomorrow"}).status_code == 400
        db.drop_all()


def test_a_future_sales_open_time_holds_every_ticket_type_until_it_passes():
    app = _new_app()
    with app.app_context():
        event = _add_event(sales_open_at=NOW + timedelta(days=1))
        tt = _add_type(event.id)
        client = app.test_client()
        assert client.get(f"/api/tickets/types?event_id={event.id}").get_json()["items"][0]["status"] == "upcoming"
        body = client.get(f"/api/events/{event.slug}").get_json()
        assert body["sales_not_open"] is True and body["sales_open_at"]
        refused = client.post("/api/orders", json=_valid_payload(event.id, tt.id))
        assert refused.status_code == 400
        assert refused.get_json()["errors"]["items"] == "Ticket sales for this event have not opened yet."

        event.sales_open_at = NOW - timedelta(minutes=1)
        db.session.commit()
        assert client.get(f"/api/tickets/types?event_id={event.id}").get_json()["items"][0]["status"] == "on_sale"
        assert client.get(f"/api/events/{event.slug}").get_json()["sales_not_open"] is False
        db.drop_all()
