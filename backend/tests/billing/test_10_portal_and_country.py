# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The card page (Stripe portal) and the billing country."""

from flask import Flask

from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401


def test_the_card_page_needs_a_payment_customer(api: Flask) -> None:
    c, h, sq = _square(api, "pt1", "roots")
    assert sq["can_manage_billing"] is False
    r = c.post(f"{PREFIX}/squares/{sq['id']}/billing/portal", headers=h)
    assert r.status_code == 409 and r.json["code"] == "no_customer"


def test_the_billing_country_is_kept_on_the_organisation_and_needed_when_money_is_on(api: Flask) -> None:
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": "Bearer fake:u-bc1:bc1@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Club bc1"}, headers=h).status_code == 201
    body = {"name": "Sq bc1", "slug": "sq-bc1", "theme_id": "paper-brick", "launch_package": "roots"}
    assert c.post(f"{PREFIX}/squares", json={**body, "billing_country": "xx1"}, headers=h).status_code == 422  # not a country code
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})
    missing = c.post(f"{PREFIX}/squares", json=body, headers=h)
    assert missing.status_code == 422 and "billing_country" in str(missing.json)
    ok = c.post(f"{PREFIX}/squares", json={**body, "billing_country": "no"}, headers=h)
    assert ok.status_code == 202
    assert c.get(f"{PREFIX}/auth/me", headers=h).json["organizations"][0]["billing_country"] == "NO"
    again = c.post(f"{PREFIX}/squares", json={**body, "slug": "sq-bc2"}, headers=h)
    assert again.status_code == 202  # the organisation already has its country
