# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""Prices are data (plan_prices), edited by a platform admin only."""

from flask import Flask

from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401
from tests.staff_client import as_admin


def test_prices_are_data_with_the_chosen_defaults(api: Flask) -> None:
    items = {p["key"]: p for p in api.test_client().get(f"{PREFIX}/prices").json["items"]}
    assert items["launch.roots"]["amount_minor"] == 14_900 and items["launch.grove"]["amount_minor"] == 39_900
    assert items["running.live.month"] == {"key": "running.live.month", "amount_minor": 2_500, "currency": "USD", "interval": "month"}
    assert items["running.live.year"]["amount_minor"] == 25_000 and items["launch.event"]["amount_minor"] == 2_500


def test_only_a_platform_admin_changes_a_price(api: Flask) -> None:
    c, h, _ = _square(api, "bl1")
    assert c.put(f"{PREFIX}/prices/launch.roots", json={"amount_minor": 9_900}, headers=h).status_code == 404
    c = as_admin(api, c)
    ok = c.put(f"{PREFIX}/prices/launch.roots", json={"amount_minor": 9_900}, headers=h)
    assert ok.status_code == 200 and ok.json["amount_minor"] == 9_900
    assert c.put(f"{PREFIX}/prices/nope", json={"amount_minor": 1}, headers=h).status_code == 404
    assert c.put(f"{PREFIX}/prices/launch.roots", json={"amount_minor": -1}, headers=h).status_code == 422
