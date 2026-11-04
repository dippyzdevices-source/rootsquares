# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The invoice of a paid order (W19-R16): only paid payments, only the owner, the seller from platform settings, the number counts the year."""

from flask import Flask

from tests.billing.helpers import HEADERS, PREFIX, _checkout, _square, api  # noqa: F401
from tests.staff_client import ADMIN, STAFF_HEADERS, as_admin, staff_client


def _pay(c, h, sq, **body) -> str:
    oid = _checkout(c, h, sq, **body).json["order_id"]
    assert c.post(f"{PREFIX}/billing/orders/{oid}/fake-confirm", json={"outcome": "paid"}, headers=h).status_code == 200
    return oid


def test_a_pending_payment_has_no_invoice_and_a_paid_one_has(api: Flask) -> None:
    c, h, sq = _square(api, "iv1", "roots")
    pending = _checkout(c, h, sq, kind="upgrade", launch_package="grove").json["order_id"]
    assert c.get(f"{PREFIX}/billing/orders/{pending}/invoice", headers=h).status_code == 409
    c.post(f"{PREFIX}/billing/orders/{pending}/fake-confirm", json={"outcome": "paid"}, headers=h)
    inv = c.get(f"{PREFIX}/billing/orders/{pending}/invoice", headers=h).json
    assert inv["order"]["amount_minor"] == 39_900 - 14_900 and inv["square_name"]
    assert inv["number"].startswith("RS-") and inv["number"].endswith("-0001")
    assert inv["net_minor"] + inv["tax_minor"] == inv["order"]["amount_minor"]
    assert inv["seller"]["prefix"] == "RS" and inv["seller"]["name"] == ""  # nothing set: nothing shown


def test_the_number_counts_the_payments_of_the_year_in_order(api: Flask) -> None:
    c, h, sq = _square(api, "iv2", "roots")
    first = _pay(c, h, sq, kind="upgrade", launch_package="square")
    second = _pay(c, h, sq, kind="upgrade", launch_package="grove")
    n1 = c.get(f"{PREFIX}/billing/orders/{first}/invoice", headers=h).json["number"]
    n2 = c.get(f"{PREFIX}/billing/orders/{second}/invoice", headers=h).json["number"]
    assert n1.endswith("-0001") and n2.endswith("-0002") and n1[:-4] == n2[:-4]
    assert c.get(f"{PREFIX}/billing/orders/{first}/invoice", headers=h).json["number"] == n1  # stable


def test_only_the_owner_reads_an_invoice(api: Flask) -> None:
    c, h, sq = _square(api, "iv3", "roots")
    oid = _pay(c, h, sq, kind="upgrade", launch_package="grove")
    _, h2, _ = _square(api, "iv4", "roots")
    assert c.get(f"{PREFIX}/billing/orders/{oid}/invoice", headers=h2).status_code == 404


def test_only_a_platform_admin_sets_the_seller(api: Flask) -> None:
    c, h, sq = _square(api, "iv5", "roots")
    seller = {"name": "Rootsquares AS", "org_no": "931 000 000", "address": "Storgata 1, Oslo", "prefix": "RSQ", "footer": "Valid without signature."}
    assert c.put(f"{PREFIX}/invoice-settings", json=seller, headers=h).status_code == 404
    c = as_admin(api, c)
    assert c.put(f"{PREFIX}/invoice-settings", json=seller, headers=h).status_code == 200
    oid = _pay(c, h, sq, kind="upgrade", launch_package="grove")
    inv = c.get(f"{PREFIX}/billing/orders/{oid}/invoice", headers=h).json
    assert inv["seller"]["name"] == "Rootsquares AS" and inv["number"].startswith("RSQ-") and inv["seller"]["footer"] == "Valid without signature."


def test_platform_staff_read_an_invoice_of_any_square(api: Flask) -> None:
    c, h, sq = _square(api, "iv6", "roots")
    oid = _pay(c, h, sq, kind="upgrade", launch_package="grove")
    c2, h2, _ = _square(api, "iv7", "roots")
    assert c2.get(f"{PREFIX}/billing/orders/{oid}/invoice", headers=h2).status_code == 404  # another organisation's customer sees nothing
    assert staff_client(api).get(f"{ADMIN}/billing/orders/{oid}/invoice", headers=STAFF_HEADERS).status_code == 200  # staff read every invoice
