"""What it is:     The owner's own colours, fonts, spinners and shapes for a square, on top of its theme (rootsquares W18-R18, themes-dynamic-plan).
What it does:   Validates and stores `{"colors": {"bg", "ink", "acc"} | null, "fonts": "<pair id>" | null,
                "spinners": ["<spinner id>", ...] | null,
                "shape": {"buttons", "cards", "photos", "edges": "<option id>"} | null,
                "feel": {"mode", "switch", "density", "text", "motion", "divider": "<option id>"} | null,
                "colors_dark": {"bg", "ink", "acc"} | null,
                "type": {"display": {"f": "<Google family>"}, "body": {"f": "<Google family>"}, "accent": "<accent id>"} | null}`
                (spinners: W18-R28; shape: W18-R41; feel: W18-R44; type: W25-R63, the owner's own heading, body and accent fonts on top of the pair;
                a family must be in google_fonts.json, the server stores it with its category and weights so the square app never needs the catalogue);
                says which packages may use it (Square and above, decision W18-R14).
How to use:     parse(raw) -> clean dict or None (raises ValueError with a plain message); to_json / from_json for the column
                squares.theme_overrides; allowed(package).
How to run:     python -m pytest tests/test_theme_overrides.py (from backend/).
Read before:    docs/plans/themes-dynamic-plan.md, docs/reference/packages-and-features.md.
Read after:     the square app: square/frontend/src/themes/applyThemeOverrides.ts (applies it), fontPairs.ts and shapes.ts (the ids, kept equal by tests).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any

from werkzeug.security import generate_password_hash

from app.platform import plans
from app.platform.spinner_ids import SPINNER_IDS

# Keep equal to square/frontend/src/themes/fontPairs.ts (tests/test_theme_overrides.py reads that file and compares).
FONT_PAIR_IDS: tuple[str, ...] = (
    "classic", "friendly", "editorial", "elegant", "clean", "dramatic",
    "warm", "soft", "bold", "playful", "contemporary", "scholarly", "sturdy", "newsroom",
    "display", "gallery", "futuristic", "fashion", "sansoverserif", "quirky", "refined", "upbeat", "literary",
)  # fmt: skip
COLOR_KEYS: tuple[str, ...] = ("bg", "ink", "acc")
# Keep equal to the option lists of square/frontend/src/themes/shapes.ts (a test reads that file and compares).
SHAPE_OPTIONS: dict[str, tuple[str, ...]] = {
    "buttons": ("square", "soft", "rounded", "pill"),
    "cards": ("square", "soft", "rounded"),
    "photos": ("square", "soft", "rounded", "arch", "circle"),
    "edges": ("flat", "line", "strong", "shadow"),
}
# Keep equal to FEEL_OPTIONS of square/frontend/src/themes/feel.ts (a test reads that file and compares).
FEEL_OPTIONS: dict[str, tuple[str, ...]] = {
    "mode": ("light", "dark", "system"),
    "switch": ("show", "hide"),
    "density": ("compact", "comfortable", "airy"),
    "text": ("normal", "large", "xlarge"),
    "motion": ("lively", "nolift", "nostrip", "calm"),
    "divider": ("glyph", "line", "none"),
}
# Root and the Event pass choose a theme as designed; Square and Grove may change its colours and fonts. A square made before packages (null) counts as Grove.
PACKAGES_WITH_OWN_LOOK: tuple[str, ...] = (plans.SQUARE, plans.GROVE)

_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# The owner's own fonts (W25-R63). The accent lines ("Come as you are" above a title) have a short list; "headings" means the heading font.
# Keep equal to ACCENTS of square/frontend/src/themes/customFonts.ts (a test reads that file and compares).
ACCENT_IDS: tuple[str, ...] = ("sacramento", "dancing", "caveat", "great-vibes", "headings")
TYPE_ROLES: tuple[str, ...] = ("display", "body")
_GOOGLE_FONTS = Path(__file__).with_name("google_fonts.json")  # made by scripts/build_google_fonts.py, equal to the picker's copy in the platform frontend


@lru_cache(maxsize=1)
def google_fonts() -> dict[str, tuple[str, tuple[int, ...]]]:
    """family -> (category, weights) of every Google font the owner may choose."""
    rows = json.loads(_GOOGLE_FONTS.read_text(encoding="utf-8"))
    return {r[0]: (r[1], tuple(r[2])) for r in rows}


def _nearest(available: tuple[int, ...], target: int) -> int:
    return min(available, key=lambda w: (abs(w - target), w))


def _face(value: Any, role: str) -> dict[str, Any]:
    """One chosen font: only the family is taken from the owner; the category and the weights come from the catalogue.
    Heading weights 400 and 700, body weights 400 and 700, each the nearest the family has."""
    family = value.get("f") if isinstance(value, dict) else None
    fonts = google_fonts()
    if not isinstance(family, str) or family not in fonts:
        raise ValueError("this font is not in the Google Fonts list")
    category, available = fonts[family]
    weights = sorted({_nearest(available, 400), _nearest(available, 700)})
    return {"f": family, "c": category, "w": weights}


def _type(value: Any) -> dict[str, Any]:
    """The `type` part: heading font, body font, accent id; a part set to null is not chosen."""
    if not isinstance(value, dict):
        raise ValueError("type must be an object")
    extra = set(value) - {*TYPE_ROLES, "accent"}
    if extra:
        raise ValueError("unknown type part: " + ", ".join(sorted(extra)))
    out: dict[str, Any] = {}
    for role in TYPE_ROLES:
        if value.get(role) is not None:
            out[role] = _face(value[role], role)
    accent = value.get("accent")
    if accent is not None:
        if accent not in ACCENT_IDS:
            raise ValueError("this accent font is not offered")
        out["accent"] = accent
    return out


def allowed(package: str | None) -> bool:
    return (package or plans.LEGACY_PACKAGE) in PACKAGES_WITH_OWN_LOOK


def _hex(value: Any) -> str:
    m = _HEX.match(value.strip()) if isinstance(value, str) else None
    if not m:
        raise ValueError("colours are written like #a8422a")
    h = m.group(1).lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h


def _choices(name: str, value: Any, table: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """A part-to-option object (shape, feel): every part and option must be offered; a part set to null is not chosen."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    unknown = set(value) - set(table)
    if unknown:
        raise ValueError(f"unknown {name} part: " + ", ".join(sorted(unknown)))
    chosen: dict[str, str] = {}
    for part, option in value.items():
        if option is None:
            continue
        if option not in table[part]:
            raise ValueError(f"this {part} {name} is not offered")
        chosen[part] = option
    return chosen


def parse(raw: Any) -> dict[str, Any] | None:
    """The clean form of what the owner sent, or None when nothing is chosen. Unknown keys are refused, not ignored."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("overrides must be an object")
    extra = set(raw) - {"colors", "colors_dark", "fonts", "spinners", "shape", "feel", "type"}
    if extra:
        raise ValueError("unknown setting: " + ", ".join(sorted(extra)))
    out: dict[str, Any] = {}
    for key in ("colors", "colors_dark"):  # colors_dark (W18-R52): the dark look's own three colours; without it the dark look is made from the light ones
        colors = raw.get(key)
        if colors is not None:
            if not isinstance(colors, dict) or set(colors) != set(COLOR_KEYS):
                raise ValueError("colours need exactly: bg, ink, acc")
            out[key] = {k: _hex(colors[k]) for k in COLOR_KEYS}
    fonts = raw.get("fonts")
    if fonts is not None:
        if fonts not in FONT_PAIR_IDS:
            raise ValueError("this font pair is not offered")
        out["fonts"] = fonts
    spinners = raw.get("spinners")
    if spinners is not None:
        if not isinstance(spinners, list) or not all(isinstance(x, str) for x in spinners):
            raise ValueError("spinners must be a list of spinner ids")
        if any(x not in SPINNER_IDS for x in spinners):
            raise ValueError("a spinner in the list is not offered")
        kept = list(dict.fromkeys(spinners))  # each once, in the order chosen
        if kept:
            out["spinners"] = kept
    feel_raw = raw.get("feel")
    if isinstance(feel_raw, dict) and feel_raw.get("motion") == "none":  # the old option that stopped everything is the calm one now (W25-R57)
        raw = {**raw, "feel": {**feel_raw, "motion": "calm"}}
    for key, table in (("shape", SHAPE_OPTIONS), ("feel", FEEL_OPTIONS)):
        chosen = _choices(key, raw.get(key), table)
        if chosen:
            out[key] = chosen
    if raw.get("type") is not None:
        chosen_type = _type(raw["type"])
        if chosen_type:
            out["type"] = chosen_type
    return out or None


def to_json(clean: dict[str, Any] | None) -> str | None:
    return json.dumps(clean, sort_keys=True) if clean else None


def _raw(stored: str | None) -> dict[str, Any] | None:
    if not stored:
        return None
    try:
        value = json.loads(stored)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def from_json(stored: str | None) -> dict[str, Any] | None:
    """The live look the column holds, for the API and the public site. A damaged value is treated as nothing chosen (the theme shows as designed).
    A draft (W18-R47) and the seasons (W18-R49) kept in the same column are never part of it: they have their own functions below."""
    raw = _raw(stored)
    if raw is None:
        return None
    raw.pop("draft", None)
    raw.pop("seasons", None)
    try:
        return parse(raw)
    except ValueError:
        return None


# The draft (W18-R47, docs/plans/themes-starting-looks-plan.md extra 2): a look the owner shares by a link before it goes live.
# It lives under the key "draft" of the same column (no migration): {"look": <as above>, "token": "<random>", "expires_at": "<iso>",
# "passcode_hash": "<hash>" (optional)}. Only the owner's API shows it, with the token (the owner builds the link from it);
# the public square answer never carries it,
# and the square server hands the look only to a visitor who sends the token (and the passcode, if one is set).
DRAFT_DAYS = 14


def _draft_raw(stored: str | None) -> dict[str, Any] | None:
    raw = _raw(stored)
    draft = raw.get("draft") if raw else None
    return draft if isinstance(draft, dict) else None


def draft_out(stored: str | None, now: dt.datetime) -> dict[str, Any] | None:
    """The draft as the owner sees it (look, token, expires_at, expired, has_passcode); never the passcode hash. None when there is none or it is damaged."""
    draft = _draft_raw(stored)
    if not draft:
        return None
    try:
        look = parse(draft.get("look"))
        expires = dt.datetime.fromisoformat(str(draft.get("expires_at")))
    except ValueError:
        return None
    token = draft.get("token")
    if not look or not isinstance(token, str) or not token:
        return None
    theme = draft.get("theme_id")
    return {
        "look": look,
        "theme_id": theme if isinstance(theme, str) and theme else None,
        "token": token,
        "expires_at": expires.isoformat(),
        "expired": expires <= now,
        "has_passcode": bool(draft.get("passcode_hash")),
    }


def _assemble(live: dict[str, Any] | None, draft: dict[str, Any] | None, seasons: list[Any] | None) -> str | None:
    """The column text: the live look with the shared draft and the seasons beside it (each only when there is one)."""
    out: dict[str, Any] = dict(live or {})
    if draft:
        out["draft"] = draft
    if seasons:
        out["seasons"] = seasons
    return json.dumps(out, sort_keys=True) if out else None


def with_live(stored: str | None, clean: dict[str, Any] | None) -> str | None:
    """The column text after the owner saved a new live look: the live look replaced, the draft and the seasons kept."""
    return _assemble(clean, _draft_raw(stored), _seasons_raw(stored))


def make_draft(stored: str | None, look_raw: Any, passcode: str | None, renew: bool, now: dt.datetime, theme_id: str | None = None) -> str:
    """The column text after the owner saved a draft. The link (token) stays the same unless `renew`;
    the 14 days start again; passcode None keeps the old one, "" removes it."""
    look = parse(look_raw)
    if not look:
        raise ValueError("choose something to share first")
    old = _draft_raw(stored) or {}
    token = old.get("token") if isinstance(old.get("token"), str) and old.get("token") and not renew else secrets.token_urlsafe(24)
    passcode_hash = old.get("passcode_hash")
    if passcode is not None:
        word = passcode.strip()
        if not word:
            passcode_hash = None
        elif 4 <= len(word) <= 40:
            passcode_hash = generate_password_hash(word)
        else:
            raise ValueError("the passcode needs 4 to 40 characters")
    draft: dict[str, Any] = {"look": look, "token": token, "expires_at": (now + dt.timedelta(days=DRAFT_DAYS)).isoformat()}
    if passcode_hash:
        draft["passcode_hash"] = passcode_hash
    if theme_id:
        draft["theme_id"] = theme_id  # the theme the owner had picked in the editor: the draft is shown, and published, with it
    return _assemble(from_json(stored), draft, _seasons_raw(stored)) or "{}"


def drop_draft(stored: str | None) -> str | None:
    """The column text without the draft (the link stops working)."""
    return _assemble(from_json(stored), None, _seasons_raw(stored))


def publish_draft(stored: str | None) -> str | None:
    """The column text when the draft goes live: its look replaces the live look and the draft is gone; the seasons stay."""
    draft = _draft_raw(stored)
    if not draft:
        return None
    return _assemble(parse(draft.get("look")), None, _seasons_raw(stored))


# Seasonal looks (W18-R49, docs/plans/themes-starting-looks-plan.md extra 3): a look (and theme) that the public site wears between two dates,
# then it goes back to the live look. Kept under the key "seasons" of the same column (no migration): a list of
# {"id", "name", "start", "end", "yearly", "theme_id"?, "look"}. The square server picks the one that covers today (UTC); with several covering
# today the earlier one in the list wins. A yearly season repeats every year and may cross the new year (20 Dec to 5 Jan).
MAX_SEASONS = 12
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SEASON_ID = re.compile(r"^[a-z0-9]{6,20}$")


def _seasons_raw(stored: str | None) -> list[Any] | None:
    raw = _raw(stored)
    seasons = raw.get("seasons") if raw else None
    return seasons if isinstance(seasons, list) and seasons else None


def _day(value: Any, what: str) -> dt.date:
    if not isinstance(value, str) or not _DATE.match(value):
        raise ValueError(f"{what} must be a date (YYYY-MM-DD)")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{what} is not a real date") from exc


def parse_seasons(raw: Any) -> list[dict[str, Any]]:
    """The clean list of seasons, or ValueError with a plain message. An empty list means no seasons."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("seasons must be a list")
    if len(raw) > MAX_SEASONS:
        raise ValueError(f"at most {MAX_SEASONS} seasons")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("a season must be an object")
        extra = set(item) - {"id", "name", "start", "end", "yearly", "theme_id", "look"}
        if extra:
            raise ValueError("unknown season setting: " + ", ".join(sorted(extra)))
        name = str(item.get("name") or "").strip()
        if not 1 <= len(name) <= 40:
            raise ValueError("a season needs a name of 1 to 40 characters")
        start, end = _day(item.get("start"), "the start"), _day(item.get("end"), "the end")
        yearly = item.get("yearly") is True
        if not yearly and end < start:
            raise ValueError("the end must not be before the start")
        look = parse(item.get("look"))
        if not look:
            raise ValueError("a season needs a look: choose something in the tabs first")
        season_id = item.get("id")
        if not (isinstance(season_id, str) and _SEASON_ID.match(season_id)) or season_id in seen:
            season_id = secrets.token_hex(4)
        seen.add(season_id)
        season: dict[str, Any] = {"id": season_id, "name": name, "start": start.isoformat(), "end": end.isoformat(), "yearly": yearly, "look": look}
        theme = item.get("theme_id")
        if theme is not None:
            if not isinstance(theme, str) or not 1 <= len(theme) <= 60:
                raise ValueError("the theme is not valid")
            season["theme_id"] = theme
        out.append(season)
    return out


def seasons_out(stored: str | None) -> list[dict[str, Any]]:
    """The seasons as the owner's API shows them; a damaged list shows as none."""
    try:
        return parse_seasons(_seasons_raw(stored))
    except ValueError:
        return []


def with_seasons(stored: str | None, seasons: list[dict[str, Any]]) -> str | None:
    """The column text after the owner saved the list of seasons: the live look and the draft stay."""
    return _assemble(from_json(stored), _draft_raw(stored), seasons)


def season_active(season: dict[str, Any], today: dt.date) -> bool:
    """Does the season cover this day? (the square server has the same rule; tests compare them)"""
    start, end = dt.date.fromisoformat(season["start"]), dt.date.fromisoformat(season["end"])
    if season.get("yearly"):
        a, b, t = (start.month, start.day), (end.month, end.day), (today.month, today.day)
        return a <= t <= b if a <= b else (t >= a or t <= b)
    return start <= today <= end
