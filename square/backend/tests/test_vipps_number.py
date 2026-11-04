"""Each square pays to its OWN Vipps number (rootsquares W6-R38). bca-oslo hardcoded its own number and QR image in the site, the emails and the
membership page, so payments of every square would have gone to BCA. Vipps QR is offered only while it is switched on AND a number is set."""

from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.settings.models import get_site_settings, vipps_qr_available
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_membership_payment_routes import _make_member_with_active_membership


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _set(**values):
    settings = get_site_settings()
    for key, value in values.items():
        setattr(settings, key, value)
    db.session.commit()


def test_vipps_qr_is_available_only_when_switched_on_and_a_number_is_set():
    app = _new_app()
    with app.app_context():
        settings = get_site_settings()
        for enabled, number, expected in [(True, "12345", True), (True, None, False), (True, "  ", False), (False, "12345", False)]:
            settings.vipps_qr_enabled, settings.vipps_number = enabled, number
            assert vipps_qr_available(settings) is expected
        db.drop_all()


def test_a_fresh_square_starts_without_vipps_qr(monkeypatch):
    # a real square's first settings row: the column defaults, not the test starting point of tests/conftest.py
    from sqlalchemy import event

    from app.settings.models import SiteSettings

    app = _new_app()
    with app.app_context():
        db.session.add(SiteSettings(id=1, vipps_qr_enabled=False))  # explicit False: the conftest listener leaves it alone
        db.session.commit()
        settings = get_site_settings()
        assert settings.vipps_number is None and vipps_qr_available(settings) is False
        assert SiteSettings.__table__.c.vipps_qr_enabled.default.arg is False
        assert event  # (imported to show the conftest listener is the only thing that turns it on for other tests)
        db.drop_all()


def test_the_public_settings_show_the_number_only_while_vipps_qr_can_be_used():
    app = _new_app()
    with app.app_context():
        client = app.test_client()
        _set(vipps_qr_enabled=True, vipps_number="54321")
        assert client.get("/api/settings").get_json()["vipps_number"] == "54321"
        _set(vipps_qr_enabled=False)
        assert client.get("/api/settings").get_json()["vipps_number"] is None
        _set(vipps_qr_enabled=True, vipps_number=None)
        assert client.get("/api/settings").get_json()["vipps_number"] is None
        db.drop_all()


def test_an_admin_sets_validates_and_clears_the_vipps_number():
    app = _new_app()
    with app.app_context():
        client = app.test_client()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            headers = _admin_headers()
            saved = client.patch("/api/admin/settings", json={"vipps_number": " 24680 "}, headers=headers)
            assert saved.status_code == 200 and saved.get_json()["vipps_number"] == "24680"
            for bad in ("abc", "12", "1234567890123", "12 345", 5):
                refused = client.patch("/api/admin/settings", json={"vipps_number": bad}, headers=headers)
                assert refused.status_code == 400 and "vipps_number" in refused.get_json()["errors"]
            # switched off: the admin still sees the saved number, customers do not
            client.patch("/api/admin/settings", json={"vipps_qr_enabled": False}, headers=headers)
            admin_view = client.get("/api/admin/settings", headers=headers).get_json()
            assert admin_view["vipps_number"] == "24680" and admin_view["vipps_qr_available"] is False
            assert client.get("/api/settings").get_json()["vipps_number"] is None
            cleared = client.patch("/api/admin/settings", json={"vipps_number": ""}, headers=headers)
            assert cleared.status_code == 200 and cleared.get_json()["vipps_number"] is None
        db.drop_all()


def test_membership_payment_options_carry_the_squares_number_and_vipps_qr_is_refused_without_one():
    app = _new_app()
    with app.app_context():
        _, membership, token = _make_member_with_active_membership()
        from app.memberships.models import MembershipPeriod

        period_ids = [p.id for p in MembershipPeriod.query.filter_by(membership_id=membership.id).limit(1)]
        client = app.test_client()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _set(vipps_qr_enabled=True, vipps_number="54321")
            options = client.get("/api/memberships/me/periods", headers=auth_header(token)).get_json()
            assert options["vipps_qr"] == {"enabled": True, "number": "54321", "image_url": None}

            _set(vipps_number=None)
            options = client.get("/api/memberships/me/periods", headers=auth_header(token)).get_json()
            assert options["vipps_qr"] == {"enabled": False, "number": None, "image_url": None}
            refused = client.post(
                "/api/memberships/me/payments", json={"membership_period_ids": period_ids, "provider": "vipps_qr"}, headers=auth_header(token)
            )
            assert refused.status_code == 400 and "not available" in refused.get_json()["errors"]["provider"]
        db.drop_all()


def test_the_order_email_names_the_squares_own_number_and_never_bcas():
    from types import SimpleNamespace

    from app.email.templates import render_order_received_email

    item = SimpleNamespace(ticket_type=SimpleNamespace(name="Adult"), quantity=1, subtotal=10000)
    order = SimpleNamespace(customer_name="Priya", order_number="BCA-1", items=[item], total_amount=10000)
    html, text, attachments = render_order_received_email(order=order, event=None, order_url="https://x.example/o/1", vipps_number="54321")
    assert "54321" in html and "54321" in text
    assert "24376" not in html + text and "cid:vipps-qr" not in html
    assert [a["filename"] for a in attachments] == ["logo.png"]


def test_qr_cannot_be_switched_on_without_a_number_or_picture_and_clearing_the_last_detail_switches_it_off():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        _set(vipps_qr_enabled=False, vipps_number=None, vipps_qr_image_url=None)
        client, headers = app.test_client(), _admin_headers()
        refused = client.patch("/api/admin/settings", json={"vipps_qr_enabled": True}, headers=headers)
        assert refused.status_code == 400 and "vipps_qr_enabled" in refused.get_json()["errors"]
        # a picture alone is enough
        _set(vipps_qr_image_url="http://x/qr.png")
        assert client.patch("/api/admin/settings", json={"vipps_qr_enabled": True}, headers=headers).status_code == 200
        assert vipps_qr_available(get_site_settings()) is True
        assert client.get("/api/settings").get_json()["vipps_qr_image_url"] == "http://x/qr.png"
        # removing the number while the picture stays keeps it on; removing the picture too switches it off
        _set(vipps_number="12345", vipps_qr_image_url=None)
        client.patch("/api/admin/settings", json={"vipps_number": ""}, headers=headers)
        assert get_site_settings().vipps_qr_enabled is False
        db.drop_all()
