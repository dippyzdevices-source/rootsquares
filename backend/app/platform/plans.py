"""Launch packages and running plans of a square (rootsquares W10-R40, docs/plans/pricing-strategy.md, ADR 042).

The launch package decides which optional modules the owner MAY switch on (entitlement): Roots = none (only the always-on parts),
Square = the Recommended modules, Grove = all, Event = the modules a single event needs (ADR 044). The owner chooses within that on the Modules page;
data is never deleted when a module is off.
The running plan says whether the site is alive: Live (always on), Keep (saved, asleep, W10-R41) or Event (one event, 60 days).

Prices are NOT here: they are data (frontend `mock/pricing.ts` for now, a table when billing exists).
Squares made before packages existed are Grove + Live (nothing taken away).
"""

from __future__ import annotations

import json

from app.platform import modules as square_modules

ROOTS, SQUARE, GROVE, EVENT = "roots", "square", "grove", "event"
CUSTOM = "custom"  # agreed with one square by a platform admin (W19-R20, ADR 082): its own modules and one amount per period; never offered for sale
PACKAGES: tuple[str, ...] = (ROOTS, SQUARE, GROVE, EVENT)  # the packages a customer can choose or buy
LIVE, KEEP, EVENT_RUN = "live", "keep", "event"
RUNNING: tuple[str, ...] = (LIVE, KEEP, EVENT_RUN)
DEFAULT_PACKAGE = SQUARE
DEFAULT_RUNNING = LIVE
LEGACY_PACKAGE = GROVE  # squares made before packages existed keep every module

# What a single event needs (user, 2026-10-12, ADR 044). Volunteering needs the Members roster (the people list); the pass has no Memberships. The list is
# completed by `modules.normalize`, so "members" comes with "volunteering".
EVENT_MODULES: tuple[str, ...] = (
    "events",
    "payments",
    "tickets",
    "coupons",
    "checkin",
    "members",
    "volunteering",
    "accounting",
    "sponsors",
    "messages",
)  # Messages with reminders for the ticket holders (W14-R25)

# Square = run the association (W14-R25, docs/reference/packages-and-features.md). Grove = all of it: it adds Donations, Newsletter, Coupons, Check-in,
# Volunteering, Magazines, Testimonials, Sponsors and Founders, and unlocks the gated features (square/backend/app/features.py).
# Not "every Recommended module" any more: Donations is Recommended but Grove.
SQUARE_MODULES: tuple[str, ...] = ("events", "payments", "tickets", "members", "memberships", "accounting", "gallery", "committee", "messages")


def custom_modules_of(raw: str | None) -> list[str]:
    """The modules agreed for a custom package, from the JSON list kept on the square: known keys only, completed with what they need, in catalogue order."""
    try:
        keys = json.loads(raw) if raw else []
    except ValueError:
        keys = []
    return square_modules.normalize([k for k in keys if k in square_modules.KEYS]) if isinstance(keys, list) else []


def custom_core_of(raw: str | None) -> list[str]:
    """The always-on parts a custom package keeps. A list saved before this existed holds none of them and means all of them (nothing is taken away)."""
    try:
        keys = json.loads(raw) if raw else []
    except ValueError:
        keys = []
    keys = keys if isinstance(keys, list) else []
    if not any(k in square_modules.CORE_KEYS for k in keys):
        return list(square_modules.CORE_KEYS)
    return square_modules.normalize_core(keys, custom_modules_of(raw))


def allowed_modules(package: str | None, custom: str | None = None) -> list[str]:
    """The optional modules a package lets the owner switch on, in catalogue order. `custom`: the square's agreed list (JSON), for the custom package only."""
    package = package or LEGACY_PACKAGE
    if package == CUSTOM:
        return custom_modules_of(custom)
    if package == ROOTS:
        return []
    if package == SQUARE:
        return [k for k in square_modules.KEYS if k in SQUARE_MODULES]
    if package == EVENT:
        return square_modules.normalize(list(EVENT_MODULES))
    return list(square_modules.KEYS)  # grove, and any unknown value (never take modules away by mistake)


def starting_modules(package: str | None, group_type: str | None = None, custom: str | None = None) -> list[str]:
    """What is on when a square of this package is created: the starter set of its kind of group (starter_sets.py; the cultural set is the Recommended modules)
    limited to what the package allows. Grove starts like Square; its extras are chosen. The Event pass has its own fixed list."""
    from app.platform import starter_sets

    allowed = set(allowed_modules(package, custom))
    return [k for k in starter_sets.starter_modules(group_type) if k in allowed] if package != EVENT else allowed_modules(EVENT)


def outside_package(package: str | None, keys: list[str], custom: str | None = None) -> list[str]:
    """The chosen modules the package does not include (empty = the choice is allowed)."""
    allowed = set(allowed_modules(package, custom))
    return [k for k in keys if k not in allowed]
