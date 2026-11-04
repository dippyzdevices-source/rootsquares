"""Tests for auth me (1 tests), e.g. me returns the full profile shape."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_me_returns_the_full_profile_shape():
    app = _new_app()
    with app.app_context():
        user, token = make_user_and_token(role="member", email="a@b.com")
        user.phone = "+4712345678"
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/auth/me", headers=auth_header(token))

        assert response.status_code == 200
        assert response.get_json() == {
            "id": user.id,
            "email": "a@b.com",
            "phone": "+4712345678",
            "role": "member",
        }

        db.drop_all()
