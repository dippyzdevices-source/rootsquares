"""Auth settings of a square's own Supabase project, changed through the Management API (ADR 028). Google sign-in: the OAuth client is the
platform's (GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET); every square project has its own callback URL, which an admin must add to that
client in Google Cloud Console first (not possible through an API). `flask enable-google <slug>` does the rest."""

from __future__ import annotations

import httpx

from app.platform.provisioning import SupabaseProvisioner

API = "https://api.supabase.com"


def callback_url(project_ref: str) -> str:
    """The redirect URI to add under 'Authorised redirect URIs' of the Google OAuth client."""
    return f"https://{project_ref}.supabase.co/auth/v1/callback"


def neon_callback_url(auth_url: str) -> str:
    """The redirect URI to add under 'Authorised redirect URIs' of the Google OAuth client for a square at Neon."""
    return f"{auth_url.rstrip('/')}/callback/google"


def trusted_addresses(slug: str, domain_suffix: str, extra: list[str]) -> list[str]:
    """The square's own address plus the development hosts, as plain addresses (Neon wants no `/**` pattern)."""
    return [f"https://{slug}.{domain_suffix}", *(u.replace("{slug}", slug).removesuffix("/**") for u in extra)]


def set_redirects(access_token: str, project_ref: str, site_url: str, extra: list[str], client: httpx.Client | None = None) -> str:
    """Set the square project's Site URL and the redirect URLs that sign-in may return to (the square's own address plus `extra`). Returns the list."""
    allow = ",".join([f"{site_url}/**", *extra])
    r = (client or httpx).patch(
        f"{API}/v1/projects/{project_ref}/config/auth",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"site_url": site_url, "uri_allow_list": allow},
        timeout=30.0,
    )
    SupabaseProvisioner._check(r, f"PATCH /v1/projects/{project_ref}/config/auth")
    return allow


def set_google_login(access_token: str, project_ref: str, client_id: str, client_secret: str, enabled: bool, client: httpx.Client | None = None) -> None:
    """Switch Google sign-in on (with the platform's OAuth client) or off for one square project."""
    body: dict[str, object] = {"external_google_enabled": enabled}
    if enabled:
        body.update(external_google_client_id=client_id, external_google_secret=client_secret)
    r = (client or httpx).patch(f"{API}/v1/projects/{project_ref}/config/auth", headers={"Authorization": f"Bearer {access_token}"}, json=body, timeout=30.0)
    SupabaseProvisioner._check(r, f"PATCH /v1/projects/{project_ref}/config/auth")
