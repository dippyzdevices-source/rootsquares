from abc import ABC, abstractmethod

from flask import current_app

from app.auth.jwt_verification import verify_neon_token, verify_supabase_token
from app.tenancy import current_tenant


def _auth_url() -> str:
    """The sign-in project to check tokens against: the served square's own (rootsquares W6-R26), else the server-wide AUTH_URL as in bca-oslo."""
    tenant = current_tenant()
    return tenant.auth_url if tenant is not None and tenant.auth_url else current_app.config["AUTH_URL"]


class AuthProvider(ABC):
    name: str

    @abstractmethod
    def verify(self, token: str) -> dict:
        """Returns {"sub": str, "email": str}. Raises jwt.PyJWTError on any invalid token."""


class SupabaseAuthProvider(AuthProvider):
    name = "supabase"

    def verify(self, token: str) -> dict:
        claims = verify_supabase_token(token, _auth_url())
        return {"sub": claims["sub"], "email": claims.get("email", "")}


class NeonAuthProvider(AuthProvider):
    name = "neon"

    def verify(self, token: str) -> dict:
        claims = verify_neon_token(token, _auth_url())
        return {"sub": claims["sub"], "email": claims.get("email", "")}


def get_auth_provider() -> AuthProvider:
    tenant = current_tenant()
    provider_name = tenant.auth_provider if tenant is not None else current_app.config["AUTH_PROVIDER"]
    if provider_name == "supabase":
        return SupabaseAuthProvider()
    if provider_name == "neon":
        return NeonAuthProvider()
    raise ValueError(f"Unrecognized AUTH_PROVIDER: {provider_name!r}")
