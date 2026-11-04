"""The platform's own running costs (opex): what each cost line adds to a month, and the year grid (W16-R9, docs/plans/opex-plan.md).

Pure functions on anything shaped like an `OpexItem`, so they are tested without a database. Money is integer minor units (US dollars, the billing currency).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any, Protocol

CADENCES = ("monthly", "quarterly", "yearly", "one_off")
_STEP = {"monthly": 1, "quarterly": 3, "yearly": 12}
DEFAULT_CATEGORIES = (
    "Hosting",
    "Database",
    "E-mail",
    "Domains and DNS",
    "Payment fees",
    "Tools and subscriptions",
    "People",
    "Marketing",
    "Legal and accounting",
    "Other",
)


class CostLine(Protocol):
    category: str
    amount_minor: int
    cadence: str
    start_on: dt.date
    end_on: dt.date | None
    annual_increase_pct: int


def _index(year: int, month: int) -> int:
    return year * 12 + month - 1


def amount_in_month(item: CostLine, year: int, month: int) -> int:
    """What the line costs in this month: 0 before it starts, after it ends, or in a month its rhythm skips.

    A yearly rise compounds once a year from the start."""
    start = _index(item.start_on.year, item.start_on.month)
    now = _index(year, month)
    if now < start or (item.end_on is not None and now > _index(item.end_on.year, item.end_on.month)):
        return 0
    gap = now - start
    if item.cadence == "one_off":
        return item.amount_minor if gap == 0 else 0
    if gap % _STEP.get(item.cadence, 1):
        return 0
    if item.annual_increase_pct:
        return round(item.amount_minor * (1 + item.annual_increase_pct / 100) ** (gap // 12))
    return item.amount_minor


class Context:
    """What a month needs besides the line itself: the money received and the paid orders per month ("YYYY-MM") for variable lines, and the real amounts
    the owner recorded, keyed (line id, "YYYY-MM")."""

    def __init__(self, revenue: dict[str, int] | None = None, orders: dict[str, int] | None = None, actuals: dict[tuple[Any, str], int] | None = None) -> None:
        self.revenue = revenue or {}
        self.orders = orders or {}
        self.actuals = actuals or {}


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def line_amount(item: CostLine, year: int, month: int, ctx: Context | None = None, *, planned: bool = False) -> int:
    """One line in one month. A variable line = its share of the month's revenue plus its fixed part for each paid order. A recorded real amount replaces the
    plan of a fixed line unless `planned` asks for the plan itself."""
    ctx = ctx or Context()
    key = month_key(year, month)
    if getattr(item, "cost_type", "fixed") == "variable":
        start = _index(item.start_on.year, item.start_on.month)
        end = _index(item.end_on.year, item.end_on.month) if item.end_on else None
        if _index(year, month) < start or (end is not None and _index(year, month) > end):
            return 0
        return round(ctx.revenue.get(key, 0) * getattr(item, "variable_bp", 0) / 10000) + getattr(item, "variable_fixed_minor", 0) * ctx.orders.get(key, 0)
    if not planned:
        real = ctx.actuals.get((getattr(item, "id", None), key))
        if real is not None:
            return real
    return amount_in_month(item, year, month)


def year_of(items: Iterable[CostLine], year: int, ctx: Context | None = None, *, planned: bool = False) -> dict[str, list[int]]:
    """Category -> twelve month amounts for one year."""
    grid: dict[str, list[int]] = {}
    for item in items:
        row = grid.setdefault(item.category, [0] * 12)
        for m in range(1, 13):
            row[m - 1] += line_amount(item, year, m, ctx, planned=planned)
    return grid


def monthly_report(items: Iterable[CostLine], year: int, ctx: Context | None = None) -> dict[str, Any]:
    """The year grid with totals and the previous year's monthly totals for comparison. `planned_totals` is the same year without the recorded real
    amounts, so the page can show what differs from the plan."""
    lines = list(items)
    grid = year_of(lines, year, ctx)
    before = year_of(lines, year - 1, ctx)
    totals = [sum(row[i] for row in grid.values()) for i in range(12)]
    previous = [sum(row[i] for row in before.values()) for i in range(12)]
    plan = year_of(lines, year, ctx, planned=True)
    return {
        "planned_totals": [sum(row[i] for row in plan.values()) for i in range(12)],
        "year": year,
        "categories": [{"name": name, "months": row, "total": sum(row)} for name, row in sorted(grid.items())],
        "totals": totals,
        "total": sum(totals),
        "previous_totals": previous,
        "previous_total": sum(previous),
    }


# ---- forecast (W16-R9 phase 2)
SCENARIOS = ("low", "base", "high")
# starting guesses until the owner sets his own: new squares per month and churn per month in percent; the revenue per square is read from the real orders
DEFAULT_ASSUMPTIONS: dict[str, dict[str, float]] = {"low": {"new": 1, "churn": 5}, "base": {"new": 2, "churn": 3}, "high": {"new": 4, "churn": 2}}


def add_months(year: int, month: int, n: int) -> tuple[int, int]:
    i = _index(year, month) + n
    return i // 12, i % 12 + 1


def forecast(
    items: Iterable[CostLine],
    *,
    year: int,
    month: int,
    months: int,
    base_monthly: int,
    new_per_month: float,
    revenue_per_square: int,
    churn_pct: float,
    opening_cash: int,
    actuals: dict[tuple[Any, str], int] | None = None,
) -> dict[str, Any]:
    """Month by month ahead, starting with (year, month): costs from the lines, revenue from what already renews (`base_monthly`) plus the new squares of the
    scenario, both thinned by churn each month. Cash starts at `opening_cash`. Break-even = the first month revenue covers the costs; runway = months until cash
    runs out (None = it does not within the horizon)."""
    lines = list(items)
    rows: list[dict[str, Any]] = []
    recurring = float(base_monthly)
    cash = opening_cash
    for step in range(months):
        y, m = add_months(year, month, step)
        recurring = recurring * (1 - churn_pct / 100) + new_per_month * revenue_per_square
        revenue = round(recurring)
        key = month_key(y, m)
        # orders ahead: the revenue over what one square pays (unknown = none); real recorded amounts still win for fixed lines
        ctx = Context({key: revenue}, {key: round(revenue / revenue_per_square) if revenue_per_square else 0}, actuals)
        cost = sum(line_amount(line, y, m, ctx) for line in lines)
        cash += revenue - cost
        rows.append({"month": f"{y:04d}-{m:02d}", "cost": cost, "revenue": revenue, "net": revenue - cost, "cash": cash})
    broke = next((i + 1 for i, r in enumerate(rows) if r["cash"] < 0), None)
    even = next((r["month"] for r in rows if r["revenue"] >= r["cost"] and r["cost"] > 0), None)
    return {
        "months": rows,
        "break_even": even,
        "runway_months": broke - 1 if broke is not None else None,
        "total_cost": sum(r["cost"] for r in rows),
        "total_revenue": sum(r["revenue"] for r in rows),
    }
