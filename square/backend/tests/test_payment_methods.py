"""Tests for payment methods (4 tests), e.g. methods and how each is approved; only the old vipps name is still accepted from a client; switches default to qr on and cash off and are admin only and audited."""
from datetime import datetime, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.payments.methods import APPROVAL, CASH, VIPPS_APP, VIPPS_QR, normalize_method
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_methods_and_how_each_is_approved():
    assert (CASH, VIPPS_QR, VIPPS_APP) == ("cash", "vipps_qr", "vipps_app")
    assert APPROVAL == {"cash": "manual", "vipps_qr": "manual", "bank_transfer": "manual", "vipps_app": "auto", "stripe": "auto"}


def test_only_the_old_vipps_name_is_still_accepted_from_a_client():
    assert normalize_method("vipps") == "vipps_qr"
    assert normalize_method("vipps_app") == "vipps_app"
    assert normalize_method("manual") == "manual"  # never valid for a member — stays rejected downstream


def test_switches_default_to_qr_on_and_cash_off_and_are_admin_only_and_audited():
    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        h = _admin_headers()
        body = client.get("/api/admin/settings", headers=h).get_json()
        assert body["vipps_qr_enabled"] is True and body["cash_enabled"] is False
        assert "cash_enabled" not in client.get("/api/settings").get_json()

        on = client.patch("/api/admin/settings", headers=h, json={"cash_enabled": True, "vipps_qr_enabled": False})
        assert on.status_code == 200 and on.get_json()["cash_enabled"] is True and on.get_json()["vipps_qr_enabled"] is False
        assert client.patch("/api/admin/settings", headers=h, json={"cash_enabled": "yes"}).status_code == 400

        from app.audit.models import AuditLog

        descriptions = [a.description for a in AuditLog.query.filter_by(action="settings_updated").all()]
        assert "Switched Cash payments ON" in descriptions and "Switched Vipps-QR payments OFF" in descriptions


def test_ticket_checkout_drops_qr_when_switched_off_but_never_leaves_nothing():
    from app.events.models import Event
    from app.orders.service import allowed_payment_methods
    from app.settings.models import get_site_settings

    app = _new_app()
    with app.app_context():
        event = Event(title="E", slug="e", event_type="festival", start_datetime=datetime.now(timezone.utc), published=True)
        settings = get_site_settings()

        assert allowed_payment_methods(event) == {"qr"}  # Vipps App is off, QR is on

        settings.vipps_qr_enabled = False
        db.session.commit()
        assert allowed_payment_methods(event) == {"cash"}  # nothing else on: tickets must stay buyable, by cash, never by a Vipps QR that may not exist

        # Switched on but the square has no Vipps number of its own: still not offered (rootsquares W6-R38)
        settings.vipps_qr_enabled = True
        settings.vipps_number = None
        db.session.commit()
        assert allowed_payment_methods(event) == {"cash"}
        settings.vipps_number = "  "
        db.session.commit()
        assert allowed_payment_methods(event) == {"cash"}
        settings.vipps_number = "54321"
        db.session.commit()
        assert allowed_payment_methods(event) == {"qr"}
        settings.vipps_qr_enabled = False  # back to QR off for the Vipps App check below
        db.session.commit()

        with patch("app.payments.vipps.is_public", return_value=True):
            assert allowed_payment_methods(event) == {"app"}  # QR off, Vipps App on
