"""The optional modules of a square (rootsquares W8-R9, docs/reference/optional-modules.md; not in bca-oslo).

The owner chooses the modules on the platform (`squares.modules`); the tenancy lookup puts the list on the tenant. This file says which blueprints
(pages of the API) belong to which module and answers 404 for the ones whose module is off. A module that is off keeps its data. Core parts
(sign-in, settings, contact, media, ...) have no entry: they are always on. Without tenancy (single-tenant mode, tests, CLI) every module is on.

The keys and their order must match platform `backend/app/platform/modules.py` (a platform test checks it).
"""

from __future__ import annotations

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException, MethodNotAllowed

MODULE_KEYS = (
    "events",
    "payments",
    "tickets",
    "coupons",
    "checkin",
    "members",
    "memberships",
    "volunteering",
    "accounting",
    "gallery",
    "news",
    "magazines",
    "newsletter",
    "testimonials",
    "sponsors",
    "committee",
    "founders",
    "donations",
    "messages",
)

# The always-on parts (W19-R24, ADR 082). Every square has all of them except a CUSTOM package that leaves some out; the platform keeps the choice in
# `squares.custom_modules` (keys equal platform `modules.CORE_KEYS`; a test checks it). A part that is off answers like a module that is off: 404 for its API,
# no menu item, no link, no page. `settings`, `media` and `about`/`legal`/`home` have no API of their own here; the site hides their pages and links.
CORE_KEYS = ("home", "about", "contact", "legal", "login", "account", "admin", "settings", "media")

# Blueprint name -> module. Not listed = core (always on). Still core because they mix modules with core parts, to be split in the module's own step:
# `members` (the member portal: account, family, tickets), `admin_reports` (reports of members, orders and tickets), `admin_events` (also tickets and
# coupons settings), `admin_settings` and `settings`. Single addresses of those that belong to a module are listed in ENDPOINT_MODULE below.
BLUEPRINT_MODULE: dict[str, str] = {
    "events": "events",
    "admin_events": "events",
    "tickets": "tickets",
    "admin_tickets": "tickets",
    "admin_ticket_types": "tickets",
    "orders": "tickets",
    "admin_orders": "tickets",
    "coupons": "coupons",
    "admin_coupons": "coupons",
    "checkin": "checkin",
    "admin_payments": "payments",
    "admin_payment_providers": "payments",  # connect Vipps / Stripe with the square's own keys (W16-R4)
    "vipps_public": "payments",
    "vipps_webhooks": "payments",
    "stripe_public": "payments",
    "stripe_webhooks": "payments",
    "admin_members": "members",
    "admin_imports": "memberships",  # the Excel import creates memberships: it belongs to Memberships (W11-R24, ADR 044)
    "memberships": "memberships",
    "memberships_payment": "memberships",
    "membership_drive": "memberships",
    "membership_join": "memberships",  # join and pay from the Membership page (ported from bca-oslo, ffa0802)
    "admin_memberships": "memberships",
    "admin_membership_types": "memberships",
    "admin_membership_followup": "memberships",
    "admin_accounting": "accounting",
    "admin_contributions": "accounting",  # donations and sponsorships recorded for one event
    "event_support": "events",  # the Donate and Sponsor forms on an event page
    "gallery": "gallery",
    "admin_gallery": "gallery",
    "news": "news",
    "admin_news": "news",
    "magazines": "magazines",
    "admin_magazines": "magazines",
    "newsletter": "newsletter",
    "admin_newsletter": "newsletter",
    "testimonials": "testimonials",
    "admin_testimonials": "testimonials",
    "sponsors": "sponsors",
    "admin_sponsors": "sponsors",
    "committee": "committee",
    "admin_committee": "committee",
    "founders": "founders",
    "admin_founders": "founders",
    "donations": "donations",
    "admin_donations": "donations",
    "messages": "messages",
    "admin_messages": "messages",
    # Always-on parts that a custom package may leave out (W19-R24)
    "auth": "login",
    "contact": "contact",
    "members": "account",  # the member portal; the addresses of a module inside it are listed in ENDPOINT_MODULE
    "admin_audit": "admin",
    "admin_event_pass": "admin",
    "admin_lookups": "admin",
    "admin_reports": "admin",
    "admin_users": "admin",
}


# Single addresses that belong to a module although their blueprint is mixed (W8-R23). Checked before the blueprint: endpoint -> module.
ENDPOINT_MODULE: dict[str, str] = {
    "admin_events.admin_create_task_assignment": "volunteering",
    "admin_events.admin_update_task_assignment": "volunteering",
    "admin_events.admin_delete_task_assignment": "volunteering",
    "members.get_my_task_assignments": "volunteering",
}


def parse_modules(stored: object) -> tuple[str, ...] | None:
    """The platform stores a JSON list; nothing stored (a square made before modules existed) means every module (None)."""
    import json

    if stored is None or stored == "":
        return None
    try:
        data = json.loads(stored) if isinstance(stored, str) else stored
    except ValueError:
        return None
    return tuple(k for k in MODULE_KEYS if k in data) if isinstance(data, list) else None


def core_off_of(package: str, custom_raw: object) -> tuple[str, ...]:
    """The always-on parts a custom package leaves out. Any other package, and a custom list saved before this existed (it holds none of the parts), leave none out."""
    import json

    if package != "custom" or not custom_raw:
        return ()
    try:
        data = json.loads(custom_raw) if isinstance(custom_raw, str) else custom_raw
    except ValueError:
        return ()
    if not isinstance(data, list) or not any(k in data for k in CORE_KEYS):
        return ()
    return tuple(k for k in CORE_KEYS if k not in data)


def enabled_modules() -> tuple[str, ...]:
    tenant = g.get("tenant") if g else None
    chosen = getattr(tenant, "modules", None)
    return MODULE_KEYS if chosen is None else chosen


def module_enabled(key: str | None) -> bool:
    """Is this module on for the square being served? None (a core part) is always on."""
    if key is None:
        return True
    if key in CORE_KEYS:
        tenant = g.get("tenant") if g else None
        return key not in (getattr(tenant, "core_off", None) or ())
    return key in enabled_modules()


def init_modules(app: Flask) -> None:
    """Call after init_tenancy: a request to a blueprint whose module is off gets 404, as if the page did not exist."""

    def endpoint_of_request() -> str:
        if request.endpoint:
            return request.endpoint
        # A wrong method on a real address (a GET on a POST-only route) has no endpoint yet: find the address anyway, so that it too answers 404
        # when its module is off instead of 405 (which would tell that the page exists).
        error = request.routing_exception
        if isinstance(error, MethodNotAllowed) and error.valid_methods:
            try:
                rule, _ = app.url_map.bind_to_environ(request.environ).match(method=error.valid_methods[0], return_rule=True)
                return str(rule.endpoint)
            except HTTPException:
                return ""
        return ""

    @app.before_request
    def _module_guard():
        endpoint = endpoint_of_request()
        module = ENDPOINT_MODULE.get(endpoint) or BLUEPRINT_MODULE.get(endpoint.split(".")[0])
        if module is not None and not module_enabled(module):
            return jsonify({"error": "Not found"}), 404
        return None
