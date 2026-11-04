# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""Each square has a phone country, chosen when it is created, Norway by default (rootsquares W6-R52)."""

from flask import Flask

from app.platform.schemas import SUPPORTED_PHONE_COUNTRIES
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)


def _signed_in(api: Flask):
    api.extensions["executor"] = RecordingExecutor()  # no real provisioning
    c = api.test_client()
    h = {**HEADERS, "Authorization": "Bearer fake:u-ph:ph@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Club"}, headers=h).status_code == 201
    return c, h


def test_default_chosen_and_listed(api: Flask) -> None:
    c, h = _signed_in(api)
    assert c.post(f"{PREFIX}/squares", json={"name": "First", "slug": "first-one", "theme_id": "paper-brick"}, headers=h).json["phone_country"] == "NO"
    chosen = c.post(f"{PREFIX}/squares", json={"name": "Second", "slug": "second-one", "theme_id": "paper-brick", "phone_country": " gb "}, headers=h)
    assert chosen.status_code == 202 and chosen.json["phone_country"] == "GB"
    listed = {s["slug"]: s["phone_country"] for s in c.get(f"{PREFIX}/squares", headers=h).json["items"]}
    assert listed == {"first-one": "NO", "second-one": "GB"}


def test_unknown_country_is_refused(api: Flask) -> None:
    c, h = _signed_in(api)
    for bad in ("XX", "norway", "", "1"):
        body = {"name": "First", "slug": "first-one", "theme_id": "paper-brick", "phone_country": bad}
        assert c.post(f"{PREFIX}/squares", json=body, headers=h).status_code == 422, bad
    assert len(SUPPORTED_PHONE_COUNTRIES) == len(set(SUPPORTED_PHONE_COUNTRIES))


def test_the_list_matches_the_square_apps_rules() -> None:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "square" / "backend" / "app" / "common" / "phone.py"
    spec = importlib.util.spec_from_file_location("square_phone", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert tuple(module.SUPPORTED_COUNTRIES) == SUPPORTED_PHONE_COUNTRIES
