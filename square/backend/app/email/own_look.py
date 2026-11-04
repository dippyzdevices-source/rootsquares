"""What it is:   The owner's own look in a square's e-mails (rootsquares W18-R51, docs/plans/themes-starting-looks-plan.md extra 5).
What it does:   colours() makes the nine e-mail colours from the owner's three colours (page, text, accent) the way the site does, close to it but not identical (an e-mail is
                always light; a theme that opens dark gets its light side derived from the three); button_radius() and card_radius() give the corner of buttons and cards in px
                when the owner chose a shape for them (buttons: square 0, soft 8, rounded 14, pill 999; cards: square 0, soft 8, rounded 18), else the e-mail's own corner.
                Photo frames, edges, fonts and feel never reach e-mails (clients ignore most CSS). The look read is the live one of the served square (no season, no draft).
How to use:     app/email/templates.py calls _pal(), _btn_r() and _card_r(); without a served square, or without a choice, nothing changes.
How to run:     python -m pytest tests/test_email_own_look.py (from square/backend).
Read before:    app/email/theme_palette.py (the colours per theme), square/frontend/src/themes/deriveTokens.ts (the site's derivation).
Read after:     app/email/templates.py.
"""

import re

from flask import has_app_context

from app.tenancy import current_tenant

BUTTON_RADIUS = {"square": 0, "soft": 8, "rounded": 14, "pill": 999}  # equal to square/frontend/src/themes/shapes.ts (a test compares them)
CARD_RADIUS = {"square": 0, "soft": 8, "rounded": 18}
DARK_FIRST = ("mela-noir", "neon-cyan", "citrus-night", "mint-night")  # themes that open dark: their three colours describe the dark look
_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _full(value: str) -> str:
    v = value.lstrip("#")
    return "#" + ("".join(c * 2 for c in v) if len(v) == 3 else v).lower()


def _rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _hex(c: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(x))):02x}" for x in c)


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return _hex((ra[0] + (rb[0] - ra[0]) * t, ra[1] + (rb[1] - ra[1]) * t, ra[2] + (rb[2] - ra[2]) * t))


def _lum(h: str) -> float:
    def ch(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (ch(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    x, y = _lum(a), _lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def _fix(colour: str, grounds: list[str], need: float, toward: str) -> str:
    """The nearest shade of the colour (moving toward `toward`) that reaches `need` on every ground."""
    x, t = colour, 0.0
    while not all(_contrast(x, g) >= need for g in grounds) and t < 1:
        t += 0.02
        x = _mix(colour, toward, t)
    return x


def palette(seeds: dict[str, str], theme_id: str) -> dict[str, str]:
    """The nine e-mail colours (the keys of theme_palette.THEME_EMAIL_COLORS) from three hex colours: bg, ink, acc."""
    bg, ink, acc = _full(seeds["bg"]), _full(seeds["ink"]), _full(seeds["acc"])
    if theme_id in DARK_FIRST or _lum(bg) < 0.18:  # the three describe a dark look; an e-mail is light, so its light side is made from them (like the site does)
        bg, ink, acc = _mix(ink, "#ffffff", 0.9), _mix(bg, "#000000", 0.4), _mix(acc, "#000000", 0.25)
    card = _mix(bg, "#ffffff", 0.6)
    sunk = _mix(bg, ink, 0.07)
    grounds = [bg, card, sunk]
    heading = _fix(ink, grounds, 7, "#000000")
    body = _fix(_mix(heading, bg, 0.25), grounds, 4.5, heading)
    muted = _fix(_mix(heading, bg, 0.45), grounds, 4.5, heading)
    on_accent = "#ffffff" if _contrast("#ffffff", acc) >= _contrast("#111111", acc) else "#111111"
    toward = "#000000" if on_accent == "#ffffff" else "#ffffff"
    accent = _fix(acc, [on_accent], 4.5, toward) if _contrast(on_accent, acc) < 4.5 else acc
    return {
        "accent": accent.upper(), "on_accent": on_accent.upper(), "heading": heading.upper(), "body": body.upper(), "muted": muted.upper(),
        "panel": bg.upper(), "card": card.upper(), "sunk": sunk.upper(), "border": _mix(bg, heading, 0.16).upper(),
    }


def _look() -> dict:
    tenant = current_tenant() if has_app_context() else None
    look = tenant.theme_overrides if tenant is not None else None
    return look if isinstance(look, dict) else {}


def colours() -> dict[str, str] | None:
    """The e-mail colours of the owner's own three colours, or None (no served square, nothing chosen, or a value that is not a hex colour)."""
    seeds = _look().get("colors")
    if not isinstance(seeds, dict) or not all(isinstance(seeds.get(k), str) and _HEX.match(seeds[k]) for k in ("bg", "ink", "acc")):
        return None
    tenant = current_tenant()
    return palette(seeds, tenant.theme_id if tenant is not None else "")


def _radius(part: str, table: dict[str, int], default: int) -> int:
    shape = _look().get("shape")
    chosen = shape.get(part) if isinstance(shape, dict) else None
    return table.get(chosen, default) if isinstance(chosen, str) else default


def button_radius(default: int) -> int:
    return _radius("buttons", BUTTON_RADIUS, default)


def card_radius(default: int) -> int:
    return _radius("cards", CARD_RADIUS, default)
