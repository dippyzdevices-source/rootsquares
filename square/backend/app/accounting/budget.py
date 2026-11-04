"""Yearly budgets of the general book (W15-R18): how much the square plans to spend on each expense category in a year, next to what it has spent.

Only expenses of the general book (no event) count as spent; an event's own costs stay in that event's accounts. A budget of 0 is not stored (the row is removed).
"""

from __future__ import annotations

from datetime import date

from flask import g, jsonify, request
from sqlalchemy import func

from app.accounting.admin_routes import admin_accounting_bp
from app.accounting.models import Expense, GeneralBudget, GeneralIncomeTarget
from app.common.site import site_currency
from app.extensions import db
from app.lookups.service import active_values, all_values, label_for
from app.modules import module_enabled

MAX_BUDGET = 2_000_000_000  # minor units; keeps the number inside a 32-bit column


def budget_rows(year: int) -> list[dict]:
    """One row per expense category that has a budget or spending in the year, or is offered in the list: budget, spent, what is left (may be negative)."""
    spent = dict(
        db.session.query(Expense.category, func.sum(Expense.amount))
        .filter(Expense.event_id.is_(None), Expense.date >= date(year, 1, 1), Expense.date <= date(year, 12, 31))
        .group_by(Expense.category)
        .all()
    )
    budgets = {b.category: b.amount for b in GeneralBudget.query.filter_by(year=year).all()}
    categories = list(dict.fromkeys([*active_values("expense_category"), *spent, *budgets]))
    rows = []
    for category in categories:
        budget = budgets.get(category, 0)
        used = int(spent.get(category, 0) or 0)
        rows.append({"category": category, "label": label_for("expense_category", category), "budget": budget, "spent": used, "remaining": budget - used})
    return rows


def income_target_rows(year: int) -> list[dict]:
    """One row per income source offered in the year (a module that is off offers none, unless it already has a target or income): target, received, still to raise (negative = beaten)."""
    from app.accounting.general import SOURCE_LABELS, income_rows

    received: dict[str, int] = {}
    for r in income_rows(date(year, 1, 1), date(year, 12, 31)):
        received[r["source"]] = received.get(r["source"], 0) + r["amount"]
    targets = {t.source: t.amount for t in GeneralIncomeTarget.query.filter_by(year=year).all()}
    offered = [s for s, module in (("donation", "donations"), ("membership", "memberships"), ("manual", None)) if module is None or module_enabled(module)]
    sources = list(dict.fromkeys([*offered, *received, *targets]))
    return [
        {"source": s, "label": SOURCE_LABELS[s], "target": targets.get(s, 0), "received": received.get(s, 0), "remaining": targets.get(s, 0) - received.get(s, 0)}
        for s in sources
    ]


def _year_arg() -> int | None:
    try:
        year = int(request.args.get("year", ""))
    except ValueError:
        return None
    return year if 2000 <= year <= 2200 else None


@admin_accounting_bp.get("/general/budget")
def admin_accounting_general_budget():
    year = _year_arg()
    if year is None:
        return jsonify({"error": "year must be a year such as 2026"}), 400
    rows = budget_rows(year)
    income = income_target_rows(year)
    budget_total = sum(r["budget"] for r in rows)
    target_total = sum(r["target"] for r in income)
    return jsonify(
        {
            "year": year,
            "currency": site_currency(),
            "items": rows,
            "budget_total": budget_total,
            "spent_total": sum(r["spent"] for r in rows),
            "income": income,
            "income_target_total": target_total,
            "income_received_total": sum(r["received"] for r in income),
            "planned_net": target_total - budget_total,  # what the square plans to keep: income target minus expense budget
        }
    )


@admin_accounting_bp.put("/general/budget")
def admin_accounting_general_set_budget():
    data = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}
    year = data.get("year")
    if isinstance(year, bool) or not isinstance(year, int) or not 2000 <= year <= 2200:
        errors["year"] = "Must be a year such as 2026."
    category = data.get("category")
    if category not in all_values("expense_category"):
        errors["category"] = "Choose an expense category."
    amount = data.get("amount", 0)
    if amount is None:
        amount = 0
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0 or amount > MAX_BUDGET:
        errors["amount"] = "Must be a number, zero or more."
    if errors:
        return jsonify({"errors": errors}), 400
    row = GeneralBudget.query.filter_by(year=year, category=category).first()
    if int(amount) == 0:
        if row is not None:
            db.session.delete(row)
    elif row is None:
        db.session.add(GeneralBudget(year=year, category=category, amount=int(amount), created_by=g.current_user.id))
    else:
        row.amount = int(amount)
    db.session.commit()
    return jsonify({"year": year, "category": category, "amount": int(amount)})



@admin_accounting_bp.put("/general/budget/income")
def admin_accounting_general_set_income_target():
    from app.accounting.general import SOURCE_LABELS

    data = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}
    year = data.get("year")
    if isinstance(year, bool) or not isinstance(year, int) or not 2000 <= year <= 2200:
        errors["year"] = "Must be a year such as 2026."
    source = data.get("source")
    if source not in SOURCE_LABELS:
        errors["source"] = "Choose an income source."
    amount = data.get("amount", 0)
    if amount is None:
        amount = 0
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0 or amount > MAX_BUDGET:
        errors["amount"] = "Must be a number, zero or more."
    if errors:
        return jsonify({"errors": errors}), 400
    row = GeneralIncomeTarget.query.filter_by(year=year, source=source).first()
    if int(amount) == 0:
        if row is not None:
            db.session.delete(row)
    elif row is None:
        db.session.add(GeneralIncomeTarget(year=year, source=source, amount=int(amount), created_by=g.current_user.id))
    else:
        row.amount = int(amount)
    db.session.commit()
    return jsonify({"year": year, "source": source, "amount": int(amount)})



@admin_accounting_bp.post("/general/budget/copy")
def admin_accounting_general_copy_budget():
    """Copies the expense budgets and income targets of the year before into a year, filling only what that year has not set (nothing is overwritten)."""
    data = request.get_json(silent=True) or {}
    year = data.get("year")
    if isinstance(year, bool) or not isinstance(year, int) or not 2001 <= year <= 2200:
        return jsonify({"errors": {"year": "Must be a year such as 2026."}}), 400
    copied = {"budgets": 0, "targets": 0}
    have = {b.category for b in GeneralBudget.query.filter_by(year=year).all()}
    for b in GeneralBudget.query.filter_by(year=year - 1).all():
        if b.category not in have:
            db.session.add(GeneralBudget(year=year, category=b.category, amount=b.amount, created_by=g.current_user.id))
            copied["budgets"] += 1
    have_sources = {t.source for t in GeneralIncomeTarget.query.filter_by(year=year).all()}
    for t in GeneralIncomeTarget.query.filter_by(year=year - 1).all():
        if t.source not in have_sources:
            db.session.add(GeneralIncomeTarget(year=year, source=t.source, amount=t.amount, created_by=g.current_user.id))
            copied["targets"] += 1
    db.session.commit()
    return jsonify({"year": year, "from_year": year - 1, **copied})
