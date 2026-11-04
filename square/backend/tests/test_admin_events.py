"""Tests for admin events (27 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin list events includes unpublished events."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.events.models import Event
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _add_event(**overrides):
    defaults = {"event_type": "festival", "published": False}
    defaults.update(overrides)
    event = Event(**defaults)
    db.session.add(event)
    db.session.commit()
    return event


def _valid_payload(**overrides):
    payload = {
        "title": "Durga Puja 2026",
        "slug": "durga-puja-2026",
        "event_type": "festival",
        "start_datetime": (NOW + timedelta(days=10)).isoformat(),
    }
    payload.update(overrides)
    return payload


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/events")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/events", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_list_events_includes_unpublished_events():
    app = _new_app()
    with app.app_context():
        _add_event(title="Draft", slug="draft", start_datetime=NOW + timedelta(days=1), published=False)
        _add_event(title="Live", slug="live", start_datetime=NOW + timedelta(days=2), published=True)
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            data = app.test_client().get("/api/admin/events", headers=headers).get_json()

        titles = {item["title"] for item in data["items"]}
        assert titles == {"Draft", "Live"}

        db.drop_all()


def test_admin_create_event_success():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/events", json=_valid_payload(), headers=headers
            )
        data = response.get_json()

        assert response.status_code == 201
        assert data["title"] == "Durga Puja 2026"
        assert data["published"] is False
        assert data["status"] == "scheduled"

        db.drop_all()


def test_admin_create_event_sanitizes_disallowed_html_out_of_description():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/events",
                json=_valid_payload(
                    description='<p>Come join us <script>alert(1)</script><strong>tonight</strong></p>'
                    '<img src=x onerror=alert(1)>',
                ),
                headers=headers,
            )

        assert response.status_code == 201
        description = response.get_json()["description"]
        assert "<script>" not in description
        assert "<img" not in description
        assert "onerror" not in description
        assert "<strong>tonight</strong>" in description
        db.drop_all()


def test_admin_create_event_keeps_allowed_formatting_tags_in_description():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/events",
                json=_valid_payload(
                    description=(
                        '<h2>Schedule</h2><p><em>Doors open</em> at 5pm.</p>'
                        '<ul><li>Bhog</li></ul>'
                        '<a href="https://example.com" target="_blank" rel="noopener">details</a>'
                    ),
                ),
                headers=headers,
            )

        description = response.get_json()["description"]
        assert "<h2>Schedule</h2>" in description
        assert "<em>Doors open</em>" in description
        assert "<ul><li>Bhog</li></ul>" in description
        assert 'href="https://example.com"' in description
        db.drop_all()


def test_admin_create_event_requires_fields():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post("/api/admin/events", json={}, headers=headers)
        data = response.get_json()

        assert response.status_code == 400
        assert set(data["errors"]) == {"title", "slug", "event_type", "start_datetime"}

        db.drop_all()


def test_admin_create_event_rejects_duplicate_slug():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.post("/api/admin/events", json=_valid_payload(), headers=headers)
            response = client.post(
                "/api/admin/events", json=_valid_payload(title="Another Event"), headers=headers
            )

        assert response.status_code == 409

        db.drop_all()


def test_admin_create_event_rejects_end_before_start():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        payload = _valid_payload(
            start_datetime=(NOW + timedelta(days=5)).isoformat(),
            end_datetime=(NOW + timedelta(days=1)).isoformat(),
        )
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post("/api/admin/events", json=payload, headers=headers)

        assert response.status_code == 400
        assert "end_datetime" in response.get_json()["errors"]

        db.drop_all()


def test_admin_get_event_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/events/999", headers=headers)

        assert response.status_code == 404

        db.drop_all()


def test_admin_update_event_success_and_partial():
    app = _new_app()
    with app.app_context():
        event = _add_event(title="Original", slug="original", start_datetime=NOW + timedelta(days=1))
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/events/{event.id}", json={"published": True}, headers=headers
            )
        data = response.get_json()

        assert response.status_code == 200
        assert data["published"] is True
        assert data["title"] == "Original"  # untouched by a partial update

        db.drop_all()


def test_admin_update_event_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/events/999", json={"published": True}, headers=headers
            )

        assert response.status_code == 404


def test_admin_create_event_records_the_creating_admin():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="admin", email="admin@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/events", json=_valid_payload(), headers=auth_header(token)
            )

        data = response.get_json()
        assert data["created_by_email"] == "admin@example.com"
        assert data["updated_by_email"] == "admin@example.com"
        db.drop_all()


def test_admin_upload_event_banner_success():
    from io import BytesIO

    from PIL import Image

    app = _new_app()
    with app.app_context():
        event = _add_event(title="Original", slug="original", start_datetime=NOW + timedelta(days=1))
        headers = _admin_headers()

        image = Image.new("RGB", (800, 400), color="red")
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/banner",
                data={"file": (buffer, "banner.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["banner_image"]
        db.session.refresh(event)
        assert event.banner_image == data["banner_image"]
        db.drop_all()


def test_admin_replacing_a_banner_deletes_the_old_one_from_storage():
    app = _new_app()
    with app.app_context():
        event = _add_event(title="Original", slug="original", start_datetime=NOW + timedelta(days=1))
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            first = app.test_client().post(
                f"/api/admin/events/{event.id}/banner",
                data={"file": _jpeg_file("first.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            storage = app.extensions["public_storage"]
            old_key = storage.key_from_url(first.get_json()["banner_image"])
            assert old_key in storage.objects  # sanity check before replacing

            second = app.test_client().post(
                f"/api/admin/events/{event.id}/banner",
                data={"file": _jpeg_file("second.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert second.status_code == 200
        new_key = storage.key_from_url(second.get_json()["banner_image"])
        assert old_key not in storage.objects
        assert new_key in storage.objects
        db.drop_all()


def test_admin_upload_event_banner_returns_404_for_unknown_event():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/events/999/banner",
                data={"file": (b"not an image", "banner.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_upload_event_banner_rejects_a_non_image_file():
    app = _new_app()
    with app.app_context():
        event = _add_event(title="Original", slug="original", start_datetime=NOW + timedelta(days=1))
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/events/{event.id}/banner",
                data={"file": (b"not an image", "banner.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
        assert response.status_code == 400
        assert "file" in response.get_json()["errors"]
        db.drop_all()


def _jpeg_file(name="banner.jpg"):
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (800, 400), color="blue")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return (buffer, name)


def test_admin_add_event_banner_appends_without_replacing_earlier_ones():
    from app.events.models import EventBanner

    app = _new_app()
    with app.app_context():
        event = _add_event(title="Original", slug="original", start_datetime=NOW + timedelta(days=1))
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            first = app.test_client().post(
                f"/api/admin/events/{event.id}/banners",
                data={"file": _jpeg_file("first.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            second = app.test_client().post(
                f"/api/admin/events/{event.id}/banners",
                data={"file": _jpeg_file("second.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert first.status_code == 201
        assert second.status_code == 201
        data = second.get_json()
        assert len(data["banners"]) == 2
        assert [b["sort_order"] for b in data["banners"]] == [0, 1]
        assert EventBanner.query.filter_by(event_id=event.id).count() == 2
        db.drop_all()


def test_admin_add_event_banner_returns_404_for_unknown_event():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/events/999/banners",
                data={"file": _jpeg_file()},
                headers=headers,
                content_type="multipart/form-data",
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_event_banner_removes_it():
    from app.events.models import EventBanner

    app = _new_app()
    with app.app_context():
        event = _add_event(title="Original", slug="original", start_datetime=NOW + timedelta(days=1))
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            created = app.test_client().post(
                f"/api/admin/events/{event.id}/banners",
                data={"file": _jpeg_file()},
                headers=headers,
                content_type="multipart/form-data",
            ).get_json()
            banner_id = created["banners"][0]["id"]

            response = app.test_client().delete(
                f"/api/admin/events/{event.id}/banners/{banner_id}", headers=headers
            )

        assert response.status_code == 200
        assert response.get_json()["banners"] == []
        assert EventBanner.query.count() == 0
        db.drop_all()


def test_admin_delete_event_banner_returns_404_for_a_banner_from_another_event():
    app = _new_app()
    with app.app_context():
        event_a = _add_event(title="A", slug="a", start_datetime=NOW + timedelta(days=1))
        event_b = _add_event(title="B", slug="b", start_datetime=NOW + timedelta(days=2))
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            created = app.test_client().post(
                f"/api/admin/events/{event_a.id}/banners",
                data={"file": _jpeg_file()},
                headers=headers,
                content_type="multipart/form-data",
            ).get_json()
            banner_id = created["banners"][0]["id"]

            response = app.test_client().delete(
                f"/api/admin/events/{event_b.id}/banners/{banner_id}", headers=headers
            )

        assert response.status_code == 404
        db.drop_all()


def test_admin_update_event_records_the_editing_admin():
    app = _new_app()
    with app.app_context():
        event = _add_event(title="Original", slug="original", start_datetime=NOW + timedelta(days=1))
        _, token = make_user_and_token(role="admin", email="editor@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/events/{event.id}", json={"published": True}, headers=auth_header(token)
            )

        assert response.get_json()["updated_by_email"] == "editor@example.com"
        db.drop_all()

        db.drop_all()


def test_admin_delete_event_success():
    app = _new_app()
    with app.app_context():
        event = _add_event(title="To Delete", slug="to-delete", start_datetime=NOW + timedelta(days=1))
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            response = client.delete(f"/api/admin/events/{event.id}", headers=headers)
            assert response.status_code == 204

            follow_up = client.get(f"/api/admin/events/{event.id}", headers=headers)
            assert follow_up.status_code == 404

        db.drop_all()


def test_admin_delete_event_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete("/api/admin/events/999", headers=headers)

        assert response.status_code == 404

        db.drop_all()


def test_admin_delete_event_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        event = _add_event(title="Durga Puja 2026", slug="durga-puja-2026", start_datetime=NOW + timedelta(days=1))
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().delete(
                f"/api/admin/events/{event.id}", headers=auth_header(token)
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "event_deleted"
        assert entry.target_type == "event"
        assert entry.target_id == event.id
        assert "Durga Puja 2026" in entry.description
        db.drop_all()


def test_admin_create_event_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                "/api/admin/events", headers=auth_header(token), json=_valid_payload()
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "event_created"
        assert entry.target_type == "event"
        assert "Durga Puja 2026" in entry.description
        db.drop_all()


def test_admin_update_event_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        event = _add_event(title="Durga Puja 2026", slug="durga-puja-2026", start_datetime=NOW + timedelta(days=1))
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().patch(
                f"/api/admin/events/{event.id}",
                headers=auth_header(token),
                json={"title": "Durga Puja 2026 (updated)"},
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "event_updated"
        assert entry.target_type == "event"
        assert entry.target_id == event.id
        assert "Durga Puja 2026 (updated)" in entry.description
        db.drop_all()
