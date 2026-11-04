"""Tests for ticketing models (6 tests), e.g. ticket type defaults; order number and totals round trip; deleting an order cascades to its items."""
from datetime import date, datetime, timezone

from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_ticket_type_defaults():
    from app.events.models import Event
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=datetime(2026, 10, 10, tzinfo=timezone.utc))
        db.session.add(event)
        db.session.commit()

        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()

        saved = TicketType.query.one()
        assert saved.capacity is None
        assert saved.members_only is False
        assert saved.sort_order == 0
        db.drop_all()


def test_order_number_and_totals_round_trip():
    from app.events.models import Event
    from app.orders.models import Order, OrderItem
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=datetime(2026, 10, 10, tzinfo=timezone.utc))
        db.session.add(event)
        db.session.commit()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()

        order = Order(
            order_number="BCA-2026-000001",
            event_id=event.id,
            customer_name="Priya Das",
            customer_email="priya@example.com",
            total_amount=30000,
        )
        db.session.add(order)
        db.session.commit()

        db.session.add(
            OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=2,
                     unit_price=15000, subtotal=30000)
        )
        db.session.commit()

        db.session.refresh(order)
        assert order.payment_status == "pending"
        assert order.order_status == "pending"
        assert len(order.items) == 1
        assert order.items[0].subtotal == 30000
        db.drop_all()


def test_deleting_an_order_cascades_to_its_items():
    from app.events.models import Event
    from app.orders.models import Order, OrderItem
    from app.tickets.models import TicketType

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=datetime(2026, 10, 10, tzinfo=timezone.utc))
        db.session.add(event)
        db.session.commit()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000)
        db.session.add(order)
        db.session.commit()
        db.session.add(OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                                 unit_price=15000, subtotal=15000))
        db.session.commit()

        db.session.delete(order)
        db.session.commit()

        assert OrderItem.query.count() == 0
        db.drop_all()


def test_ticket_belongs_to_an_order_item_and_defaults_to_valid():
    from app.events.models import Event
    from app.orders.models import Order, OrderItem
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=datetime(2026, 10, 10, tzinfo=timezone.utc))
        db.session.add(event)
        db.session.commit()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000)
        db.session.add(order)
        db.session.commit()
        item = OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                         unit_price=15000, subtotal=15000)
        db.session.add(item)
        db.session.commit()

        ticket = Ticket(order_item_id=item.id, ticket_code="abc123")
        db.session.add(ticket)
        db.session.commit()

        saved = Ticket.query.one()
        assert saved.status == "valid"
        assert saved.order_item_id == item.id
        db.drop_all()


def test_payment_defaults_to_pending_nok():
    from app.events.models import Event
    from app.orders.models import Order
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=datetime(2026, 10, 10, tzinfo=timezone.utc))
        db.session.add(event)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000)
        db.session.add(order)
        db.session.commit()

        payment = Payment(payment_type="event_ticket", order_id=order.id, provider="manual", amount=15000)
        db.session.add(payment)
        db.session.commit()

        saved = Payment.query.one()
        assert saved.status == "pending"
        assert saved.currency == "NOK"
        db.drop_all()


def test_ticket_check_in_columns_default_to_null():
    from app.events.models import Event
    from app.orders.models import Order, OrderItem
    from app.tickets.models import Ticket, TicketType

    app = _new_app()
    with app.app_context():
        event = Event(title="Durga Puja 2026", slug="durga-puja-2026", event_type="festival",
                      start_datetime=datetime(2026, 10, 10, tzinfo=timezone.utc))
        db.session.add(event)
        db.session.commit()
        ticket_type = TicketType(event_id=event.id, name="Adult", price=15000)
        db.session.add(ticket_type)
        db.session.commit()
        order = Order(order_number="BCA-2026-000001", event_id=event.id,
                      customer_name="Priya Das", customer_email="priya@example.com",
                      total_amount=15000)
        db.session.add(order)
        db.session.commit()
        item = OrderItem(order_id=order.id, ticket_type_id=ticket_type.id, quantity=1,
                         unit_price=15000, subtotal=15000)
        db.session.add(item)
        db.session.commit()

        ticket = Ticket(order_item_id=item.id, ticket_code="abc123")
        db.session.add(ticket)
        db.session.commit()

        saved = Ticket.query.one()
        assert saved.checked_in_at is None
        assert saved.checked_in_by_user_id is None
        db.drop_all()
