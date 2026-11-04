"""The general book of Accounting (W14-R15, ADR 066): expenses that belong to no event, and the income of the modules that take money without one.

A square without the Events module still has money to follow: costs (rent, printing) and gifts and membership payments. The general book shows exactly that:
income is worked out live from the Donations and Memberships modules (only while those modules are on; their data is never copied), expenses are the
ordinary `expenses` rows with an empty `event_id`. Ticket income stays in each event's own book (Collections), so nothing is counted twice.
Expense edit, delete and receipts are the existing routes by expense id.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from flask import Response, g, jsonify, request

from app.accounting.admin_routes import (
    MAX_PER_PAGE,
    _filtered_expenses_stmt,
    _serialize_expense,
    _validate_expense_payload,
    admin_accounting_bp,
)
from app.accounting.models import Expense, GeneralIncome
from app.accounting.report_pdf import build_general_report_pdf
from app.common.site import site_currency
from app.extensions import db
from app.imports.excel import write_xlsx_sheets
from app.lookups.service import label_for
from app.audit.service import log_action
from app.auth.models import User
from app.modules import module_enabled
from app.payments.models import Payment

SOURCE_LABELS = {"donation": "Donations", "membership": "Membership payments", "manual": "Added by hand"}


def _day(value: datetime | None) -> date | None:
    return value.date() if value else None


def _range() -> tuple[date | None, date | None]:
    """date_from / date_to from the query string; a bad date raises ValueError."""
    out = []
    for name in ("date_from", "date_to"):
        raw = request.args.get(name)
        try:
            out.append(datetime.strptime(raw, "%Y-%m-%d").date() if raw else None)
        except ValueError:
            raise ValueError(f"{name} must be YYYY-MM-DD") from None
    return out[0], out[1]


def income_rows(date_from: date | None, date_to: date | None) -> list[dict]:
    """Paid gifts and paid membership payments, newest first. A module that is off contributes nothing (its data stays in the database)."""
    rows: list[dict] = []
    if module_enabled("donations"):
        from app.donations.models import Donation

        for d in Donation.query.filter_by(status="paid").all():
            rows.append({"source": "donation", "reference": d.reference, "name": "Anonymous" if d.anonymous else d.donor_name, "date": _day(d.paid_at or d.created_at), "amount": d.amount})
    if module_enabled("memberships"):
        for p in Payment.query.filter_by(payment_type="membership", status="paid").all():
            # the Vipps app fee is paid by the member on top and is not the square's income
            rows.append({"source": "membership", "reference": p.payment_reference, "name": None, "date": _day(p.paid_at or p.created_at), "amount": p.amount - (p.surcharge_amount or 0)})
    for m in GeneralIncome.query.all():  # typed in by an admin (W15-R16): always part of the book, whatever modules are on
        rows.append({"source": "manual", "id": m.id, "reference": m.description, "name": m.source_name, "date": m.date, "amount": m.amount, "notes": m.notes})
    rows = [r for r in rows if r["date"] and (date_from is None or r["date"] >= date_from) and (date_to is None or r["date"] <= date_to)]
    rows.sort(key=lambda r: (r["date"], r["reference"] or ""), reverse=True)
    return [{**r, "date": r["date"].isoformat()} for r in rows]


@admin_accounting_bp.get("/general")
def admin_accounting_general_summary():
    try:
        date_from, date_to = _range()
        stmt = _filtered_expenses_stmt(None)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    expenses = db.session.scalars(stmt).all()
    by_category: dict[str, int] = {}
    for e in expenses:
        by_category[e.category] = by_category.get(e.category, 0) + e.amount
    income = income_rows(date_from, date_to)
    by_source: dict[str, dict] = {}
    for row in income:
        entry = by_source.setdefault(row["source"], {"source": row["source"], "label": SOURCE_LABELS[row["source"]], "count": 0, "total": 0})
        entry["count"] += 1
        entry["total"] += row["amount"]
    income_total = sum(r["amount"] for r in income)
    expense_total = sum(e.amount for e in expenses)
    return jsonify(
        {
            "currency": site_currency(),
            "income": {"total": income_total, "by_source": list(by_source.values())},
            "expenses": {
                "total": expense_total,
                "count": len(expenses),
                "by_category": [{"category": c, "label": label_for("expense_category", c), "total": t} for c, t in sorted(by_category.items(), key=lambda kv: -kv[1])],
            },
            "net": income_total - expense_total,
        }
    )


@admin_accounting_bp.get("/general/income")
def admin_accounting_general_income():
    try:
        date_from, date_to = _range()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"items": income_rows(date_from, date_to)})


def _validate_income(data: dict, *, is_create: bool) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}
    for field in ("date", "description", "amount"):
        if is_create and data.get(field) in (None, ""):
            errors[field] = "This field is required."
    if "date" in data and "date" not in errors:
        try:
            cleaned["date"] = datetime.strptime(data["date"], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            errors["date"] = "Must be a valid date (YYYY-MM-DD)."
    if "description" in data and "description" not in errors:
        value = data["description"]
        if not isinstance(value, str) or not value.strip():
            errors["description"] = "This field is required."
        elif len(value) > 300:
            errors["description"] = "Must be at most 300 characters."
        else:
            cleaned["description"] = value.strip()
    if "amount" in data and "amount" not in errors:
        value = data["amount"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            errors["amount"] = "Must be a number greater than zero."
        else:
            cleaned["amount"] = int(value)
    for field, limit in (("source_name", 200), ("notes", 2000)):
        if field in data:
            value = data[field]
            if value is None or value == "":
                cleaned[field] = None
            elif not isinstance(value, str):
                errors[field] = "Must be a string or null."
            elif len(value) > limit:
                errors[field] = f"Must be at most {limit} characters."
            else:
                cleaned[field] = value.strip()
    return cleaned, errors


def _serialize_income(row: GeneralIncome) -> dict:
    return {"id": row.id, "date": row.date.isoformat(), "description": row.description, "amount": row.amount, "source_name": row.source_name, "notes": row.notes}


@admin_accounting_bp.post("/general/manual-income")
def admin_accounting_general_create_income():
    cleaned, errors = _validate_income(request.get_json(silent=True) or {}, is_create=True)
    if errors:
        return jsonify({"errors": errors}), 400
    row = GeneralIncome(created_by=g.current_user.id, **cleaned)
    db.session.add(row)
    db.session.commit()
    return jsonify(_serialize_income(row)), 201


@admin_accounting_bp.patch("/general/manual-income/<int:income_id>")
def admin_accounting_general_update_income(income_id: int):
    row = db.session.get(GeneralIncome, income_id)
    if row is None:
        return jsonify({"error": "Income not found"}), 404
    cleaned, errors = _validate_income(request.get_json(silent=True) or {}, is_create=False)
    if errors:
        return jsonify({"errors": errors}), 400
    for field, value in cleaned.items():
        setattr(row, field, value)
    db.session.commit()
    return jsonify(_serialize_income(row))


@admin_accounting_bp.delete("/general/manual-income/<int:income_id>")
def admin_accounting_general_delete_income(income_id: int):
    row = db.session.get(GeneralIncome, income_id)
    if row is None:
        return jsonify({"error": "Income not found"}), 404
    db.session.delete(row)
    db.session.commit()
    log_action(g.current_user, "income_deleted", "Deleted income from the general accounts", target_type="general_income", target_id=income_id)
    return "", 204


@admin_accounting_bp.get("/general/expenses")
def admin_accounting_general_expenses():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    try:
        stmt = _filtered_expenses_stmt(None)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    pagination = db.paginate(stmt.order_by(Expense.date.desc(), Expense.id.desc()), page=page, per_page=min(per_page, MAX_PER_PAGE), error_out=False)
    return jsonify(
        {
            "items": [_serialize_expense(e) for e in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_accounting_bp.post("/general/expenses")
def admin_accounting_general_create_expense():
    cleaned, errors = _validate_expense_payload(request.get_json(silent=True) or {}, is_create=True)
    if errors:
        return jsonify({"errors": errors}), 400
    expense = Expense(
        event_id=None,
        date=cleaned["date"],
        description=cleaned["description"],
        category=cleaned["category"],
        amount=cleaned["amount"],
        vendor=cleaned.get("vendor"),
        notes=cleaned.get("notes"),
        created_by=g.current_user.id,
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify(_serialize_expense(expense)), 201


@admin_accounting_bp.get("/general/report")
def admin_accounting_general_report():
    """The general book as one PDF, narrowed by the same date range as the page (W15-R17). Receipts are only marked Yes/No."""
    try:
        date_from, date_to = _range()
        stmt = _filtered_expenses_stmt(None)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    expenses = db.session.scalars(stmt.order_by(Expense.date.asc(), Expense.id.asc())).all()
    income = list(reversed(income_rows(date_from, date_to)))
    for r in income:
        r["source_label"] = SOURCE_LABELS[r["source"]]
    by_source: dict[str, dict] = {}
    for r in income:
        entry = by_source.setdefault(r["source"], {"label": SOURCE_LABELS[r["source"]], "count": 0, "total": 0})
        entry["count"] += 1
        entry["total"] += r["amount"]
    if date_from and date_to:
        period = f"{date_from.isoformat()} to {date_to.isoformat()}"
    elif date_from or date_to:
        period = f"from {date_from.isoformat()}" if date_from else f"until {date_to.isoformat()}"
    else:
        period = "All time"
    budget = None
    income_targets = None
    if date_from and date_to and date_from == date(date_from.year, 1, 1) and date_to == date(date_from.year, 12, 31):
        from app.accounting.budget import budget_rows

        rows = [r for r in budget_rows(date_from.year) if r["budget"] or r["spent"]]
        budget = rows if any(r["budget"] for r in rows) else None  # a year without any budget has no budget section
        from app.accounting.budget import income_target_rows

        targets = [r for r in income_target_rows(date_from.year) if r["target"] or r["received"]]
        income_targets = targets if any(r["target"] for r in targets) else None
    data = build_general_report_pdf(
        budget=budget,
        income_targets=income_targets,
        period_label=period,
        income=income,
        expenses=[
            {"date": e.date.isoformat(), "description": e.description, "category": e.category, "amount": e.amount, "vendor": e.vendor, "notes": e.notes, "receipt_key": e.receipt_key}
            for e in expenses
        ],
        income_by_source=list(by_source.values()),
        category_label=lambda value: label_for("expense_category", value),
        generated_at=datetime.now(timezone.utc),
    )
    return Response(data, mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=general-accounts-report.pdf"})


@admin_accounting_bp.get("/general/export")
def admin_accounting_general_export():
    """Income and expenses of the general book in one sheet pair, narrowed by the same date range; money in plain currency units like every export."""
    try:
        date_from, date_to = _range()
        stmt = _filtered_expenses_stmt(None)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    expenses = db.session.scalars(stmt.order_by(Expense.date.asc(), Expense.id.asc())).all()
    expense_rows = []
    for e in expenses:
        creator = db.session.get(User, e.created_by) if e.created_by else None
        expense_rows.append([e.date.isoformat(), e.description, label_for("expense_category", e.category), e.vendor, e.amount / 100, "Yes" if e.receipt_key else "No", e.notes, creator.email if creator else None])
    if expense_rows:
        expense_rows.append(["Total", None, None, None, sum(e.amount for e in expenses) / 100, None, None, None])
    income = list(reversed(income_rows(date_from, date_to)))
    income_sheet = [[r["date"], SOURCE_LABELS[r["source"]], r["reference"], r["name"], r["amount"] / 100] for r in income]
    if income_sheet:
        income_sheet.append(["Total", None, None, None, sum(r["amount"] for r in income) / 100])
    data = write_xlsx_sheets(
        [
            ("Income", ["Date", "Source", "Reference", "Name", f"Amount ({site_currency()})"], income_sheet),
            ("Expenses", ["Date", "Description", "Category", "Vendor", f"Amount ({site_currency()})", "Receipt attached", "Notes", "Added by"], expense_rows),
        ]
    )
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=general-accounts.xlsx"},
    )
