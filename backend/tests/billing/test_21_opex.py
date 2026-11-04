# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The platform's running costs (W16-R9): how a line spreads over the months, the year grid, and who may use it."""

import datetime as dt
from types import SimpleNamespace

from flask import Flask

from app.platform import opex
from tests.billing.helpers import PREFIX, _square, api  # noqa: F401
from tests.staff_client import as_admin


def _line(cadence="monthly", amount=1000, start=(2026, 3, 1), end=None, pct=0, category="Hosting"):
    end_on = dt.date(*end) if end else None
    return SimpleNamespace(category=category, amount_minor=amount, cadence=cadence, start_on=dt.date(*start), end_on=end_on, annual_increase_pct=pct)


def test_a_line_spreads_over_the_months_by_its_rhythm():
    monthly = [opex.amount_in_month(_line(), 2026, m) for m in range(1, 13)]
    assert monthly == [0, 0] + [1000] * 10  # from March, every month
    quarterly = [opex.amount_in_month(_line("quarterly"), 2026, m) for m in range(1, 13)]
    assert [m + 1 for m, a in enumerate(quarterly) if a] == [3, 6, 9, 12]
    yearly = [opex.amount_in_month(_line("yearly"), y, 3) for y in (2025, 2026, 2027)]
    assert yearly == [0, 1000, 1000] and opex.amount_in_month(_line("yearly"), 2027, 4) == 0
    one_off = [opex.amount_in_month(_line("one_off"), 2026, m) for m in range(1, 13)]
    assert sum(one_off) == 1000 and one_off[2] == 1000
    assert opex.amount_in_month(_line("one_off"), 2027, 3) == 0


def test_an_end_month_stops_the_line_and_a_yearly_rise_compounds_once_a_year():
    ended = _line(end=(2026, 5, 31))
    assert [opex.amount_in_month(ended, 2026, m) for m in (4, 5, 6)] == [1000, 1000, 0]
    rising = _line(pct=10)
    assert opex.amount_in_month(rising, 2026, 12) == 1000 and opex.amount_in_month(rising, 2027, 3) == 1100 and opex.amount_in_month(rising, 2028, 3) == 1210


def test_the_year_grid_has_totals_and_the_year_before():
    report = opex.monthly_report([_line(), _line("yearly", 12000, category="Domains and DNS")], 2027)
    assert report["total"] == 12 * 1000 + 12000 and report["previous_total"] == 10 * 1000 + 12000
    assert [c["name"] for c in report["categories"]] == ["Domains and DNS", "Hosting"] and len(report["totals"]) == 12


def _admin(api: Flask, who: str):
    c, h, _ = _square(api, who)
    c = as_admin(api, c)
    return c, h


def _item(c, h, **body):
    base = {"name": "Render", "category": "Hosting", "amount_minor": 2500, "cadence": "monthly", "start_on": "2026-01-01"}
    return c.post(f"{PREFIX}/opex/items", json={**base, **body}, headers=h)


def test_only_a_platform_admin_uses_the_costs_and_a_bad_line_is_refused(api: Flask) -> None:
    c, h, _ = _square(api, "ox1")
    assert _item(c, h).status_code == 404 and c.get(f"{PREFIX}/opex/monthly", headers=h).status_code == 404
    c = as_admin(api, c)
    made = _item(c, h)
    assert made.status_code == 201 and made.json["currency"] == "USD" and made.json["amount_minor"] == 2500
    assert _item(c, h, cadence="weekly").status_code == 422
    assert _item(c, h, amount_minor=-5).status_code == 422
    assert _item(c, h, start_on="2026-05-01", end_on="2026-04-01").status_code == 422
    listing = c.get(f"{PREFIX}/opex/items", headers=h).json
    assert len(listing["items"]) == 1 and "Hosting" in listing["categories"] and "People" in listing["categories"]


def test_a_line_can_be_changed_ended_and_deleted_and_the_grid_follows(api: Flask) -> None:
    c, h = _admin(api, "ox2")
    item = _item(c, h).json
    year = c.get(f"{PREFIX}/opex/monthly?year=2026", headers=h).json
    assert year["total"] == 12 * 2500 and year["categories"][0]["months"][0] == 2500
    ended = c.patch(f"{PREFIX}/opex/items/{item['id']}", json={"end_on": "2026-06-30", "amount_minor": 3000}, headers=h)
    assert ended.status_code == 200 and ended.json["end_on"] == "2026-06-30"
    assert c.get(f"{PREFIX}/opex/monthly?year=2026", headers=h).json["total"] == 6 * 3000
    reopened = c.patch(f"{PREFIX}/opex/items/{item['id']}", json={"clear": ["end_on"]}, headers=h)
    assert reopened.json["end_on"] is None
    assert c.patch(f"{PREFIX}/opex/items/{item['id']}", json={"clear": ["name"]}, headers=h).status_code == 422
    assert c.delete(f"{PREFIX}/opex/items/{item['id']}", headers=h).status_code == 200
    assert c.get(f"{PREFIX}/opex/monthly?year=2026", headers=h).json["total"] == 0
    assert c.delete(f"{PREFIX}/opex/items/{item['id']}", headers=h).status_code == 404


def test_the_year_is_checked_and_the_csv_has_a_total_row(api: Flask) -> None:
    c, h = _admin(api, "ox3")
    _item(c, h)
    assert c.get(f"{PREFIX}/opex/monthly?year=1900", headers=h).status_code == 422
    csv_text = c.get(f"{PREFIX}/opex/export.csv?year=2026", headers=h).get_data(as_text=True)
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("Category,Jan,Feb") and lines[1].startswith("Hosting,25.00") and lines[-1].endswith("300.00")


def test_the_forecast_runs_month_by_month_with_churn_break_even_and_runway():
    line = _line(amount=1000, start=(2026, 1, 1))
    flat = opex.forecast([line], year=2026, month=1, months=4, base_monthly=1500, new_per_month=0, revenue_per_square=0, churn_pct=0, opening_cash=2000)
    assert [r["revenue"] for r in flat["months"]] == [1500] * 4 and flat["break_even"] == "2026-01" and flat["runway_months"] is None
    assert flat["months"][-1]["cash"] == 2000 + 4 * 500
    falling = opex.forecast([line], year=2026, month=1, months=6, base_monthly=900, new_per_month=0, revenue_per_square=0, churn_pct=10, opening_cash=500)
    assert falling["break_even"] is None and falling["runway_months"] is not None and falling["months"][0]["revenue"] == 810
    growing = opex.forecast([line], year=2026, month=1, months=12, base_monthly=0, new_per_month=2, revenue_per_square=400, churn_pct=0, opening_cash=0)
    assert growing["break_even"] == "2026-02" and growing["total_revenue"] == sum(800 * (i + 1) for i in range(12))
    assert opex.add_months(2026, 11, 3) == (2027, 2)


def test_forecast_endpoints_are_admin_only_and_the_assumptions_are_remembered(api: Flask) -> None:
    c, h, _ = _square(api, "ox4")
    assert c.get(f"{PREFIX}/opex/forecast", headers=h).status_code == 404 and c.get(f"{PREFIX}/opex/assumptions", headers=h).status_code == 404
    c = as_admin(api, c)
    _item(c, h, amount_minor=1000, start_on="2020-01-01")
    first = c.get(f"{PREFIX}/opex/forecast?months=6", headers=h)
    assert first.status_code == 200 and len(first.json["months"]) == 6 and first.json["months"][0]["cost"] == 1000 and first.json["scenario"] == "base"
    assert (
        c.get(f"{PREFIX}/opex/forecast?scenario=wild", headers=h).status_code == 422
        and c.get(f"{PREFIX}/opex/forecast?months=99", headers=h).status_code == 422
    )
    mine = {s: {"new_per_month": 3.5, "churn_pct": 1.5, "revenue_per_square_minor": 2000} for s in ("low", "base", "high")}
    saved = c.put(f"{PREFIX}/opex/assumptions", json={"opening_cash_minor": 50000, "scenarios": mine}, headers=h)
    assert saved.status_code == 200 and saved.json["opening_cash_minor"] == 50000 and saved.json["scenarios"]["base"]["new_per_month"] == 3.5
    assert c.put(f"{PREFIX}/opex/assumptions", json={"opening_cash_minor": 0, "scenarios": {"base": mine["base"]}}, headers=h).status_code == 422
    after = c.get(f"{PREFIX}/opex/forecast?months=3", headers=h).json
    assert after["revenue_per_square_used"] == 2000 and after["months"][0]["revenue"] == 7000 and after["months"][0]["cash"] == 50000 + 7000 - 1000


def test_a_variable_line_follows_the_money_received_and_a_recorded_amount_replaces_the_plan():
    fee = SimpleNamespace(id="fee", category="Payment fees", amount_minor=0, cadence="monthly", start_on=dt.date(2026, 1, 1), end_on=None,
                          annual_increase_pct=0,
                          cost_type="variable", variable_bp=290, variable_fixed_minor=30)  # fmt: skip
    ctx = opex.Context({"2026-03": 100_000}, {"2026-03": 4})
    assert opex.line_amount(fee, 2026, 3, ctx) == round(100_000 * 0.029) + 4 * 30 and opex.line_amount(fee, 2026, 4, ctx) == 0
    hosting = _line()
    hosting.id = "host"
    real = opex.Context(actuals={("host", "2026-04"): 1800})
    assert opex.line_amount(hosting, 2026, 4, real) == 1800 and opex.line_amount(hosting, 2026, 4, real, planned=True) == 1000
    report = opex.monthly_report([hosting], 2026, real)
    assert report["totals"][3] == 1800 and report["planned_totals"][3] == 1000
    ahead = opex.forecast([fee], year=2026, month=1, months=2, base_monthly=10_000, new_per_month=0, revenue_per_square=2_000, churn_pct=0, opening_cash=0)
    assert ahead["months"][0]["cost"] == round(10_000 * 0.029) + 5 * 30


def test_variable_lines_and_recorded_amounts_through_the_api(api: Flask) -> None:
    c, h = _admin(api, "ox5")
    fixed = _item(c, h, start_on="2026-01-01").json
    var = _item(c, h, name="Stripe fee", category="Payment fees", amount_minor=0, cost_type="variable", variable_bp=290, variable_fixed_minor=30)
    assert var.status_code == 201 and var.json["cost_type"] == "variable" and var.json["variable_bp"] == 290
    assert _item(c, h, variable_bp=20000).status_code == 422
    put = c.put(f"{PREFIX}/opex/actuals", json={"item_id": fixed["id"], "month": "2026-02", "amount_minor": 4000}, headers=h)
    assert put.status_code == 200 and put.json["item_name"] == "Render"
    again = c.put(f"{PREFIX}/opex/actuals", json={"item_id": fixed["id"], "month": "2026-02", "amount_minor": 4100}, headers=h)
    assert again.status_code == 200 and len(c.get(f"{PREFIX}/opex/actuals", headers=h).json["actuals"]) == 1
    year = c.get(f"{PREFIX}/opex/monthly?year=2026", headers=h).json
    assert year["totals"][1] == 4100 and year["planned_totals"][1] == 2500
    assert c.put(f"{PREFIX}/opex/actuals", json={"item_id": var.json["id"], "month": "2026-02", "amount_minor": 1}, headers=h).status_code == 422
    assert c.put(f"{PREFIX}/opex/actuals", json={"item_id": fixed["id"], "month": "2026-13", "amount_minor": 1}, headers=h).status_code == 422
    gone = c.delete(f"{PREFIX}/opex/actuals/{put.json['id']}", headers=h)
    assert gone.status_code == 200 and c.get(f"{PREFIX}/opex/actuals", headers=h).json["actuals"] == []
    assert c.get(f"{PREFIX}/opex/forecast?months=2", headers=h).status_code == 200


def test_rates_are_fetched_on_demand_kept_typed_by_hand_and_admin_only(api: Flask, monkeypatch) -> None:
    from app.platform import opex_rates

    c, h, _ = _square(api, "ox6")
    assert c.get(f"{PREFIX}/opex/rates", headers=h).status_code == 404 and c.post(f"{PREFIX}/opex/rates/refresh", headers=h).status_code == 404
    c = as_admin(api, c)
    assert c.get(f"{PREFIX}/opex/rates", headers=h).json["rates"] == []
    monkeypatch.setattr(opex_rates, "fetch_rates", lambda: ({"NOK": 10.5, "INR": 84.25}, "2026-10-19"))
    got = c.post(f"{PREFIX}/opex/rates/refresh", headers=h).json["rates"]
    assert {r["code"]: (r["rate"], r["date"], r["source"]) for r in got} == {
        "NOK": (10.5, "2026-10-19", "frankfurter"),
        "INR": (84.25, "2026-10-19", "frankfurter"),
    }
    typed = c.put(f"{PREFIX}/opex/rates", json={"code": "NOK", "rate": 11}, headers=h).json["rates"]
    assert {r["code"]: (r["rate"], r["source"]) for r in typed}["NOK"] == (11.0, "manual")
    assert c.put(f"{PREFIX}/opex/rates", json={"code": "EUR", "rate": 1}, headers=h).status_code == 422
    assert c.put(f"{PREFIX}/opex/rates", json={"code": "NOK", "rate": 0}, headers=h).status_code == 422

    def down():
        raise opex_rates.RatesUnavailableError("down")

    monkeypatch.setattr(opex_rates, "fetch_rates", down)
    assert c.post(f"{PREFIX}/opex/rates/refresh", headers=h).status_code == 422
