"""Verifying a square's own tokens (ADR 028, auth item C). A square has its own auth project, so a token issued to one of its members is checked
against THAT project's signing keys, never the platform's. The square API (not built yet) calls `SquareAuthVerifier.authenticate(square_id, token)`.

What it does: load the square from the platform database, decrypt its secrets (project url), build the matching provider (Supabase now, Neon when
the NeonProvisioner stores an `auth_url`), verify the JWT, then look the person up in the square's own `admins` table.

Security rule: the admin is matched by the auth user id (JWT `sub`) only, never by email. An email in a token is only as trustworthy as the
square project's sign-up settings; the id is stored by the provisioner when it creates the owner."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

import jwt
import psycopg
from sqlalchemy.orm import Session, sessionmaker

from app.platform.models import Square, SquareStatus
from app.platform.provisioning import to_libpq
from app.providers.auth import NeonAuthProvider, SupabaseAuthProvider
from app.shared.config import Settings
from app.shared.crypto import Encryptor
from app.shared.interfaces import AuthProvider


class SquareAuthError(Exception):
    """The square cannot authenticate anybody (unknown, not ready, no own auth project). `code` is stable, the text is safe to show."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SquareAdmin:
    id: str
    email: str
    name: str
    role: str


@dataclass(frozen=True)
class SquareIdentity:
    square_id: uuid.UUID
    sub: str
    email: str
    name: str
    admin: SquareAdmin | None  # None = a valid member of the square's auth project who is not an admin


def default_provider_factory(provider: str, secrets: dict[str, str]) -> AuthProvider:
    if provider == "neon" and secrets.get("auth_url"):
        return NeonAuthProvider(secrets["auth_url"])
    if provider == "supabase" and secrets.get("project_url"):
        return SupabaseAuthProvider(secrets["project_url"])
    raise SquareAuthError("no_auth", "This square has no auth project of its own")


def default_admin_lookup(connection_url: str, auth_user_id: str) -> SquareAdmin | None:
    """One short connection per call. Fine for tools and tests; the square API should pool connections instead."""
    with psycopg.connect(to_libpq(connection_url), connect_timeout=10, prepare_threshold=None) as conn:
        row = conn.execute("select id::text, email, name, role from admins where auth_user_id = %s", (auth_user_id,)).fetchone()
    return SquareAdmin(id=row[0], email=row[1], name=row[2], role=row[3]) if row else None


class SquareAuthVerifier:
    def __init__(
        self,
        session_factory: Callable[[], sessionmaker[Session]],
        settings: Settings,
        provider_factory: Callable[[str, dict[str, str]], AuthProvider] = default_provider_factory,
        admin_lookup: Callable[[str, str], SquareAdmin | None] = default_admin_lookup,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session_factory = session_factory
        self._enc = Encryptor(settings.fernet_key)
        self._ttl = float(settings.SQUARE_AUTH_CACHE_SECONDS)
        self._provider_factory, self._admin_lookup, self._clock = provider_factory, admin_lookup, clock
        self._cache: dict[uuid.UUID, tuple[float, AuthProvider, str]] = {}  # square id -> (expires, provider, decrypted connection url)
        self._lock = Lock()

    def _entry(self, square_id: uuid.UUID) -> tuple[AuthProvider, str]:
        now = self._clock()
        with self._lock:
            hit = self._cache.get(square_id)
            if hit and hit[0] > now:
                return hit[1], hit[2]
        with self._session_factory()() as db:
            sq = db.get(Square, square_id)
            if sq is None:
                raise SquareAuthError("not_found", "Square not found")
            if sq.status != SquareStatus.READY or not sq.db_connection:
                raise SquareAuthError("not_ready", "This square is not ready")
            secrets: dict[str, Any] = json.loads(self._enc.decrypt(sq.provider_secrets)) if sq.provider_secrets else {}
            provider = self._provider_factory(sq.provider or ("supabase" if sq.provider_project_ref else ""), secrets)
            connection = self._enc.decrypt(sq.db_connection)
        with self._lock:
            self._cache[square_id] = (now + self._ttl, provider, connection)  # keys and secrets can change: re-read after the TTL
        return provider, connection

    def forget(self, square_id: uuid.UUID) -> None:
        with self._lock:
            self._cache.pop(square_id, None)

    def authenticate(self, square_id: uuid.UUID, token: str) -> SquareIdentity | None:
        """The identity behind a token issued by this square's own auth project, or None for an invalid or expired token."""
        provider, connection = self._entry(square_id)
        try:
            claims = provider.verify(token)
        except jwt.PyJWTError:
            return None
        admin = self._admin_lookup(connection, claims["sub"])
        return SquareIdentity(square_id=square_id, sub=claims["sub"], email=claims.get("email", ""), name=claims.get("name", ""), admin=admin)
