"""Platform routes of the invoice (W19-R16): the owner reads the invoice of a paid order; a platform admin sets who the seller is.
The handlers are registered on the platform blueprint by `register()` (called at the end of routes.py)."""

from __future__ import annotations

import uuid

from flask import Response, request
from spectree import Response as SpecResponse

from app.platform import billing as billing_service
from app.platform import invoices
from app.platform.models import BillingOrder, Organization, Square
from app.platform.schemas import InvoiceOut, InvoiceSeller, OrderOut
from app.shared.db import get_session
from app.shared.errors import ConflictError, NotFoundError


def register() -> None:
    from app.platform import routes as R

    bp, api = R.bp, R.api

    @bp.get("/billing/orders/<uuid:order_id>/invoice")
    @api.validate(resp=SpecResponse(HTTP_200=InvoiceOut), tags=["billing"])
    @R.login_required
    def get_invoice(order_id: uuid.UUID) -> Response:
        db = get_session()
        order = db.get(BillingOrder, order_id)
        if order is None:
            raise NotFoundError("Order not found")
        if not R._is_staff():
            R._billing_square(order.square_id)  # the owner's organisation; platform staff may read every invoice (the owner console lists every payment)
        if order.status not in invoices.INVOICED:
            raise ConflictError("Only a paid payment has an invoice", code="not_paid")
        sq = db.get(Square, order.square_id)
        org = db.get(Organization, sq.org_id) if sq else None
        country = org.billing_country if org else None
        percent = billing_service.tax_percent(R._settings(), country)
        net, tax = billing_service.tax_split(order.amount_minor, percent)
        seller = invoices.get_seller(db)
        span = invoices.period(order)
        return R._out(InvoiceOut(
            number=invoices.invoice_number(db, order, seller["prefix"]), issued_at=order.paid_at or order.created_at,
            seller=InvoiceSeller(**seller), buyer_name=org.name if org else "", square_name=sq.name if sq else "", country=country,
            tax_percent=percent, net_minor=net, tax_minor=tax, period_start=span[0] if span else None, period_end=span[1] if span else None,
            order=OrderOut.model_validate(order),
        ))  # fmt: skip

    @bp.get("/invoice-settings")
    @api.validate(resp=SpecResponse(HTTP_200=InvoiceSeller), tags=["billing"])
    @R.admin_required
    def get_invoice_settings() -> Response:
        return R._out(InvoiceSeller(**invoices.get_seller(get_session())))

    @bp.put("/invoice-settings")
    @api.validate(json=InvoiceSeller, resp=SpecResponse(HTTP_200=InvoiceSeller), tags=["billing"])
    @R.admin_required
    def put_invoice_settings() -> Response:
        body: InvoiceSeller = request.context.json  # type: ignore[attr-defined]
        db = get_session()
        invoices.set_seller(db, body.model_dump())
        R._audit("invoice.settings", "platform", "invoice_seller", None)
        db.commit()
        return R._out(InvoiceSeller(**invoices.get_seller(db)))
