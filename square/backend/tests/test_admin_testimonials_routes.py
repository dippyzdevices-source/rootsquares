"""Tests for admin testimonials routes (17 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin routes allow a cors preflight with no auth header."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.testimonials.models import Testimonial
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _add_testimonial(**overrides):
    defaults = {"quote": "BCA Oslo feels like family.", "author_name": "Priya Das"}
    defaults.update(overrides)
    testimonial = Testimonial(**defaults)
    db.session.add(testimonial)
    db.session.commit()
    return testimonial


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/testimonials")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/testimonials", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/testimonials", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_admin_list_testimonials_includes_inactive_ones():
    app = _new_app()
    with app.app_context():
        _add_testimonial(author_name="Active", is_active=True)
        _add_testimonial(author_name="Inactive", is_active=False)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            data = app.test_client().get("/api/admin/testimonials", headers=headers).get_json()

        assert {item["author_name"] for item in data["items"]} == {"Active", "Inactive"}
        db.drop_all()


def test_admin_list_testimonials_filters_by_status():
    app = _new_app()
    with app.app_context():
        _add_testimonial(author_name="Awaiting", status="pending")
        _add_testimonial(author_name="Live", status="approved")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            data = app.test_client().get(
                "/api/admin/testimonials?status=pending", headers=headers
            ).get_json()

        assert {item["author_name"] for item in data["items"]} == {"Awaiting"}
        db.drop_all()


def test_admin_list_testimonials_rejects_an_invalid_status_filter():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/testimonials?status=not-a-real-status", headers=headers
            )
        assert response.status_code == 400
        db.drop_all()


def test_admin_create_testimonial_requires_quote_and_author_name():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post("/api/admin/testimonials", json={}, headers=headers)

        assert response.status_code == 400
        assert set(response.get_json()["errors"]) == {"quote", "author_name"}
        db.drop_all()


def test_admin_create_testimonial_success():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/testimonials",
                json={"quote": "Great community.", "author_name": "Rohan Sen"},
                headers=headers,
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["quote"] == "Great community."
        assert data["is_active"] is True
        # An admin authoring one directly needs no review step of its own.
        assert data["status"] == "approved"
        db.drop_all()


def test_admin_can_approve_a_pending_submission():
    app = _new_app()
    with app.app_context():
        testimonial = _add_testimonial(status="pending", is_active=False)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/testimonials/{testimonial.id}",
                json={"status": "approved", "is_active": True},
                headers=headers,
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "approved"
        assert data["is_active"] is True
        db.drop_all()


def test_admin_can_reject_a_pending_submission():
    app = _new_app()
    with app.app_context():
        testimonial = _add_testimonial(status="pending", is_active=False)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/testimonials/{testimonial.id}",
                json={"status": "rejected"},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.get_json()["status"] == "rejected"
        db.drop_all()


def test_admin_update_testimonial_rejects_an_invalid_status():
    app = _new_app()
    with app.app_context():
        testimonial = _add_testimonial()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/testimonials/{testimonial.id}",
                json={"status": "not-a-real-status"},
                headers=headers,
            )

        assert response.status_code == 400
        assert "status" in response.get_json()["errors"]
        db.drop_all()


def test_admin_get_testimonial_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/testimonials/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_admin_update_testimonial_can_deactivate():
    app = _new_app()
    with app.app_context():
        testimonial = _add_testimonial()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/testimonials/{testimonial.id}",
                json={"is_active": False},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.get_json()["is_active"] is False
        db.drop_all()


def test_admin_update_testimonial_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/testimonials/999", json={"is_active": False}, headers=headers
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_testimonial_success():
    app = _new_app()
    with app.app_context():
        testimonial = _add_testimonial()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            response = client.delete(f"/api/admin/testimonials/{testimonial.id}", headers=headers)
            assert response.status_code == 204

            follow_up = client.get(f"/api/admin/testimonials/{testimonial.id}", headers=headers)
            assert follow_up.status_code == 404
        db.drop_all()


def test_admin_delete_testimonial_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete("/api/admin/testimonials/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_list_testimonials_searches_author_and_quote():
    app = _new_app()
    with app.app_context():
        _add_testimonial(author_name="Priya Das", quote="A wonderful Durga Puja")
        _add_testimonial(author_name="Arjun Sen", quote="The food was great")
        headers = _admin_headers()

        def authors(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"/api/admin/testimonials?{query}", headers=headers)
            assert response.status_code == 200
            return {t["author_name"] for t in response.get_json()["items"]}

        assert authors("q=priya") == {"Priya Das"}
        assert authors("q=food") == {"Arjun Sen"}
        assert authors("q=nobody") == set()
        assert authors("") == {"Priya Das", "Arjun Sen"}
        db.drop_all()
