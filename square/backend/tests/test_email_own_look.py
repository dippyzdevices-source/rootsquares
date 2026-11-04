"""A square's e-mails wear the owner's own colours and the corners of the chosen button and card shapes (W18-R51); nothing chosen means the e-mails as they were."""

import re
from pathlib import Path

from flask import g

from app import create_app
from app.email import own_look, templates
from app.tenancy import Tenant

ROOT = Path(__file__).resolve().parents[2]
KEYS = {"accent", "on_accent", "heading", "body", "muted", "panel", "card", "sunk", "border"}


def _tenant(theme: str = "pearl", overrides: dict | None = None) -> Tenant:
    return Tenant(
        slug="first-org", name="First Org", theme_id=theme, domain="first-org.rootsquares.com", db_url="sqlite://",
        auth_provider="supabase", auth_url="https://a.supabase.co", auth_public_key="pk", theme_overrides=overrides,
    )


def _html(render, overrides: dict | None, theme: str = "pearl") -> str:
    app = create_app("testing")
    with app.test_request_context():
        g.tenant = _tenant(theme, overrides)
        out = render()
    return next(part for part in out[:2] if "<html" in part.lower())


def _reset(overrides: dict | None = None, theme: str = "pearl") -> str:
    return _html(lambda: templates.render_password_reset_email(reset_url="https://x.test/r/1", expires_at="2026-10-14 12:00"), overrides, theme)


def _code(overrides: dict | None = None) -> str:
    return _html(lambda: templates.render_signup_code_email(code="123456", expires_at="2026-10-14 12:00"), overrides)


def test_without_a_choice_the_corners_and_colours_are_what_they_were() -> None:
    plain = _reset()
    assert plain.count("border-radius:8px") >= 2 and "border-radius:999px" not in plain
    assert "border-radius:8px" in _code()
    assert _reset({"fonts": "soft"}) == plain  # fonts, feel and the rest never reach e-mails


def test_the_owners_three_colours_become_the_email_colours() -> None:
    seeds = {"bg": "#f6f1e7", "ink": "#2b2a28", "acc": "#c2410c"}
    html = _reset({"colors": seeds})
    pal = own_look.palette(seeds, "pearl")
    assert set(pal) == KEYS and pal["accent"] in html and pal["heading"] in html
    assert pal["accent"] != "#A8422A" and "#A8422A" not in html


def test_the_derived_colours_are_readable_for_any_three_colours_and_for_a_theme_that_opens_dark() -> None:
    for seeds in (
        {"bg": "#f6f1e7", "ink": "#2b2a28", "acc": "#c2410c"}, {"bg": "#fff", "ink": "#ddd", "acc": "#eee"}, {"bg": "#101820", "ink": "#e8efe9", "acc": "#3ddc97"},
        {"bg": "#ffe9a8", "ink": "#ffe0a0", "acc": "#ffd400"},
    ):
        for theme in ("pearl", "mela-noir"):
            pal = own_look.palette(seeds, theme)
            assert set(pal) == KEYS and all(re.fullmatch(r"#[0-9A-F]{6}", v) for v in pal.values()), (seeds, theme)
            low = {k: v.lower() for k, v in pal.items()}
            assert own_look._contrast(low["on_accent"], low["accent"]) >= 4.5, (seeds, theme)
            for ground in ("panel", "card", "sunk"):
                assert own_look._contrast(low["heading"], low[ground]) >= 7 and own_look._contrast(low["body"], low[ground]) >= 4.5 and own_look._contrast(low["muted"], low[ground]) >= 4.5, (seeds, theme, ground)


def test_the_chosen_button_and_card_shapes_set_the_corners() -> None:
    pill = _reset({"shape": {"buttons": "pill"}})
    assert pill.count("border-radius:999px") >= 2
    assert "border-radius:0px" in _reset({"shape": {"buttons": "square"}})
    assert "border-radius:18px" in _code({"shape": {"cards": "rounded"}}) and "border-radius:0px" in _code({"shape": {"cards": "square"}})
    assert "border-radius:8px" in _code({"shape": {"buttons": "pill"}})  # cards keep their corner when only buttons were chosen
    assert "border-radius:8px" in _code({"shape": {"cards": "nonsense"}})  # an unknown id changes nothing


def test_a_damaged_look_changes_nothing() -> None:
    assert _reset({"colors": {"bg": "red", "ink": "#000", "acc": "#fff"}}) == _reset()
    assert own_look.colours() is None  # no served square


def test_the_button_corners_equal_the_site() -> None:
    source = (ROOT / "frontend/src/themes/shapes.ts").read_text(encoding="utf-8")
    found = re.search(r"BUTTON_SHAPES: Record<string, string> = \{([^}]*)\}", source)
    assert found
    site = {k: int(v) for k, v in re.findall(r"(\w+): '(\d+)px'", found.group(1))}
    assert site == own_look.BUTTON_RADIUS
