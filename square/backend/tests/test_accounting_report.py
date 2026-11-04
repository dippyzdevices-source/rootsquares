"""Tests for accounting report (5 tests), e.g. report is a pdf download named after the event; report handles bengali text and an empty event; report is admin only and 404s for an unknown event."""
from datetime import date
from unittest.mock import patch

from app.accounting.models import Expense
from app.coupons.models import Coupon
from app.extensions import db
from app.tickets.models import TicketType
from tests.auth_helpers import FakeJWKClient
from tests.test_admin_accounting_routes import (
    _add_event,
    _add_order,
    _admin_headers,
    _member_headers,
    _new_app,
)


def _get(app, event_id, headers):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().get(f"/api/admin/accounting/events/{event_id}/report", headers=headers)


def test_report_is_a_pdf_download_named_after_the_event():
    app = _new_app()
    with app.app_context():
        event = _add_event(title="Durga Puja 2026", venue="Bølerlia 6")
        adult = TicketType(event_id=event.id, name="Adult", price=1000)
        db.session.add_all([adult, Coupon(event_id=event.id, code="MEMBER", discount_percent=20, is_active=True)])
        db.session.commit()
        _add_order(event, amount=800, payment_status="paid", ticket_type=adult, coupon_code="MEMBER", discount_amount=200)
        _add_order(event, amount=1000, payment_status="paid", ticket_type=adult)
        db.session.add(Expense(event_id=event.id, date=date(2026, 10, 1), description="Hall rental", category="venue", amount=5000, vendor="Hall AS", receipt_key="r/1"))
        db.session.commit()

        response = _get(app, event.id, _admin_headers())

        assert response.status_code == 200
        assert response.mimetype == "application/pdf"
        assert response.headers["Content-Disposition"] == "attachment; filename=durga-puja-2026-accounting-report.pdf"
        assert response.data.startswith(b"%PDF-") and len(response.data) > 3000
        db.drop_all()


def test_report_handles_bengali_text_and_an_empty_event():
    app = _new_app()
    with app.app_context():
        event = _add_event(title="দুর্গা পূজা ২০২৬")
        # empty: no orders, expenses or coupons
        empty = _get(app, event.id, _admin_headers())
        assert empty.status_code == 200 and empty.data.startswith(b"%PDF-")

        db.session.add(Expense(event_id=event.id, date=date(2026, 10, 1), description="ফুল ও মিষ্টি", category="food", amount=12345, notes="নোট"))
        db.session.commit()
        full = _get(app, event.id, _admin_headers())
        assert full.status_code == 200 and full.data.startswith(b"%PDF-")
        db.drop_all()


def test_report_is_admin_only_and_404s_for_an_unknown_event():
    app = _new_app()
    with app.app_context():
        event = _add_event()
        assert _get(app, event.id, _member_headers()).status_code == 403
        assert _get(app, 9999, _admin_headers()).status_code == 404
        db.drop_all()


def test_collection_row_names_the_coupon_when_there_is_no_payment():
    from app.accounting.admin_routes import _serialize_order_collection
    from app.orders.models import Order

    app = _new_app()
    with app.app_context():
        event = _add_event()
        _add_order(event, amount=0, payment_status="paid", coupon_code="BCAMEMBER26", discount_amount=45000)
        row = _serialize_order_collection(Order.query.first(), None)
        assert row["payment_method"] is None and row["coupon_code"] == "BCAMEMBER26"
        db.drop_all()


def test_report_shows_what_each_order_bought_only_when_details_is_on():
    app = _new_app()
    with app.app_context():
        event = _add_event(title="Durga Puja 2026")
        adult = TicketType(event_id=event.id, name="Adult", price=1000)
        db.session.add(adult)
        db.session.commit()
        _add_order(event, amount=1000, payment_status="paid", ticket_type=adult, quantity=3)
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            plain = client.get(f"/api/admin/accounting/events/{event.id}/report", headers=headers)
            detailed = client.get(f"/api/admin/accounting/events/{event.id}/report?details=1", headers=headers)
        assert plain.status_code == detailed.status_code == 200
        # The detail line is extra content in the Collections table, so the file is bigger with it.
        assert len(detailed.data) > len(plain.data)
        db.drop_all()
