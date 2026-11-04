# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""Each square has a currency, chosen when it is created, NOK by default (rootsquares W6-R47)."""

from flask import Flask

from app.platform.schemas import SUPPORTED_CURRENCIES
from tests.staff_client import as_admin
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)


def _signed_in(api: Flask):
    api.extensions["executor"] = RecordingExecutor()  # no real provisioning
    c = api.test_client()
    h = {**HEADERS, "Authorization": "Bearer fake:u-cur:cur@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Club"}, headers=h).status_code == 201
    return c, h


def test_a_square_is_created_with_nok_unless_another_currency_is_chosen(api: Flask) -> None:
    c, h = _signed_in(api)
    default = c.post(f"{PREFIX}/squares", json={"name": "First", "slug": "first-one", "theme_id": "paper-brick"}, headers=h)
    assert default.status_code == 202 and default.json["currency"] == "NOK"
    chosen = c.post(f"{PREFIX}/squares", json={"name": "Second", "slug": "second-one", "theme_id": "paper-brick", "currency": " sek "}, headers=h)
    assert chosen.status_code == 202 and chosen.json["currency"] == "SEK"  # trimmed and upper-cased
    listed = {s["slug"]: s["currency"] for s in c.get(f"{PREFIX}/squares", headers=h).json["items"]}
    assert listed == {"first-one": "NOK", "second-one": "SEK"}


def test_an_unknown_currency_is_refused(api: Flask) -> None:
    c, h = _signed_in(api)
    for bad in ("XXX", "kroner", "", "12"):
        r = c.post(f"{PREFIX}/squares", json={"name": "First", "slug": "first-one", "theme_id": "paper-brick", "currency": bad}, headers=h)
        assert r.status_code == 422, bad
    assert "NOK" in SUPPORTED_CURRENCIES and len(SUPPORTED_CURRENCIES) == len(set(SUPPORTED_CURRENCIES))


def test_the_platform_admin_sees_the_currency_in_the_owner_console(api: Flask) -> None:
    c, h = _signed_in(api)
    made = c.post(f"{PREFIX}/squares", json={"name": "First", "slug": "first-one", "theme_id": "paper-brick", "currency": "DKK"}, headers=h).json
    c = as_admin(api, c)
    assert c.get(f"{PREFIX}/owner/squares/{made['id']}", headers=h).json["currency"] == "DKK"
    assert c.get(f"{PREFIX}/owner/squares", headers=h).json["items"][0]["currency"] == "DKK"
