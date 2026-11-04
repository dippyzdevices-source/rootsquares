import jwt
from jwt import PyJWKClient
from urllib.parse import urlparse

_jwks_client: PyJWKClient | None = None
_jwks_client_url: str | None = None


def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    global _jwks_client, _jwks_client_url
    if _jwks_client is None or _jwks_client_url != jwks_url:
        _jwks_client = PyJWKClient(jwks_url)
        _jwks_client_url = jwks_url
    return _jwks_client


def verify_supabase_token(token: str, supabase_url: str) -> dict:
    """Verify a Supabase-issued JWT and return its claims.

    Raises jwt.PyJWTError (or a subclass) if the token is invalid, expired,
    has a bad signature, or has the wrong audience or issuer.

    rootsquares W6-R37 (hardcodings 8): the issuer is checked too. bca-oslo checked the audience only, because it could not see a real token's
    `iss`; the platform confirmed it on a real square token: it is `<project url>/auth/v1`. A token of one square's sign-in project is
    therefore refused by every other square, even if a key were shared. (A custom Supabase auth domain would issue its own address.)
    """
    base = supabase_url.rstrip("/")
    jwks_url = f"{base}/auth/v1/.well-known/jwks.json"
    client = _get_jwks_client(jwks_url)
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256"],
        audience="authenticated",
        issuer=f"{base}/auth/v1",
    )


def verify_neon_token(token: str, neon_auth_url: str) -> dict:
    """Verify a Neon Auth (Managed Better Auth) JWT and return its claims.

    Raises jwt.PyJWTError (or a subclass) if the token is invalid, expired,
    has a bad signature, or has the wrong issuer or audience. Neon Auth signs
    with EdDSA (Ed25519), unlike Supabase's ES256 — see docs/superpowers/specs/
    2026-09-23-dual-provider-auth-design.md for the sourcing. The issuer is the
    Neon Auth URL's own origin (scheme + host), not the full path, per Neon's
    own docs example (an auth URL of https://ep-xx.aws.neon.tech/neondb/auth
    has issuer https://ep-xx.aws.neon.tech). Better Auth's JWT plugin always
    sets `aud`, defaulting to the same value as `iss` — passing no `audience`
    to jwt.decode() would make PyJWT skip that check entirely, so `audience`
    is set to the same issuer value here.
    """
    jwks_url = f"{neon_auth_url}/.well-known/jwks.json"
    client = _get_jwks_client(jwks_url)
    signing_key = client.get_signing_key_from_jwt(token)
    parsed = urlparse(neon_auth_url)
    issuer = f"{parsed.scheme}://{parsed.netloc}"
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["EdDSA"],
        issuer=issuer,
        audience=issuer,
    )
