"""Tests for settings description style (1 tests), e.g. description style defaults to karla and can be changed by an admin onl."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_description_style_defaults_to_karla_and_can_be_changed_by_an_admin_only_to_known_values():
    app = _new_app()
    with app.app_context():
        client = app.test_client()
        assert client.get("/api/settings").get_json()["description_style"] == "karla"

        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            ok = client.patch("/api/admin/settings", json={"description_style": "cormorant"}, headers=headers)
            bad = client.patch("/api/admin/settings", json={"description_style": "comic-sans"}, headers=headers)

        assert ok.status_code == 200 and ok.get_json()["description_style"] == "cormorant"
        assert bad.status_code == 400 and "description_style" in bad.get_json()["errors"]
        assert client.get("/api/settings").get_json()["description_style"] == "cormorant"
        db.drop_all()
