"""The optional modules of a square (rootsquares W8-R9): a module that is off answers 404, a square without a stored choice has every module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text

from app import create_app
from app.config import TestingConfig
from app.modules import BLUEPRINT_MODULE, CORE_KEYS, MODULE_KEYS, core_off_of, parse_modules
from tests.test_tenancy import _enc, _square_db


@pytest.fixture
def server(tmp_path: Path):
    url = _square_db(tmp_path / "a.db", "a@example.org")
    platform_url = f"sqlite:///{tmp_path / 'platform.db'}"
    platform = create_engine(platform_url)
    with platform.begin() as conn:
        conn.execute(
            text("create table squares (slug text, name text, theme_id text, domain text, status text, suspended_at text, db_connection text, provider_secrets text, currency text, phone_country text, logo_url text, logo_dark_url text, modules text)")
        )
        for slug, modules in (("few", json.dumps(["news", "gallery"])), ("none", json.dumps([])), ("all", None), ("novol", json.dumps([k for k in MODULE_KEYS if k != "volunteering"]))):
            conn.execute(
                text("insert into squares values (:slug, :name, 'paper-brick', :domain, 'ready', null, :url, :sec, null, null, null, null, :modules)"),
                {"slug": slug, "name": slug, "domain": f"{slug}.rootsquares.com", "url": _enc(url), "sec": _enc(json.dumps({})), "modules": modules},
            )
    platform.dispose()
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", platform_url):
        return create_app("testing")


def _get(app, slug: str, path: str):
    return app.test_client().get(path, base_url=f"http://{slug}.localhost")


def test_a_module_that_is_off_answers_404_and_one_that_is_on_works(server) -> None:
    assert _get(server, "few", "/api/events").status_code == 404
    assert _get(server, "few", "/api/donations/config").status_code == 404  # Donations (wave 14)
    assert _get(server, "all", "/api/donations/config").status_code == 200
    assert _get(server, "few", "/api/sponsors").status_code == 404
    assert _get(server, "few", "/api/news").status_code == 200
    assert _get(server, "few", "/api/gallery/albums").status_code == 200


def test_core_stays_on_whatever_is_chosen(server) -> None:
    for path in ("/api/settings", "/api/health", "/api/lookups/contact_reason"):
        assert _get(server, "none", path).status_code != 404 or path.startswith("/api/lookups")  # lookups: 404 only for an unknown list
    assert _get(server, "none", "/api/settings").status_code == 200
    assert _get(server, "none", "/api/news").status_code == 404


def test_no_stored_choice_means_every_module(server) -> None:
    assert _get(server, "all", "/api/events").status_code == 200
    assert _get(server, "all", "/api/square/config").get_json()["modules"] == list(MODULE_KEYS)


def test_config_tells_the_frontend_what_is_on(server) -> None:
    assert _get(server, "few", "/api/square/config").get_json()["modules"] == ["gallery", "news"]
    assert _get(server, "none", "/api/square/config").get_json()["modules"] == []


def test_registry_is_consistent() -> None:
    assert set(BLUEPRINT_MODULE.values()) <= set(MODULE_KEYS) | set(CORE_KEYS)
    assert parse_modules(None) is None and parse_modules("not json") is None
    assert parse_modules('["news", "nope", "events"]') == ("events", "news")  # unknown dropped, catalogue order


def test_every_mapped_blueprint_exists() -> None:
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", ""):
        app = create_app("testing")
    assert set(BLUEPRINT_MODULE) <= set(app.blueprints), set(BLUEPRINT_MODULE) - set(app.blueprints)


# ---- Testimonials (W8-R10): the first module split out completely


def test_testimonials_off_has_no_api_and_no_list(server) -> None:
    assert _get(server, "none", "/api/testimonials").status_code == 404
    assert _get(server, "none", "/api/lookups/testimonial_status").status_code == 404  # the review-status list belongs to the module
    assert _get(server, "all", "/api/testimonials").status_code == 200
    assert _get(server, "all", "/api/lookups/testimonial_status").status_code == 200


def test_admin_lists_leave_out_the_list_of_a_module_that_is_off(server) -> None:
    from flask import g

    from app.lookups.service import list_available
    from app.tenancy import Tenant

    def tenant(modules):
        return Tenant(slug="x", name="X", theme_id="paper-brick", domain="x", db_url="", auth_provider="supabase", auth_url="", auth_public_key="", modules=modules)

    with server.test_request_context("/"):
        g.tenant = tenant(("news",))
        assert not list_available("testimonial_status") and list_available("contact_reason")
    with server.test_request_context("/"):
        g.tenant = tenant(("testimonials",))
        assert list_available("testimonial_status") and not list_available("no_such_list")
    with server.test_request_context("/"):
        g.tenant = tenant(None)  # no stored choice: every module
        assert list_available("testimonial_status")


# ---- Sponsors (W8-R11)


def test_sponsors_off_has_no_api_public_or_admin(server) -> None:
    assert _get(server, "none", "/api/sponsors").status_code == 404
    assert _get(server, "none", "/api/admin/sponsors").status_code == 404  # not even a sign-in question: the page does not exist
    assert _get(server, "all", "/api/sponsors").status_code == 200
    assert _get(server, "all", "/api/admin/sponsors").status_code in (401, 403)


# ---- Committee (W8-R12)


def test_committee_off_has_no_api_and_no_roles_list(server) -> None:
    assert _get(server, "none", "/api/committee").status_code == 404
    assert _get(server, "none", "/api/admin/committee").status_code == 404
    assert _get(server, "none", "/api/lookups/committee_role").status_code == 404
    assert _get(server, "all", "/api/committee").status_code == 200
    assert _get(server, "all", "/api/lookups/committee_role").status_code == 200


# ---- Founders (W8-R13)


def test_founders_off_has_no_api_public_or_admin(server) -> None:
    assert _get(server, "none", "/api/founders").status_code == 404
    assert _get(server, "none", "/api/admin/founders").status_code == 404
    assert _get(server, "all", "/api/founders").status_code == 200


# ---- Magazines (W8-R14)


def test_magazines_off_has_no_api_public_or_admin(server) -> None:
    assert _get(server, "none", "/api/magazines").status_code == 404
    assert _get(server, "none", "/api/admin/magazines").status_code == 404
    assert _get(server, "few", "/api/magazines").status_code == 404  # News on, Magazines off: articles stay, magazines go
    assert _get(server, "few", "/api/news").status_code == 200
    assert _get(server, "all", "/api/magazines").status_code == 200


# ---- Newsletter (W8-R15)


def test_newsletter_off_has_no_api_public_or_admin_and_no_status_list(server) -> None:
    assert _get(server, "none", "/api/newsletter/subscribe").status_code == 404  # the whole blueprint is gone (a GET would otherwise be 405)
    assert _get(server, "none", "/api/admin/newsletter/subscribers").status_code == 404
    assert _get(server, "none", "/api/lookups/newsletter_status").status_code == 404
    assert _get(server, "few", "/api/newsletter/subscribe").status_code == 404
    assert _get(server, "all", "/api/newsletter/subscribe").status_code == 405
    assert _get(server, "all", "/api/lookups/newsletter_status").status_code == 200


def test_a_job_of_a_module_skips_the_squares_without_it() -> None:
    from types import SimpleNamespace

    from app.jobs.squares import for_each_square

    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", ""):
        app = create_app("testing")
    tenants = [SimpleNamespace(slug="a", modules=("newsletter", "news")), SimpleNamespace(slug="b", modules=("news",)), SimpleNamespace(slug="c", modules=None)]
    app.extensions["tenancy"] = SimpleNamespace(all_tenants=lambda: tenants)
    from flask import g

    ran = for_each_square(app, lambda: g.tenant.slug, module="newsletter")
    assert ran == ["a", "c"]  # b has no Newsletter; c has no stored choice, so every module
    assert for_each_square(app, lambda: g.tenant.slug) == ["a", "b", "c"]  # a job of no module runs everywhere


# ---- News (W8-R16)


def test_news_off_has_no_api_no_lists_and_is_not_in_the_sitemap(server) -> None:
    assert _get(server, "none", "/api/news").status_code == 404
    assert _get(server, "none", "/api/admin/news").status_code == 404
    assert _get(server, "none", "/api/lookups/news_category").status_code == 404
    assert _get(server, "none", "/api/lookups/news_status").status_code == 404
    assert _get(server, "all", "/api/lookups/news_category").status_code == 200
    none_map = _get(server, "none", "/sitemap.xml").get_data(as_text=True)
    few_map = _get(server, "few", "/sitemap.xml").get_data(as_text=True)
    all_map = _get(server, "all", "/sitemap.xml").get_data(as_text=True)
    assert "/news" not in none_map and "/gallery" not in none_map and "/events" not in none_map and "/contact" in none_map
    assert "/news" in few_map and "/gallery" in few_map and "/events" not in few_map
    assert "/news" in all_map and "/events" in all_map


# ---- Gallery (W8-R17)


def test_gallery_off_has_no_api_and_no_category_list(server) -> None:
    assert _get(server, "none", "/api/gallery/albums").status_code == 404
    assert _get(server, "none", "/api/admin/gallery/albums").status_code == 404
    assert _get(server, "none", "/api/lookups/album_category").status_code == 404
    assert _get(server, "all", "/api/gallery/albums").status_code == 200
    assert _get(server, "all", "/api/lookups/album_category").status_code == 200


def test_welcome_email_points_only_at_what_the_square_has() -> None:
    from app.email.templates import render_welcome_email

    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", ""):
        app = create_app("testing")
    with app.app_context():
        everything = render_welcome_email(dashboard_url="https://x/member", events_url="https://x/events", gallery_url="https://x/gallery")[1]
        no_gallery = render_welcome_email(dashboard_url="https://x/member", events_url="https://x/events", gallery_url=None)[1]
        dashboard_only = render_welcome_email(dashboard_url="https://x/member")[1]
    assert "https://x/gallery" in everything and "https://x/events" in everything
    assert "https://x/gallery" not in no_gallery and "https://x/events" in no_gallery
    assert "https://x/events" not in dashboard_only and "https://x/member" in dashboard_only


# ---- Members and Memberships (W8-R19)


def test_memberships_off_has_no_member_apis_and_no_member_lists(server) -> None:
    for path in ("/api/memberships/types", "/api/admin/members", "/api/admin/membership-types", "/api/admin/imports/members"):
        assert _get(server, "none", path).status_code == 404, path
    assert _get(server, "none", "/api/lookups/membership_status").status_code == 404
    assert _get(server, "none", "/api/lookups/relationship_type").status_code == 404
    assert _get(server, "all", "/api/memberships/types").status_code == 200
    assert _get(server, "all", "/api/lookups/membership_status").status_code == 200


def test_welcome_email_dashboard_line_names_only_what_the_square_has() -> None:
    from flask import g

    from app.auth.emails import _dashboard_text
    from app.tenancy import Tenant

    def tenant(modules):
        return Tenant(slug="x", name="X", theme_id="paper-brick", domain="x", db_url="", auth_provider="supabase", auth_url="", auth_public_key="", modules=modules)

    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", ""):
        app = create_app("testing")
    cases = {("memberships", "tickets"): "Update your details, request a membership and find your tickets.", ("tickets",): "Update your details and find your tickets.", ("memberships",): "Update your details and request a membership.", (): "Update your details."}
    for modules, expected in cases.items():
        with app.test_request_context("/"):
            g.tenant = tenant(modules)
            assert _dashboard_text() == expected


# ---- Coupons (W8-R21)


def test_coupons_off_has_no_coupon_api(server) -> None:
    assert _get(server, "none", "/api/coupons/validate").status_code == 404
    assert _get(server, "none", "/api/admin/events/1/coupons").status_code == 404
    assert _get(server, "few", "/api/coupons/validate").status_code == 404
    assert _get(server, "all", "/api/coupons/validate").status_code != 404  # exists (a GET without an event is a 400)


# ---- Check-in (W8-R22)


def test_checkin_off_has_no_scan_api(server) -> None:
    assert _get(server, "none", "/api/admin/checkin/scan").status_code == 404
    assert _get(server, "few", "/api/admin/checkin/scan").status_code == 404
    assert _get(server, "all", "/api/admin/checkin/scan").status_code != 404


# ---- Volunteering (W8-R23)


def test_volunteering_off_has_no_task_api_but_the_rest_of_events_and_the_portal_stay(server) -> None:
    assert _get(server, "novol", "/api/members/me/task-assignments").status_code == 404
    assert _get(server, "novol", "/api/admin/events/1/task-assignments").status_code == 404  # a wrong method used to say 405
    assert _get(server, "novol", "/api/lookups/task_category").status_code == 404
    assert _get(server, "novol", "/api/events").status_code == 200  # events and the member portal stay
    assert _get(server, "novol", "/api/members/me").status_code in (401, 403)  # asks for a sign-in: it exists
    assert _get(server, "all", "/api/members/me/task-assignments").status_code in (401, 403)
    assert _get(server, "all", "/api/admin/events/1/task-assignments").status_code == 405
    assert _get(server, "all", "/api/lookups/task_category").status_code == 200


def test_every_endpoint_of_the_endpoint_map_exists() -> None:
    from app.modules import ENDPOINT_MODULE

    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", ""):
        app = create_app("testing")
    assert set(ENDPOINT_MODULE) <= set(app.view_functions), set(ENDPOINT_MODULE) - set(app.view_functions)


# ---- Accounting (W8-R24)


def test_accounting_off_has_no_accounting_api_and_no_expense_list(server) -> None:
    assert _get(server, "none", "/api/admin/accounting/events/1").status_code == 404
    assert _get(server, "few", "/api/admin/accounting/events/1").status_code == 404
    assert _get(server, "all", "/api/admin/accounting/events/1").status_code in (401, 403)  # exists: asks for a sign-in
    assert _get(server, "none", "/api/lookups/expense_category").status_code == 404
    assert _get(server, "all", "/api/lookups/expense_category").status_code == 200


# ---- The Lists page follows the modules (W8-R25)


def test_lists_show_nothing_of_a_module_that_is_off() -> None:
    from app.extensions import db
    from app.lookups.registry import LOOKUP_LISTS
    from app.lookups.service import list_available, lookup_items

    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", ""):
        app = create_app("testing")
    with app.app_context():
        db.create_all()

    def values(modules, key):
        with app.app_context(), patch("app.modules.enabled_modules", return_value=modules):
            return [i["value"] for i in lookup_items(key)] if list_available(key) else None

    # every value and list named in the registry belongs to a real module
    for spec in LOOKUP_LISTS.values():
        assert spec.get("module") in (None, *MODULE_KEYS)
        assert set(spec.get("value_modules", {}).values()) <= set(MODULE_KEYS)

    assert values((), "audit_action") == ["user_role_changed", "settings_updated", "lookup_value_changed"]  # only the core actions
    assert "newsletter_sent" in values(("newsletter",), "audit_action") and "order_marked_paid" not in values(("newsletter",), "audit_action")
    assert values((), "user_role") == ["member", "admin"] and "volunteer" in values(("checkin",), "user_role")
    assert values((), "payment_type") is None  # the list belongs to Payments
    assert values(("payments",), "payment_type") == ["vipps_test"] and values(("payments", "tickets"), "payment_type") == ["event_ticket", "vipps_test"]
    assert values((), "ticket_status") is None and values(("tickets",), "ticket_status") is not None
    assert values((), "event_type") is None and values(("events",), "event_type") is not None
    assert values((), "payment_status") is None
    assert values((), "contact_reason") is not None  # core lists stay


# ---- Events (W8-R28)


def test_events_off_has_no_events_api_no_type_list_and_nothing_in_the_sitemap(server) -> None:
    assert _get(server, "none", "/api/events").status_code == 404
    assert _get(server, "none", "/api/admin/events").status_code == 404
    assert _get(server, "none", "/api/lookups/event_type").status_code == 404
    assert "/events" not in _get(server, "none", "/sitemap.xml").get_data(as_text=True)
    assert _get(server, "all", "/api/events").status_code == 200


# ---- Tickets and orders (W8-R29)


def test_tickets_off_has_no_ticket_or_order_api(server) -> None:
    for path in ("/api/tickets/types", "/api/orders", "/api/admin/orders", "/api/admin/tickets", "/api/admin/events/1/ticket-types"):
        assert _get(server, "none", path).status_code == 404, path
    assert _get(server, "few", "/api/orders").status_code == 404
    assert _get(server, "none", "/api/lookups/ticket_status").status_code == 404
    assert _get(server, "none", "/api/lookups/ticket_age_category").status_code == 404
    assert _get(server, "all", "/api/lookups/ticket_status").status_code == 200


# ---- Payments (W8-R30)


def test_payments_off_has_no_payment_api_and_no_vipps_number(server) -> None:
    for path in ("/api/admin/payments", "/api/payments/vipps-app", "/api/webhooks/vipps"):
        assert _get(server, "none", path).status_code == 404, path
    assert _get(server, "none", "/api/lookups/payment_status").status_code == 404
    assert _get(server, "none", "/api/settings").get_json()["vipps_number"] is None


def test_vipps_qr_is_only_available_with_payments() -> None:
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.settings.models import vipps_qr_available

    settings = SimpleNamespace(vipps_qr_enabled=True, vipps_number="12345")
    with patch("app.modules.enabled_modules", return_value=("payments",)):
        assert vipps_qr_available(settings) is True  # type: ignore[arg-type]
    with patch("app.modules.enabled_modules", return_value=()):
        assert vipps_qr_available(settings) is False  # type: ignore[arg-type]


def test_a_custom_package_can_leave_always_on_parts_out():
    assert core_off_of("custom", json.dumps(["news", "home", "about"])) == ("contact", "legal", "login", "account", "admin", "settings", "media")
    assert core_off_of("custom", json.dumps(["news"])) == ()  # a list saved before: nothing is taken away
    assert core_off_of("square", json.dumps(["home"])) == ()  # only a custom package leaves parts out
    assert core_off_of("custom", None) == ()
