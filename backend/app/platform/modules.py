"""The optional modules of a square (rootsquares W8-R9, docs/reference/optional-modules.md).

The owner chooses which modules a square has, on the platform; the square app reads the list from `squares.modules` and shows and serves
only those. Core parts (sign-in, Home, About, Contact, legal pages, settings, media store, ...) are not in this list: they are always on.

This file is the catalogue the owner sees and the rules for a valid choice. The square app has the other half (which pages and endpoints belong
to a key) in square/backend/app/modules.py; a test here checks that both name the same keys.
"""

from __future__ import annotations

from dataclasses import dataclass

CORE = "core"
RECOMMENDED = "recommended"  # preselected when a square is created; the owner can turn it off
GOOD_TO_HAVE = "good_to_have"  # off until the owner turns it on


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    description: str
    tier: str
    needs: tuple[str, ...] = ()  # hard dependencies: cannot be on unless these are on
    parent: str | None = None  # shown indented under this module and switched on with it by default (W14-R13); the switch stays its own
    starts_off: bool = False  # a sub-switch that is NOT switched on together with its parent (W14-R23); the owner turns it on


MODULES: tuple[Module, ...] = (
    Module("events", "Events", "Public list and pages of events, and the events admin.", RECOMMENDED),
    Module("payments", "Payments", "Payment records and online payment (Vipps).", RECOMMENDED),
    Module("tickets", "Tickets and orders", "Buying tickets, orders, tickets with QR codes and the order emails.", RECOMMENDED, ("events", "payments")),
    Module("coupons", "Coupons", "Coupon codes at checkout.", RECOMMENDED, ("tickets",), parent="tickets"),
    Module(
        "checkin",
        "Check-in",
        "Scanning tickets at the door, and the Volunteers page that gives members door access.",
        RECOMMENDED,
        ("tickets",),
        parent="tickets",
    ),
    Module(
        "members",
        "Members",
        "The member list (the people roster), families, duplicates and Excel import. Works on its own; Memberships builds on it.",
        RECOMMENDED,
    ),
    Module(
        "memberships",
        "Memberships",
        "Membership types, the Become a member page, the sign-up drive and member payments. Needs Members.",
        GOOD_TO_HAVE,
        ("members", "payments"),
        parent="members",
    ),
    Module("volunteering", "Volunteering", "Volunteer tasks at events and the volunteering page for members.", GOOD_TO_HAVE, ("events", "members")),
    Module(
        "accounting",
        "Accounting",
        "Expenses, receipts and the accounting report of each event, and a general book for costs and income that belong to no event "
        "(gifts and membership payments). Works without Events.",
        RECOMMENDED,
    ),
    Module("gallery", "Gallery", "Photo albums and the gallery page.", RECOMMENDED),
    Module("news", "News", "News articles and the News page.", RECOMMENDED),
    Module("magazines", "Magazines", "Magazine issues next to the news.", GOOD_TO_HAVE, ("news",), parent="news", starts_off=True),
    Module(
        "newsletter",
        "Newsletter",
        "A sign-up form and the subscriber list. Newsletters are written and sent in Messages, so it needs Messages. "
        "Works without News (it then has its own sign-up page).",
        GOOD_TO_HAVE,
        ("messages",),
    ),
    Module("testimonials", "Testimonials", "Words from members, sent in and approved.", GOOD_TO_HAVE),
    Module("sponsors", "Sponsors", "Sponsor logos on the home page.", GOOD_TO_HAVE),
    Module("committee", "Committee", "The Committee page and its admin.", RECOMMENDED),
    Module("founders", "Founders", "Founders' quotes on the About page.", GOOD_TO_HAVE),
    Module(
        "donations",
        "Donations",
        "A donate page: gifts by Vipps, bank transfer or cash, receipts by e-mail, and a list with export. Needs Payments.",
        GOOD_TO_HAVE,
        ("payments",),
        parent="payments",
        starts_off=True,
    ),
    Module(
        "messages",
        "Messages",
        "E-mail to groups of members, ticket holders, volunteers or donors, scheduled sending, an opt-out list and automatic reminders.",
        RECOMMENDED,
    ),
)

KEYS: tuple[str, ...] = tuple(m.key for m in MODULES)
RECOMMENDED_KEYS: tuple[str, ...] = tuple(m.key for m in MODULES if m.tier == RECOMMENDED)
_BY_KEY = {m.key: m for m in MODULES}


def unknown_keys(keys: list[str]) -> list[str]:
    return [k for k in keys if k not in _BY_KEY]


def normalize(keys: list[str]) -> list[str]:
    """The valid form of a choice: unknown keys dropped, what a chosen module needs added (Memberships needs Members, ADR 044), catalogue order."""
    chosen = {k for k in keys if k in _BY_KEY}
    grew = True
    while grew:
        grew = False
        for key in list(chosen):
            for need in _BY_KEY[key].needs:
                if need not in chosen:
                    chosen.add(need)
                    grew = True
    return [k for k in KEYS if k in chosen]


def effective(stored: list[str] | None) -> list[str]:
    """What a square has: nothing stored (a square made before modules existed, such as first-org) means every module."""
    return list(KEYS) if stored is None else normalize(stored)


@dataclass(frozen=True)
class CorePart:
    key: str
    label: str
    description: str
    needs: tuple[str, ...] = ()


# The always-on parts of a square (W19-R24, ADR 082). Every package has all of them; only a CUSTOM package can leave some out. The hierarchy decides what can be
# left out: a part that needs another cannot be on without it, and a module needs the parts it is run from.
# Keys equal the square app's CORE_KEYS (a test checks it).
CORE_PARTS: tuple[CorePart, ...] = (
    CorePart("home", "Home", "The front page of the site."),
    CorePart("about", "About", "The About page."),
    CorePart("contact", "Contact", "The Contact page and its form."),
    CorePart("legal", "Legal pages", "Privacy, terms and the other legal pages."),
    CorePart("login", "Sign-in", "Sign-in and sign-up for members and admins."),
    CorePart("account", "Member account", "The member's own pages: profile and what they bought or joined.", ("login",)),
    CorePart("admin", "Admin", "The admin area where the site is run.", ("login",)),
    CorePart("settings", "Settings", "The square's settings in the admin.", ("admin",)),
    CorePart("media", "Media", "The media store for pictures and files.", ("admin",)),
)
CORE_KEYS: tuple[str, ...] = tuple(c.key for c in CORE_PARTS)
_CORE_BY_KEY = {c.key: c for c in CORE_PARTS}
# Every optional module is run from the Admin; the ones with pages for members also need the member account.
MODULE_CORE_NEEDS: dict[str, tuple[str, ...]] = {
    **{k: ("admin",) for k in KEYS},
    "tickets": ("admin", "account"),
    "memberships": ("admin", "account"),
    "volunteering": ("admin", "account"),
}


def normalize_core(keys: list[str], modules: list[str] | None = None) -> list[str]:
    """The valid form of a choice of always-on parts: unknown keys dropped, what a part needs added (and what the chosen modules need), in order."""
    chosen = {k for k in keys if k in _CORE_BY_KEY}
    for m in modules or []:
        chosen.update(MODULE_CORE_NEEDS.get(m, ()))
    grew = True
    while grew:
        grew = False
        for key in list(chosen):
            for need in _CORE_BY_KEY[key].needs:
                if need not in chosen:
                    chosen.add(need)
                    grew = True
    return [k for k in CORE_KEYS if k in chosen]
