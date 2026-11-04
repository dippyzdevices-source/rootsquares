"""Health and configuration of the platform for the owner console: what is switched on and whether each outside service answers right now.
Never returns a secret: only booleans, host names and short status words. Every network call has a short timeout and a failure only gives the
exception's type name, so no URL or key can leak into the page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.config import Settings

TIMEOUT = 5.0
SUPABASE_API = "https://api.supabase.com"


@dataclass
class Check:
    id: str
    status: str  # ok | warn | fail | off
    detail: str = ""


def _host(url: str) -> str:
    return urlparse(url).hostname or ""


def _database(db: Session) -> Check:
    try:
        db.execute(select(1))
        return Check("database", "ok", db.get_bind().dialect.name)
    except Exception as exc:  # noqa: BLE001 (any failure means: not reachable)
        return Check("database", "fail", type(exc).__name__)


def _secrets(settings: Settings) -> list[Check]:
    checks = [
        Check("jwt_secret", "ok" if settings.JWT_SECRET else "warn", "" if settings.JWT_SECRET else "development key in use"),
        Check("fernet_key", "ok" if settings.FERNET_KEY else "warn", "" if settings.FERNET_KEY else "development key in use"),
        Check("auth_admin_key", "ok" if settings.AUTH_ADMIN_KEY else "warn", "" if settings.AUTH_ADMIN_KEY else "account deletion leaves the sign-in account"),
        Check("cookie_secure", "ok" if settings.COOKIE_SECURE else "warn", "" if settings.COOKIE_SECURE else "cookies also travel over plain http"),
    ]
    return checks


def _platform_auth(settings: Settings, client: httpx.Client) -> Check:
    if not settings.AUTH_PROVIDER:
        return Check("platform_auth", "off", "own cookie login only")
    path = "/auth/v1/.well-known/jwks.json" if settings.AUTH_PROVIDER == "supabase" else "/.well-known/jwks.json"
    url = settings.auth_url + path
    try:
        ok = client.get(url).status_code == 200
        return Check("platform_auth", "ok" if ok else "fail", settings.AUTH_PROVIDER if ok else "keys not served")
    except Exception as exc:  # noqa: BLE001
        return Check("platform_auth", "fail", type(exc).__name__)


def _provider_token(settings: Settings, client: httpx.Client) -> Check:
    if settings.PROVISIONER == "local":
        return Check("provider_token", "off", "squares get a database in the local Postgres")
    if settings.PROVISIONER == "neon":
        if not settings.NEON_API_KEY:
            return Check("provider_token", "fail", "NEON_API_KEY not set")
        return Check("provider_token", "warn", "key set; Neon has never been run")
    if not settings.SUPABASE_ACCESS_TOKEN:
        return Check("provider_token", "fail", "SUPABASE_ACCESS_TOKEN not set")
    try:
        r = client.get(f"{SUPABASE_API}/v1/organizations", headers={"Authorization": f"Bearer {settings.SUPABASE_ACCESS_TOKEN}"})
    except Exception as exc:  # noqa: BLE001
        return Check("provider_token", "fail", type(exc).__name__)
    if r.status_code in (401, 403):
        return Check("provider_token", "fail", "the token was refused")
    if r.status_code != 200:
        return Check("provider_token", "fail", f"HTTP {r.status_code}")
    slugs = {str(o.get("slug")) for o in r.json() if isinstance(o, dict)}
    if settings.SUPABASE_ORG_SLUG and settings.SUPABASE_ORG_SLUG not in slugs:
        return Check("provider_token", "fail", "token works, but SUPABASE_ORG_SLUG is not one of its organisations")
    return Check("provider_token", "ok", "token works")


def _storage(settings: Settings, providers: Any) -> Check:
    if not settings.STORAGE_S3_ENDPOINT_URL:
        return Check("storage", "warn", "in-memory fake (local only)")
    bad = []
    for label, store in (("public", providers.storage), ("private", providers.private_storage)):
        check = getattr(store, "check", None)
        try:
            if check is not None:
                check()
        except Exception:  # noqa: BLE001
            bad.append(label)
    return Check("storage", "fail", f"bucket not reachable: {', '.join(bad)}") if bad else Check("storage", "ok", _host(settings.STORAGE_S3_ENDPOINT_URL))


def _google(settings: Settings) -> Check:
    ready = bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)
    return Check("google_client", "ok" if ready else "warn", "" if ready else "squares cannot switch Google sign-in on")


def environment(settings: Settings) -> dict[str, str]:
    return {
        "env": settings.ENV,
        "provisioner": settings.PROVISIONER,
        "auth_provider": settings.AUTH_PROVIDER or "none",
        "auth_host": _host(settings.auth_url),
        "storage": _host(settings.STORAGE_S3_ENDPOINT_URL) or "in-memory fake",
        "square_domain": settings.SQUARE_DOMAIN_SUFFIX,
        "themes": ", ".join(settings.enabled_theme_ids),
    }


def run_checks(settings: Settings, providers: Any, db: Session, client: httpx.Client | None = None) -> list[Check]:
    own = client is None
    http = client or httpx.Client(timeout=TIMEOUT)
    try:
        return [
            _database(db),
            _platform_auth(settings, http),
            _provider_token(settings, http),
            _storage(settings, providers),
            _google(settings),
            *_secrets(settings),
        ]
    finally:
        if own:
            http.close()
