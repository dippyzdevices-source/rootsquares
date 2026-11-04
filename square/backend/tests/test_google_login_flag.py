"""Google sign-in is offered only where it is switched on (rootsquares W23-R86): the square's config says so, from the platform's `squares.google_login`."""

import base64
import hashlib
import json
from unittest.mock import patch

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text

from app import create_app
from app.config import TestingConfig

FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"dev-only-fernet-key").digest()))


def _enc(value: str) -> str:
    return FERNET.encrypt(value.encode()).decode()


def _server(tmp_path, with_column: bool):
    url = f"sqlite:///{tmp_path / 'platform.db'}"
    engine = create_engine(url)
    cols = "slug text, name text, theme_id text, domain text, status text, suspended_at text, db_connection text, provider_secrets text" + (", google_login text" if with_column else "")
    with engine.begin() as conn:
        conn.execute(text(f"create table squares ({cols})"))
        for slug, flag in (("on-square", "enabled"), ("asked-square", "requested"), ("null-square", None)):
            values = {"slug": slug, "name": slug, "domain": f"{slug}.rootsquares.com", "url": _enc(f"sqlite:///{tmp_path / (slug + '.db')}"), "sec": _enc(json.dumps({"project_url": "https://a.supabase.co", "publishable": "pk"}))}
            if with_column:
                conn.execute(text("insert into squares values (:slug, :name, 'paper-brick', :domain, 'ready', null, :url, :sec, :flag)"), {**values, "flag": flag})
            else:
                conn.execute(text("insert into squares values (:slug, :name, 'paper-brick', :domain, 'ready', null, :url, :sec)"), values)
    engine.dispose()
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", url):
        return create_app("testing")


def _google(app, slug: str):
    return app.test_client().get("/api/square/config", base_url=f"http://{slug}.localhost").get_json()["google_login"]


def test_google_is_offered_only_where_it_is_enabled(tmp_path):
    app = _server(tmp_path, with_column=True)
    assert _google(app, "on-square") is True
    assert _google(app, "asked-square") is False  # asked for, not switched on yet: no button that ends in an error page
    assert _google(app, "null-square") is False  # nothing recorded means not enabled


def test_an_older_platform_database_that_cannot_say_keeps_the_button(tmp_path):
    app = _server(tmp_path, with_column=False)
    assert _google(app, "on-square") is True
