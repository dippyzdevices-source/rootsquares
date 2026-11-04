"""Tests for admin gallery routes (19 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin list albums includes unpublished albums."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.gallery.models import Album
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _add_album(**overrides):
    defaults = {"title": "Durga Puja 2026", "year": 2026, "published": False}
    defaults.update(overrides)
    album = Album(**defaults)
    db.session.add(album)
    db.session.commit()
    return album


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/gallery/albums")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/gallery/albums", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_list_albums_includes_unpublished_albums():
    app = _new_app()
    with app.app_context():
        _add_album(title="Draft", published=False)
        _add_album(title="Live", published=True)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            data = app.test_client().get("/api/admin/gallery/albums", headers=headers).get_json()

        assert {item["title"] for item in data["items"]} == {"Draft", "Live"}
        db.drop_all()


def test_admin_create_album_requires_a_title():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post("/api/admin/gallery/albums", json={}, headers=headers)

        assert response.status_code == 400
        assert "title" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_album_success():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/gallery/albums", json={"title": "Mahalaya 2026", "year": 2026}, headers=headers
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "Mahalaya 2026"
        assert data["published"] is False
        assert data["media"] == []
        db.drop_all()


def test_admin_create_album_with_a_category():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/gallery/albums",
                json={"title": "Mahalaya 2026", "year": 2026, "category": "festivals"},
                headers=headers,
            )

        assert response.status_code == 201
        assert response.get_json()["category"] == "festivals"
        db.drop_all()


def test_admin_create_album_rejects_an_unknown_category():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/gallery/albums",
                json={"title": "Mahalaya 2026", "category": "not-a-category"},
                headers=headers,
            )

        assert response.status_code == 400
        assert "category" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_album_category():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/gallery/albums/{album.id}",
                json={"category": "archive"},
                headers=headers,
            )

        assert response.get_json()["category"] == "archive"
        db.drop_all()


def test_admin_create_album_records_the_creating_admin():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="admin", email="admin@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/gallery/albums", json={"title": "Mahalaya 2026", "year": 2026},
                headers=auth_header(token),
            )

        data = response.get_json()
        assert data["created_by_email"] == "admin@example.com"
        assert data["updated_by_email"] == "admin@example.com"
        db.drop_all()


def test_admin_update_album_records_the_editing_admin():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        _, token = make_user_and_token(role="admin", email="editor@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/gallery/albums/{album.id}", json={"published": True},
                headers=auth_header(token),
            )

        assert response.get_json()["updated_by_email"] == "editor@example.com"
        db.drop_all()


def test_admin_get_album_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/gallery/albums/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_admin_update_album_partial():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/gallery/albums/{album.id}", json={"published": True}, headers=headers
            )

        data = response.get_json()
        assert response.status_code == 200
        assert data["published"] is True
        assert data["title"] == "Durga Puja 2026"  # untouched by the partial update
        db.drop_all()


def test_admin_update_album_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/gallery/albums/999", json={"published": True}, headers=headers
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_album_with_no_media_succeeds():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            response = client.delete(f"/api/admin/gallery/albums/{album.id}", headers=headers)
            assert response.status_code == 204

            follow_up = client.get(f"/api/admin/gallery/albums/{album.id}", headers=headers)
            assert follow_up.status_code == 404
        db.drop_all()


def test_admin_delete_album_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete("/api/admin/gallery/albums/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_album_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        album = _add_album(title="Durga Puja 2026")
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().delete(
                f"/api/admin/gallery/albums/{album.id}", headers=auth_header(token)
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "gallery_album_deleted"
        assert entry.target_type == "album"
        assert entry.target_id == album.id
        assert "Durga Puja 2026" in entry.description
        db.drop_all()


def test_admin_create_album_requires_a_valid_year():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            missing = client.post("/api/admin/gallery/albums", json={"title": "X"}, headers=headers)
            bad = client.post("/api/admin/gallery/albums", json={"title": "X", "year": 1850}, headers=headers)
            ok = client.post("/api/admin/gallery/albums", json={"title": "X", "year": 2012}, headers=headers)
        assert "year" in missing.get_json()["errors"]
        assert bad.status_code == 400
        assert ok.status_code == 201 and ok.get_json()["year"] == 2012
        db.drop_all()


def test_admin_update_album_rejects_a_blank_year():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/gallery/albums/{album.id}", json={"year": None}, headers=_admin_headers()
            )
        assert response.status_code == 400 and "year" in response.get_json()["errors"]
        db.drop_all()


def test_list_albums_filters_by_title_search_and_published_state():
    app = _new_app()
    with app.app_context():
        _add_album(title="Durga Puja 2025", published=True)
        _add_album(title="Saraswati Puja 2025", published=False)
        headers = _admin_headers()

        def titles(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"/api/admin/gallery/albums?{query}", headers=headers)
            assert response.status_code == 200
            return {a["title"] for a in response.get_json()["items"]}

        assert titles("") == {"Durga Puja 2025", "Saraswati Puja 2025"}
        assert titles("q=saraswati") == {"Saraswati Puja 2025"}
        assert titles("published=true") == {"Durga Puja 2025"}
        assert titles("published=false") == {"Saraswati Puja 2025"}
        assert titles("published=true&q=puja") == {"Durga Puja 2025"}
        db.drop_all()
