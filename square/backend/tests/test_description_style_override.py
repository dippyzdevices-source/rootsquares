"""News, gallery albums and magazines can override the site-wide description typeface per item
(`description_style`, null = site default) — same behaviour events already had."""

from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _setup():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_news_description_style_round_trips_and_validates():
    app = _setup()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        client, h = app.test_client(), _admin()
        created = client.post(
            "/api/admin/news",
            json={"title": "Hello", "content": "<p>Body</p>", "status": "published", "published_at": "2025-01-01T00:00:00+00:00", "description_style": "cormorant"},
            headers=h,
        )
        assert created.status_code == 201 and created.get_json()["description_style"] == "cormorant"
        slug = created.get_json()["slug"]
        assert client.get(f"/api/news/{slug}").get_json()["description_style"] == "cormorant"
        listed = client.get("/api/news").get_json()["items"][0]
        assert listed["description_style"] == "cormorant"
        nid = created.get_json()["id"]
        assert client.patch(f"/api/admin/news/{nid}", json={"description_style": "comic"}, headers=h).status_code == 400
        cleared = client.patch(f"/api/admin/news/{nid}", json={"description_style": ""}, headers=h)
        assert cleared.status_code == 200 and cleared.get_json()["description_style"] is None
        db.drop_all()


def test_album_description_style_round_trips_and_validates():
    app = _setup()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        client, h = app.test_client(), _admin()
        created = client.post(
            "/api/admin/gallery/albums",
            json={"title": "Puja 2025", "year": 2025, "published": True, "description_style": "source"},
            headers=h,
        )
        assert created.status_code == 201 and created.get_json()["description_style"] == "source"
        aid = created.get_json()["id"]
        assert client.get(f"/api/gallery/albums/{aid}").get_json()["description_style"] == "source"
        assert client.get("/api/gallery/albums").get_json()["items"][0]["description_style"] == "source"
        bad = client.patch(f"/api/admin/gallery/albums/{aid}", json={"description_style": "x"}, headers=h)
        assert bad.status_code == 400
        cleared = client.patch(f"/api/admin/gallery/albums/{aid}", json={"description_style": None}, headers=h)
        assert cleared.get_json()["description_style"] is None
        db.drop_all()


def test_magazine_description_style_round_trips_and_validates():
    app = _setup()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        client, h = app.test_client(), _admin()
        created = client.post(
            "/api/admin/magazines", json={"title": "Pujo Barta", "description_style": "karla"}, headers=h
        )
        assert created.status_code == 201 and created.get_json()["description_style"] == "karla"
        mid = created.get_json()["id"]
        assert client.patch(f"/api/admin/magazines/{mid}", json={"description_style": "nope"}, headers=h).status_code == 400
        cleared = client.patch(f"/api/admin/magazines/{mid}", json={"description_style": None}, headers=h)
        assert cleared.get_json()["description_style"] is None
        db.drop_all()
