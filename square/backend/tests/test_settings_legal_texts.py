"""Tests for settings legal texts (2 tests), e.g. legal texts are empty by default and editable by an admin only; about text is editable by an admin and public."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def test_legal_texts_are_empty_by_default_and_editable_by_an_admin_only():
    """rootsquares W6-R51: each square writes its own Privacy Policy and Terms of Sale."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        public = client.get("/api/settings").get_json()
        assert public["privacy_text"] == "" and public["terms_text"] == "" and public["about_text"] == ""

        assert client.patch("/api/admin/settings", json={"privacy_text": "x"}).status_code in (401, 403)

        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            ok = client.patch("/api/admin/settings", json={"privacy_text": "  Our policy.\nLine two.  ", "terms_text": "Our terms."}, headers=headers)
            too_long = client.patch("/api/admin/settings", json={"terms_text": "x" * 30001}, headers=headers)
            not_text = client.patch("/api/admin/settings", json={"privacy_text": 5}, headers=headers)

        assert ok.status_code == 200 and ok.get_json()["privacy_text"] == "Our policy.\nLine two."
        assert too_long.status_code == 400 and "terms_text" in too_long.get_json()["errors"]
        assert not_text.status_code == 400
        after = client.get("/api/settings").get_json()
        assert after["privacy_text"] == "Our policy.\nLine two." and after["terms_text"] == "Our terms."
        db.drop_all()


def test_about_text_is_editable_by_an_admin_and_public():
    """rootsquares W6-R58: the About page text is the square's own."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()
        _, token = make_user_and_token(role="admin")
        headers = auth_header(token)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            ok = client.patch("/api/admin/settings", json={"about_text": " We are a club. "}, headers=headers)
            bad = client.patch("/api/admin/settings", json={"about_text": 3}, headers=headers)
        assert ok.status_code == 200 and ok.get_json()["about_text"] == "We are a club."
        assert bad.status_code == 400
        assert client.get("/api/settings").get_json()["about_text"] == "We are a club."
        db.drop_all()
