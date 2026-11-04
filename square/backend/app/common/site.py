"""The identity of the site that is being served: its name, its domain and the prefix of its order numbers (rootsquares W6-R40).

bca-oslo wrote "BCA Oslo" into every email, the PDF report and the order numbers. A served square (app/tenancy.py) has its own name and
domain; without one (single-tenant mode, tests) the values come from the config, defaulting to bca-oslo's own.
"""

import html
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app, has_app_context

from app.common.phone import PhoneRule, phone_rule
from app.tenancy import current_tenant


def _config(key: str, default: str) -> str:
    return current_app.config.get(key, default) if has_app_context() else default  # the email builders are also used outside a request (tests, scripts)


def site_name() -> str:
    tenant = current_tenant() if has_app_context() else None
    return tenant.name if tenant is not None else _config("SITE_NAME", "BCA Oslo")


def site_name_html() -> str:
    return html.escape(site_name())


def site_theme_id() -> str:
    """The theme of the served square (chosen on the platform), else SITE_THEME (single tenant, default paper-brick): its colours reach the emails (W13-R29)."""
    tenant = current_tenant() if has_app_context() else None
    return tenant.theme_id if tenant is not None else _config("SITE_THEME", "paper-brick")


def site_domain() -> str:
    """Used in calendar UIDs: the square's own domain, else SITE_DOMAIN (single tenant)."""
    tenant = current_tenant() if has_app_context() else None
    return tenant.domain if tenant is not None and tenant.domain else _config("SITE_DOMAIN", "localhost")


def site_currency() -> str:
    """The currency of the served square (chosen when it was created), else SITE_CURRENCY (single tenant, default NOK)."""
    tenant = current_tenant() if has_app_context() else None
    return tenant.currency if tenant is not None else _config("SITE_CURRENCY", "NOK")


def site_logo_url() -> str:
    """The square's uploaded logo (a web address), or empty: then the letter mark is used (platform squares.logo_url, W6-R53)."""
    tenant = current_tenant()
    return (tenant.logo_url or tenant.logo_dark_url) if tenant is not None else ""


def site_phone_rule() -> PhoneRule:
    """The phone number rule of the served square (its country, chosen when it was created), else SITE_PHONE_COUNTRY (single tenant, default NO)."""
    tenant = current_tenant()
    return phone_rule(tenant.phone_country if tenant is not None else current_app.config.get("SITE_PHONE_COUNTRY", "NO"))


def site_timezone() -> ZoneInfo:
    """The square's own time zone (site_settings.timezone, set by its admin), UTC if the stored name is unusable."""
    from app.settings.models import get_site_settings

    try:
        return ZoneInfo(get_site_settings().timezone)
    except (ValueError, ZoneInfoNotFoundError, OSError):
        return ZoneInfo("UTC")


def order_prefix() -> str:
    """The letters in front of an order number: the square's short name (up to 4 letters or digits), else SITE_ORDER_PREFIX (default BCA)."""
    tenant = current_tenant() if has_app_context() else None
    if tenant is not None:
        return re.sub(r"[^A-Z0-9]", "", tenant.slug.upper())[:4] or "SQ"
    return _config("SITE_ORDER_PREFIX", "BCA")
