"""A served square's emails, reports and order numbers carry the square's own name, domain and short name, never BCA's (rootsquares W6-R40)."""

import re
from types import SimpleNamespace

from flask import g

from app import create_app
from app.common.site import order_prefix, site_domain, site_name
from app.tenancy import Tenant

SQUARE = Tenant(
    slug="first-org",
    name="First Org & Friends",
    theme_id="paper-brick",
    domain="first-org.rootsquares.com",
    db_url="sqlite://",
    auth_provider="supabase",
    auth_url="https://a.supabase.co",
    auth_public_key="pk",
)


def _app():
    return create_app("testing")


def test_without_a_served_square_the_values_are_bca_oslos_own_defaults():
    app = _app()
    with app.test_request_context():
        assert (site_name(), site_domain(), order_prefix()) == ("BCA Oslo", "localhost", "BCA")
    assert site_name() == "BCA Oslo"  # also outside any request (scripts)


def test_a_served_square_gives_its_own_name_domain_and_order_prefix():
    app = _app()
    with app.test_request_context():
        g.tenant = SQUARE
        assert site_name() == "First Org & Friends"
        assert site_domain() == "first-org.rootsquares.com"
        assert order_prefix() == "FIRS"


def test_emails_of_a_served_square_carry_its_name_and_no_bca_branding():
    from app.email.templates import render_newsletter_subscribed_email, render_order_received_email

    app = _app()
    with app.test_request_context():
        g.tenant = SQUARE
        html, text, attachments = render_newsletter_subscribed_email(unsubscribe_url="https://x.example/u")
        item = SimpleNamespace(ticket_type=SimpleNamespace(name="Adult"), quantity=1, subtotal=10000)
        order = SimpleNamespace(customer_name="Priya", order_number="FIRS-1", items=[item], total_amount=10000)
        order_html, order_text, _ = render_order_received_email(order=order, event=None, order_url="https://x.example/o", vipps_number="54321")
    for body in (html, text, order_html, order_text):
        body = re.sub(r"data:[^\"')]*", "", body)  # the embedded fonts are base64 and can contain any letters
        assert "BCA" not in body and "Bengali" not in body and "বঙ্গীয়" not in body
    assert "First Org &amp; Friends" in html  # escaped in HTML
    assert "First Org & Friends" in text
    assert attachments[0]["filename"] == "logo.png" and bytes(attachments[0]["content"])[:4] == b"\x89PNG"
