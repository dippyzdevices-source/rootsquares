"""Tests for settings routes (19 tests), e.g. get settings is public and lazily creates defaults; get settings returns the stored values; admin settings reject requests with no token."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.settings.models import SiteSettings
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_get_settings_is_public_and_lazily_creates_defaults():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/settings")

        assert response.status_code == 200
        assert response.get_json() == {
            "contact_email": "",
            "contact_phone": "",
            "contact_address": "",
            "timezone": "Europe/Oslo",
            "maintenance_mode": True,
            "maintenance_allowed_event_slugs": "",
            "maintenance_allowed_page_paths": "",
            "maintenance_hidden_page_paths": "",
            "heritage_image_url": None,
            "description_style": "karla",
            "privacy_text": "",
            "terms_text": "",
            "about_text": "",
            "home_content": {},
            "vipps_number": "12345",  # the test starting point is a square with Vipps QR on (tests/conftest.py)
            "vipps_qr_image_url": None,
        }
        assert SiteSettings.query.count() == 1
        db.drop_all()


def test_get_settings_returns_the_stored_values():
    app = _new_app()
    with app.app_context():
        db.session.add(
            SiteSettings(id=1, contact_email="a@b.com", contact_phone="123", contact_address="Oslo")
        )
        db.session.commit()

        response = app.test_client().get("/api/settings")

        assert response.get_json() == {
            "contact_email": "a@b.com",
            "contact_phone": "123",
            "contact_address": "Oslo",
            "timezone": "Europe/Oslo",
            "maintenance_mode": True,
            "maintenance_allowed_event_slugs": "",
            "maintenance_allowed_page_paths": "",
            "maintenance_hidden_page_paths": "",
            "heritage_image_url": None,
            "description_style": "karla",
            "privacy_text": "",
            "terms_text": "",
            "about_text": "",
            "home_content": {},
            "vipps_number": "12345",  # the test starting point is a square with Vipps QR on (tests/conftest.py)
            "vipps_qr_image_url": None,
        }
        db.drop_all()


def test_admin_settings_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/settings")
        assert response.status_code == 401
        db.drop_all()


def test_admin_settings_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/settings", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_settings_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/settings", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_admin_update_settings_changes_the_stored_values():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings",
                json={"contact_email": "new@bcaoslo.no", "contact_phone": "+47 111 11 111"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["contact_email"] == "new@bcaoslo.no"
        assert data["contact_phone"] == "+47 111 11 111"

        # Confirmed it round-trips through the public endpoint too.
        follow_up = app.test_client().get("/api/settings")
        assert follow_up.get_json()["contact_email"] == "new@bcaoslo.no"
        db.drop_all()


def test_admin_update_settings_trims_whitespace():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings", json={"contact_email": "  a@b.com  "}, headers=_admin_headers()
            )
        assert response.get_json()["contact_email"] == "a@b.com"
        db.drop_all()


def test_admin_update_settings_rejects_a_non_string_value():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings", json={"contact_email": 12345}, headers=_admin_headers()
            )
        assert response.status_code == 400
        assert "contact_email" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_settings_can_toggle_maintenance_mode():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings", json={"maintenance_mode": False}, headers=_admin_headers()
            )

        assert response.status_code == 200
        assert response.get_json()["maintenance_mode"] is False

        # Confirmed it round-trips through the public endpoint too — this is what the
        # frontend's go-live gate actually reads, with no rebuild/redeploy needed.
        follow_up = app.test_client().get("/api/settings")
        assert follow_up.get_json()["maintenance_mode"] is False
        db.drop_all()


def test_admin_update_settings_can_change_the_maintenance_allowed_event_slugs():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings",
                json={"maintenance_allowed_event_slugs": "saraswati-2027"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        assert response.get_json()["maintenance_allowed_event_slugs"] == "saraswati-2027"

        # Confirmed it round-trips through the public endpoint too — this is what the
        # frontend's go-live gate reads to decide which single event stays reachable.
        follow_up = app.test_client().get("/api/settings")
        assert follow_up.get_json()["maintenance_allowed_event_slugs"] == "saraswati-2027"
        db.drop_all()


def test_admin_update_settings_allows_multiple_comma_separated_slugs():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings",
                json={"maintenance_allowed_event_slugs": "mahalaya-2026,saraswati-2027"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        assert response.get_json()["maintenance_allowed_event_slugs"] == "mahalaya-2026,saraswati-2027"
        db.drop_all()


def test_admin_update_settings_normalizes_the_slug_list():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings",
                json={"maintenance_allowed_event_slugs": " mahalaya-2026 ,, saraswati-2027,mahalaya-2026,"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        # Whitespace trimmed, empty entries dropped, duplicates removed, first-seen order kept.
        assert response.get_json()["maintenance_allowed_event_slugs"] == "mahalaya-2026,saraswati-2027"
        db.drop_all()


def test_admin_update_settings_can_change_the_maintenance_allowed_page_paths():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings",
                json={"maintenance_allowed_page_paths": "home,heritage"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        assert response.get_json()["maintenance_allowed_page_paths"] == "home,heritage"

        # Round-trips through the public endpoint too — this is what the frontend's go-live
        # gate reads to decide which main pages stay reachable.
        follow_up = app.test_client().get("/api/settings")
        assert follow_up.get_json()["maintenance_allowed_page_paths"] == "home,heritage"
        db.drop_all()


def test_admin_update_settings_normalizes_the_page_path_list():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings",
                json={"maintenance_allowed_page_paths": " home ,, heritage,home,"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        assert response.get_json()["maintenance_allowed_page_paths"] == "home,heritage"
        db.drop_all()


def test_admin_update_settings_rejects_an_unknown_page_key():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings",
                json={"maintenance_allowed_page_paths": "home,not-a-real-page"},
                headers=_admin_headers(),
            )

        assert response.status_code == 400
        assert "maintenance_allowed_page_paths" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_settings_rejects_a_non_boolean_maintenance_mode():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/settings", json={"maintenance_mode": "false"}, headers=_admin_headers()
            )
        assert response.status_code == 400
        assert "maintenance_mode" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_settings_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().patch(
                "/api/admin/settings", json={"contact_email": "new@bcaoslo.no"},
                headers=auth_header(token),
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "settings_updated"
        assert entry.target_type is None
        db.drop_all()


def test_admin_uploads_the_heritage_image_and_it_is_public():
    from io import BytesIO

    from PIL import Image

    app = _new_app()
    with app.app_context():
        buffer = BytesIO()
        Image.new("RGB", (400, 300), color="blue").save(buffer, format="JPEG")
        buffer.seek(0)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            response = client.post(
                "/api/admin/settings/heritage-image",
                data={"file": (buffer, "group.jpg")},
                headers=_admin_headers(),
                content_type="multipart/form-data",
            )
            missing = client.post("/api/admin/settings/heritage-image", headers=_admin_headers())

        assert response.status_code == 200
        assert missing.status_code == 400
        assert client.get("/api/settings").get_json()["heritage_image_url"]
        db.drop_all()


def test_admin_can_set_hidden_pages_and_unknown_keys_are_rejected():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            ok = client.patch(
                "/api/admin/settings",
                json={"maintenance_hidden_page_paths": "committee, gallery"},
                headers=_admin_headers(),
            )
            bad = client.patch(
                "/api/admin/settings",
                json={"maintenance_hidden_page_paths": "committee,nonsense"},
                headers=_admin_headers(),
            )
        assert ok.status_code == 200
        assert ok.get_json()["maintenance_hidden_page_paths"] == "committee,gallery"
        assert bad.status_code == 400 and "maintenance_hidden_page_paths" in bad.get_json()["errors"]
        db.drop_all()
