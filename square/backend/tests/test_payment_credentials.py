"""A square connects Vipps with its own keys: stored encrypted, write-only, checked with Vipps first, never from the environment (W16-R4)."""

import json
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app import create_app
from app.audit.models import AuditLog
from app.extensions import db
from app.payments import credentials, vipps
from app.payments.models import PaymentCredential
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

KEYS = {
    "client_id": "client-id-1234567890abcd",
    "client_secret": "super-secret-value-XYZ",
    "subscription_key": "sub-key-0987654321",
    "msn": "123456",
    "mode": "test",
}
SECRETS = (KEYS["client_secret"], KEYS["subscription_key"], KEYS["client_id"])


def _app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _call(app, method, path="/vipps", *, email="owner@example.com", **kw):
    _, token = make_user_and_token(role="admin", email=email)
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return getattr(app.test_client(), method)(f"/api/admin/payments/providers{path}", headers=auth_header(token), **kw)


def _ok_token():
    return patch.object(vipps.VippsClient, "_access_token", return_value="tok")


def test_connect_stores_the_keys_encrypted_and_never_returns_them():
    app = _app()
    with app.app_context(), _ok_token(), patch.object(vipps.VippsClient, "register_webhook", return_value={"secret": "whsec-1"}):
        res = _call(app, "put", json=KEYS)
        assert res.status_code == 200
        body = res.get_data(as_text=True)
        assert not any(s in body for s in SECRETS) and "whsec-1" not in body
        view = res.get_json()["providers"]["vipps"]
        assert view["connected"] is True and view["mode"] == "test" and view["hint"]["msn"] == "123456"
        assert res.headers["Cache-Control"] == "no-store"

        row = PaymentCredential.query.filter_by(provider="vipps").one()
        assert row.ciphertext.startswith("v1:") and not any(s in row.ciphertext for s in SECRETS)
        assert not any(s in json.dumps(row.hint) for s in SECRETS)
        creds = credentials.get_vipps()
        assert creds.client_secret == KEYS["client_secret"] and creds.mode == "test"
        assert vipps.is_enabled() is True
        listing = _call(app, "get", "")
        assert not any(s in listing.get_data(as_text=True) for s in SECRETS)
        audit = " ".join(a.description for a in AuditLog.query.all())
        assert "Connected Vipps" in audit and not any(s in audit for s in SECRETS)


def test_keys_that_vipps_refuses_are_not_saved():
    app = _app()
    with app.app_context(), patch.object(vipps.VippsClient, "_access_token", side_effect=vipps.VippsError("no", 401)):
        res = _call(app, "put", json=KEYS)
        assert res.status_code == 422 and "did not accept" in res.get_json()["errors"]["_"]
        assert PaymentCredential.query.count() == 0 and vipps.is_enabled() is False


def test_missing_or_odd_fields_are_listed_per_field():
    app = _app()
    with app.app_context(), _ok_token():
        res = _call(app, "put", json={"client_id": "has space", "msn": "12ab", "mode": "live"})
        errors = res.get_json()["errors"]
        assert res.status_code == 400
        assert set(errors) == {"client_id", "client_secret", "subscription_key", "msn", "mode"}


def test_no_environment_fallback_exists():
    app = _app()
    app.config.update(VIPPS_CLIENT_ID="id", VIPPS_CLIENT_SECRET="s", VIPPS_SUBSCRIPTION_KEY="k", VIPPS_MSN="1", VIPPS_WEBHOOK_SECRET="w")
    with app.app_context():
        assert vipps.is_enabled() is False and vipps.is_public() is False
        with pytest.raises(vipps.VippsError):
            vipps.VippsClient()


def test_only_the_owner_may_connect_but_an_admin_sees_the_status():
    app = _app()
    with app.app_context(), _ok_token():
        db.session.execute(text("create table admins (auth_user_id varchar(100))"))
        db.session.commit()
        res = _call(app, "put", email="helper@example.com", json=KEYS)
        assert res.status_code == 403 and PaymentCredential.query.count() == 0
        status = _call(app, "get", "", email="helper@example.com")
        assert status.status_code == 200 and status.get_json()["can_edit"] is False
        assert _call(app, "delete", email="helper@example.com").status_code == 403


def test_disconnect_removes_the_keys_and_switches_vipps_off():
    app = _app()
    with app.app_context(), _ok_token(), patch.object(vipps.VippsClient, "register_webhook", return_value={}):
        _call(app, "put", json=KEYS)
        assert vipps.is_enabled() is True
        res = _call(app, "delete")
        assert res.status_code == 200 and res.get_json()["providers"]["vipps"]["connected"] is False
        assert vipps.is_enabled() is False


def test_the_webhook_is_checked_with_this_squares_own_secret():
    app = _app()
    with app.app_context():
        credentials.save("vipps", {**{k: v for k, v in KEYS.items() if k != "mode"}, "webhook_secret": ""}, mode="test", hint={})
        res = app.test_client().post("/api/webhooks/vipps", data=b"{}", headers={"x-ms-date": "d", "x-ms-content-sha256": "h"})
        assert res.status_code == 401  # no webhook secret stored: nothing can be authenticated


def test_two_merchants_never_share_an_access_token():
    a = credentials.VippsCredentials("idA", "sa", "ka", "1", "test")
    b = credentials.VippsCredentials("idB", "sb", "kb", "2", "test")
    vipps.VippsClient._tokens.clear()
    calls = []

    class Resp:
        def __init__(self, token):
            self.token = token

        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": self.token, "expires_on": "9999999999"}

    def fake_post(url, headers, timeout):
        calls.append(headers["client_id"])
        return Resp("token-for-" + headers["client_id"])

    with patch("app.payments.vipps.requests.post", side_effect=fake_post):
        assert vipps.VippsClient(a)._access_token() == "token-for-idA"
        assert vipps.VippsClient(b)._access_token() == "token-for-idB"
        assert vipps.VippsClient(a)._access_token() == "token-for-idA"  # cached
    assert calls == ["idA", "idB"]
