"""Platform routes of the owner's running costs (W16-R9, docs/plans/opex-plan.md): cost lines, the year grid, a CSV.

Platform admins only. The handlers are registered on the platform blueprint by `register()` (called at the end of routes.py).
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import uuid
from typing import Any, Literal

from flask import Response, g, jsonify, request
from pydantic import BaseModel, Field
from spectree import Response as SpecResponse
from sqlalchemy import select

from app.platform import opex, opex_forecast, opex_rates
from app.platform.models import OpexActual, OpexItem
from app.shared.db import get_session
from app.shared.errors import NotFoundError, ValidationFailedError

Cadence = Literal["monthly", "quarterly", "yearly", "one_off"]


class OpexItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    amount_minor: int = Field(ge=0, le=100_000_000_00)
    cadence: Cadence
    start_on: dt.date
    end_on: dt.date | None = None
    annual_increase_pct: int = Field(default=0, ge=0, le=100)
    vendor: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    cost_type: Literal["fixed", "variable"] = "fixed"
    variable_bp: int = Field(default=0, ge=0, le=10000)  # share of revenue in hundredths of a percent, for a variable line
    variable_fixed_minor: int = Field(default=0, ge=0, le=1_000_000)  # per paid order, for a variable line


class OpexItemPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=60)
    amount_minor: int | None = Field(default=None, ge=0, le=100_000_000_00)
    cadence: Cadence | None = None
    start_on: dt.date | None = None
    end_on: dt.date | None = None
    annual_increase_pct: int | None = Field(default=None, ge=0, le=100)
    vendor: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=500)
    cost_type: Literal["fixed", "variable"] | None = None
    variable_bp: int | None = Field(default=None, ge=0, le=10000)
    variable_fixed_minor: int | None = Field(default=None, ge=0, le=1_000_000)
    clear: list[str] = Field(default_factory=list)  # fields to empty: end_on, vendor, note


class OpexItemOut(OpexItemIn):
    id: uuid.UUID
    currency: str
    created_at: dt.datetime


class OpexItemList(BaseModel):
    items: list[OpexItemOut]
    categories: list[str]  # the usual ones plus the ones already used, for the form


class OpexCategoryRow(BaseModel):
    name: str
    months: list[int]
    total: int


class OpexMonthly(BaseModel):
    year: int
    planned_totals: list[int]
    currency: str
    categories: list[OpexCategoryRow]
    totals: list[int]
    total: int
    previous_totals: list[int]
    previous_total: int


class ScenarioIn(BaseModel):
    new_per_month: float = Field(ge=0, le=1000)
    churn_pct: float = Field(ge=0, le=100)
    revenue_per_square_minor: int | None = Field(default=None, ge=0, le=100_000_000)  # empty = the average of what squares pay now


class AssumptionsIn(BaseModel):
    opening_cash_minor: int = Field(ge=-100_000_000_00, le=100_000_000_00)
    scenarios: dict[str, ScenarioIn]


class ForecastMonth(BaseModel):
    month: str
    cost: int
    revenue: int
    net: int
    cash: int


class ActualMonth(BaseModel):
    month: str
    revenue: int


class OpexForecast(BaseModel):
    scenario: str
    currency: str
    months: list[ForecastMonth]
    actuals: list[ActualMonth]
    break_even: str | None
    runway_months: int | None
    total_cost: int
    total_revenue: int
    renewing_monthly: int  # what already renews, per month
    paying_squares: int
    assumptions: AssumptionsIn
    revenue_per_square_used: int


class RateOut(BaseModel):
    code: str
    rate: float  # units of this currency for one US dollar
    date: str
    source: str  # frankfurter | manual


class RateList(BaseModel):
    rates: list[RateOut]


class RateIn(BaseModel):
    code: str
    rate: float = Field(gt=0, le=100000)


class ActualIn(BaseModel):
    item_id: uuid.UUID
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount_minor: int = Field(ge=0, le=100_000_000_00)


class ActualOut(ActualIn):
    id: uuid.UUID
    item_name: str


class ActualList(BaseModel):
    actuals: list[ActualOut]


CLEARABLE = ("end_on", "vendor", "note")


def _bad(field: str, message: str) -> ValidationFailedError:
    return ValidationFailedError("Check the cost line", errors=[{"loc": [field], "msg": message, "type": "value_error"}])


def _out(i: OpexItem) -> OpexItemOut:
    return OpexItemOut(
        id=i.id, name=i.name, category=i.category, amount_minor=i.amount_minor, currency=i.currency, cadence=i.cadence,
        start_on=i.start_on, end_on=i.end_on, annual_increase_pct=i.annual_increase_pct, vendor=i.vendor, note=i.note, created_at=i.created_at,
        cost_type=i.cost_type, variable_bp=i.variable_bp, variable_fixed_minor=i.variable_fixed_minor,
    )  # fmt: skip


def register() -> None:
    from app.platform import routes as R

    bp, api = R.bp, R.api

    def _get(db: Any, item_id: uuid.UUID) -> OpexItem:
        item: OpexItem | None = db.get(OpexItem, item_id)
        if item is None:
            raise NotFoundError("Cost line not found")
        return item

    def _check_dates(start: dt.date, end: dt.date | None) -> None:
        if end is not None and end < start:
            raise _bad("end_on", "The end cannot be before the start.")

    @bp.get("/opex/items")
    @api.validate(resp=SpecResponse(HTTP_200=OpexItemList), tags=["opex"])
    @R.admin_required
    def list_opex_items() -> Response:
        db = get_session()
        rows = db.scalars(select(OpexItem).order_by(OpexItem.category, OpexItem.name)).all()
        used = {r.category for r in rows}
        return R._out(OpexItemList(items=[_out(r) for r in rows], categories=sorted(set(opex.DEFAULT_CATEGORIES) | used)))

    @bp.post("/opex/items")
    @api.validate(json=OpexItemIn, resp=SpecResponse(HTTP_201=OpexItemOut), tags=["opex"])
    @R.admin_required
    def create_opex_item() -> Response:
        body: OpexItemIn = request.context.json  # type: ignore[attr-defined]
        _check_dates(body.start_on, body.end_on)
        db = get_session()
        item = OpexItem(**body.model_dump(), created_by=g.user_id)
        item.category = item.category.strip()
        db.add(item)
        db.flush()
        R._audit("opex.created", "opex_item", str(item.id), None, name=item.name, category=item.category)
        db.commit()
        return R._out(_out(item), 201)

    @bp.patch("/opex/items/<uuid:item_id>")
    @api.validate(json=OpexItemPatch, resp=SpecResponse(HTTP_200=OpexItemOut), tags=["opex"])
    @R.admin_required
    def update_opex_item(item_id: uuid.UUID) -> Response:
        body: OpexItemPatch = request.context.json  # type: ignore[attr-defined]
        db = get_session()
        item = _get(db, item_id)
        data = body.model_dump(exclude_unset=True, exclude={"clear"})
        for field in body.clear:
            if field not in CLEARABLE:
                raise _bad(field, "This field cannot be emptied.")
            data[field] = None
        for field, value in data.items():
            if value is None and field not in CLEARABLE:
                continue
            setattr(item, field, value)
        _check_dates(item.start_on, item.end_on)
        R._audit("opex.updated", "opex_item", str(item.id), None, name=item.name, fields=sorted(data))
        db.commit()
        return R._out(_out(item))

    @bp.delete("/opex/items/<uuid:item_id>")
    @R.admin_required
    def delete_opex_item(item_id: uuid.UUID) -> Response:
        db = get_session()
        item = _get(db, item_id)
        R._audit("opex.deleted", "opex_item", str(item.id), None, name=item.name)
        db.delete(item)
        db.commit()
        return jsonify({"deleted": True})

    def _year() -> int:
        raw = request.args.get("year", "")
        year = int(raw) if raw.isdigit() else dt.date.today().year
        if not 2000 <= year <= 2100:
            raise _bad("year", "Choose a year between 2000 and 2100.")
        return year

    @bp.get("/opex/monthly")
    @api.validate(resp=SpecResponse(HTTP_200=OpexMonthly), tags=["opex"])
    @R.admin_required
    def opex_monthly() -> Response:
        rows = get_session().scalars(select(OpexItem)).all()
        return R._out(OpexMonthly(currency="USD", **opex.monthly_report(rows, _year(), opex_forecast.context(get_session()))))

    @bp.get("/opex/export.csv")
    @R.admin_required
    def opex_export() -> Response:
        year = _year()
        report = opex.monthly_report(get_session().scalars(select(OpexItem)).all(), year, opex_forecast.context(get_session()))
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["Category", *[dt.date(year, m, 1).strftime("%b") for m in range(1, 13)], "Total"])

        def money(minor: int) -> str:
            return f"{minor / 100:.2f}"

        for row in report["categories"]:
            writer.writerow([row["name"], *[money(x) for x in row["months"]], money(row["total"])])
        writer.writerow(["Total", *[money(x) for x in report["totals"]], money(report["total"])])
        return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="opex-{year}.csv"'})

    @bp.get("/opex/assumptions")
    @api.validate(resp=SpecResponse(HTTP_200=AssumptionsIn), tags=["opex"])
    @R.admin_required
    def get_opex_assumptions() -> Response:
        return R._out(AssumptionsIn(**opex_forecast.load_assumptions(get_session())))

    @bp.put("/opex/assumptions")
    @api.validate(json=AssumptionsIn, resp=SpecResponse(HTTP_200=AssumptionsIn), tags=["opex"])
    @R.admin_required
    def put_opex_assumptions() -> Response:
        body: AssumptionsIn = request.context.json  # type: ignore[attr-defined]
        if set(body.scenarios) != set(opex.SCENARIOS):
            raise _bad("scenarios", "Give low, base and high.")
        db = get_session()
        opex_forecast.save_assumptions(db, body.opening_cash_minor, {k: v.model_dump() for k, v in body.scenarios.items()})
        R._audit("opex.assumptions_changed", "opex", "assumptions", None)
        db.commit()
        return R._out(AssumptionsIn(**opex_forecast.load_assumptions(db)))

    @bp.get("/opex/forecast")
    @api.validate(resp=SpecResponse(HTTP_200=OpexForecast), tags=["opex"])
    @R.admin_required
    def opex_forecast_view() -> Response:
        scenario = request.args.get("scenario", "base")
        if scenario not in opex.SCENARIOS:
            raise _bad("scenario", "Choose low, base or high.")
        raw = request.args.get("months", "12")
        months = int(raw) if raw.isdigit() else 12
        if not 1 <= months <= 36:
            raise _bad("months", "Choose between 1 and 36 months.")
        db = get_session()
        today = dt.date.today()
        seen = opex_forecast.observed(db)
        assumptions = opex_forecast.load_assumptions(db)
        s = assumptions["scenarios"][scenario]
        arpu = s["revenue_per_square_minor"]
        if arpu is None:
            arpu = round(seen["base_monthly"] / seen["squares"]) if seen["squares"] else 0
        result = opex.forecast(
            db.scalars(select(OpexItem)).all(), year=today.year, month=today.month, months=months, base_monthly=seen["base_monthly"],
            new_per_month=s["new_per_month"], revenue_per_square=arpu, churn_pct=s["churn_pct"], opening_cash=assumptions["opening_cash_minor"],
            actuals=opex_forecast.context(db).actuals,
        )  # fmt: skip
        return R._out(
            OpexForecast(
                scenario=scenario,
                currency="USD",
                actuals=[ActualMonth(**a) for a in opex_forecast.actual_revenue(db, today.year, today.month)],
                renewing_monthly=seen["base_monthly"],
                paying_squares=seen["squares"],
                assumptions=AssumptionsIn(**assumptions),
                revenue_per_square_used=arpu,
                **result,
            )  # fmt: skip
        )

    def _actual_out(a: OpexActual, name: str) -> ActualOut:
        return ActualOut(id=a.id, item_id=a.item_id, month=a.month, amount_minor=a.amount_minor, item_name=name)

    @bp.get("/opex/actuals")
    @api.validate(resp=SpecResponse(HTTP_200=ActualList), tags=["opex"])
    @R.admin_required
    def list_opex_actuals() -> Response:
        db = get_session()
        names = {i.id: i.name for i in db.scalars(select(OpexItem))}
        rows = db.scalars(select(OpexActual).order_by(OpexActual.month.desc())).all()
        return R._out(ActualList(actuals=[_actual_out(a, names.get(a.item_id, "")) for a in rows]))

    @bp.put("/opex/actuals")
    @api.validate(json=ActualIn, resp=SpecResponse(HTTP_200=ActualOut), tags=["opex"])
    @R.admin_required
    def put_opex_actual() -> Response:
        body: ActualIn = request.context.json  # type: ignore[attr-defined]
        db = get_session()
        item = _get(db, body.item_id)
        if item.cost_type != "fixed":
            raise _bad("item_id", "A variable line is worked out from the money received; record a real amount for a fixed line.")
        row = db.scalars(select(OpexActual).where(OpexActual.item_id == item.id, OpexActual.month == body.month)).first()
        if row is None:
            row = OpexActual(item_id=item.id, month=body.month, amount_minor=body.amount_minor)
            db.add(row)
        else:
            row.amount_minor = body.amount_minor
        db.flush()
        R._audit("opex.actual_recorded", "opex_item", str(item.id), None, name=item.name, month=body.month)
        db.commit()
        return R._out(_actual_out(row, item.name))

    @bp.delete("/opex/actuals/<uuid:actual_id>")
    @R.admin_required
    def delete_opex_actual(actual_id: uuid.UUID) -> Response:
        db = get_session()
        row = db.get(OpexActual, actual_id)
        if row is None:
            raise NotFoundError("Recorded amount not found")
        R._audit("opex.actual_removed", "opex_item", str(row.item_id), None, month=row.month)
        db.delete(row)
        db.commit()
        return jsonify({"deleted": True})

    def _rates() -> RateList:
        loaded = opex_rates.load(get_session())
        return RateList(rates=[RateOut(code=c, **v) for c, v in loaded.items()])

    @bp.get("/opex/rates")
    @api.validate(resp=SpecResponse(HTTP_200=RateList), tags=["opex"])
    @R.admin_required
    def get_opex_rates() -> Response:
        return R._out(_rates())

    @bp.post("/opex/rates/refresh")
    @api.validate(resp=SpecResponse(HTTP_200=RateList), tags=["opex"])
    @R.admin_required
    def refresh_opex_rates() -> Response:
        db = get_session()
        try:
            opex_rates.refresh(db)
        except opex_rates.RatesUnavailableError as exc:
            raise _bad("rates", "The rate service did not answer. Try again later or type a rate yourself.") from exc
        R._audit("opex.rates_refreshed", "opex", "rates", None)
        db.commit()
        return R._out(_rates())

    @bp.put("/opex/rates")
    @api.validate(json=RateIn, resp=SpecResponse(HTTP_200=RateList), tags=["opex"])
    @R.admin_required
    def put_opex_rate() -> Response:
        body: RateIn = request.context.json  # type: ignore[attr-defined]
        if body.code not in opex_rates.CURRENCIES:
            raise _bad("code", "Choose NOK or INR.")
        db = get_session()
        opex_rates.save(db, body.code, body.rate, opex_rates.today(), "manual")
        R._audit("opex.rate_typed", "opex", body.code, None)
        db.commit()
        return R._out(_rates())
