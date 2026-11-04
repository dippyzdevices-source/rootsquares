# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""Each square has a list of optional modules, chosen by its owner on the platform (rootsquares W8-R9, docs/reference/optional-modules.md)."""

import re
from pathlib import Path

from flask import Flask

from app.platform import modules
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)


def _signed_in(api: Flask):
    api.extensions["executor"] = RecordingExecutor()  # no real provisioning
    c = api.test_client()
    h = {**HEADERS, "Authorization": "Bearer fake:u-mod:mod@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Club"}, headers=h).status_code == 201
    return c, h


def test_normalize_adds_what_is_needed() -> None:
    assert modules.normalize(["tickets"]) == ["events", "payments", "tickets"]  # tickets cannot be paid for without Payments
    assert modules.normalize(["members"]) == ["members"]  # Members works alone (ADR 044)
    assert modules.normalize(["memberships"]) == ["payments", "members", "memberships"]  # Memberships builds on Members and Payments
    assert modules.normalize(["volunteering"]) == ["events", "members", "volunteering"]  # volunteers are the roster; no Memberships needed
    assert modules.normalize(["newsletter", "nonsense"]) == ["newsletter", "messages"]  # works without News (W14-R13) but sends through Messages (W14-R19)
    assert modules.normalize(["accounting"]) == ["accounting"]  # accounting works without Events (W14-R15: the general book)
    assert modules.normalize([]) == []
    assert modules.effective(None) == list(modules.KEYS)  # a square without a stored choice has every module


def test_new_square_gets_the_recommended_modules(api: Flask) -> None:
    c, h = _signed_in(api)
    made = c.post(f"{PREFIX}/squares", json={"name": "First", "slug": "first-one", "theme_id": "paper-brick"}, headers=h)
    # a new square is Square-package and cultural: the cultural list limited to what Square includes (W15-R27)
    assert made.status_code == 202 and made.json["modules"] == modules.normalize(
        ["events", "tickets", "payments", "members", "messages", "gallery", "committee", "accounting"]
    )
    assert "coupons" not in made.json["modules"] and "memberships" not in made.json["modules"] and "events" in made.json["modules"]


def test_chosen_at_creation_is_completed_and_unknown_is_refused(api: Flask) -> None:
    c, h = _signed_in(api)
    chosen = c.post(f"{PREFIX}/squares", json={"name": "Second", "slug": "second-one", "theme_id": "paper-brick", "modules": ["tickets"]}, headers=h)
    assert chosen.status_code == 202 and chosen.json["modules"] == ["events", "payments", "tickets"]
    bad = c.post(f"{PREFIX}/squares", json={"name": "Third", "slug": "third-one", "theme_id": "paper-brick", "modules": ["nope"]}, headers=h)
    assert bad.status_code == 422


def test_owner_changes_the_modules_and_it_is_audited(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = c.post(f"{PREFIX}/squares", json={"name": "First", "slug": "first-one", "theme_id": "paper-brick", "launch_package": "grove"}, headers=h).json
    changed = c.put(f"{PREFIX}/squares/{sq['id']}/modules", json={"modules": ["news", "newsletter", "gallery"]}, headers=h)
    assert changed.status_code == 200 and changed.json["modules"] == ["gallery", "news", "newsletter", "messages"]
    assert c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json["modules"] == ["gallery", "news", "newsletter", "messages"]
    none = c.put(f"{PREFIX}/squares/{sq['id']}/modules", json={"modules": []}, headers=h)
    assert none.status_code == 200 and none.json["modules"] == []  # only the core is left
    assert c.put(f"{PREFIX}/squares/{sq['id']}/modules", json={"modules": ["x"]}, headers=h).status_code == 422


def test_somebody_else_cannot_change_them(api: Flask) -> None:
    c, h = _signed_in(api)
    sq = c.post(f"{PREFIX}/squares", json={"name": "First", "slug": "first-one", "theme_id": "paper-brick"}, headers=h).json
    other = {**HEADERS, "Authorization": "Bearer fake:u-oth:oth@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Other club"}, headers=other).status_code == 201
    assert c.put(f"{PREFIX}/squares/{sq['id']}/modules", json={"modules": ["news"]}, headers=other).status_code == 404


def test_catalogue_is_listed(api: Flask) -> None:
    c, h = _signed_in(api)
    items = c.get(f"{PREFIX}/modules", headers=h).json["items"]
    assert [i["key"] for i in items] == list(modules.KEYS)
    assert {i["tier"] for i in items} == {"recommended", "good_to_have"}


def test_square_app_knows_the_same_keys() -> None:
    """The square app has the other half of the registry; both must name the same modules."""
    text = (Path(__file__).resolve().parents[2] / "square" / "backend" / "app" / "modules.py").read_text(encoding="utf-8")
    square_keys = re.search(r"MODULE_KEYS\s*=\s*\(([^)]*)\)", text, re.S)
    assert square_keys is not None, "square/backend/app/modules.py must define MODULE_KEYS"
    assert re.findall(r'"([a-z_]+)"', square_keys.group(1)) == list(modules.KEYS)


def test_owner_changes_the_theme_of_a_square(api: Flask) -> None:
    """W9-R5: the theme can be changed after creation; an unknown theme is refused; someone else's square is not found."""
    c, h = _signed_in(api)
    made = c.post(f"{PREFIX}/squares", json={"name": "Themed", "slug": "themed-one", "theme_id": "paper-brick"}, headers=h).json
    changed = c.put(f"{PREFIX}/squares/{made['id']}/theme", json={"theme_id": "marquee-showbill"}, headers=h)
    assert changed.status_code == 200 and changed.json["theme_id"] == "marquee-showbill"
    assert c.put(f"{PREFIX}/squares/{made['id']}/theme", json={"theme_id": "nonsense"}, headers=h).status_code == 422
    other = {**HEADERS, "Authorization": "Bearer fake:u-other:other@example.com"}
    assert c.put(f"{PREFIX}/squares/{made['id']}/theme", json={"theme_id": "pearl"}, headers=other).status_code == 404


def test_the_catalogue_names_the_parent_of_a_sub_switch() -> None:
    from app.platform import modules as square_modules

    parents = {m.key: m.parent for m in square_modules.MODULES if m.parent}
    assert parents == {"coupons": "tickets", "checkin": "tickets", "memberships": "members", "magazines": "news", "donations": "payments"}
    assert [m.key for m in square_modules.MODULES if m.starts_off] == ["magazines", "donations"]
    assert all(parent in square_modules.KEYS and parent in next(x for x in square_modules.MODULES if x.key == key).needs for key, parent in parents.items())


def test_square_app_knows_the_same_always_on_parts() -> None:
    """W19-R24: the always-on parts a custom package can leave out are named the same on both sides."""
    text = (Path(__file__).resolve().parents[2] / "square" / "backend" / "app" / "modules.py").read_text(encoding="utf-8")
    square_core = re.search(r"CORE_KEYS\s*=\s*\(([^)]*)\)", text, re.S)
    assert square_core is not None, "square/backend/app/modules.py must define CORE_KEYS"
    assert re.findall(r'"([a-z_]+)"', square_core.group(1)) == list(modules.CORE_KEYS)
