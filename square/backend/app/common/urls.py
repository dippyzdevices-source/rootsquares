from flask import current_app, has_request_context, request

from app.tenancy import current_tenant


def frontend_base_url() -> str:
    """The one public site URL to put in links (emails, sitemap).

    `FRONTEND_ORIGIN` is a comma-separated CORS allowlist (see `app/__init__.py`), so it must
    never be interpolated into a link as-is — only its first entry is the canonical origin.

    A served square (rootsquares W6-R43) has its own address: links point at the host the request came in on (first-org.rootsquares.com, a custom
    domain, or first-org.localhost:5274 while developing), never at another square's or at bca-oslo's.
    """
    tenant = current_tenant()
    if tenant is not None:
        if has_request_context():
            return request.host_url.rstrip("/")
        return f"https://{tenant.domain}" if tenant.domain else ""  # a background job: no request, so the square's own domain
    origins = [o.strip() for o in current_app.config.get("FRONTEND_ORIGIN", "").split(",") if o.strip()]
    return origins[0].rstrip("/") if origins else ""
