"""Tests for sponsors routes (4 tests), e.g. public list returns only active sponsors in order without admin fields; admin routes require admin; admin create validates name and website url."""
import io
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.sponsors.models import Sponsor
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_public_list_returns_only_active_sponsors_in_order_without_admin_fields():
    app = _new_app()
    with app.app_context():
        db.session.add_all([
            Sponsor(name="B", display_order=2),
            Sponsor(name="A", display_order=1),
            Sponsor(name="Hidden", is_active=False),
        ])
        db.session.commit()

        items = app.test_client().get("/api/sponsors").get_json()["items"]

        assert [i["name"] for i in items] == ["A", "B"]
        assert "is_active" not in items[0] and "display_order" not in items[0]
        db.drop_all()


def test_admin_routes_require_admin():
    app = _new_app()
    with app.app_context():
        assert app.test_client().get("/api/admin/sponsors").status_code == 401
        db.drop_all()


def test_admin_create_validates_name_and_website_url():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _admin_headers()
            missing = client.post("/api/admin/sponsors", json={}, headers=headers)
            bad_url = client.post(
                "/api/admin/sponsors", json={"name": "X", "website_url": "javascript:alert(1)"}, headers=headers
            )
        assert set(missing.get_json()["errors"]) == {"name"}
        assert set(bad_url.get_json()["errors"]) == {"website_url"}
        db.drop_all()


def test_admin_create_update_logo_delete_roundtrip_and_audit():
    from PIL import Image

    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _admin_headers()

            created = client.post(
                "/api/admin/sponsors",
                json={"name": "Acme", "website_url": "https://acme.no"},
                headers=headers,
            )
            assert created.status_code == 201
            sponsor_id = created.get_json()["id"]

            updated = client.patch(
                f"/api/admin/sponsors/{sponsor_id}", json={"is_active": False, "website_url": ""}, headers=headers
            )
            assert updated.get_json()["is_active"] is False
            assert updated.get_json()["website_url"] is None

            buf = io.BytesIO()
            Image.new("RGB", (40, 20), "white").save(buf, "PNG")
            buf.seek(0)
            uploaded = client.post(
                f"/api/admin/sponsors/{sponsor_id}/logo",
                data={"file": (buf, "logo.png")},
                content_type="multipart/form-data",
                headers=headers,
            )
            assert uploaded.status_code == 200
            assert uploaded.get_json()["logo_url"]

            assert client.delete(f"/api/admin/sponsors/{sponsor_id}", headers=headers).status_code == 204

        assert AuditLog.query.filter_by(action="sponsor_deleted").count() == 1
        db.drop_all()
