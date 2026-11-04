# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The Event pass is paid before it is built when money is on."""

from flask import Flask

from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401
from tests.staff_client import as_admin


def test_a_new_event_pass_is_built_and_started_only_when_paid(api: Flask) -> None:
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})
    c, h, sq = _square(api, "bl12", "event", country="NO")
    ex = api.extensions["executor"]
    assert sq["awaiting_payment"] is True and sq["event_pass"] is None and ex.jobs == []  # nothing built, no clock
    co = _checkout(c, h, sq, kind="event_pass")
    assert co.status_code == 201
    order = c.get(f"{PREFIX}/billing/orders/{co.json['order_id']}", headers=h).json
    assert order["amount_minor"] == 2_500 and order["kind"] == "event_pass"
    assert c.post(f"{PREFIX}/billing/orders/{order['id']}/fake-confirm", json={"outcome": "cancelled"}, headers=h).json["status"] == "cancelled"
    assert ex.jobs == []
    again = _checkout(c, h, sq, kind="event_pass").json["order_id"]
    assert c.post(f"{PREFIX}/billing/orders/{again}/fake-confirm", json={"outcome": "paid"}, headers=h).json["status"] == "paid"
    assert len(ex.jobs) == 1  # the build starts once
    now = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert now["awaiting_payment"] is False and now["event_pass"]["phase"] == "live"
    assert _checkout(c, h, sq, kind="event_pass").status_code == 409  # already paid


def test_an_event_pass_starts_at_once_when_no_payment_is_required(api: Flask) -> None:
    _, _, sq = _square(api, "bl13", "event")
    assert sq["awaiting_payment"] is False and sq["event_pass"]["phase"] == "live"


def test_an_unpaid_event_pass_can_be_deleted_by_its_owner(api: Flask) -> None:
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})
    c, h, sq = _square(api, "bl14", "event", country="NO")
    assert sq["awaiting_payment"] is True and sq["status"] == "provisioning"
    assert c.delete(f"{PREFIX}/squares/{sq['id']}", json={"confirm_slug": sq["slug"]}, headers=h).status_code == 200  # nothing was built, nothing to wait for
    assert c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).status_code == 404


def test_the_owner_overview_counts_an_unpaid_event_pass_as_waiting_for_payment_not_provisioning(api: Flask) -> None:
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})
    c, h, sq = _square(api, "bl15", "event", country="NO")
    c = as_admin(api, c)
    ov = c.get(f"{PREFIX}/owner/overview", headers=h).json
    assert ov["squares_awaiting_payment"] == 1 and ov["squares_provisioning"] == 0 and ov["squares_total"] == 1
    people = c.get(f"{PREFIX}/owner/users", headers=h).json
    items = people["items"] if isinstance(people, dict) else people
    uid = next(u["id"] for u in items if u["email"] == "bl15@example.com")
    refs = [s for o in c.get(f"{PREFIX}/owner/users/{uid}", headers=h).json["orgs"] for s in o["squares"]]
    assert [(r["slug"], r["awaiting_payment"]) for r in refs] == [(sq["slug"], True)]
