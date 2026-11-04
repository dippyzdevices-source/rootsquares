"""Starter sets: what a new square starts with, by the kind of group it is (rootsquares W14-R10, ADR 064).

A starter set is data, not code: a key, a name for the owner, and the optional modules that start switched on. Adding a kind of group (a language school
when one asks) is one entry here and nothing else. The launch package still decides what MAY be switched on (plans.py); a starter set only decides what
STARTS on, so the starting modules are the set's modules the package allows. The owner can change everything afterwards on the Modules page.
The key is kept on the square (`squares.group_type`, operational metadata only, ADR 038) so the square app can offer suggestions that fit the group.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.platform import modules as square_modules

DEFAULT_GROUP_TYPE = "cultural"


@dataclass(frozen=True)
class StarterSet:
    key: str
    label: str
    description: str
    modules: tuple[str, ...]  # the optional modules that start on; completed with what they need


STARTER_SETS: tuple[StarterSet, ...] = (
    StarterSet(
        "cultural",
        "Cultural group",
        "Events and tickets with coupons and check-in, payments, members, messages, a gallery, news, a committee page and accounting.",
        # The list is the Recommended group of the Modules page for this kind of group and what a new square starts with (W15-R27); the rest is Good to have.
        ("events", "tickets", "coupons", "checkin", "payments", "members", "messages", "gallery", "committee", "news", "accounting"),
    ),
    StarterSet(
        "religious",
        "Religious community",
        "Gatherings and events, a member list, donations, messages to the community, news, a gallery and a committee page. "
        "No ticket sales or paid memberships to begin with.",
        ("events", "payments", "members", "donations", "messages", "news", "gallery", "committee"),
    ),
    StarterSet(
        "band",
        "Band or artist",
        "Gigs and tickets, news, a gallery, a newsletter, messages to fans, donations, sponsors and testimonials. No member list or accounting to begin with.",
        ("events", "tickets", "payments", "news", "gallery", "newsletter", "messages", "donations", "sponsors", "testimonials"),
    ),
    StarterSet(
        "charity",
        "Charity or fundraiser",
        "Donations, events, news, a gallery, messages and a newsletter to supporters, sponsors and accounting.",
        ("donations", "payments", "events", "news", "gallery", "messages", "newsletter", "sponsors", "accounting"),
    ),
)

KEYS: tuple[str, ...] = tuple(s.key for s in STARTER_SETS)
_BY_KEY = {s.key: s for s in STARTER_SETS}


def get(key: str | None) -> StarterSet:
    """The set for a key; an unknown or missing key (a square made before starter sets) is the cultural one."""
    return _BY_KEY.get(key or "", _BY_KEY[DEFAULT_GROUP_TYPE])


def starter_modules(key: str | None) -> list[str]:
    return square_modules.normalize(list(get(key).modules))
