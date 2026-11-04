"""Tests for admin accounting routes (41 tests), e.g. non admin cannot access accounting summary; admin routes reject requests with no token; summary returns 404 for unknown event."""
import io
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
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


def _member_headers():
    _, token = make_user_and_token(role="member")
    return auth_header(token)


def _add_event(**overrides):
    from app.events.models import Event

    defaults = {
        "title": "Durga Puja 2026",
        "slug": "durga-puja-2026",
        "event_type": "festival",
        "start_datetime": NOW + timedelta(days=10),
        "published": True,
    }
    defaults.update(overrides)
    event = Event(**defaults)
    db.session.add(event)
    db.session.commit()
    return event


def _add_order(
    event, *, amount, payment_status, ticket_type=None, quantity=1,
    coupon_code=None, discount_amount=0,
):
    from app.orders.models import Order, OrderItem
    from app.tickets.models import Ticket, TicketType

    if ticket_type is None:
        ticket_type = TicketType(event_id=event.id, name="Adult", price=amount)
        db.session.add(ticket_type)
        db.session.commit()

    order = Order(
        order_number=f"BCA-2026-{db.session.query(Order).count() + 1:06d}",
        event_id=event.id,
        customer_name="Priya Das",
        customer_email="priya@example.com",
        total_amount=amount,
        payment_status=payment_status,
        coupon_code=coupon_code,
        discount_amount=discount_amount,
    )
    db.session.add(order)
    db.session.commit()
    item = OrderItem(
        order_id=order.id, ticket_type_id=ticket_type.id, quantity=quantity,
        unit_price=amount // quantity, subtotal=amount,
    )
    db.session.add(item)
    db.session.commit()

    if payment_status == "paid":
        for _ in range(quantity):
            db.session.add(Ticket(order_item_id=item.id, ticket_code=f"code-{item.id}-{_}"))
        db.session.commit()

    return order


def test_non_admin_cannot_access_accounting_summary():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _member_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}", headers=headers
            )
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        response = app.test_client().get(f"/api/admin/accounting/events/{event.id}")
        assert response.status_code == 401
        db.drop_all()


def test_summary_returns_404_for_unknown_event():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/accounting/events/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_summary_only_counts_paid_orders_as_collection():
    from app.accounting.models import Expense

    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_order(event, amount=1000, payment_status="paid")
        _add_order(event, amount=2000, payment_status="paid")
        _add_order(event, amount=500, payment_status="paid")
        _add_order(event, amount=9999, payment_status="pending_verification")
        _add_order(event, amount=8888, payment_status="cancelled")
        _add_order(event, amount=7777, payment_status="rejected")
        db.session.add(Expense(event_id=event.id, date=NOW.date(), description="Hall rent",
                                category="venue", amount=750, created_by=None))
        db.session.add(Expense(event_id=event.id, date=NOW.date(), description="Snacks",
                                category="food", amount=250, created_by=None))
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}", headers=headers
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["collection_total"] == 3500
        assert data["expenses_total"] == 1000
        assert data["net_total"] == 2500
        assert data["tickets_sold"] == 3
        db.drop_all()


def test_collections_lists_only_paid_orders():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_order(event, amount=1000, payment_status="paid")
        _add_order(event, amount=500, payment_status="pending")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}/collections", headers=headers
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["amount"] == 1000


def test_summary_includes_tickets_by_sale_mode():
    from app.orders.models import Order, OrderItem
    from app.payments.models import Payment
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        ticket_type = TicketType(event_id=event.id, name="Adult", price=1000)
        db.session.add(ticket_type)
        db.session.commit()

        def _paid_order_with_payment(provider):
            order = Order(
                order_number=f"BCA-2026-{db.session.query(Order).count() + 1:06d}",
                event_id=event.id, customer_name="Priya Das", customer_email="priya@example.com",
                total_amount=1000, payment_status="paid",
            )
            db.session.add(order)
            db.session.commit()
            item = OrderItem(
                order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                unit_price=1000, subtotal=1000,
            )
            db.session.add(item)
            db.session.commit()
            db.session.add(Ticket(order_item_id=item.id, ticket_code=f"code-{item.id}"))
            db.session.add(Payment(
                payment_type="event_ticket", order_id=order.id, provider=provider,
                amount=1000, status="paid",
            ))
            db.session.commit()

        _paid_order_with_payment("manual")
        _paid_order_with_payment("manual")
        _paid_order_with_payment("vipps")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}", headers=headers
            )

        by_mode = {row["provider"]: row["count"] for row in response.get_json()["tickets_by_sale_mode"]}
        assert by_mode == {"manual": 2, "vipps": 1}
        amounts = {row["provider"]: row["amount"] for row in response.get_json()["tickets_by_sale_mode"]}
        assert amounts == {"manual": 2000, "vipps": 1000}
        db.drop_all()


def test_summary_includes_coupon_usage_by_ticket_type():
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        adult = TicketType(event_id=event.id, name="Adult", price=1000)
        child = TicketType(event_id=event.id, name="Child", price=500)
        db.session.add_all([adult, child])
        db.session.commit()

        # MEMBER used on 2 orders (one adult-only, one mixed adult+child); FAMILY on 1 order.
        _add_order(event, amount=1000, payment_status="paid", ticket_type=adult, coupon_code="MEMBER", discount_amount=200)
        _add_order(event, amount=500, payment_status="paid", ticket_type=child, coupon_code="MEMBER", discount_amount=100)
        _add_order(event, amount=500, payment_status="paid", ticket_type=child, coupon_code="FAMILY", discount_amount=250)
        # No coupon at all — must not show up under coupon_usage.
        _add_order(event, amount=1000, payment_status="paid", ticket_type=adult)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}", headers=headers
            )

        coupon_usage = {row["coupon_code"]: row for row in response.get_json()["coupon_usage"]}
        assert set(coupon_usage) == {"MEMBER", "FAMILY"}

        member = coupon_usage["MEMBER"]
        assert member["orders_count"] == 2
        assert member["tickets_count"] == 2
        assert member["discount_total"] == 300
        assert member["paid_total"] == 1500 and member["gross_total"] == 1800
        # no Coupon row exists for this code, so its setup reads as unknown
        assert member["discount_percent"] is None and member["is_active"] is None
        assert {row["name"]: row["count"] for row in member["by_ticket_type"]} == {"Adult": 1, "Child": 1}

        family = coupon_usage["FAMILY"]
        assert family["orders_count"] == 1
        assert family["tickets_count"] == 1
        assert family["discount_total"] == 250
        assert {row["name"]: row["count"] for row in family["by_ticket_type"]} == {"Child": 1}
        db.drop_all()


def test_summary_tickets_by_type_are_sorted_by_day_with_undated_last():
    from datetime import date

    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        sun = TicketType(event_id=event.id, name="Sun Adult", price=1000, valid_on=date(2099, 10, 18))
        none = TicketType(event_id=event.id, name="Pass", price=1000)
        fri = TicketType(event_id=event.id, name="Fri Adult", price=1000, valid_on=date(2099, 10, 16))
        db.session.add_all([sun, none, fri])
        db.session.commit()
        for tt in (sun, none, fri):
            _add_order(event, amount=1000, payment_status="paid", ticket_type=tt)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            rows = app.test_client().get(f"/api/admin/accounting/events/{event.id}", headers=headers).get_json()["tickets_by_type"]

        assert [r["name"] for r in rows] == ["Fri Adult", "Sun Adult", "Pass"]
        assert rows[0]["valid_on"] == "2099-10-16" and rows[2]["valid_on"] is None

        # collection lines: same order, day shown for dated types
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            coll = app.test_client().get(f"/api/admin/accounting/events/{event.id}/collections", headers=headers).get_json()["items"]
        lines = sorted(l for item in coll for l in item["tickets"])
        assert lines == ["1 × Fri Adult · Fri 16 Oct", "1 × Pass", "1 × Sun Adult · Sun 18 Oct"]
        db.drop_all()


def test_summary_coupon_usage_lists_only_tickets_the_coupon_discounted():
    from app.coupons.models import Coupon
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        sat = TicketType(event_id=event.id, name="Saturday", price=1000)
        sun = TicketType(event_id=event.id, name="Sunday", price=1000)
        db.session.add_all([sat, sun])
        db.session.commit()
        db.session.add(Coupon(event_id=event.id, code="SAT", discount_percent=100, allowed_ticket_type_ids=str(sat.id)))
        db.session.commit()
        # one order carrying the SAT code with a Saturday ticket (discounted) ...
        _add_order(event, amount=0, payment_status="paid", ticket_type=sat, coupon_code="SAT", discount_amount=1000)
        # ... and a Sunday ticket in an order with the same code, paid in full
        _add_order(event, amount=1000, payment_status="paid", ticket_type=sun, coupon_code="SAT", discount_amount=0)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            usage = app.test_client().get(f"/api/admin/accounting/events/{event.id}", headers=headers).get_json()["coupon_usage"]

        assert len(usage) == 1
        assert usage[0]["tickets_count"] == 1
        assert [r["name"] for r in usage[0]["by_ticket_type"]] == ["Saturday"]
        db.drop_all()


def test_collection_and_expense_filters_accept_several_values():
    from app.orders.models import Order
    from app.payments.models import Payment
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        a = TicketType(event_id=event.id, name="A", price=1000)
        b = TicketType(event_id=event.id, name="B", price=1000)
        c = TicketType(event_id=event.id, name="C", price=1000)
        db.session.add_all([a, b, c])
        db.session.commit()
        for tt, code, provider in ((a, "X1", "cash"), (b, "X2", "vipps_qr"), (c, None, "vipps_app")):
            order = _add_order(event, amount=1000, payment_status="paid", ticket_type=tt, coupon_code=code)
            db.session.add(Payment(payment_type="event_ticket", order_id=order.id, provider=provider, amount=1000, status="paid"))
        db.session.commit()
        a_id, b_id = a.id, b.id

        def numbers(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                res = app.test_client().get(f"/api/admin/accounting/events/{event.id}/collections?{query}", headers=headers)
            return len(res.get_json()["items"])

        assert numbers("") == 3
        assert numbers(f"ticket_type_id={a_id}") == 1
        assert numbers(f"ticket_type_id={a_id},{b_id}") == 2
        assert numbers("coupon_code=x1,X2") == 2
        assert numbers("payment_method=cash,vipps_app") == 2
        assert numbers(f"ticket_type_id={a_id},{b_id}&payment_method=cash,vipps_app") == 1  # filters combine with AND
        assert numbers("payment_method=,") == 3  # empty values are no filter
        assert numbers("ticket_type_id=abc") == 3  # junk is ignored
        db.drop_all()


def test_expenses_filter_accepts_several_categories():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            for cat in ("venue", "food", "other"):
                client.post(
                    f"/api/admin/accounting/events/{event.id}/expenses",
                    headers=headers,
                    json={"date": "2026-01-01", "description": cat, "category": cat, "amount": 100},
                )
            res = client.get(f"/api/admin/accounting/events/{event.id}/expenses?category=venue,food", headers=headers)
        assert sorted(i["category"] for i in res.get_json()["items"]) == ["food", "venue"]
        db.drop_all()


def test_summary_coupon_usage_only_counts_paid_orders():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        _add_order(event, amount=1000, payment_status="paid", coupon_code="MEMBER", discount_amount=200)
        _add_order(event, amount=1000, payment_status="pending_verification", coupon_code="MEMBER", discount_amount=200)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}", headers=headers
            )

        coupon_usage = response.get_json()["coupon_usage"]
        assert len(coupon_usage) == 1
        assert coupon_usage[0]["orders_count"] == 1
        db.drop_all()


def test_summary_returns_empty_coupon_usage_when_no_coupons_used():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        _add_order(event, amount=1000, payment_status="paid")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}", headers=headers
            )

        assert response.get_json()["coupon_usage"] == []
        db.drop_all()


def test_summary_includes_top_expense_categories_ordered_by_amount():
    from app.accounting.models import Expense

    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        db.session.add(Expense(event_id=event.id, date=NOW.date(), description="Hall rent",
                                category="venue", amount=50000))
        db.session.add(Expense(event_id=event.id, date=NOW.date(), description="Catering",
                                category="food", amount=80000))
        db.session.add(Expense(event_id=event.id, date=NOW.date(), description="Flowers",
                                category="decoration", amount=10000))
        db.session.add(Expense(event_id=event.id, date=NOW.date(), description="Printing",
                                category="printing", amount=5000))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}", headers=headers
            )

        top = response.get_json()["top_expense_categories"]
        assert [row["category"] for row in top] == ["food", "venue", "decoration"]
        assert top[0]["amount"] == 80000
        db.drop_all()
        db.drop_all()


def test_create_expense_requires_positive_amount():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/accounting/events/{event.id}/expenses",
                headers=headers,
                json={
                    "date": "2026-01-01",
                    "description": "Bad expense",
                    "category": "venue",
                    "amount": 0,
                },
            )

        assert response.status_code == 400
        assert "amount" in response.get_json()["errors"]
        db.drop_all()


def test_create_expense_rejects_unknown_category():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/accounting/events/{event.id}/expenses",
                headers=headers,
                json={
                    "date": "2026-01-01",
                    "description": "Mystery",
                    "category": "not-a-real-category",
                    "amount": 100,
                },
            )

        assert response.status_code == 400
        assert "category" in response.get_json()["errors"]
        db.drop_all()


def test_create_expense_returns_404_for_unknown_event():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/accounting/events/999/expenses",
                headers=headers,
                json={"date": "2026-01-01", "description": "x", "category": "venue", "amount": 100},
            )
        assert response.status_code == 404
        db.drop_all()


def test_create_update_and_delete_expense_full_cycle():
    from app.accounting.models import Expense
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        event = _add_event()
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            create_response = client.post(
                f"/api/admin/accounting/events/{event.id}/expenses",
                headers=headers,
                json={
                    "date": "2026-01-15",
                    "description": "Hall rent",
                    "category": "venue",
                    "amount": 75000,
                    "vendor": "Community Hall",
                },
            )
            assert create_response.status_code == 201
            expense_id = create_response.get_json()["id"]
            assert create_response.get_json()["created_by"] == "admin@example.com"

            update_response = client.patch(
                f"/api/admin/accounting/expenses/{expense_id}",
                headers=headers,
                json={"amount": 80000, "notes": "Adjusted after final invoice"},
            )
            assert update_response.status_code == 200
            assert update_response.get_json()["amount"] == 80000

            delete_response = client.delete(
                f"/api/admin/accounting/expenses/{expense_id}", headers=headers
            )
            assert delete_response.status_code == 204

        assert db.session.get(Expense, expense_id) is None
        entry = AuditLog.query.filter_by(action="expense_deleted").one()
        assert entry.actor_user_id == admin_user.id
        assert entry.target_id == expense_id
        db.drop_all()


def test_expenses_are_filtered_by_event():
    app = _new_app()
    with app.app_context():
        event_a = _add_event(title="Event A", slug="event-a")
        event_b = _add_event(title="Event B", slug="event-b")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.post(
                f"/api/admin/accounting/events/{event_a.id}/expenses",
                headers=headers,
                json={"date": "2026-01-01", "description": "A expense", "category": "venue", "amount": 100},
            )
            client.post(
                f"/api/admin/accounting/events/{event_b.id}/expenses",
                headers=headers,
                json={"date": "2026-01-01", "description": "B expense", "category": "food", "amount": 200},
            )

            response_a = client.get(
                f"/api/admin/accounting/events/{event_a.id}/expenses", headers=headers
            )

        items = response_a.get_json()["items"]
        assert len(items) == 1
        assert items[0]["description"] == "A expense"
        db.drop_all()


def test_expenses_filter_by_category():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.post(
                f"/api/admin/accounting/events/{event.id}/expenses",
                headers=headers,
                json={"date": "2026-01-01", "description": "Rent", "category": "venue", "amount": 100},
            )
            client.post(
                f"/api/admin/accounting/events/{event.id}/expenses",
                headers=headers,
                json={"date": "2026-01-01", "description": "Snacks", "category": "food", "amount": 200},
            )

            response = client.get(
                f"/api/admin/accounting/events/{event.id}/expenses?category=food", headers=headers
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["category"] == "food"
        db.drop_all()


def test_update_expense_returns_404_for_unknown_expense():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/accounting/expenses/999", headers=headers, json={"amount": 100}
            )
        assert response.status_code == 404
        db.drop_all()


def test_delete_expense_returns_404_for_unknown_expense():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete(
                "/api/admin/accounting/expenses/999", headers=headers
            )
        assert response.status_code == 404
        db.drop_all()


def _create_expense(client, headers, event_id):
    response = client.post(
        f"/api/admin/accounting/events/{event_id}/expenses",
        headers=headers,
        json={"date": "2026-01-01", "description": "Rent", "category": "venue", "amount": 100},
    )
    return response.get_json()["id"]


def _png_bytes() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_upload_receipt_attaches_it_to_the_expense():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            expense_id = _create_expense(client, headers, event.id)

            response = client.post(
                f"/api/admin/accounting/expenses/{expense_id}/receipt",
                headers=headers,
                data={"file": (io.BytesIO(_png_bytes()), "receipt.png")},
                content_type="multipart/form-data",
            )

        body = response.get_json()
        assert response.status_code == 200
        assert body["receipt_key"] is not None
        assert body["receipt_url"] is not None
        db.drop_all()


def test_upload_receipt_rejects_unsupported_file_type():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            expense_id = _create_expense(client, headers, event.id)

            response = client.post(
                f"/api/admin/accounting/expenses/{expense_id}/receipt",
                headers=headers,
                data={"file": (io.BytesIO(b"not a real file"), "receipt.txt")},
                content_type="multipart/form-data",
            )

        assert response.status_code == 400
        assert "file" in response.get_json()["errors"]
        db.drop_all()


def test_upload_receipt_returns_404_for_unknown_expense():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/accounting/expenses/999/receipt",
                headers=headers,
                data={"file": (io.BytesIO(_png_bytes()), "receipt.png")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 404
        db.drop_all()


def test_replacing_a_receipt_uploads_the_new_one():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            expense_id = _create_expense(client, headers, event.id)

            first = client.post(
                f"/api/admin/accounting/expenses/{expense_id}/receipt",
                headers=headers,
                data={"file": (io.BytesIO(_png_bytes()), "receipt.png")},
                content_type="multipart/form-data",
            ).get_json()

            second = client.post(
                f"/api/admin/accounting/expenses/{expense_id}/receipt",
                headers=headers,
                data={"file": (io.BytesIO(b"second-file"), "receipt.pdf")},
                content_type="multipart/form-data",
            ).get_json()

        assert first["receipt_key"] != second["receipt_key"]
        db.drop_all()


def test_delete_receipt_clears_it_from_the_expense():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            expense_id = _create_expense(client, headers, event.id)
            client.post(
                f"/api/admin/accounting/expenses/{expense_id}/receipt",
                headers=headers,
                data={"file": (io.BytesIO(_png_bytes()), "receipt.png")},
                content_type="multipart/form-data",
            )

            response = client.delete(
                f"/api/admin/accounting/expenses/{expense_id}/receipt", headers=headers
            )

        body = response.get_json()
        assert response.status_code == 200
        assert body["receipt_key"] is None
        assert body["receipt_url"] is None
        db.drop_all()


def test_delete_receipt_returns_404_for_unknown_expense():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete(
                "/api/admin/accounting/expenses/999/receipt", headers=headers
            )
        assert response.status_code == 404
        db.drop_all()


def test_upload_receipt_converts_an_image_to_webp_and_caps_pdfs_at_2mb():
    from app.accounting.receipts import ReceiptValidationError, validate_receipt

    class F:
        def __init__(self, data, mimetype):
            self._d, self.mimetype = data, mimetype

        def read(self):
            return self._d

    data, content_type = validate_receipt(F(_png_bytes(), "image/png"))
    assert content_type == "image/webp" and data[:4] == b"RIFF"

    assert validate_receipt(F(b"%PDF-1", "application/pdf"))[1] == "application/pdf"
    try:
        validate_receipt(F(b"0" * (2 * 1024 * 1024 + 1), "application/pdf"))
        raise AssertionError("expected ReceiptValidationError")
    except ReceiptValidationError as exc:
        assert "2MB" in str(exc)


def test_export_event_buyers_has_a_buyers_sheet_and_a_tickets_sheet_for_paid_orders_only():
    from openpyxl import load_workbook

    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        other = _add_event(title="Other", slug="other")
        paid = _add_order(event, amount=3000, payment_status="paid", quantity=2, coupon_code="SAVE20", discount_amount=600)
        paid.customer_phone = "41234567"
        _add_order(event, amount=500, payment_status="pending")
        _add_order(other, amount=900, payment_status="paid")
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}/collections/export", headers=headers
            )

        assert response.status_code == 200
        assert "durga-puja-2026-buyers.xlsx" in response.headers["Content-Disposition"]
        wb = load_workbook(io.BytesIO(response.data))
        assert wb.sheetnames == ["Buyers", "Tickets", "Donations & sponsors"]

        buyers = list(wb["Buyers"].iter_rows(values_only=True))
        header = list(buyers[0])
        assert len(buyers) == 2  # header + the one paid order of THIS event
        row = dict(zip(header, buyers[1]))
        assert row["Order number"] == paid.order_number
        assert (row["Name"], row["Email"], row["Phone"]) == ("Priya Das", "priya@example.com", "41234567")
        assert row["Tickets"] == "2 × Adult" and row["Ticket count"] == 2
        assert (row["Coupon"], row["Discount (NOK)"], row["Amount paid (NOK)"]) == ("SAVE20", 6.0, 30.0)

        tickets = list(wb["Tickets"].iter_rows(values_only=True))
        assert len(tickets) == 3  # header + 2 individual tickets
        assert {dict(zip(tickets[0], t))["Status"] for t in tickets[1:]} == {"valid"}
        assert Order.query.count() == 3
        db.drop_all()


def test_export_event_expenses_lists_this_events_expenses_with_a_total_row():
    from datetime import date

    from openpyxl import load_workbook

    from app.accounting.models import Expense

    app = _new_app()
    with app.app_context():
        event = _add_event()
        other = _add_event(title="Other", slug="other")
        db.session.add_all(
            [
                Expense(event_id=event.id, date=date(2026, 10, 2), description="Hall", category="venue", amount=250000, vendor="Hall AS", receipt_key="r/1"),
                Expense(event_id=event.id, date=date(2026, 10, 1), description="Flowers", category="decoration", amount=40050, notes="for stage"),
                Expense(event_id=other.id, date=date(2026, 10, 1), description="Not mine", category="other", amount=999),
            ]
        )
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            response = client.get(f"/api/admin/accounting/events/{event.id}/expenses/export", headers=headers)
            empty = client.get(f"/api/admin/accounting/events/{other.id + 5}/expenses/export", headers=headers)

        assert response.status_code == 200 and empty.status_code == 404
        assert "durga-puja-2026-expenses.xlsx" in response.headers["Content-Disposition"]
        rows = list(load_workbook(io.BytesIO(response.data)).active.iter_rows(values_only=True))
        header = list(rows[0])
        data = [dict(zip(header, r)) for r in rows[1:]]
        assert [r["Description"] for r in data[:2]] == ["Flowers", "Hall"]  # oldest first
        assert (data[0]["Category"], data[0]["Amount (NOK)"], data[0]["Receipt attached"]) == ("Decoration", 400.5, "No")
        assert (data[1]["Vendor"], data[1]["Receipt attached"]) == ("Hall AS", "Yes")
        assert data[2]["Date"] == "Total" and data[2]["Amount (NOK)"] == 2900.5  # the other event's expense is excluded
        db.drop_all()


def test_export_event_buyers_requires_admin_and_a_real_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        client = app.test_client()
        assert client.get(f"/api/admin/accounting/events/{event.id}/collections/export").status_code == 401
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            assert client.get(
                f"/api/admin/accounting/events/{event.id}/collections/export", headers=_member_headers()
            ).status_code == 403
            assert client.get(
                "/api/admin/accounting/events/9999/collections/export", headers=_admin_headers()
            ).status_code == 404
            assert client.get(
                f"/api/admin/accounting/events/{event.id}/expenses/export", headers=_member_headers()
            ).status_code == 403
        db.drop_all()


def test_summary_event_carries_published_and_dates_for_the_draft_marker():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(f"/api/admin/accounting/events/{event.id}", headers=headers)

        assert response.status_code == 200
        summary_event = response.get_json()["event"]
        assert summary_event["published"] == event.published
        assert summary_event["start_datetime"].startswith(event.start_datetime.date().isoformat())
        assert "end_datetime" in summary_event
        db.drop_all()


def test_summary_coupon_usage_carries_the_coupons_own_setup():
    from app.coupons.models import Coupon
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        adult = TicketType(event_id=event.id, name="Adult", price=1000)
        db.session.add_all([adult, Coupon(event_id=event.id, code="MEMBER", discount_percent=20, is_active=False, max_redemptions=40)])
        db.session.commit()
        _add_order(event, amount=800, payment_status="paid", ticket_type=adult, coupon_code="MEMBER", discount_amount=200)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            row = app.test_client().get(f"/api/admin/accounting/events/{event.id}", headers=headers).get_json()["coupon_usage"][0]

        assert (row["discount_percent"], row["is_active"], row["max_redemptions"]) == (20, False, 40)
        assert (row["paid_total"], row["gross_total"], row["discount_total"]) == (800, 1000, 200)
        db.drop_all()


def test_summary_counts_event_check_in_and_ignores_voided_tickets():
    from app.orders.models import OrderItem
    from app.tickets.models import Ticket

    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        _add_order(event, amount=1000, payment_status="paid", quantity=3)
        item = db.session.query(OrderItem).first()
        tickets = Ticket.query.filter_by(order_item_id=item.id).all()
        tickets[0].status = "used"
        tickets[1].status = "void"
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            data = app.test_client().get(f"/api/admin/accounting/events/{event.id}", headers=headers).get_json()

        assert data["tickets_sold"] == 3
        assert data["tickets_expected"] == 2
        assert data["tickets_checked_in"] == 1
        db.drop_all()


def test_collections_list_and_export_share_the_search_method_and_ticket_type_filters():
    from openpyxl import load_workbook

    from app.orders.models import Order
    from app.payments.models import Payment
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = TicketType(event_id=event.id, name="Adult", price=1000)
        child = TicketType(event_id=event.id, name="Child", price=0)
        db.session.add_all([adult, child])
        db.session.commit()
        cash_order = _add_order(event, amount=1000, payment_status="paid", ticket_type=adult)
        qr_order = _add_order(event, amount=1000, payment_status="paid", ticket_type=child)
        free_order = _add_order(event, amount=1000, payment_status="paid", ticket_type=adult, coupon_code="FREE")
        qr_order.customer_name = "Rohan Sen"
        db.session.add_all(
            [
                Payment(payment_type="event_ticket", order_id=cash_order.id, provider="cash", amount=1000, status="paid"),
                Payment(payment_type="event_ticket", order_id=qr_order.id, provider="vipps_qr", amount=1000, status="paid"),
            ]
        )
        db.session.commit()
        headers = _admin_headers()
        base = f"/api/admin/accounting/events/{event.id}/collections"

        def listed(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"{base}{query}", headers=headers)
            assert response.status_code == 200
            return {i["order_number"] for i in response.get_json()["items"]}

        def exported(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"{base}/export{query}", headers=headers)
            assert response.status_code == 200
            rows = list(load_workbook(io.BytesIO(response.data))["Buyers"].iter_rows(values_only=True))
            return {r[0] for r in rows[1:]}

        everyone = {cash_order.order_number, qr_order.order_number, free_order.order_number}
        assert listed("") == everyone and exported("") == everyone
        for query, expected in (
            ("?payment_method=cash", {cash_order.order_number}),
            ("?payment_method=coupon", {free_order.order_number}),
            ("?coupon_code=free", {free_order.order_number}),
            ("?coupon_code=NOPE", set()),
            (f"?ticket_type_id={child.id}", {qr_order.order_number}),
            ("?q=rohan", {qr_order.order_number}),
            ("?payment_method=cash&q=rohan", set()),
        ):
            assert listed(query) == expected, query
            assert exported(query) == expected, query
        assert Order.query.count() == 3
        db.drop_all()


def test_expenses_export_can_be_narrowed_by_category_and_total_covers_only_those_rows():
    from datetime import date

    from openpyxl import load_workbook

    from app.accounting.models import Expense

    app = _new_app()
    with app.app_context():
        event = _add_event()
        db.session.add_all(
            [
                Expense(event_id=event.id, date=date(2026, 10, 2), description="Hall", category="venue", amount=250000),
                Expense(event_id=event.id, date=date(2026, 10, 1), description="Flowers", category="decoration", amount=40050),
            ]
        )
        db.session.commit()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}/expenses/export?category=venue", headers=_admin_headers()
            )
        rows = list(load_workbook(io.BytesIO(response.data)).active.iter_rows(values_only=True))
        assert [r[1] for r in rows[1:3]] == ["Hall", None]  # one expense, then the Total row
        assert rows[2][0] == "Total" and rows[2][4] == 2500.0
        db.drop_all()


def test_collections_rows_say_what_each_order_bought():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_order(event, amount=3000, payment_status="paid", quantity=2)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                f"/api/admin/accounting/events/{event.id}/collections", headers=_admin_headers()
            )
        assert response.get_json()["items"][0]["tickets"] == ["2 × Adult"]
        db.drop_all()


def test_pdf_report_lists_what_each_order_bought_only_when_details_is_asked_for():
    from app.accounting import report_pdf

    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_order(event, amount=3000, payment_status="paid", quantity=2)
        headers = _admin_headers()
        seen = []
        real_table = report_pdf._table

        def spy(pdf, header, rows, *args, **kwargs):
            if header and header[0] == "Date" and "Reference" in header:
                seen.append(rows)
            return real_table(pdf, header, rows, *args, **kwargs)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()), patch.object(
            report_pdf, "_table", spy
        ):
            client = app.test_client()
            plain = client.get(f"/api/admin/accounting/events/{event.id}/report", headers=headers)
            detailed = client.get(f"/api/admin/accounting/events/{event.id}/report?details=1", headers=headers)

        assert plain.status_code == 200 and detailed.status_code == 200
        assert len(seen[0]) == 1  # one order row, nothing under it
        assert len(seen[1]) == 2 and "2 × Adult" in seen[1][1][1][0]  # plus the line saying what it bought
        db.drop_all()


def test_pdf_hero_helpers_round_the_cards_and_describe_the_schedule():
    from datetime import datetime
    from types import SimpleNamespace

    from app.accounting.report_pdf import _schedule, money_rounded

    assert money_rounded(-5700240) == "-57 002 kr" and money_rounded(0) == "0 kr"
    multi = SimpleNamespace(start_datetime=datetime(2026, 10, 16, 10), end_datetime=datetime(2026, 10, 18, 22))
    assert _schedule(multi) == ("Multi-day event · 3 days", "16 Oct 2026 – 18 Oct 2026")
    single = SimpleNamespace(start_datetime=datetime(2026, 10, 16, 10), end_datetime=datetime(2026, 10, 16, 22))
    assert _schedule(single) == ("Single-day event", "16 Oct 2026 · 10:00 – 22:00")


def test_pdf_coupon_table_draws_with_and_without_a_redemption_limit():
    from app.accounting.report_pdf import _Report, _coupon_table

    pdf = _Report("t", "now")
    pdf.add_page()
    base = {"is_active": True, "orders_count": 2, "gross_total": 1000, "discount_total": 500, "paid_total": 500, "by_ticket_type": [{"name": "Lunch", "valid_on": "2026-10-17", "count": 2}]}
    _coupon_table(pdf, [
        {**base, "coupon_code": "A", "discount_percent": 50, "max_redemptions": 10, "tickets_count": 4},
        {**base, "coupon_code": "B", "discount_percent": None, "max_redemptions": None, "tickets_count": 2, "is_active": False},
    ])
    assert bytes(pdf.output()).startswith(b"%PDF")
