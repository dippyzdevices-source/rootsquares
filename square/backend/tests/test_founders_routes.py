"""Tests for founders routes (4 tests), e.g. public list returns only active founders in order without admin fields; admin routes require admin; admin create requires name role and quote."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.founders.models import Founder
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_public_list_returns_only_active_founders_in_order_without_admin_fields():
    app = _new_app()
    with app.app_context():
        db.session.add_all([
            Founder(name="B", role="President", quote="q2", display_order=2),
            Founder(name="A", role="Founding member", quote="q1", display_order=1),
            Founder(name="Hidden", role="x", quote="q", is_active=False),
        ])
        db.session.commit()

        items = app.test_client().get("/api/founders").get_json()["items"]

        assert [i["name"] for i in items] == ["A", "B"]
        assert "is_active" not in items[0] and "display_order" not in items[0]
        db.drop_all()


def test_admin_routes_require_admin():
    app = _new_app()
    with app.app_context():
        assert app.test_client().get("/api/admin/founders").status_code == 401
        db.drop_all()


def test_admin_create_requires_name_role_and_quote():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/founders", json={"name": "Anil"}, headers=_admin_headers()
            )
        assert response.status_code == 400
        assert set(response.get_json()["errors"]) == {"role", "quote"}
        db.drop_all()


def test_admin_create_update_delete_roundtrip_and_audit():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post(
                "/api/admin/founders",
                json={"name": "Anil", "sub_name": "অনিল", "role": "Founding member", "quote": "Hello"},
                headers=headers,
            )
            assert created.status_code == 201
            founder_id = created.get_json()["id"]

            updated = client.patch(
                f"/api/admin/founders/{founder_id}", json={"quote": "New words"}, headers=headers
            )
            assert updated.get_json()["quote"] == "New words"

            assert client.delete(f"/api/admin/founders/{founder_id}", headers=headers).status_code == 204

        assert Founder.query.count() == 0
        assert AuditLog.query.filter_by(action="founder_deleted").count() == 1
        db.drop_all()
