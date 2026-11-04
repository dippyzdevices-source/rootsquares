"""Auth providers (ADR 028): verify a bearer JWT issued by Supabase Auth (local/test) or Neon Auth (production). Flask never sees a password
or OAuth token for these users, only the JWT the frontend obtained directly from the provider.

Adapted from the bca-oslo reference (backend/app/auth/providers.py, jwt_verification.py): same signing algorithms and claims, but the JWKS
client belongs to the provider instance (no module globals)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient

from app.shared.config import Settings


class _JwksProvider:
    name = ""

    def __init__(self, base_url: str, jwks_client: PyJWKClient | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._jwks = jwks_client or PyJWKClient(self._jwks_url)  # PyJWKClient caches the keys

    @property
    def _jwks_url(self) -> str:
        raise NotImplementedError

    def _decode(self, token: str, key: Any) -> dict[str, Any]:
        raise NotImplementedError

    def verify(self, token: str) -> dict[str, str]:
        claims = self._decode(token, self._jwks.get_signing_key_from_jwt(token).key)
        meta = claims.get("user_metadata") or {}
        name = claims.get("name") or meta.get("full_name") or meta.get("name") or ""
        return {"sub": str(claims["sub"]), "email": str(claims.get("email", "")), "name": str(name)}


class SupabaseAuthProvider(_JwksProvider):
    """Supabase Auth: ES256 tokens, keys at <project url>/auth/v1/.well-known/jwks.json, audience "authenticated", issuer <project url>/auth/v1
    (issuer confirmed on a real token of a square project, W5-R27). A project with a custom auth domain would issue its own domain instead."""

    name = "supabase"

    @property
    def _jwks_url(self) -> str:
        return f"{self._base_url}/auth/v1/.well-known/jwks.json"

    def _decode(self, token: str, key: Any) -> dict[str, Any]:
        return jwt.decode(token, key, algorithms=["ES256"], audience="authenticated", issuer=f"{self._base_url}/auth/v1")


class NeonAuthProvider(_JwksProvider):
    """Neon Auth (managed Better Auth): EdDSA tokens, keys at <auth url>/.well-known/jwks.json. Issuer and audience are the auth URL's origin."""

    name = "neon"

    @property
    def _jwks_url(self) -> str:
        return f"{self._base_url}/.well-known/jwks.json"

    def _decode(self, token: str, key: Any) -> dict[str, Any]:
        parsed = urlparse(self._base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return jwt.decode(token, key, algorithms=["EdDSA"], issuer=origin, audience=origin)


class FakeAuthProvider:
    """Tests: the token "fake:<sub>:<email>" is valid, anything else is not. No network."""

    name = "fake"

    def verify(self, token: str) -> dict[str, str]:
        parts = token.split(":", 2)
        if len(parts) != 3 or parts[0] != "fake" or not parts[1]:
            raise jwt.InvalidTokenError("not a fake token")
        return {"sub": parts[1], "email": parts[2], "name": ""}


def build_auth_provider(settings: Settings) -> SupabaseAuthProvider | NeonAuthProvider | None:
    """None = no provider configured (own cookie login only). Settings validation guarantees AUTH_URL when a provider is named."""
    if settings.AUTH_PROVIDER == "supabase":
        return SupabaseAuthProvider(settings.auth_url)
    if settings.AUTH_PROVIDER == "neon":
        return NeonAuthProvider(settings.auth_url)
    return None
