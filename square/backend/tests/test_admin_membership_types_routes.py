"""Tests for admin membership types routes (15 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin routes allow a cors preflight with no auth header."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.memberships.models import MembershipType
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post("/api/admin/membership-types", json={})
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-types", json={}, headers=auth_header(token)
            )
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/membership-types", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_admin_create_membership_type_requires_name_and_price():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-types", json={}, headers=_admin_headers()
            )
        assert response.status_code == 400
        errors = response.get_json()["errors"]
        assert "name" in errors
        assert "price" in errors
        db.drop_all()


def test_admin_create_membership_type_succeeds_and_defaults_active():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-types",
                json={"name": "Individual", "price": 500},
                headers=_admin_headers(),
            )
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "individual"  # normalized lowercase, matches Membership rows
        assert data["price"] == 500
        assert data["is_active"] is True
        assert data["billing_frequency"] == "yearly"  # default
        assert data["contact_for_price"] is False  # default
        db.drop_all()


def test_admin_create_membership_type_accepts_frequency_and_contact_for_price():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-types",
                json={
                    "name": "lifetime",
                    "price": 0,
                    "billing_frequency": "monthly",
                    "contact_for_price": True,
                },
                headers=_admin_headers(),
            )
        assert response.status_code == 201
        data = response.get_json()
        assert data["billing_frequency"] == "monthly"
        assert data["contact_for_price"] is True
        db.drop_all()


def test_admin_create_membership_type_rejects_an_invalid_frequency():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-types",
                json={"name": "individual", "price": 500, "billing_frequency": "weekly"},
                headers=_admin_headers(),
            )
        assert response.status_code == 400
        assert "billing_frequency" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_membership_type_rejects_a_duplicate_name():
    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="individual", price=0))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-types",
                json={"name": "individual", "price": 500},
                headers=_admin_headers(),
            )
        assert response.status_code == 400
        assert "name" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_membership_type_rejects_a_negative_price():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/membership-types",
                json={"name": "individual", "price": -1},
                headers=_admin_headers(),
            )
        assert response.status_code == 400
        assert "price" in response.get_json()["errors"]
        db.drop_all()


def test_admin_list_membership_types_includes_inactive_ones():
    app = _new_app()
    with app.app_context():
        db.session.add_all(
            [
                MembershipType(name="individual", price=500, is_active=True),
                MembershipType(name="retired", price=0, is_active=False),
            ]
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/membership-types", headers=_admin_headers()
            )

        names = {item["name"] for item in response.get_json()["items"]}
        assert names == {"individual", "retired"}
        db.drop_all()


def test_admin_update_membership_type_changes_price_and_active_flag():
    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="individual", price=500))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/membership-types/individual",
                json={"price": 750, "is_active": False},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["price"] == 750
        assert data["is_active"] is False
        db.drop_all()


def test_admin_update_membership_type_can_switch_to_contact_for_price():
    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="lifetime", price=0, billing_frequency="yearly"))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/membership-types/lifetime",
                json={"contact_for_price": True},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["contact_for_price"] is True
        # Admin's own view keeps the real price even while it's hidden from the public.
        assert data["price"] == 0
        db.drop_all()


def test_admin_update_membership_type_returns_404_for_unknown_name():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/membership-types/bogus",
                json={"price": 100},
                headers=_admin_headers(),
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_update_membership_type_rejects_a_negative_price():
    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="individual", price=500))
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/membership-types/individual",
                json={"price": -5},
                headers=_admin_headers(),
            )
        assert response.status_code == 400
        assert "price" in response.get_json()["errors"]
        db.drop_all()


def test_membership_type_description_is_saved_and_exposed_publicly():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _admin_headers()
            created = client.post(
                "/api/admin/membership-types", headers=headers,
                json={"name": "student", "price": 100, "description": "  For students.  "},
            )
            assert created.status_code == 201
            assert created.get_json()["description"] == "For students."
            assert client.patch("/api/admin/membership-types/student", headers=headers, json={"description": "x" * 301}).status_code == 400
            cleared = client.patch("/api/admin/membership-types/student", headers=headers, json={"description": "  "})
            assert cleared.get_json()["description"] is None
            client.patch("/api/admin/membership-types/student", headers=headers, json={"description": "Reduced rate."})
            public = client.get("/api/memberships/types").get_json()["items"]
            assert [t["description"] for t in public if t["name"] == "student"] == ["Reduced rate."]
        db.drop_all()
