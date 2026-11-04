"""The listed price includes the tax Stripe adds (W13-R51, ADR 060): for a country in BILLING_TAX_RATES we send Stripe the price without the tax, so with
the tax added the customer pays exactly the listed price. Stripe's HTTP is mocked."""

import uuid
from types import SimpleNamespace

import pytest

from app.platform import billing
from app.platform.billing import StripeBillingProvider, net_minor, tax_percent, tax_rates, tax_split
from tests.conftest import make_settings


def _order(kind="first", **kw):
    base = dict(id=uuid.uuid4(), kind=kind, launch_package="grove", running_plan="live", interval="month", amount_minor=17_400, currency="USD")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.parametrize(("gross", "net"), [(14_900, 11_920), (1_500, 1_200), (4_900, 3_920), (500, 400), (2_900, 2_320)])
def test_the_amount_sent_with_25_percent_added_is_the_listed_price(gross, net) -> None:
    assert net_minor(gross, 25) == net
    assert net + round(net * 0.25) == gross


def test_no_tax_inside_the_price_sends_the_listed_price() -> None:
    assert net_minor(14_900, 0) == 14_900 and tax_split(14_900, 0) == (14_900, 0)


def test_the_split_is_what_the_pages_show() -> None:
    assert tax_split(14_900, 25) == (11_920, 2_980)
    assert tax_split(1_500, 25) == (1_200, 300)
    assert tax_split(1_000, 25.5)[0] + tax_split(1_000, 25.5)[1] == 1_000


def test_the_rates_come_from_the_setting_and_a_bad_pair_is_skipped() -> None:
    s = make_settings(BILLING_TAX_RATES="NO:25, se:25 ,FI:25.5,XX,DK:abc,GERMANY:19,SE:0")
    assert tax_rates(s) == {"NO": 25.0, "SE": 25.0, "FI": 25.5}  # "SE:0" is skipped, the earlier "se:25" stays
    assert tax_percent(s, "no") == 25.0 and tax_percent(s, "DE") == 0.0 and tax_percent(s, None) == 0.0
    assert tax_rates(make_settings(BILLING_TAX_RATES="")) == {}
    assert billing.tax_percent(make_settings(), "NO") == 25.0  # the default: Norway


def _seen(monkeypatch, order, **kw):
    seen: dict = {}

    def fake_create(self, params=None, options=None):
        seen.update(params)
        return SimpleNamespace(url="https://checkout.stripe.test/s", id="cs_test_1")

    monkeypatch.setattr("stripe.checkout._session_service.SessionService.create", fake_create)
    StripeBillingProvider("sk_test_x", "whsec_x").create_checkout(order, "https://ok", "https://no", **kw)
    return seen


def test_a_first_payment_in_a_tax_country_sends_both_lines_without_the_tax(monkeypatch) -> None:
    seen = _seen(monkeypatch, _order(), launch_minor=14_900, tax_percent=25.0)
    period, once = seen["line_items"][0]["price_data"], seen["line_items"][1]["price_data"]
    assert once["unit_amount"] == 11_920 and period["unit_amount"] == 2_000  # 149.00 and 25.00 listed
    assert period["recurring"] == {"interval": "month"}


def test_an_event_pass_in_a_tax_country_sends_twelve_dollars(monkeypatch) -> None:
    seen = _seen(monkeypatch, _order("event_pass", amount_minor=1_500, running_plan=None, interval=None), tax_percent=25.0)
    assert seen["line_items"][0]["price_data"]["unit_amount"] == 1_200


def test_another_country_is_sent_the_listed_price(monkeypatch) -> None:
    seen = _seen(monkeypatch, _order("event_pass", amount_minor=1_500, running_plan=None, interval=None), tax_percent=0.0)
    assert seen["line_items"][0]["price_data"]["unit_amount"] == 1_500
    seen = _seen(monkeypatch, _order("event_pass", amount_minor=1_500, running_plan=None, interval=None))  # no argument at all
    assert seen["line_items"][0]["price_data"]["unit_amount"] == 1_500
