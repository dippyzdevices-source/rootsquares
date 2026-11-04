"""Platform routes of vouchers and partners (W14-R27, docs/reference/prices-and-vouchers.md).

Platform admin: create and change vouchers and partners, see redemptions and the partner report. The owner of a square: price a code before paying.
The handlers are registered on the platform blueprint by `register()` (called at the end of routes.py, when every helper it uses exists).
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import Response, current_app, g, request
from spectree import Response as SpecResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.platform import billing as billing_service
from app.platform import plans as square_plans
from app.platform import vouchers as vs
from app.platform.models import BillingOrder, Organization, Partner, Square, Voucher
from app.platform.schemas import (
    CheckoutIn,
    PartnerIn,
    PartnerList,
    PartnerOut,
    PartnerPatch,
    PartnerReport,
    PartnerReportLine,
    RedemptionList,
    RedemptionOut,
    VoucherCheckIn,
    VoucherCheckOut,
    VoucherIn,
    VoucherList,
    VoucherOut,
    VoucherPatch,
    VoucherPreviewIn,
    VoucherSettings,
)
from app.shared.db import get_session
from app.shared.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError


def _bad(field: str, message: str) -> ValidationFailedError:
    return ValidationFailedError("Check the voucher", errors=[{"loc": [field], "msg": message, "type": "value_error"}])


def _clean(data: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    """Validate the fields that were given; returns them ready to store. Raises a 422 that names the field."""
    out = dict(data)
    if "code" in out and out["code"] is not None:
        out["code"] = vs.normalize_code(out["code"])
        if not vs.CODE_RE.match(out["code"]):
            raise _bad("code", "Use 3 to 40 letters, digits or dashes.")
    if creating and not out.get("code"):
        raise _bad("code", "A code is required.")
    if out.get("kind") is not None and out["kind"] not in vs.KINDS:
        raise _bad("kind", "Choose percent or fixed.")
    if out.get("applies_to") is not None and out["applies_to"] not in vs.APPLIES_TO:
        raise _bad("applies_to", "Choose all, launch or event_pass.")
    if out.get("packages"):
        if any(p not in vs.LAUNCH_PACKAGES for p in out["packages"]):
            raise _bad("packages", "Packages are roots, square or grove.")
        out["packages"] = sorted(set(out["packages"]))
    elif "packages" in out:
        out["packages"] = None
    return out


def _check_value(kind: str | None, value: int | None) -> None:
    if kind == "percent" and value is not None and not 1 <= value <= 100:
        raise _bad("value", "A percentage is 1 to 100.")


def register() -> None:
    from app.platform import routes as R

    bp, api = R.bp, R.api

    def _voucher_out(db: Any, v: Voucher) -> VoucherOut:
        given = [int(d) for _, d in db.execute(vs.voucher_orders_stmt(v.id)).all()]
        stats = (len(given), sum(given))
        partner = db.get(Partner, v.partner_id) if v.partner_id else None
        return VoucherOut(
            id=v.id, code=v.code, kind=v.kind, value=v.value, applies_to=v.applies_to, packages=v.packages, valid_from=v.valid_from, valid_until=v.valid_until,
            max_uses=v.max_uses, once_per_org=v.once_per_org, new_customers_only=v.new_customers_only, active=v.active, stackable=v.stackable,
            partner_id=v.partner_id,
            partner_name=partner.name if partner else None, note=v.note, created_at=v.created_at, uses=int(stats[0]), discount_minor=int(stats[1]),
        )  # fmt: skip

    def _check_out(applied: vs.AppliedMany) -> VoucherCheckOut:
        return VoucherCheckOut(
            valid=True, list_minor=applied.list_minor, discount_minor=applied.discount_minor,
            payable_minor=applied.payable_minor,
            codes=[a.voucher.code for a in applied.applied], ignored=[{"code": c, "why": w} for c, w in applied.ignored],
        )  # fmt: skip

    @bp.get("/voucher-settings")
    @api.validate(resp=SpecResponse(HTTP_200=VoucherSettings), tags=["vouchers"])
    @R.admin_required
    def get_voucher_settings() -> Response:
        mode, most = vs.get_stacking(get_session())
        return R._out(VoucherSettings(mode=mode, max_codes=most))

    @bp.put("/voucher-settings")
    @api.validate(json=VoucherSettings, resp=SpecResponse(HTTP_200=VoucherSettings), tags=["vouchers"])
    @R.admin_required
    def put_voucher_settings() -> Response:
        body: VoucherSettings = request.context.json  # type: ignore[attr-defined]
        if body.mode not in vs.STACKING_MODES:
            raise _bad("mode", "Choose best, sequential or additive.")
        db = get_session()
        vs.set_stacking(db, body.mode, body.max_codes)
        R._audit("voucher.settings", "platform", "voucher_stacking", None, mode=body.mode, max_codes=body.max_codes)
        db.commit()
        return R._out(body)

    def _get(db: Any, voucher_id: uuid.UUID) -> Voucher:
        v: Voucher | None = db.get(Voucher, voucher_id)
        if v is None:
            raise NotFoundError("Voucher not found")
        return v

    def _check_partner(db: Any, partner_id: uuid.UUID | None) -> None:
        if partner_id is not None and db.get(Partner, partner_id) is None:
            raise _bad("partner_id", "This partner does not exist.")

    # ---- vouchers -------------------------------------------------------------------------------------------------

    @bp.get("/vouchers")
    @api.validate(resp=SpecResponse(HTTP_200=VoucherList), tags=["vouchers"])
    @R.admin_required
    def list_vouchers() -> Response:
        db = get_session()
        rows = db.scalars(select(Voucher).order_by(Voucher.created_at.desc())).all()
        return R._out(VoucherList(items=[_voucher_out(db, v) for v in rows]))

    @bp.post("/vouchers")
    @api.validate(json=VoucherIn, resp=SpecResponse(HTTP_201=VoucherOut), tags=["vouchers"])
    @R.admin_required
    def create_voucher() -> Response:
        body: VoucherIn = request.context.json  # type: ignore[attr-defined]
        data = _clean(body.model_dump(), creating=True)
        _check_value(data["kind"], data["value"])
        if data.get("valid_from") and data.get("valid_until") and data["valid_until"] <= data["valid_from"]:
            raise _bad("valid_until", "The end must be after the start.")
        db = get_session()
        _check_partner(db, data.get("partner_id"))
        v = Voucher(**data)
        db.add(v)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError("This code exists already", code="voucher_code_taken") from exc
        R._audit("voucher.created", "voucher", str(v.id), None, code=v.code, kind=v.kind, value=v.value)
        db.commit()
        return R._out(_voucher_out(db, v), 201)

    @bp.patch("/vouchers/<uuid:voucher_id>")
    @api.validate(json=VoucherPatch, resp=SpecResponse(HTTP_200=VoucherOut), tags=["vouchers"])
    @R.admin_required
    def update_voucher(voucher_id: uuid.UUID) -> Response:
        body: VoucherPatch = request.context.json  # type: ignore[attr-defined]
        db = get_session()
        v = _get(db, voucher_id)
        given = body.model_dump(exclude_unset=True)
        clear = given.pop("clear", [])
        data = _clean({k: val for k, val in given.items() if val is not None}, creating=False)
        for field in clear:
            if field in ("packages", "valid_from", "valid_until", "max_uses", "partner_id", "note"):
                data[field] = None
        if "code" in data and data["code"] != v.code and db.scalar(select(func.count(BillingOrder.id)).where(vs.used_by(v.id))):
            raise ConflictError("A code that was used on an order cannot be renamed; switch it off and make a new one", code="voucher_code_locked")
        _check_value(data.get("kind", v.kind), data.get("value", v.value))
        _check_partner(db, data.get("partner_id"))
        for field, value in data.items():
            setattr(v, field, value)
        if v.valid_from and v.valid_until and v.valid_until <= v.valid_from:
            raise _bad("valid_until", "The end must be after the start.")
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise ConflictError("This code exists already", code="voucher_code_taken") from exc
        R._audit("voucher.updated", "voucher", str(v.id), None, code=v.code, fields=sorted(data))
        db.commit()
        return R._out(_voucher_out(db, v))

    @bp.get("/vouchers/<uuid:voucher_id>/redemptions")
    @api.validate(resp=SpecResponse(HTTP_200=RedemptionList), tags=["vouchers"])
    @R.admin_required
    def voucher_redemptions(voucher_id: uuid.UUID) -> Response:
        db = get_session()
        _get(db, voucher_id)
        own = vs.voucher_orders_stmt(voucher_id).subquery()
        rows = db.execute(
            select(BillingOrder, Square.name, Organization.name, own.c.given)
            .join(own, own.c.id == BillingOrder.id)
            .join(Square, Square.id == BillingOrder.square_id)
            .join(Organization, Organization.id == Square.org_id)
            .order_by(BillingOrder.paid_at.desc())
        ).all()
        items = [
            RedemptionOut(
                order_id=o.id, paid_at=o.paid_at, square_name=sq_name, organization_name=org_name, kind=o.kind, list_minor=int(o.list_minor or o.amount_minor),
                discount_minor=int(given or 0), paid_minor=int(o.amount_minor - (o.refunded_minor or 0)),
            )
            for o, sq_name, org_name, given in rows
        ]  # fmt: skip
        return R._out(RedemptionList(items=items))

    # ---- partners -------------------------------------------------------------------------------------------------

    def _partner_out(db: Any, p: Partner) -> PartnerOut:
        n = int(db.scalar(select(func.count(Voucher.id)).where(Voucher.partner_id == p.id)) or 0)
        return PartnerOut(id=p.id, name=p.name, email=p.email, commission_percent=p.commission_percent, active=p.active, created_at=p.created_at, vouchers=n)

    @bp.get("/partners")
    @api.validate(resp=SpecResponse(HTTP_200=PartnerList), tags=["vouchers"])
    @R.admin_required
    def list_partners() -> Response:
        db = get_session()
        rows = db.scalars(select(Partner).order_by(Partner.name)).all()
        return R._out(PartnerList(items=[_partner_out(db, p) for p in rows]))

    @bp.post("/partners")
    @api.validate(json=PartnerIn, resp=SpecResponse(HTTP_201=PartnerOut), tags=["vouchers"])
    @R.admin_required
    def create_partner() -> Response:
        body: PartnerIn = request.context.json  # type: ignore[attr-defined]
        db = get_session()
        p = Partner(**body.model_dump())
        db.add(p)
        db.flush()
        R._audit("partner.created", "partner", str(p.id), None, name=p.name)
        db.commit()
        return R._out(_partner_out(db, p), 201)

    @bp.patch("/partners/<uuid:partner_id>")
    @api.validate(json=PartnerPatch, resp=SpecResponse(HTTP_200=PartnerOut), tags=["vouchers"])
    @R.admin_required
    def update_partner(partner_id: uuid.UUID) -> Response:
        body: PartnerPatch = request.context.json  # type: ignore[attr-defined]
        db = get_session()
        p = db.get(Partner, partner_id)
        if p is None:
            raise NotFoundError("Partner not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(p, field, value)
        R._audit("partner.updated", "partner", str(p.id), None, name=p.name)
        db.commit()
        return R._out(_partner_out(db, p))

    @bp.get("/partners/<uuid:partner_id>/report")
    @api.validate(resp=SpecResponse(HTTP_200=PartnerReport), tags=["vouchers"])
    @R.admin_required
    def partner_report(partner_id: uuid.UUID) -> Response:
        """What a partner's codes brought in: paid uses, what customers paid after refunds, the discount given, and the commission owed (paid out by hand)."""
        db = get_session()
        p = db.get(Partner, partner_id)
        if p is None:
            raise NotFoundError("Partner not found")
        lines: list[PartnerReportLine] = []
        for v in db.scalars(select(Voucher).where(Voucher.partner_id == p.id).order_by(Voucher.code)).all():
            uses, paid, refunded, discount = db.execute(
                select(
                    func.count(BillingOrder.id),
                    func.coalesce(func.sum(BillingOrder.amount_minor), 0),
                    func.coalesce(func.sum(BillingOrder.refunded_minor), 0),
                    func.coalesce(func.sum(BillingOrder.discount_minor), 0),
                ).where(BillingOrder.voucher_id == v.id, BillingOrder.status == "paid")
            ).one()
            revenue = int(paid) - int(refunded)
            lines.append(
                PartnerReportLine(
                    code=v.code, uses=int(uses), revenue_minor=revenue, discount_minor=int(discount), commission_minor=revenue * p.commission_percent // 100
                )
            )
        return R._out(
            PartnerReport(
                partner=_partner_out(db, p), lines=lines, uses=sum(x.uses for x in lines), revenue_minor=sum(x.revenue_minor for x in lines),
                discount_minor=sum(x.discount_minor for x in lines), commission_minor=sum(x.commission_minor for x in lines),
            )
        )  # fmt: skip

    # ---- the owner prices a code before paying --------------------------------------------------------------------

    @bp.post("/squares/<uuid:square_id>/billing/voucher-check")
    @api.validate(json=VoucherCheckIn, resp=SpecResponse(HTTP_200=VoucherCheckOut), tags=["billing"])
    @R.login_required
    def voucher_check(square_id: uuid.UUID) -> Response:
        """What a code would take off this payment. Nothing is saved or reserved: the order is made and thrown away."""
        body: VoucherCheckIn = request.context.json  # type: ignore[attr-defined]
        sq = R._billing_square(square_id)
        db = get_session()
        provider = current_app.extensions["billing"]
        with db.begin_nested() as savepoint:
            try:
                order = R._make_order(
                    db, sq, CheckoutIn(kind=body.kind, launch_package=body.launch_package, running_plan=body.running_plan, interval=body.interval), provider
                )
                launch_minor = billing_service.price_of(db, f"launch.{order.launch_package}") if order.kind == "first" else 0
                applied = vs.evaluate_codes(
                    db, body.code, kind=order.kind, package=order.launch_package, org_id=sq.org_id, list_minor=order.amount_minor, launch_minor=launch_minor
                )
                out = _check_out(applied)
            except vs.VoucherRejected as exc:
                out = VoucherCheckOut(valid=False, reason=exc.code, message=exc.detail, list_minor=0, discount_minor=0, payable_minor=0)
            finally:
                savepoint.rollback()
        return R._out(out)

    @bp.post("/billing/voucher-preview")
    @api.validate(json=VoucherPreviewIn, resp=SpecResponse(HTTP_200=VoucherCheckOut), tags=["billing"])
    @R.login_required
    def voucher_preview() -> Response:
        """What a code would take off a payment that does not exist yet: the first payment of a launch package, or a new Event pass (Create square, W14-R30)."""
        body: VoucherPreviewIn = request.context.json  # type: ignore[attr-defined]
        db = get_session()
        org_ids = R._member_org_ids(db, g.user)
        if not org_ids:
            raise ForbiddenError("No organization", code="no_organization")
        try:
            if body.kind == "event_pass":
                list_minor, launch_minor, package, kind = billing_service.price_of(db, f"launch.{square_plans.EVENT}"), 0, square_plans.EVENT, "event_pass"
            elif body.kind == "first" and body.launch_package in vs.LAUNCH_PACKAGES:
                launch_minor = billing_service.price_of(db, f"launch.{body.launch_package}")
                list_minor, package, kind = launch_minor + billing_service.price_of(db, f"running.{square_plans.LIVE}.month"), body.launch_package, "first"
            else:
                raise _bad("kind", "Choose first with a launch package, or event_pass.")
            applied = vs.evaluate_codes(db, body.code, kind=kind, package=package, org_id=org_ids[0], list_minor=list_minor, launch_minor=launch_minor)
            out = _check_out(applied)
        except vs.VoucherRejected as exc:
            out = VoucherCheckOut(valid=False, reason=exc.code, message=exc.detail)
        return R._out(out)
