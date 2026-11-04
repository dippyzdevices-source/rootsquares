# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The prospect list (W19-R22): a public form on the Pricing page, a list for platform admins."""

from flask import Flask

from tests.billing.helpers import HEADERS, PREFIX, _square, api  # noqa: F401
from tests.staff_client import as_admin

GOOD = {"name": "Kari Nordmann", "email": "kari@example.com", "phone": "+47 900 00 000", "message": "We need ticketing and a shop", "consent": True}


def test_anyone_can_ask_to_be_contacted_and_only_an_admin_reads_the_list(api: Flask) -> None:
    c = api.test_client()
    r = c.post(f"{PREFIX}/prospects", json=GOOD, headers=HEADERS)
    assert r.status_code == 201 and r.json == {"ok": True}
    assert c.get(f"{PREFIX}/prospects", headers=HEADERS).status_code == 404  # the customer API does not serve the list at all
    _, h, _ = _square(api, "pr1", "roots")
    assert c.get(f"{PREFIX}/prospects", headers=h).status_code == 404
    c = as_admin(api, c)
    items = c.get(f"{PREFIX}/prospects", headers=h).json["items"]
    assert len(items) == 1 and items[0]["email"] == "kari@example.com" and items[0]["status"] == "new" and items[0]["phone"] == "+47 900 00 000"


def test_the_form_checks_consent_phone_and_e_mail(api: Flask) -> None:
    c = api.test_client()
    assert c.post(f"{PREFIX}/prospects", json={**GOOD, "consent": False}, headers=HEADERS).status_code == 422
    assert c.post(f"{PREFIX}/prospects", json={**GOOD, "phone": "abc"}, headers=HEADERS).status_code == 422
    assert c.post(f"{PREFIX}/prospects", json={**GOOD, "email": "nope"}, headers=HEADERS).status_code == 422
    assert c.post(f"{PREFIX}/prospects", json={k: v for k, v in GOOD.items() if k != "name"}, headers=HEADERS).status_code == 422


def test_a_bot_and_a_repeat_store_nothing_extra(api: Flask) -> None:
    c = api.test_client()
    assert c.post(f"{PREFIX}/prospects", json={**GOOD, "website": "http://spam"}, headers=HEADERS).status_code == 201  # the bot is told it worked
    c.post(f"{PREFIX}/prospects", json=GOOD, headers=HEADERS)
    c.post(f"{PREFIX}/prospects", json={**GOOD, "name": "Kari again"}, headers=HEADERS)  # the same e-mail the same day: one row
    _, h, _ = _square(api, "pr2", "roots")
    c = as_admin(api, c)
    items = c.get(f"{PREFIX}/prospects", headers=h).json["items"]
    assert [i["name"] for i in items] == ["Kari Nordmann"]


def test_an_admin_sets_status_and_notes_and_deletes(api: Flask) -> None:
    c = api.test_client()
    c.post(f"{PREFIX}/prospects", json=GOOD, headers=HEADERS)
    _, h, _ = _square(api, "pr3", "roots")
    c = as_admin(api, c)
    pid = c.get(f"{PREFIX}/prospects", headers=h).json["items"][0]["id"]
    r = c.patch(f"{PREFIX}/prospects/{pid}", json={"status": "contacted", "notes": "Called on Monday"}, headers=h)
    assert r.status_code == 200 and r.json["status"] == "contacted" and r.json["notes"] == "Called on Monday"
    assert c.patch(f"{PREFIX}/prospects/{pid}", json={"status": "nope"}, headers=h).status_code == 422
    assert len(c.get(f"{PREFIX}/prospects?status=won", headers=h).json["items"]) == 0
    assert len(c.get(f"{PREFIX}/prospects?status=contacted", headers=h).json["items"]) == 1
    assert c.delete(f"{PREFIX}/prospects/{pid}", headers=h).status_code == 200
    assert c.get(f"{PREFIX}/prospects", headers=h).json["items"] == []
