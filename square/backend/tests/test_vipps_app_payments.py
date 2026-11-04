"""Tests for vipps app payments (8 tests), e.g. surcharge is 5 percent rounded half up in ore; start vipps app payment adds surcharge and returns redirect; start vipps app payment is unavailable without credentials."""
import base64
import hashlib
import hmac
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.vipps_helpers import connect_vipps
from app.payments import vipps
from app.payments.fees import convenience_fee_for
from app.payments.models import Payment
from tests.auth_helpers import FakeJWKClient, auth_header
from tests.test_membership_payment_routes import _make_member_with_active_membership

SECRET = "whsec-test"


def _periods(membership):
    from app.memberships.models import MembershipPeriod

    return (
        MembershipPeriod.query.filter_by(membership_id=membership.id)
        .order_by(MembershipPeriod.period_start)
        .all()
    )


def _app(enabled=True):
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        if enabled:
            from app.settings.models import get_site_settings

            get_site_settings().vipps_app_public = True  # admin switch on (the tests' default)
            connect_vipps(SECRET)
            db.session.commit()
    return app


def _client_patches(state="CREATED"):
    return (
        patch.object(vipps.VippsClient, "create_payment", return_value={"redirectUrl": "https://vipps.test/pay"}),
        patch.object(vipps.VippsClient, "get_payment", return_value={"state": state}),
        patch.object(vipps.VippsClient, "capture", return_value={}),
        patch.object(vipps.VippsClient, "cancel", return_value={}),
        patch.object(vipps.VippsClient, "refund", return_value={}),
    )


def _start(app, token, period_ids):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().post(
            "/api/memberships/me/payments",
            json={"membership_period_ids": period_ids, "provider": "vipps_app"},
            headers=auth_header(token),
        )


def test_surcharge_is_5_percent_rounded_half_up_in_ore():
    app = _app()
    with app.app_context():
        assert convenience_fee_for("vipps_app", 20000) == 1000
        assert convenience_fee_for("vipps_app", 25000) == 1250
        assert convenience_fee_for("vipps_app", 10010) == 501  # 500.5 -> 501
        assert convenience_fee_for("vipps_app", 10009) == 500  # 500.45 -> 500
        db.drop_all()


def test_start_vipps_app_payment_adds_surcharge_and_returns_redirect():
    app = _app()
    with app.app_context():
        _, membership, token = _make_member_with_active_membership(price=200)
        period_ids = [p.id for p in _periods(membership)[:2]]
        create, get, cap, can, ref = _client_patches()
        with create as create_mock, get, cap, can, ref:
            response = _start(app, token, period_ids)

        assert response.status_code == 200
        data = response.get_json()
        assert data["redirect_url"] == "https://vipps.test/pay"
        assert data["payment"]["status"] == "initiated"
        assert data["payment"]["surcharge_amount"] == 2000  # 5% of 2 x 20000
        assert data["payment"]["amount"] == 42000
        assert create_mock.call_args.args[1] == 42000
        payment = db.session.get(Payment, data["payment"]["id"])
        assert payment.provider == "vipps_app" and payment.provider_transaction_id
        assert all(p.status == "unpaid" for p in _periods(membership))
        db.drop_all()


def test_start_vipps_app_payment_is_unavailable_without_credentials():
    app = _app(enabled=False)
    with app.app_context():
        _, membership, token = _make_member_with_active_membership()
        response = _start(app, token, [_periods(membership)[0].id])
        assert response.status_code == 503
        assert Payment.query.count() == 0
        db.drop_all()


def test_refresh_captures_once_marks_periods_paid_and_is_idempotent():
    app = _app()
    with app.app_context():
        _, membership, token = _make_member_with_active_membership(price=200)
        period_id = _periods(membership)[0].id
        create, get, cap, can, ref = _client_patches("AUTHORIZED")
        with create, get, cap as capture_mock, can, ref:
            payment_id = _start(app, token, [period_id]).get_json()["payment"]["id"]
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                client = app.test_client()
                first = client.post(f"/api/memberships/me/payments/{payment_id}/refresh", headers=auth_header(token))
                second = client.post(f"/api/memberships/me/payments/{payment_id}/refresh", headers=auth_header(token))

        assert first.get_json()["payment"]["status"] == "paid"
        assert second.get_json()["payment"]["status"] == "paid"
        assert capture_mock.call_count == 1
        assert capture_mock.call_args.args[1] == 21000  # 20000 + 1000 fee
        db.session.expire_all()
        assert _periods(membership)[0].status == "paid"
        db.drop_all()


def test_refresh_marks_an_aborted_payment_failed_and_leaves_periods_unpaid():
    app = _app()
    with app.app_context():
        _, membership, token = _make_member_with_active_membership()
        create, get, cap, can, ref = _client_patches("ABORTED")
        with create, get, cap, can, ref:
            payment_id = _start(app, token, [_periods(membership)[0].id]).get_json()["payment"]["id"]
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                res = app.test_client().post(
                    f"/api/memberships/me/payments/{payment_id}/refresh", headers=auth_header(token)
                )
        assert res.get_json()["payment"]["status"] == "failed"
        db.session.expire_all()
        assert _periods(membership)[0].status == "unpaid"
        db.drop_all()


def _signed_headers(body: bytes, path: str, secret=SECRET):
    date = "Mon, 05 Oct 2026 10:00:00 GMT"
    host = "localhost"
    content_hash = base64.b64encode(hashlib.sha256(body).digest()).decode()
    to_sign = f"POST\n{path}\n{date};{host};{content_hash}"
    sig = base64.b64encode(hmac.new(secret.encode(), to_sign.encode(), hashlib.sha256).digest()).decode()
    return {
        "x-ms-date": date,
        "x-ms-content-sha256": content_hash,
        "Host": host,
        "Authorization": f"HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256&Signature={sig}",
    }


def test_webhook_rejects_a_bad_signature_and_accepts_a_good_one():
    app = _app()
    with app.app_context():
        _, membership, token = _make_member_with_active_membership(price=200)
        create, get, cap, can, ref = _client_patches("AUTHORIZED")
        with create, get, cap, can, ref:
            payment_id = _start(app, token, [_periods(membership)[0].id]).get_json()["payment"]["id"]
            reference = db.session.get(Payment, payment_id).provider_transaction_id
            body = ('{"reference": "%s", "name": "epayments.payment.authorized.v1"}' % reference).encode()
            client = app.test_client()
            path = "/api/webhooks/vipps"

            bad = client.post(path, data=body, content_type="application/json", headers=_signed_headers(body, path, "wrong"))
            assert bad.status_code == 401
            assert db.session.get(Payment, payment_id).status == "initiated"

            good = client.post(path, data=body, content_type="application/json", headers=_signed_headers(body, path))
            assert good.status_code == 200
            assert db.session.get(Payment, payment_id).status == "paid"

            unknown = b'{"reference": "nope-nope-nope"}'
            res = client.post(path, data=unknown, content_type="application/json", headers=_signed_headers(unknown, path))
            assert res.status_code == 200
        db.drop_all()


def test_refunding_a_vipps_app_payment_calls_vipps_first():
    from tests.auth_helpers import make_user_and_token

    app = _app()
    with app.app_context():
        _, membership, token = _make_member_with_active_membership(price=200)
        _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
        create, get, cap, can, ref = _client_patches("AUTHORIZED")
        with create, get, cap, can, ref as refund_mock:
            payment_id = _start(app, token, [_periods(membership)[0].id]).get_json()["payment"]["id"]
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                client = app.test_client()
                client.post(f"/api/memberships/me/payments/{payment_id}/refresh", headers=auth_header(token))
                res = client.post(f"/api/admin/payments/{payment_id}/refund", json={}, headers=auth_header(admin_token))
        assert res.status_code == 200
        assert refund_mock.call_args.args[1] == 21000
        assert db.session.get(Payment, payment_id).status == "refunded"
        db.drop_all()


def test_admin_payment_list_gives_the_member_id_of_a_membership_payment():
    from tests.auth_helpers import auth_header, make_user_and_token

    app = _app()
    with app.app_context():
        member, membership, token = _make_member_with_active_membership(price=200)
        _, admin_token = make_user_and_token(email="admin@example.com", role="admin")
        create, get, cap, can, ref = _client_patches()
        with create, get, cap, can, ref:
            _start(app, token, [_periods(membership)[0].id])
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            item = app.test_client().get("/api/admin/payments", headers=auth_header(admin_token)).get_json()["items"][0]
        assert item["member_id"] == member.id and item["order_id"] is None
        db.drop_all()
