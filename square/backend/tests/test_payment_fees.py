"""Tests for payment fees (5 tests), e.g. convenience fee defaults and rounding; processing fee percent plus fixed and settings driven; snapshot only sets an empty fee."""
from decimal import Decimal
from unittest.mock import patch

from app.extensions import db
from app.payments.fees import convenience_fee_for, processing_fee_for, snapshot_processing_fee
from app.payments.models import Payment
from app.settings.models import get_site_settings
from tests.auth_helpers import FakeJWKClient
from tests.test_admin_accounting_routes import _add_event, _add_order, _admin_headers, _new_app


def _paid_payment(order, provider, amount, surcharge=None, fee=None):
    payment = Payment(
        payment_type="event_ticket", order_id=order.id, provider=provider, amount=amount,
        surcharge_amount=surcharge, processing_fee_amount=fee, status="paid",
    )
    db.session.add(payment)
    db.session.commit()
    return payment


def test_convenience_fee_defaults_and_rounding():
    app = _new_app()
    with app.app_context():
        assert convenience_fee_for("vipps_app", 20000) == 1000
        assert convenience_fee_for("vipps_app", 10010) == 501  # 500.5 -> 501
        assert convenience_fee_for("vipps_app", 10009) == 500
        assert convenience_fee_for("vipps_qr", 20000) == 0
        assert convenience_fee_for("cash", 20000) == 0
        assert convenience_fee_for("stripe", 20000) == 0
        db.drop_all()


def test_processing_fee_percent_plus_fixed_and_settings_driven():
    app = _new_app()
    with app.app_context():
        assert processing_fee_for("vipps_app", 10500) == 314 + 100  # 2.99% of 105 kr + 1 kr
        assert processing_fee_for("vipps_app", 0) == 0
        assert processing_fee_for("cash", 10000) == 0
        s = get_site_settings()
        s.vipps_qr_processing_percent = Decimal("1.50")
        s.vipps_qr_processing_fixed_ore = 50
        db.session.commit()
        assert processing_fee_for("vipps_qr", 10000) == 150 + 50
        db.drop_all()


def test_snapshot_only_sets_an_empty_fee():
    app = _new_app()
    with app.app_context():
        payment = Payment(payment_type="membership", provider="vipps_app", amount=10500, status="paid")
        snapshot_processing_fee(payment)
        assert payment.processing_fee_amount == 414
        get_site_settings().vipps_app_processing_percent = Decimal("10")
        snapshot_processing_fee(payment)
        assert payment.processing_fee_amount == 414  # a later rate change never rewrites it
        db.drop_all()


def test_settings_validation_and_save():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            ok = client.patch(
                "/api/admin/settings", headers=headers,
                json={"vipps_qr_processing_percent": 1.5, "vipps_qr_processing_fixed_ore": 75, "vipps_app_convenience_percent": "3"},
            )
            assert ok.status_code == 200
            body = ok.get_json()
            assert body["vipps_qr_processing_percent"] == 1.5
            assert body["vipps_qr_processing_fixed_ore"] == 75
            assert body["vipps_app_convenience_percent"] == 3.0
            assert body["vipps_app_processing_fixed_ore"] == 100  # default
            for bad in ({"cash_convenience_percent": 101}, {"cash_convenience_percent": -1},
                        {"cash_convenience_percent": 1.234}, {"cash_convenience_percent": True},
                        {"cash_processing_fixed_ore": -5}, {"cash_processing_fixed_ore": 1.5}):
                assert client.patch("/api/admin/settings", headers=headers, json=bad).status_code == 400
        db.drop_all()


def test_accounting_collection_includes_convenience_and_expenses_include_processing_fees():
    from app.accounting.models import Expense
    from datetime import date

    app = _new_app()
    with app.app_context():
        event = _add_event()
        headers = _admin_headers()
        paid = _add_order(event, amount=10000, payment_status="paid")
        _paid_payment(paid, "vipps_app", 10500, surcharge=500, fee=414)
        cash = _add_order(event, amount=2000, payment_status="paid")
        _paid_payment(cash, "cash", 2000, fee=0)
        # a refunded order: no convenience fee counted any more, the provider's fee is kept
        refunded = _add_order(event, amount=3000, payment_status="cancelled")
        _paid_payment(refunded, "vipps_app", 3150, surcharge=150, fee=194)
        db.session.add(Expense(event_id=event.id, date=date.today(), description="Flowers", category="decor", amount=1000))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            summary = client.get(f"/api/admin/accounting/events/{event.id}", headers=headers).get_json()
            expenses = client.get(f"/api/admin/accounting/events/{event.id}/expenses", headers=headers).get_json()

        assert summary["collection_total"] == 10000 + 2000 + 500
        assert summary["processing_fees_total"] == 414 + 194
        assert summary["recorded_expenses_total"] == 1000
        assert summary["expenses_total"] == 1000 + 608
        assert summary["net_total"] == 12500 - 1608
        assert summary["fees_by_provider"] == [{"provider": "vipps_app", "convenience": 500, "processing": 608}]
        assert expenses["processing_fee_lines"] == [{"provider": "vipps_app", "amount": 608}]
        db.drop_all()
