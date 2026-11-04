"""Tests for admin committee routes (14 tests), e.g. admin routes reject requests with no token; admin routes allow a cors preflight with no auth header; admin creates and lists a committee member."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
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
        response = app.test_client().get("/api/admin/committee")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/committee", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_admin_creates_and_lists_a_committee_member():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            create_response = client.post(
                "/api/admin/committee",
                headers=headers,
                json={"name": "Priya Das", "role": "President", "display_order": 1},
            )
            assert create_response.status_code == 201

            list_response = client.get("/api/admin/committee", headers=headers)

        assert list_response.status_code == 200
        items = list_response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "Priya Das"
        assert items[0]["is_active"] is True
        db.drop_all()


def _jpeg_file(name="portrait.jpg"):
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (400, 400), color="blue")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return (buffer, name)


def test_admin_uploads_a_committee_member_photo():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post(
                "/api/admin/committee", headers=headers,
                json={"name": "Priya Das", "role": "President", "display_order": 1},
            ).get_json()

            response = client.post(
                f"/api/admin/committee/{created['id']}/photo",
                data={"file": _jpeg_file()},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        assert response.get_json()["portrait_url"]
        db.drop_all()


def test_admin_replacing_a_committee_photo_deletes_the_old_one_from_storage():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post(
                "/api/admin/committee", headers=headers,
                json={"name": "Priya Das", "role": "President", "display_order": 1},
            ).get_json()

            first = client.post(
                f"/api/admin/committee/{created['id']}/photo",
                data={"file": _jpeg_file("first.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            storage = app.extensions["public_storage"]
            old_key = storage.key_from_url(first.get_json()["portrait_url"])
            assert old_key in storage.objects

            second = client.post(
                f"/api/admin/committee/{created['id']}/photo",
                data={"file": _jpeg_file("second.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert second.status_code == 200
        new_key = storage.key_from_url(second.get_json()["portrait_url"])
        assert old_key not in storage.objects
        assert new_key in storage.objects
        db.drop_all()


def test_admin_create_requires_name_and_role():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/committee", headers=headers, json={}
            )

        assert response.status_code == 400
        errors = response.get_json()["errors"]
        assert "name" in errors
        assert "role" in errors
        db.drop_all()


def test_admin_updates_a_committee_member():
    from app.committee.models import CommitteeMember

    app = _new_app()
    with app.app_context():
        member = CommitteeMember(name="Priya Das", role="President")
        db.session.add(member)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/committee/{member.id}",
                headers=headers,
                json={"role": "Vice President", "is_active": False},
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["role"] == "Vice President"
        assert data["is_active"] is False
        db.drop_all()


def test_admin_deletes_a_committee_member_and_logs_an_audit_entry():
    from app.audit.models import AuditLog
    from app.committee.models import CommitteeMember

    app = _new_app()
    with app.app_context():
        member = CommitteeMember(name="Priya Das", role="President")
        db.session.add(member)
        db.session.commit()
        member_id = member.id
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete(
                f"/api/admin/committee/{member_id}", headers=headers
            )

        assert response.status_code == 204
        assert db.session.get(CommitteeMember, member_id) is None
        entry = AuditLog.query.one()
        assert entry.action == "committee_member_deleted"
        assert entry.target_id == member_id
        db.drop_all()


def test_admin_get_returns_404_for_unknown_member():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/committee/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_admin_creates_a_committee_member_with_contact_fields_and_quote():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/committee",
                headers=headers,
                json={
                    "name": "Sujata Bose",
                    "role": "Chair",
                    "email": "chair@bcaoslo.no",
                    "phone": "+47 401 22 318",
                    "member_since": 1994,
                    "quote": "Somebody has to unlock the hall at seven.",
                },
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["email"] == "chair@bcaoslo.no"
        assert data["phone"] == "+47 401 22 318"
        assert data["member_since"] == 1994
        assert data["quote"] == "Somebody has to unlock the hall at seven."
        db.drop_all()


def test_admin_create_rejects_an_invalid_email():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/committee",
                headers=headers,
                json={"name": "Priya Das", "role": "President", "email": "not-an-email"},
            )

        assert response.status_code == 400
        assert "email" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_rejects_an_out_of_range_member_since_year():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/committee",
                headers=headers,
                json={"name": "Priya Das", "role": "President", "member_since": 1800},
            )

        assert response.status_code == 400
        assert "member_since" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_can_clear_contact_fields_and_quote_back_to_null():
    from app.committee.models import CommitteeMember

    app = _new_app()
    with app.app_context():
        member = CommitteeMember(
            name="Priya Das", role="President", email="priya@bcaoslo.no",
            phone="+47 401 22 318", member_since=1994, quote="A line.",
        )
        db.session.add(member)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/committee/{member.id}",
                headers=headers,
                json={"email": None, "phone": None, "member_since": None, "quote": None},
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["email"] is None
        assert data["phone"] is None
        assert data["member_since"] is None
        assert data["quote"] is None
        db.drop_all()


def test_admin_committee_sub_name_is_optional_and_clearable():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            created = client.post(
                "/api/admin/committee",
                headers=headers,
                json={"name": "Sujata Bose", "sub_name": "সুজাতা বসু", "role": "Chair"},
            )
            assert created.status_code == 201
            assert created.get_json()["sub_name"] == "সুজাতা বসু"
            member_id = created.get_json()["id"]

            public = client.get("/api/committee").get_json()["items"][0]
            assert public["sub_name"] == "সুজাতা বসু"

            cleared = client.patch(f"/api/admin/committee/{member_id}", headers=headers, json={"sub_name": None})
            assert cleared.status_code == 200
            assert cleared.get_json()["sub_name"] is None
        db.drop_all()
