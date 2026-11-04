"""Tests for orders checkout (49 tests), e.g. checkout succeeds as a guest; checkout attaches user id when authenticated; checkout requires customer name and email."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


# Per-event ticket limits (Event.max_tickets_per_email / coupon_max_adult / coupon_max_child);
# blank = unlimited, which is what every other test's plain `_add_event()` gets.
LIMITS = {"max_tickets_per_email": 4, "coupon_max_adult": 2, "coupon_max_child": 2}

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


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


def _add_type(event_id, **overrides):
    from app.tickets.models import TicketType

    defaults = {"event_id": event_id, "name": "Adult", "price": 15000}
    defaults.update(overrides)
    ticket_type = TicketType(**defaults)
    db.session.add(ticket_type)
    db.session.commit()
    return ticket_type


def _add_coupon(event_id, **overrides):
    from app.coupons.models import Coupon

    defaults = {"event_id": event_id, "code": "SAVE20", "discount_percent": 20}
    defaults.update(overrides)
    coupon = Coupon(**defaults)
    db.session.add(coupon)
    db.session.commit()
    return coupon


def _valid_payload(event_id, ticket_type_id, **overrides):
    payload = {
        "event_id": event_id,
        "items": [{"ticket_type_id": ticket_type_id, "quantity": 2}],
        "customer_name": "Priya Das",
        "customer_email": "priya@example.com",
        "customer_phone": "41234567",
    }
    payload.update(overrides)
    return payload


def test_checkout_succeeds_as_a_guest():
    from app.orders.models import Order
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, price=15000)

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, ticket_type.id)
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["total_amount"] == 30000
        assert data["payment_status"] == "pending"
        assert data["order_number"].startswith("BCA-")
        assert Order.query.count() == 1
        assert Order.query.one().user_id is None
        assert Payment.query.count() == 1
        db.drop_all()


def test_checkout_attaches_user_id_when_authenticated():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        user, token = make_user_and_token(email="priya@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/orders",
                json=_valid_payload(event.id, ticket_type.id),
                headers=auth_header(token),
            )

        assert response.status_code == 201
        assert Order.query.one().user_id == user.id
        db.drop_all()


def test_checkout_requires_customer_name_and_email():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)

        response = app.test_client().post(
            "/api/orders",
            json={"event_id": event.id, "items": [{"ticket_type_id": ticket_type.id, "quantity": 1}]},
        )

        assert response.status_code == 400
        assert set(response.get_json()["errors"]) == {"customer_name", "customer_email", "customer_phone"}
        db.drop_all()


def test_checkout_rejects_a_malformed_email():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)

        response = app.test_client().post(
            "/api/orders",
            json=_valid_payload(event.id, ticket_type.id, customer_email="not-an-email"),
        )

        assert response.status_code == 400
        assert "customer_email" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_accepts_a_norwegian_mobile_number_in_various_formats():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)

        for i, phone in enumerate(("41234567", "412 34 567", "+47 412 34 567", "0047 412 34 567")):
            # A distinct email per iteration — otherwise the per-email/event ticket cap (max 4)
            # would trip on the 3rd iteration, which has nothing to do with what this test checks.
            response = app.test_client().post(
                "/api/orders",
                json=_valid_payload(event.id, ticket_type.id, customer_phone=phone, customer_email=f"priya{i}@example.com"),
            )
            assert response.status_code == 201, phone

        assert Order.query.count() == 4
        db.drop_all()


def test_checkout_rejects_a_phone_number_that_isnt_8_digits():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)

        response = app.test_client().post(
            "/api/orders",
            json=_valid_payload(event.id, ticket_type.id, customer_phone="+47 123"),
        )

        assert response.status_code == 400
        assert "customer_phone" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_requires_a_phone_number():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)

        response = app.test_client().post(
            "/api/orders",
            json=_valid_payload(event.id, ticket_type.id, customer_phone=""),
        )

        assert response.status_code == 400
        assert "customer_phone" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_returns_404_for_an_unpublished_event():
    app = _new_app()
    with app.app_context():
        event = _add_event(published=False)
        ticket_type = _add_type(event.id)

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, ticket_type.id)
        )

        assert response.status_code == 404
        db.drop_all()


def test_checkout_allows_an_authenticated_admin_to_buy_a_ticket_for_an_unpublished_event():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event(published=False)
        ticket_type = _add_type(event.id)
        _, token = make_user_and_token(role="admin")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/orders",
                json=_valid_payload(event.id, ticket_type.id),
                headers=auth_header(token),
            )

        assert response.status_code == 201
        assert Order.query.count() == 1
        db.drop_all()


def test_checkout_still_returns_404_for_a_non_admin_authenticated_user_on_an_unpublished_event():
    app = _new_app()
    with app.app_context():
        event = _add_event(published=False)
        ticket_type = _add_type(event.id)
        _, token = make_user_and_token(role="member")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/orders",
                json=_valid_payload(event.id, ticket_type.id),
                headers=auth_header(token),
            )

        assert response.status_code == 404
        db.drop_all()


def test_checkout_rejects_a_ticket_type_from_a_different_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        other_event = _add_event(slug="other-event")
        other_type = _add_type(other_event.id)

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, other_type.id)
        )

        assert response.status_code == 400
        assert "items" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_rejects_a_ticket_type_outside_its_sale_window():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, sale_end=NOW - timedelta(days=1))

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, ticket_type.id)
        )

        assert response.status_code == 400
        assert "items" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_rejects_a_quantity_exceeding_remaining_capacity():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, capacity=1)

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, ticket_type.id)
        )

        assert response.status_code == 400
        assert "items" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_rejects_a_child_ticket_with_no_adult_ticket():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        child = _add_type(event.id, name="Child", price=5000, age_category="child")

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, child.id)
        )

        assert response.status_code == 400
        assert "items" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_allows_a_child_ticket_alongside_an_adult_ticket():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult", price=15000, age_category="adult")
        child = _add_type(event.id, name="Child", price=5000, age_category="child")

        payload = {
            "event_id": event.id,
            "items": [
                {"ticket_type_id": adult.id, "quantity": 1},
                {"ticket_type_id": child.id, "quantity": 2},
            ],
            "customer_name": "Priya Das",
            "customer_email": "priya@example.com",
            "customer_phone": "41234567",
        }
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        assert Order.query.count() == 1
        db.drop_all()


def test_checkout_allows_only_adult_tickets_with_no_child():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult", price=15000, age_category="adult")

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, adult.id)
        )

        assert response.status_code == 201
        db.drop_all()


def test_checkout_allows_only_other_category_tickets():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        vip = _add_type(event.id, name="VIP", price=50000, age_category="other")

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, vip.id)
        )

        assert response.status_code == 201
        db.drop_all()


def test_checkout_calculates_total_from_multiple_items_server_side():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult", price=15000)
        child = _add_type(event.id, name="Child", price=5000)

        payload = {
            "event_id": event.id,
            "items": [
                {"ticket_type_id": adult.id, "quantity": 2},
                {"ticket_type_id": child.id, "quantity": 1},
            ],
            "customer_name": "Priya Das",
            "customer_email": "priya@example.com",
            "customer_phone": "41234567",
        }
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        # 2*15000 + 1*5000 = 35000, regardless of any price the client might have sent
        assert Order.query.one().total_amount == 35000
        db.drop_all()


def test_checkout_ignores_a_client_supplied_price():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, price=15000)

        payload = _valid_payload(event.id, ticket_type.id)
        payload["items"][0]["price"] = 1  # attempted price tampering

        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        assert Order.query.one().total_amount == 30000  # server price, not the tampered one
        db.drop_all()


def test_checkout_applies_a_percentage_coupon_case_insensitively():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, price=15000)  # qty 2 -> 30000
        _add_coupon(event.id, code="SAVE20", discount_percent=20)

        payload = _valid_payload(event.id, ticket_type.id, coupon_code="save20")
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.get_json()
        assert data["coupon_code"] == "SAVE20"
        assert data["discount_amount"] == 6000  # 20% of 30000
        assert data["total_amount"] == 24000
        order = Order.query.one()
        assert order.payment_status == "pending"  # still needs collecting — not a 100% coupon
        db.drop_all()


def test_checkout_rejects_an_unknown_coupon_code():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, ticket_type.id, coupon_code="NOPE")
        )

        assert response.status_code == 400
        assert "coupon_code" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_rejects_an_inactive_coupon_code():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        _add_coupon(event.id, is_active=False)

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, ticket_type.id, coupon_code="SAVE20")
        )

        assert response.status_code == 400
        assert "coupon_code" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_rejects_a_coupon_code_from_a_different_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        other_event = _add_event(slug="other-event")
        ticket_type = _add_type(event.id)
        _add_coupon(other_event.id)

        response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, ticket_type.id, coupon_code="SAVE20")
        )

        assert response.status_code == 400
        assert "coupon_code" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_rejects_more_than_2_adult_tickets_with_a_coupon():
    app = _new_app()
    with app.app_context():
        event = _add_event(**LIMITS)
        adult = _add_type(event.id, name="Adult", price=15000, age_category="adult")
        _add_coupon(event.id)

        payload = {
            "event_id": event.id,
            "items": [{"ticket_type_id": adult.id, "quantity": 3}],
            "customer_name": "Priya Das",
            "customer_email": "priya@example.com",
            "customer_phone": "41234567",
            "coupon_code": "SAVE20",
        }
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 400
        assert "coupon_code" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_rejects_more_than_2_child_tickets_with_a_coupon():
    app = _new_app()
    with app.app_context():
        event = _add_event(**LIMITS)
        adult = _add_type(event.id, name="Adult", price=15000, age_category="adult")
        child = _add_type(event.id, name="Child", price=5000, age_category="child")
        _add_coupon(event.id)

        payload = {
            "event_id": event.id,
            "items": [
                {"ticket_type_id": adult.id, "quantity": 1},
                {"ticket_type_id": child.id, "quantity": 3},
            ],
            "customer_name": "Priya Das",
            "customer_email": "priya@example.com",
            "customer_phone": "41234567",
            "coupon_code": "SAVE20",
        }
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 400
        assert "coupon_code" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_allows_2_adults_and_2_children_with_a_coupon():
    app = _new_app()
    with app.app_context():
        event = _add_event(**LIMITS)
        adult = _add_type(event.id, name="Adult", price=15000, age_category="adult")
        child = _add_type(event.id, name="Child", price=5000, age_category="child")
        _add_coupon(event.id, discount_percent=10)

        payload = {
            "event_id": event.id,
            "items": [
                {"ticket_type_id": adult.id, "quantity": 2},
                {"ticket_type_id": child.id, "quantity": 2},
            ],
            "customer_name": "Priya Das",
            "customer_email": "priya@example.com",
            "customer_phone": "41234567",
            "coupon_code": "SAVE20",
        }
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        db.drop_all()


def test_checkout_does_not_enforce_the_adult_child_cap_without_a_coupon():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult", price=15000, age_category="adult")

        # Quantity 3 exceeds the coupon-specific MAX_COUPON_ADULT_QTY (2) but stays within the
        # general per-email/event ticket cap (4) — this test is only about the former not
        # applying without a coupon, not about the latter.
        payload = {
            "event_id": event.id,
            "items": [{"ticket_type_id": adult.id, "quantity": 3}],
            "customer_name": "Priya Das",
            "customer_email": "priya@example.com",
            "customer_phone": "41234567",
        }
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        db.drop_all()


def test_checkout_with_a_100_percent_coupon_issues_tickets_immediately():
    from app.orders.models import Order
    from app.tickets.models import Ticket

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, price=15000)
        _add_coupon(event.id, code="FREE100", discount_percent=100)

        payload = _valid_payload(event.id, ticket_type.id, coupon_code="FREE100")
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.get_json()
        assert data["total_amount"] == 0
        assert data["payment_status"] == "paid"
        assert data["order_status"] == "confirmed"

        order = Order.query.one()
        assert order.payment_status == "paid"
        # 2 tickets — the payload's quantity — created with no admin mark-paid step at all.
        assert Ticket.query.count() == 2
        from app.payments.models import Payment

        assert Payment.query.count() == 0  # nothing to collect, no Payment row needed
        db.drop_all()


def test_checkout_with_a_100_percent_coupon_auto_deactivates_it_at_the_redemption_limit():
    from app.coupons.models import Coupon

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, price=15000)
        # _valid_payload requests quantity=2 — max_redemptions=2 means this single order exactly
        # exhausts the limit (tickets, not orders — see the next two tests for that distinction).
        coupon = _add_coupon(event.id, code="FREE100", discount_percent=100, max_redemptions=2)

        payload = _valid_payload(event.id, ticket_type.id, coupon_code="FREE100")
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        # The order that just used up the last redemption slot is what triggers the flip — the
        # coupon is inactive immediately after, not just on some later request.
        assert db.session.get(Coupon, coupon.id).is_active is False
        db.drop_all()


def test_checkout_rejects_a_coupon_when_the_order_would_exceed_the_remaining_redemptions():
    """The core bug this guards: a single order can carry any quantity, so the limit must be
    enforced against TICKETS, not orders — otherwise a max_redemptions=1 coupon could issue an
    unbounded number of tickets in one checkout (the order's own quantity was never checked)."""
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, price=15000)
        _add_coupon(event.id, code="FREE100", discount_percent=100, max_redemptions=1)

        payload = _valid_payload(event.id, ticket_type.id, coupon_code="FREE100")  # quantity=2
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 400
        assert "coupon_code" in response.get_json()["errors"]
        assert Order.query.count() == 0  # rejected outright, no order created at all
        db.drop_all()


def test_checkout_rejects_a_coupon_once_a_prior_order_used_up_the_remaining_redemptions():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, price=15000)
        _add_coupon(event.id, code="FREE100", discount_percent=100, max_redemptions=3)

        client = app.test_client()
        first = client.post(
            "/api/orders", json=_valid_payload(event.id, ticket_type.id, coupon_code="FREE100")
        )  # quantity=2, uses up 2 of 3
        assert first.status_code == 201

        # Only 1 slot left — a second 2-ticket order must be rejected, not partially honored.
        second = client.post(
            "/api/orders", json=_valid_payload(event.id, ticket_type.id, coupon_code="FREE100")
        )
        assert second.status_code == 400
        assert "This coupon only has 1 use(s) left." in second.get_json()["errors"]["coupon_code"]
        assert Order.query.count() == 1
        db.drop_all()


def test_redemption_limit_counts_only_tickets_the_coupon_discounts():
    """A full-price ticket of another type in the same order is not a use of the coupon: with a limit of 2 on a
    Saturday-only coupon, 2 Saturday + 2 Sunday tickets fit (2 uses), and only the Saturday ones are counted."""
    from app.coupons.models import redemption_count_for_coupon

    app = _new_app()
    with app.app_context():
        event = _add_event()
        sat = _add_type(event.id, name="Saturday", price=10000)
        sun = _add_type(event.id, name="Sunday", price=10000)
        coupon = _add_coupon(event.id, code="SAT100", discount_percent=100, max_redemptions=2, allowed_ticket_type_ids=str(sat.id))
        coupon_id = coupon.id

        payload = _valid_payload(event.id, sat.id, coupon_code="SAT100")
        payload["items"] = [{"ticket_type_id": sat.id, "quantity": 2}, {"ticket_type_id": sun.id, "quantity": 2}]
        client = app.test_client()
        response = client.post("/api/orders", json=payload)
        assert response.status_code == 201

        from app.orders.models import Order

        order = Order.query.one()
        order.payment_status = "paid"
        db.session.commit()
        from app.orders.service import issue_tickets_for_order

        issue_tickets_for_order(order)
        db.session.commit()

        assert redemption_count_for_coupon(coupon_id) == 2  # not 4
        # the limit is now used up, so one more discounted ticket is refused, while the count was never 4
        again = client.post("/api/orders", json=_valid_payload(event.id, sat.id, coupon_code="SAT100", customer_email="b@example.com"))
        assert again.status_code == 400
        db.drop_all()


def test_checkout_with_a_100_percent_coupon_stays_active_below_the_redemption_limit():
    from app.coupons.models import Coupon

    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id, price=15000)
        coupon = _add_coupon(event.id, code="FREE100", discount_percent=100, max_redemptions=5)

        payload = _valid_payload(event.id, ticket_type.id, coupon_code="FREE100")
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        assert db.session.get(Coupon, coupon.id).is_active is True
        db.drop_all()


def test_checkout_coupon_discounts_only_the_eligible_ticket_type():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        eligible = _add_type(event.id, name="Adult", price=15000, coupon_eligible=True)
        ineligible = _add_type(event.id, name="VIP", price=50000, coupon_eligible=False)
        _add_coupon(event.id, code="SAVE20", discount_percent=20)

        payload = {
            "event_id": event.id,
            "items": [
                {"ticket_type_id": eligible.id, "quantity": 1},  # 15000, eligible
                {"ticket_type_id": ineligible.id, "quantity": 1},  # 50000, not eligible
            ],
            "customer_name": "Priya Das",
            "customer_email": "priya@example.com",
            "customer_phone": "41234567",
            "coupon_code": "SAVE20",
        }
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.get_json()
        # Only the eligible 15000 is discounted 20% -> 3000 off; the ineligible 50000 is
        # charged in full. discount_amount = 3000, total = 15000 + 50000 - 3000 = 62000.
        assert data["discount_amount"] == 3000
        assert data["total_amount"] == 62000
        assert Order.query.one().total_amount == 62000
        db.drop_all()


def test_checkout_rejects_a_coupon_when_no_selected_ticket_type_is_eligible():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ineligible = _add_type(event.id, name="VIP", price=50000, coupon_eligible=False)
        _add_coupon(event.id, code="SAVE20", discount_percent=20)

        payload = _valid_payload(event.id, ineligible.id, coupon_code="SAVE20")
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 400
        assert "coupon_code" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_coupon_with_a_ticket_type_restriction_discounts_only_the_allowed_type():
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult", price=15000)
        child = _add_type(event.id, name="Child", price=5000)
        # "SANATAN" is restricted to Adult only, even though both types are coupon_eligible.
        _add_coupon(event.id, code="SANATAN", discount_percent=20, allowed_ticket_type_ids=str(adult.id))

        payload = {
            "event_id": event.id,
            "items": [
                {"ticket_type_id": adult.id, "quantity": 1},
                {"ticket_type_id": child.id, "quantity": 1},
            ],
            "customer_name": "Priya Das",
            "customer_email": "priya@example.com",
            "customer_phone": "41234567",
            "coupon_code": "SANATAN",
        }
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        data = response.get_json()
        # Only Adult (15000) is discounted 20% -> 3000 off; Child (5000) is charged in full.
        assert data["discount_amount"] == 3000
        assert data["total_amount"] == 17000
        assert Order.query.one().total_amount == 17000
        db.drop_all()


def test_checkout_rejects_a_coupon_restricted_away_from_every_selected_ticket_type():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult", price=15000)
        child = _add_type(event.id, name="Child", price=5000)
        # "SANATAN" only ever applies to Child — an Adult-only order can't use it at all,
        # even though Adult is generally coupon_eligible.
        _add_coupon(event.id, code="SANATAN", discount_percent=20, allowed_ticket_type_ids=str(child.id))

        payload = _valid_payload(event.id, adult.id, coupon_code="SANATAN")
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 400
        assert "coupon_code" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_two_coupons_can_target_the_same_ticket_type_differently():
    """The user's own scenario: MEMBER still discounts Adult, but SANATAN is restricted to
    Child only, so it no longer discounts Adult even though both are coupon_eligible."""
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult", price=15000)
        child = _add_type(event.id, name="Child", price=5000)
        _add_coupon(event.id, code="MEMBER", discount_percent=10)  # unrestricted
        _add_coupon(event.id, code="SANATAN", discount_percent=20, allowed_ticket_type_ids=str(child.id))

        member_response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, adult.id, coupon_code="MEMBER")
        )
        assert member_response.status_code == 201
        assert member_response.get_json()["discount_amount"] > 0

        sanatan_response = app.test_client().post(
            "/api/orders", json=_valid_payload(event.id, adult.id, coupon_code="SANATAN")
        )
        assert sanatan_response.status_code == 400
        assert "coupon_code" in sanatan_response.get_json()["errors"]

        assert Order.query.count() == 1  # only MEMBER's order was actually created
        db.drop_all()


def test_checkout_coupon_adult_child_cap_ignores_ineligible_ticket_types():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        eligible_adult = _add_type(event.id, name="Adult", price=15000, age_category="adult", coupon_eligible=True)
        ineligible_adult = _add_type(event.id, name="VIP Adult", price=50000, age_category="adult", coupon_eligible=False)
        _add_coupon(event.id, code="SAVE20", discount_percent=20)

        # 2 eligible adults (at the coupon-specific cap) + 2 ineligible "adult" VIP tickets —
        # the coupon cap only ever counts eligible tickets, so this should be allowed and the
        # VIP tickets are simply charged in full with no discount. Kept at 4 total (not 5) to
        # stay within the separate, coupon-independent per-email/event ticket cap.
        payload = {
            "event_id": event.id,
            "items": [
                {"ticket_type_id": eligible_adult.id, "quantity": 2},
                {"ticket_type_id": ineligible_adult.id, "quantity": 2},
            ],
            "customer_name": "Priya Das",
            "customer_email": "priya@example.com",
            "customer_phone": "41234567",
            "coupon_code": "SAVE20",
        }
        response = app.test_client().post("/api/orders", json=payload)

        assert response.status_code == 201
        db.drop_all()


def test_checkout_allows_exactly_the_per_email_ticket_cap():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()

        response = client.post(
            "/api/orders",
            json=_valid_payload(event.id, ticket_type.id, items=[{"ticket_type_id": ticket_type.id, "quantity": 4}]),
        )

        assert response.status_code == 201
        db.drop_all()


def test_checkout_rejects_a_5th_ticket_for_the_same_email_and_event():
    app = _new_app()
    with app.app_context():
        event = _add_event(**LIMITS)
        ticket_type = _add_type(event.id)
        client = app.test_client()
        client.post(
            "/api/orders",
            json=_valid_payload(event.id, ticket_type.id, items=[{"ticket_type_id": ticket_type.id, "quantity": 4}]),
        )

        response = client.post(
            "/api/orders",
            json=_valid_payload(event.id, ticket_type.id, items=[{"ticket_type_id": ticket_type.id, "quantity": 1}]),
        )

        assert response.status_code == 400
        assert "customer_email" in response.get_json()["errors"]
        db.drop_all()


def test_checkout_email_ticket_cap_is_case_insensitive():
    app = _new_app()
    with app.app_context():
        event = _add_event(**LIMITS)
        ticket_type = _add_type(event.id)
        client = app.test_client()
        client.post(
            "/api/orders",
            json=_valid_payload(
                event.id, ticket_type.id,
                customer_email="Priya@Example.com",
                items=[{"ticket_type_id": ticket_type.id, "quantity": 4}],
            ),
        )

        response = client.post(
            "/api/orders",
            json=_valid_payload(
                event.id, ticket_type.id,
                customer_email="priya@example.com",
                items=[{"ticket_type_id": ticket_type.id, "quantity": 1}],
            ),
        )

        assert response.status_code == 400
        db.drop_all()


def test_checkout_email_ticket_cap_is_scoped_per_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        other_event = _add_event(slug="other-event")
        ticket_type = _add_type(event.id)
        other_type = _add_type(other_event.id)
        client = app.test_client()
        client.post(
            "/api/orders",
            json=_valid_payload(event.id, ticket_type.id, items=[{"ticket_type_id": ticket_type.id, "quantity": 4}]),
        )

        response = client.post(
            "/api/orders",
            json=_valid_payload(other_event.id, other_type.id, items=[{"ticket_type_id": other_type.id, "quantity": 4}]),
        )

        assert response.status_code == 201
        db.drop_all()


def test_checkout_email_ticket_cap_is_scoped_per_ticket_type_not_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult_type = _add_type(event.id, name="Adult")
        vip_type = _add_type(event.id, name="VIP")
        client = app.test_client()
        client.post(
            "/api/orders",
            json=_valid_payload(event.id, adult_type.id, items=[{"ticket_type_id": adult_type.id, "quantity": 4}]),
        )

        response = client.post(
            "/api/orders",
            json=_valid_payload(event.id, vip_type.id, items=[{"ticket_type_id": vip_type.id, "quantity": 4}]),
        )

        assert response.status_code == 201
        db.drop_all()


def test_checkout_rejects_a_5th_ticket_of_the_same_type_even_with_other_types_available():
    app = _new_app()
    with app.app_context():
        event = _add_event(**LIMITS)
        adult_type = _add_type(event.id, name="Adult")
        vip_type = _add_type(event.id, name="VIP")
        client = app.test_client()
        client.post(
            "/api/orders",
            json=_valid_payload(event.id, adult_type.id, items=[{"ticket_type_id": adult_type.id, "quantity": 4}]),
        )

        response = client.post(
            "/api/orders",
            json=_valid_payload(
                event.id, vip_type.id,
                items=[
                    {"ticket_type_id": adult_type.id, "quantity": 1},
                    {"ticket_type_id": vip_type.id, "quantity": 1},
                ],
            ),
        )

        assert response.status_code == 400
        assert "Adult" in response.get_json()["errors"]["customer_email"]
        db.drop_all()


def test_checkout_email_ticket_cap_frees_up_once_the_order_is_rejected():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        first = client.post(
            "/api/orders",
            json=_valid_payload(event.id, ticket_type.id, items=[{"ticket_type_id": ticket_type.id, "quantity": 4}]),
        ).get_json()
        _, token = make_user_and_token(role="admin")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client.post(
                f"/api/admin/orders/{first['id']}/reject",
                headers=auth_header(token),
                json={"reason": "Payment never received"},
            )

            response = client.post(
                "/api/orders",
                json=_valid_payload(event.id, ticket_type.id, items=[{"ticket_type_id": ticket_type.id, "quantity": 4}]),
            )

        assert response.status_code == 201
        db.drop_all()


def test_checkout_email_ticket_cap_frees_up_once_the_order_is_cancelled():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        ticket_type = _add_type(event.id)
        client = app.test_client()
        first = client.post(
            "/api/orders",
            json=_valid_payload(event.id, ticket_type.id, items=[{"ticket_type_id": ticket_type.id, "quantity": 4}]),
        ).get_json()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client.post(f"/api/admin/orders/{first['id']}/mark-paid", headers=headers)
            client.post(
                f"/api/admin/orders/{first['id']}/cancel",
                headers=headers,
                json={"reason": "Event postponed"},
            )

            response = client.post(
                "/api/orders",
                json=_valid_payload(event.id, ticket_type.id, items=[{"ticket_type_id": ticket_type.id, "quantity": 4}]),
            )

        assert response.status_code == 201
        db.drop_all()


def test_ticket_limits_are_unlimited_when_the_event_leaves_them_blank():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        adult = _add_type(event.id, name="Adult", price=15000, age_category="adult")
        _add_coupon(event.id)
        client = app.test_client()
        for _ in range(2):
            response = client.post(
                "/api/orders",
                json=_valid_payload(event.id, adult.id, items=[{"ticket_type_id": adult.id, "quantity": 5}], coupon_code="SAVE20"),
            )
            assert response.status_code == 201
        db.drop_all()


def test_each_event_limit_is_independent():
    app = _new_app()
    with app.app_context():
        event = _add_event(coupon_max_adult=1)
        adult = _add_type(event.id, name="Adult", price=15000, age_category="adult")
        _add_coupon(event.id)
        client = app.test_client()
        over = client.post(
            "/api/orders",
            json=_valid_payload(event.id, adult.id, items=[{"ticket_type_id": adult.id, "quantity": 2}], coupon_code="SAVE20"),
        )
        assert over.status_code == 400 and "1 adult" in over.get_json()["errors"]["coupon_code"]
        # Without a coupon the coupon limit doesn't apply, and no per-email limit is set.
        plain = client.post(
            "/api/orders",
            json=_valid_payload(event.id, adult.id, items=[{"ticket_type_id": adult.id, "quantity": 6}]),
        )
        assert plain.status_code == 201
        db.drop_all()
