"""Tests for admin tickets routes (12 tests), e.g. admin routes reject requests with no token; admin routes reject a volunteer role; admin routes allow a cors preflight with no auth header."""
from datetime import datetime, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.events.models import Event
from app.orders.models import Order, OrderItem
from app.tickets.models import Ticket, TicketType
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _add_ticket(event_title="Durga Puja 2026", event_slug="durga-puja-2026", status="valid",
                customer_name="Priya Das", customer_email="priya@example.com",
                ticket_code="abc123"):
    event = Event(title=event_title, slug=event_slug, event_type="festival", start_datetime=NOW)
    db.session.add(event)
    db.session.commit()
    ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
    db.session.add(ticket_type)
    db.session.commit()
    order = Order(order_number=f"BCA-2026-{event.id:06d}", event_id=event.id,
                  customer_name=customer_name, customer_email=customer_email,
                  total_amount=15000)
    db.session.add(order)
    db.session.commit()
    item = OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                     unit_price=15000, subtotal=15000)
    db.session.add(item)
    db.session.commit()
    ticket = Ticket(order_item_id=item.id, ticket_code=ticket_code, status=status)
    db.session.add(ticket)
    db.session.commit()
    return event, ticket


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/tickets")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_volunteer_role():
    # This one is admin-only, unlike checkin_bp's admin+volunteer scan/summary routes.
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="volunteer")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/tickets", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/tickets", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_list_tickets_includes_customer_type_event_and_status():
    app = _new_app()
    with app.app_context():
        _add_ticket()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/tickets", headers=_admin_headers())

        assert response.status_code == 200
        item = response.get_json()["items"][0]
        assert item["ticket_code"] == "abc123"
        assert item["customer_name"] == "Priya Das"
        assert item["customer_email"] == "priya@example.com"
        assert item["ticket_type"] == "Adult"
        assert item["event_title"] == "Durga Puja 2026"
        assert item["status"] == "valid"
        assert item["issued_at"] is not None
        assert item["checked_in_at"] is None
        assert item["checked_in_by"] is None
        db.drop_all()


def test_list_tickets_includes_checked_in_details_once_used():
    app = _new_app()
    with app.app_context():
        admin_user, token = make_user_and_token(role="admin", email="door@example.com")
        _add_ticket()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.post("/api/admin/checkin/scan",
                       json={"ticket_code": "abc123"}, headers=auth_header(token))
            response = client.get("/api/admin/tickets", headers=auth_header(token))

        item = response.get_json()["items"][0]
        assert item["status"] == "used"
        assert item["checked_in_at"] is not None
        assert item["checked_in_by"] == "door@example.com"
        db.drop_all()


def test_list_tickets_filters_by_event_id():
    app = _new_app()
    with app.app_context():
        event1, _ = _add_ticket(event_title="Durga Puja 2026", event_slug="durga-puja-2026",
                                ticket_code="code1")
        event2, _ = _add_ticket(event_title="Saraswati Puja 2026", event_slug="saraswati-puja-2026",
                                ticket_code="code2")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/tickets?event_id={event1.id}", headers=_admin_headers()
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["ticket_code"] == "code1"
        db.drop_all()


def test_list_tickets_filters_by_status():
    app = _new_app()
    with app.app_context():
        _add_ticket(ticket_code="valid-one", status="valid")
        _add_ticket(event_title="Other Event", event_slug="other-event",
                   ticket_code="used-one", status="used")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/tickets?status=used", headers=_admin_headers()
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["ticket_code"] == "used-one"
        db.drop_all()


def test_list_tickets_sorts_by_checked_in_at_descending():
    # Ticket creation order (id) is unrelated to scan order — the admin Check-in overview's
    # "Last scans" list needs the most-recently-*scanned* ticket first, not the newest ticket.
    app = _new_app()
    with app.app_context():
        _, first = _add_ticket(event_title="Durga Puja 2026", event_slug="durga-puja-2026",
                               ticket_code="first-created", status="used")
        first.checked_in_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _, second = _add_ticket(event_title="Other Event", event_slug="other-event",
                                ticket_code="second-created", status="used")
        second.checked_in_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/tickets?sort=checked_in_at_desc", headers=_admin_headers()
            )

        codes = [item["ticket_code"] for item in response.get_json()["items"]]
        assert codes == ["second-created", "first-created"]
        db.drop_all()


def test_list_tickets_rejects_an_invalid_status_filter():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/tickets?status=bogus", headers=_admin_headers()
            )
        assert response.status_code == 400
        db.drop_all()


def test_list_tickets_searches_by_code_name_or_email():
    app = _new_app()
    with app.app_context():
        _add_ticket(customer_name="Priya Das", customer_email="priya@example.com",
                   ticket_code="findme")
        _add_ticket(event_title="Other Event", event_slug="other-event",
                   customer_name="Rohan Sen", customer_email="rohan@example.com",
                   ticket_code="other-code")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/tickets?q=rohan", headers=_admin_headers()
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["customer_name"] == "Rohan Sen"
        db.drop_all()


def test_export_tickets_returns_an_xlsx_file():
    from io import BytesIO
    from openpyxl import load_workbook

    app = _new_app()
    with app.app_context():
        _add_ticket()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/tickets/export", headers=_admin_headers())

        assert response.status_code == 200
        assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        workbook = load_workbook(BytesIO(response.data))
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        assert rows[0][0] == "Ticket code"
        assert rows[1][0] == "abc123"
        assert rows[1][1] == "Priya Das"
        db.drop_all()


def test_export_tickets_uses_the_same_filters_as_the_list():
    from io import BytesIO
    from openpyxl import load_workbook

    app = _new_app()
    with app.app_context():
        _add_ticket(ticket_code="valid-1", status="valid", event_title="A", event_slug="a")
        _add_ticket(ticket_code="used-1", status="used", customer_name="Rohan Sen", event_title="B", event_slug="b")

        def exported(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"/api/admin/tickets/export{query}", headers=_admin_headers())
            assert response.status_code == 200
            return [r[0] for r in list(load_workbook(BytesIO(response.data)).active.iter_rows(values_only=True))[1:]]

        assert sorted(exported("")) == ["used-1", "valid-1"]
        assert exported("?status=used") == ["used-1"]
        assert exported("?q=rohan") == ["used-1"]
        db.drop_all()
