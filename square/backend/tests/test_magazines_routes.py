"""Tests for magazines routes (5 tests), e.g. public list hides unpublished and pdfless and orders newest first; admin sees unpublished in public list tagged false; admin routes require admin."""
import io
from datetime import date
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.magazines.models import Magazine
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

PDF_BYTES = b"%PDF-1.4\n%fake\n"


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _mag(**kw):
    defaults = {"title": "T", "slug": "t", "published": True, "pdf_url": "https://cdn/x.pdf"}
    defaults.update(kw)
    m = Magazine(**defaults)
    db.session.add(m)
    db.session.commit()
    return m


def test_public_list_hides_unpublished_and_pdfless_and_orders_newest_first():
    app = _new_app()
    with app.app_context():
        _mag(title="Old", slug="old", issue_date=date(2024, 1, 1))
        _mag(title="New", slug="new", issue_date=date(2026, 1, 1))
        _mag(title="Draft", slug="draft", published=False)
        _mag(title="NoPdf", slug="nopdf", pdf_url=None)

        client = app.test_client()
        items = client.get("/api/magazines").get_json()["items"]

        assert [i["title"] for i in items] == ["New", "Old"]
        assert client.get("/api/magazines/draft").status_code == 404
        assert client.get("/api/magazines/new").get_json()["pdf_url"] == "https://cdn/x.pdf"
        db.drop_all()


def test_admin_sees_unpublished_in_public_list_tagged_false():
    app = _new_app()
    with app.app_context():
        _mag(title="Draft", slug="draft", published=False)
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            items = app.test_client().get("/api/magazines", headers=_admin_headers()).get_json()["items"]
        assert [(i["title"], i["published"]) for i in items] == [("Draft", False)]
        db.drop_all()


def test_admin_routes_require_admin():
    app = _new_app()
    with app.app_context():
        assert app.test_client().get("/api/admin/magazines").status_code == 401
        db.drop_all()


def test_admin_full_flow_create_pdf_publish_cover_delete():
    from PIL import Image

    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _admin_headers()

            created = client.post(
                "/api/admin/magazines",
                json={"title": "Puja Special 2026", "issue_label": "Puja 2026", "issue_date": "2026-10-01"},
                headers=headers,
            )
            assert created.status_code == 201
            mid = created.get_json()["id"]
            assert created.get_json()["slug"] == "puja-special-2026"

            # Cannot publish before a PDF exists.
            early = client.patch(f"/api/admin/magazines/{mid}", json={"published": True}, headers=headers)
            assert early.status_code == 400 and "published" in early.get_json()["errors"]

            not_pdf = client.post(
                f"/api/admin/magazines/{mid}/pdf",
                data={"file": (io.BytesIO(b"hello"), "x.pdf")},
                content_type="multipart/form-data",
                headers=headers,
            )
            assert not_pdf.status_code == 400

            pdf = client.post(
                f"/api/admin/magazines/{mid}/pdf",
                data={"file": (io.BytesIO(PDF_BYTES), "issue.pdf")},
                content_type="multipart/form-data",
                headers=headers,
            )
            assert pdf.status_code == 200 and pdf.get_json()["pdf_url"]

            buf = io.BytesIO()
            Image.new("RGB", (30, 40), "white").save(buf, "PNG")
            buf.seek(0)
            cover = client.post(
                f"/api/admin/magazines/{mid}/cover",
                data={"file": (buf, "cover.png")},
                content_type="multipart/form-data",
                headers=headers,
            )
            assert cover.status_code == 200 and cover.get_json()["cover_url"]

            published = client.patch(f"/api/admin/magazines/{mid}", json={"published": True}, headers=headers)
            assert published.get_json()["published"] is True
            assert len(client.get("/api/magazines").get_json()["items"]) == 1

            assert client.delete(f"/api/admin/magazines/{mid}", headers=headers).status_code == 204

        assert AuditLog.query.filter_by(action="magazine_deleted").count() == 1
        db.drop_all()


def test_duplicate_titles_get_unique_slugs():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            client = app.test_client()
            headers = _admin_headers()
            a = client.post("/api/admin/magazines", json={"title": "Issue"}, headers=headers).get_json()
            b = client.post("/api/admin/magazines", json={"title": "Issue"}, headers=headers).get_json()
        assert a["slug"] == "issue" and b["slug"] == "issue-2"
        db.drop_all()
