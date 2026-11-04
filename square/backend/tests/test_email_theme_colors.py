"""A square's e-mails take their colours from the square's theme (W13-R29); paper-brick, the original look, keeps exactly the colours they always had."""

import re

from flask import g

from app import create_app
from app.common.site import site_theme_id
from app.email import templates
from app.email.theme_palette import THEME_EMAIL_COLORS
from app.tenancy import Tenant

KEYS = {"accent", "on_accent", "heading", "body", "muted", "panel", "card", "sunk", "border"}
PAPER_BRICK = {
    "accent": "#A8422A", "on_accent": "#FDF8F1", "heading": "#4A3627", "body": "#6E5540", "muted": "#8A7359",
    "panel": "#F9F2E8", "card": "#FDF8F1", "sunk": "#F4EADC", "border": "#E0D0BA",
}


def _tenant(theme: str) -> Tenant:
    return Tenant(
        slug="first-org", name="First Org", theme_id=theme, domain="first-org.rootsquares.com", db_url="sqlite://",
        auth_provider="supabase", auth_url="https://a.supabase.co", auth_public_key="pk",
    )


def _reset_html(theme: str | None) -> str:
    app = create_app("testing")
    with app.test_request_context():
        if theme is not None:
            g.tenant = _tenant(theme)
        out = templates.render_password_reset_email(reset_url="https://x.test/r/1", expires_at="2026-10-14 12:00")
    return next(part for part in out[:2] if "<html" in part.lower())


def test_paper_brick_keeps_exactly_the_colours_its_emails_always_had():
    assert THEME_EMAIL_COLORS["paper-brick"] == PAPER_BRICK


def test_every_theme_has_a_full_palette_of_hex_colours():
    assert len(THEME_EMAIL_COLORS) == 56
    for theme, colours in THEME_EMAIL_COLORS.items():
        assert set(colours) == KEYS, theme
        assert all(re.fullmatch(r"#[0-9A-Fa-f]{6}", v) for v in colours.values()), theme


def test_a_square_without_a_theme_or_with_an_unknown_one_uses_the_paper_brick_colours():
    for html in (_reset_html(None), _reset_html("no-such-theme")):
        for key in ("accent", "heading", "body", "muted", "card", "sunk", "border"):
            assert PAPER_BRICK[key] in html, key


def test_a_squares_email_follows_its_theme_and_keeps_none_of_the_paper_brick_colours():
    colours = THEME_EMAIL_COLORS["stillwater"]
    html = _reset_html("stillwater")
    for key in ("accent", "heading", "body", "muted", "card", "sunk", "border"):
        assert colours[key] in html, key
    assert PAPER_BRICK["accent"] not in html and PAPER_BRICK["sunk"] not in html and PAPER_BRICK["heading"] not in html


def test_the_theme_id_of_the_served_square_is_read_when_the_email_is_made():
    app = create_app("testing")
    with app.test_request_context():
        assert site_theme_id() == "paper-brick"
        g.tenant = _tenant("stillwater")
        assert site_theme_id() == "stillwater"
