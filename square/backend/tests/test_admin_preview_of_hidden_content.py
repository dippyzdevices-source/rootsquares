"""An admin's own request to the public content endpoints also gets hidden/draft items, tagged
`published: false`, so they can be reviewed before going live; everyone else never sees them."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.committee.models import CommitteeMember
from app.extensions import db
from app.founders.models import Founder
from app.gallery.models import Album
from app.news.models import News
from app.testimonials.models import Testimonial
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _get(client, path, headers=None):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return client.get(path, headers=headers or {}).get_json()


def _admin():
    _, token = make_user_and_token(role="admin", email="admin@example.com")
    return auth_header(token)


def _member():
    _, token = make_user_and_token(role="member", email="member@example.com")
    return auth_header(token)


def test_committee_and_founders_hidden_items_appear_only_for_admins():
    app = _new_app()
    with app.app_context():
        db.session.add_all([
            CommitteeMember(name="Shown", role="President", is_active=True),
            CommitteeMember(name="Hidden", role="Treasurer", is_active=False),
            Founder(name="Shown F", role="Founder", quote="q", is_active=True),
            Founder(name="Hidden F", role="Founder", quote="q", is_active=False),
        ])
        db.session.commit()
        client = app.test_client()
        admin, member = _admin(), _member()

        for path in ("/api/committee", "/api/founders"):
            anon = _get(client, path)["items"]
            as_member = _get(client, path, member)["items"]
            as_admin = _get(client, path, admin)["items"]
            assert len(anon) == 1 and len(as_member) == 1
            assert len(as_admin) == 2
            assert [i["published"] for i in as_admin].count(False) == 1
        db.drop_all()


def test_news_drafts_and_scheduled_articles_appear_only_for_admins():
    app = _new_app()
    with app.app_context():
        now = datetime.now(timezone.utc)
        db.session.add_all([
            News(title="Live", slug="live", content="x", status="published", published_at=now - timedelta(days=1)),
            News(title="Draft", slug="draft", content="x", status="draft"),
            News(title="Soon", slug="soon", content="x", status="published", published_at=now + timedelta(days=5)),
        ])
        db.session.commit()
        client = app.test_client()

        assert [i["slug"] for i in _get(client, "/api/news")["items"]] == ["live"]
        admin_items = _get(client, "/api/news", _admin())["items"]
        assert {i["slug"] for i in admin_items} == {"live", "draft", "soon"}
        assert {i["slug"]: i["published"] for i in admin_items} == {"live": True, "draft": False, "soon": False}
        # Detail: a draft 404s for the public, resolves for an admin.
        assert client.get("/api/news/draft").status_code == 404
        assert _get(client, "/api/news/draft", _admin())["published"] is False
        db.drop_all()


def test_unpublished_albums_and_pending_testimonials_appear_only_for_admins():
    app = _new_app()
    with app.app_context():
        album = Album(title="Hidden album", year=2026, published=False)
        db.session.add_all([
            album,
            Album(title="Live album", year=2026, published=True),
            Testimonial(quote="ok", author_name="A", status="approved", is_active=True),
            Testimonial(quote="wait", author_name="B", status="pending", is_active=False),
        ])
        db.session.commit()
        client = app.test_client()

        assert len(_get(client, "/api/gallery/albums")["items"]) == 1
        assert len(_get(client, "/api/gallery/albums", _admin())["items"]) == 2
        assert client.get(f"/api/gallery/albums/{album.id}").status_code == 404
        assert _get(client, f"/api/gallery/albums/{album.id}", _admin())["published"] is False

        assert len(_get(client, "/api/testimonials")["items"]) == 1
        as_admin = _get(client, "/api/testimonials", _admin())["items"]
        assert len(as_admin) == 2 and [t["published"] for t in as_admin].count(False) == 1
        db.drop_all()
