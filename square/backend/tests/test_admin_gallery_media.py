"""Tests for admin gallery media (16 tests), e.g. upload requires admin; upload returns 404 for unknown album; upload requires at least one file."""
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from app import create_app
from app.extensions import db
from app.gallery.models import Album, Media
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
    defaults = {"title": "Durga Puja 2026", "year": 2026}
    defaults.update(overrides)
    album = Album(**defaults)
    db.session.add(album)
    db.session.commit()
    return album


def _jpeg_bytes(width=800, height=600) -> bytes:
    image = Image.new("RGB", (width, height), color="red")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def test_upload_requires_admin():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        response = app.test_client().post(f"/api/admin/gallery/albums/{album.id}/media")
        assert response.status_code == 401
        db.drop_all()


def test_upload_returns_404_for_unknown_album():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/gallery/albums/999/media",
                data={"files": (BytesIO(_jpeg_bytes()), "photo.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
        assert response.status_code == 404
        db.drop_all()


def test_upload_requires_at_least_one_file():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/gallery/albums/{album.id}/media", headers=headers
            )
        assert response.status_code == 400
        assert "files" in response.get_json()["errors"]
        db.drop_all()


def test_upload_succeeds_and_stores_original_and_thumbnail():
    from app.storage.service import get_public_storage

    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/gallery/albums/{album.id}/media",
                data={"files": (BytesIO(_jpeg_bytes()), "photo.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert response.status_code == 201
        data = response.get_json()
        assert len(data["created"]) == 1
        assert data["errors"] == []
        assert data["created"][0]["width"] == 800

        assert Media.query.filter_by(album_id=album.id).count() == 1
        media = Media.query.filter_by(album_id=album.id).one()
        storage = get_public_storage()
        assert media.storage_key in storage.objects
        assert media.thumbnail_storage_key in storage.objects
        db.drop_all()


def test_upload_processes_files_independently_reporting_per_file_errors():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/gallery/albums/{album.id}/media",
                data={
                    "files": [
                        (BytesIO(_jpeg_bytes()), "good.jpg"),
                        (BytesIO(b"not an image"), "bad.jpg"),
                    ]
                },
                headers=headers,
                content_type="multipart/form-data",
            )

        assert response.status_code == 201
        data = response.get_json()
        assert len(data["created"]) == 1
        assert len(data["errors"]) == 1
        assert data["errors"][0]["filename"] == "bad.jpg"
        db.drop_all()


def test_upload_returns_400_when_every_file_fails():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/gallery/albums/{album.id}/media",
                data={"files": (BytesIO(b"not an image"), "bad.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert response.status_code == 400
        data = response.get_json()
        assert data["created"] == []
        assert len(data["errors"]) == 1
        db.drop_all()


def test_update_media_caption_success():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            upload = client.post(
                f"/api/admin/gallery/albums/{album.id}/media",
                data={"files": (BytesIO(_jpeg_bytes()), "photo.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            media_id = upload.get_json()["created"][0]["id"]

            response = client.patch(
                f"/api/admin/gallery/media/{media_id}",
                json={"caption": "Cultural programme, Friday evening"},
                headers=headers,
            )

        assert response.status_code == 200
        assert response.get_json()["caption"] == "Cultural programme, Friday evening"
        db.drop_all()


def test_update_media_caption_can_clear_it():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        media = Media(album_id=album.id, filename="photo.jpg", storage_key="k", thumbnail_storage_key="t",
                      mime_type="image/jpeg", width=800, height=600, caption="Old caption")
        db.session.add(media)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/gallery/media/{media.id}", json={"caption": None}, headers=headers
            )

        assert response.status_code == 200
        assert response.get_json()["caption"] is None
        db.drop_all()


def test_update_media_caption_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/gallery/media/999", json={"caption": "x"}, headers=headers
            )
        assert response.status_code == 404
        db.drop_all()


def test_update_media_caption_rejects_a_non_string():
    app = _new_app()
    with app.app_context():
        album = _add_album()
        media = Media(album_id=album.id, filename="photo.jpg", storage_key="k", thumbnail_storage_key="t",
                      mime_type="image/jpeg", width=800, height=600)
        db.session.add(media)
        db.session.commit()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/gallery/media/{media.id}", json={"caption": 123}, headers=headers
            )

        assert response.status_code == 400
        assert "caption" in response.get_json()["errors"]
        db.drop_all()


def test_delete_media_removes_row_and_storage_objects():
    from app.storage.service import get_public_storage

    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            upload = client.post(
                f"/api/admin/gallery/albums/{album.id}/media",
                data={"files": (BytesIO(_jpeg_bytes()), "photo.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            media_id = upload.get_json()["created"][0]["id"]
            media = db.session.get(Media, media_id)
            storage_key, thumbnail_key = media.storage_key, media.thumbnail_storage_key

            response = client.delete(f"/api/admin/gallery/media/{media_id}", headers=headers)
            assert response.status_code == 204

        storage = get_public_storage()
        assert storage_key not in storage.objects
        assert thumbnail_key not in storage.objects
        assert Media.query.count() == 0
        db.drop_all()


def test_delete_media_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete("/api/admin/gallery/media/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_delete_media_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        album = _add_album(title="Durga Puja 2026")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            upload = client.post(
                f"/api/admin/gallery/albums/{album.id}/media",
                data={"files": (BytesIO(_jpeg_bytes()), "photo.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            media_id = upload.get_json()["created"][0]["id"]

            client.delete(f"/api/admin/gallery/media/{media_id}", headers=headers)

        entry = AuditLog.query.one()
        assert entry.action == "gallery_media_deleted"
        assert entry.target_type == "media"
        assert entry.target_id == media_id
        assert "Durga Puja 2026" in entry.description
        db.drop_all()


def test_deleting_an_album_with_media_removes_its_storage_objects_too():
    from app.storage.service import get_public_storage

    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            upload = client.post(
                f"/api/admin/gallery/albums/{album.id}/media",
                data={"files": (BytesIO(_jpeg_bytes()), "photo.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            upload.get_json()["created"][0]

            response = client.delete(f"/api/admin/gallery/albums/{album.id}", headers=headers)
            assert response.status_code == 204

        storage = get_public_storage()
        assert len(storage.objects) == 0
        db.drop_all()


def test_oversized_request_gets_a_json_413_and_is_logged(caplog):
    app = _new_app()
    app.config["MAX_CONTENT_LENGTH"] = 1024
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            with caplog.at_level("WARNING"):
                response = app.test_client().post(
                    f"/api/admin/gallery/albums/{album.id}/media",
                    data={"files": (BytesIO(b"0" * 5000), "big.jpg")},
                    headers=headers,
                    content_type="multipart/form-data",
                )
        assert response.status_code == 413
        assert "too large" in response.get_json()["error"]
        assert "Request rejected as too large" in caplog.text
        db.drop_all()


def test_a_crash_while_processing_one_file_is_logged_and_reported_not_fatal(caplog):
    app = _new_app()
    with app.app_context():
        album = _add_album()
        headers = _admin_headers()
        real = __import__("app.gallery.admin_routes", fromlist=["process_upload"]).process_upload
        calls = {"n": 0}

        def flaky(file):
            calls["n"] += 1
            if calls["n"] == 1:
                raise MemoryError("boom")
            return real(file)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()), patch(
            "app.gallery.admin_routes.process_upload", side_effect=flaky
        ):
            with caplog.at_level("WARNING"):
                response = app.test_client().post(
                    f"/api/admin/gallery/albums/{album.id}/media",
                    data={"files": [(BytesIO(_jpeg_bytes()), "bad.jpg"), (BytesIO(_jpeg_bytes()), "good.jpg")]},
                    headers=headers,
                    content_type="multipart/form-data",
                )
        body = response.get_json()
        assert response.status_code == 201
        assert len(body["created"]) == 1
        assert body["errors"] == [{"filename": "bad.jpg", "error": "Could not process this image."}]
        assert "failed while processing" in caplog.text
        db.drop_all()
