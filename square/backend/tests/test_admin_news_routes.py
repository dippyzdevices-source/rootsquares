"""Tests for admin news routes (32 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin list news includes drafts and archived."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.news.models import News
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _add_news(**overrides):
    defaults = {"title": "Draft article", "slug": "draft-article", "content": "Body.", "status": "draft"}
    defaults.update(overrides)
    article = News(**defaults)
    db.session.add(article)
    db.session.commit()
    return article


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/news")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/news", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_list_news_includes_drafts_and_archived():
    app = _new_app()
    with app.app_context():
        _add_news(title="Draft", slug="draft", status="draft")
        _add_news(title="Archived", slug="archived", status="archived")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            data = app.test_client().get("/api/admin/news", headers=headers).get_json()

        assert {item["title"] for item in data["items"]} == {"Draft", "Archived"}
        db.drop_all()


def test_admin_create_news_requires_title_slug_and_content():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post("/api/admin/news", json={}, headers=headers)

        assert response.status_code == 400
        assert set(response.get_json()["errors"]) == {"title", "content"}
        db.drop_all()


def test_admin_create_news_success():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/news",
                json={"title": "New article", "slug": "new-article", "content": "Body text."},
                headers=headers,
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["title"] == "New article"
        assert data["status"] == "draft"
        db.drop_all()


def test_admin_create_news_rejects_duplicate_slug():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        payload = {"title": "One", "slug": "dup", "content": "Body."}
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            client.post("/api/admin/news", json=payload, headers=headers)
            response = client.post(
                "/api/admin/news", json={**payload, "title": "Two"}, headers=headers
            )

        assert response.status_code == 409
        db.drop_all()


def test_admin_get_news_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/news/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_admin_update_news_can_publish_with_a_scheduled_date():
    app = _new_app()
    with app.app_context():
        article = _add_news()
        headers = _admin_headers()
        future = (NOW + timedelta(days=1)).isoformat()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/news/{article.id}",
                json={"status": "published", "published_at": future},
                headers=headers,
            )

        data = response.get_json()
        assert response.status_code == 200
        assert data["status"] == "published"
        assert data["published_at"] is not None
        assert data["title"] == "Draft article"  # untouched by the partial update
        db.drop_all()


def test_admin_update_news_rejects_an_invalid_status():
    app = _new_app()
    with app.app_context():
        article = _add_news()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/news/{article.id}", json={"status": "bogus"}, headers=headers
            )

        assert response.status_code == 400
        assert "status" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_news_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/news/999", json={"status": "archived"}, headers=headers
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_news_success():
    app = _new_app()
    with app.app_context():
        article = _add_news()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            response = client.delete(f"/api/admin/news/{article.id}", headers=headers)
            assert response.status_code == 204

            follow_up = client.get(f"/api/admin/news/{article.id}", headers=headers)
            assert follow_up.status_code == 404
        db.drop_all()


def test_admin_delete_news_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().delete("/api/admin/news/999", headers=headers)
        assert response.status_code == 404
        db.drop_all()


def test_admin_create_news_accepts_a_category():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/news",
                json={"title": "New article", "slug": "new-article", "content": "Body text.",
                      "category": "story"},
                headers=headers,
            )

        assert response.status_code == 201
        assert response.get_json()["category"] == "story"
        db.drop_all()


def test_admin_create_news_rejects_an_invalid_category():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/news",
                json={"title": "New article", "slug": "new-article", "content": "Body text.",
                      "category": "not-a-category"},
                headers=headers,
            )

        assert response.status_code == 400
        assert "category" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_news_can_clear_a_category():
    app = _new_app()
    with app.app_context():
        article = _add_news(category="story")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/news/{article.id}", json={"category": None}, headers=headers
            )

        assert response.status_code == 200
        assert response.get_json()["category"] is None
        db.drop_all()


def test_admin_create_news_records_the_creating_admin():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="admin", email="admin@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/news",
                json={"title": "New article", "slug": "new-article", "content": "Body text."},
                headers=auth_header(token),
            )

        data = response.get_json()
        assert data["created_by_email"] == "admin@example.com"
        assert data["updated_by_email"] == "admin@example.com"
        db.drop_all()


def test_admin_update_news_records_the_editing_admin():
    app = _new_app()
    with app.app_context():
        article = _add_news()
        creator, creator_token = make_user_and_token(role="admin", email="creator@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().patch(
                f"/api/admin/news/{article.id}", json={"status": "draft"},
                headers=auth_header(creator_token),
            )

        editor, editor_token = make_user_and_token(role="admin", email="editor@example.com")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/news/{article.id}", json={"status": "published"},
                headers=auth_header(editor_token),
            )

        data = response.get_json()
        assert data["created_by_email"] is None  # article was never created via this admin API
        assert data["updated_by_email"] == "editor@example.com"
        db.drop_all()


def test_admin_create_news_sanitizes_disallowed_html_out_of_content():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/news",
                json={
                    "title": "New article",
                    "slug": "new-article",
                    "content": '<p>Hello <script>alert(1)</script><strong>world</strong></p>'
                    '<img src=x onerror=alert(1)>',
                },
                headers=headers,
            )

        assert response.status_code == 201
        content = response.get_json()["content"]
        assert "<script>" not in content
        assert "<img" not in content
        assert "onerror" not in content
        assert "<strong>world</strong>" in content
        db.drop_all()


def test_admin_create_news_keeps_allowed_formatting_tags():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/news",
                json={
                    "title": "New article",
                    "slug": "new-article",
                    "content": (
                        '<h2>Heading</h2><p><em>emphasis</em></p>'
                        '<ul><li>one</li></ul>'
                        '<a href="https://example.com" target="_blank" rel="noopener">link</a>'
                    ),
                },
                headers=headers,
            )

        content = response.get_json()["content"]
        assert "<h2>Heading</h2>" in content
        assert "<em>emphasis</em>" in content
        assert "<ul><li>one</li></ul>" in content
        assert 'href="https://example.com"' in content
        db.drop_all()


def test_admin_create_news_strips_a_javascript_link_protocol():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/news",
                json={
                    "title": "New article",
                    "slug": "new-article",
                    "content": '<a href="javascript:alert(1)">click me</a>',
                },
                headers=headers,
            )

        content = response.get_json()["content"]
        assert "javascript:" not in content
        db.drop_all()


def test_admin_upload_news_banner_success():
    from io import BytesIO

    from PIL import Image

    app = _new_app()
    with app.app_context():
        article = _add_news()
        headers = _admin_headers()

        image = Image.new("RGB", (800, 400), color="blue")
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        buffer.seek(0)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/news/{article.id}/banner",
                data={"file": (buffer, "banner.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["banner_image"]
        db.session.refresh(article)
        assert article.banner_image == data["banner_image"]
        db.drop_all()


def _jpeg_file(name="banner.jpg"):
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (800, 400), color="blue")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return (buffer, name)


def test_admin_replacing_a_news_banner_deletes_the_old_one_from_storage():
    app = _new_app()
    with app.app_context():
        article = _add_news()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            first = app.test_client().post(
                f"/api/admin/news/{article.id}/banner",
                data={"file": _jpeg_file("first.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            storage = app.extensions["public_storage"]
            old_key = storage.key_from_url(first.get_json()["banner_image"])
            assert old_key in storage.objects

            second = app.test_client().post(
                f"/api/admin/news/{article.id}/banner",
                data={"file": _jpeg_file("second.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert second.status_code == 200
        new_key = storage.key_from_url(second.get_json()["banner_image"])
        assert old_key not in storage.objects
        assert new_key in storage.objects
        db.drop_all()


def test_admin_upload_news_banner_returns_404_for_unknown_article():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/news/999/banner",
                data={"file": (b"not an image", "banner.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_upload_news_banner_rejects_a_non_image_file():
    app = _new_app()
    with app.app_context():
        article = _add_news()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/news/{article.id}/banner",
                data={"file": (b"not an image", "banner.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
        assert response.status_code == 400
        assert "file" in response.get_json()["errors"]
        db.drop_all()


def test_admin_add_news_image_appends_without_replacing_earlier_ones():
    from app.news.models import NewsImage

    app = _new_app()
    with app.app_context():
        article = _add_news()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            first = app.test_client().post(
                f"/api/admin/news/{article.id}/images",
                data={"file": _jpeg_file("first.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
            second = app.test_client().post(
                f"/api/admin/news/{article.id}/images",
                data={"file": _jpeg_file("second.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )

        assert first.status_code == 201
        assert second.status_code == 201
        data = second.get_json()
        assert len(data["images"]) == 2
        assert [i["sort_order"] for i in data["images"]] == [0, 1]
        assert NewsImage.query.filter_by(news_id=article.id).count() == 2
        db.drop_all()


def test_admin_add_news_image_returns_404_for_unknown_article():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/news/999/images",
                data={"file": _jpeg_file()},
                headers=headers,
                content_type="multipart/form-data",
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_add_news_image_rejects_a_non_image_file():
    app = _new_app()
    with app.app_context():
        article = _add_news()
        headers = _admin_headers()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                f"/api/admin/news/{article.id}/images",
                data={"file": (b"not an image", "photo.jpg")},
                headers=headers,
                content_type="multipart/form-data",
            )
        assert response.status_code == 400
        assert "file" in response.get_json()["errors"]
        db.drop_all()


def test_admin_delete_news_image_removes_it():
    from app.news.models import NewsImage

    app = _new_app()
    with app.app_context():
        article = _add_news()
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            created = app.test_client().post(
                f"/api/admin/news/{article.id}/images",
                data={"file": _jpeg_file()},
                headers=headers,
                content_type="multipart/form-data",
            ).get_json()
            image_id = created["images"][0]["id"]

            response = app.test_client().delete(
                f"/api/admin/news/{article.id}/images/{image_id}", headers=headers
            )

        assert response.status_code == 200
        assert response.get_json()["images"] == []
        assert NewsImage.query.count() == 0
        db.drop_all()


def test_admin_delete_news_image_returns_404_for_an_image_from_another_article():
    app = _new_app()
    with app.app_context():
        article_a = _add_news(title="A", slug="a")
        article_b = _add_news(title="B", slug="b")
        headers = _admin_headers()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            created = app.test_client().post(
                f"/api/admin/news/{article_a.id}/images",
                data={"file": _jpeg_file()},
                headers=headers,
                content_type="multipart/form-data",
            ).get_json()
            image_id = created["images"][0]["id"]

            response = app.test_client().delete(
                f"/api/admin/news/{article_b.id}/images/{image_id}", headers=headers
            )

        assert response.status_code == 404
        db.drop_all()


def test_admin_delete_news_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        article = _add_news(title="Durga Puja recap", slug="durga-puja-recap")
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().delete(
                f"/api/admin/news/{article.id}", headers=auth_header(token)
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "news_deleted"
        assert entry.target_type == "news"
        assert entry.target_id == article.id
        assert "Durga Puja recap" in entry.description
        db.drop_all()


def test_admin_create_news_autogenerates_unique_slug():
    app = _new_app()
    with app.app_context():
        headers = _admin_headers()
        payload = {"title": "Durga Puja på Østensjø!", "content": "Body."}
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            first = client.post("/api/admin/news", json=payload, headers=headers)
            second = client.post("/api/admin/news", json=payload, headers=headers)

        assert first.status_code == 201 and second.status_code == 201
        assert first.get_json()["slug"] == "durga-puja-pa-ostensjo"
        assert second.get_json()["slug"] == "durga-puja-pa-ostensjo-2"
        db.drop_all()


def test_list_news_filters_by_search_and_status_including_scheduled():
    from datetime import datetime, timedelta, timezone

    app = _new_app()
    with app.app_context():
        now = datetime.now(timezone.utc)
        _add_news(title="Mahalaya recap", slug="mahalaya-recap", status="published", published_at=now - timedelta(days=2))
        _add_news(title="Upcoming festival", slug="upcoming-festival", status="published", published_at=now + timedelta(days=5))
        _add_news(title="Work in progress", slug="work-in-progress", status="draft")
        _add_news(title="Old notice", slug="old-notice", status="archived")
        headers = _admin_headers()

        def titles(query):
            with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
                response = app.test_client().get(f"/api/admin/news?{query}", headers=headers)
            assert response.status_code == 200
            return {a["title"] for a in response.get_json()["items"]}

        assert len(titles("")) == 4
        assert titles("status=published") == {"Mahalaya recap"}
        assert titles("status=scheduled") == {"Upcoming festival"}
        assert titles("status=draft") == {"Work in progress"}
        assert titles("status=archived") == {"Old notice"}
        assert titles("q=festival") == {"Upcoming festival"}
        assert titles("q=notice&status=archived") == {"Old notice"}

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            bad = app.test_client().get("/api/admin/news?status=nonsense", headers=headers)
        assert bad.status_code == 400
        db.drop_all()
