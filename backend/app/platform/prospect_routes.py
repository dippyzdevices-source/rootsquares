"""Platform routes of the prospect list (W19-R22): "Nothing fits you? Speak to us" on the Pricing page stores the person's name, e-mail and phone here;
a platform admin works the list in the owner console (status, notes, delete).

The form is public, so it is protected: the consent box is required, a hidden field catches simple bots (normal answer, nothing stored), the number
of requests per address is limited, and the same e-mail is stored once per day. Personal data: only what the person typed; the audit log never holds it.
The handlers are registered on the platform blueprint by `register()` (called at the end of routes.py).
"""

from __future__ import annotations

import datetime as dt
import uuid

from flask import Response, current_app, jsonify, request
from spectree import Response as SpecResponse
from sqlalchemy import desc, select

from app.platform.models import Prospect
from app.platform.schemas import ProspectIn, ProspectList, ProspectOut, ProspectPatch
from app.shared.db import get_session
from app.shared.errors import NotFoundError

STATUSES = ("new", "contacted", "won", "closed")
RATE_LIMIT, RATE_WINDOW = 5, 3600  # five requests an hour for one address


def _ok() -> Response:
    resp = jsonify({"ok": True})
    resp.status_code = 201
    return resp


def register() -> None:
    from app.platform import routes as R

    bp, api = R.bp, R.api

    @bp.post("/prospects")
    @api.validate(json=ProspectIn, tags=["prospects"])
    def create_prospect() -> Response:
        """Public: a person asks to be contacted about a custom package. Always answers 201 so a bot learns nothing."""
        body: ProspectIn = request.context.json  # type: ignore[attr-defined]
        if body.website:  # the hidden field a person never fills
            return _ok()
        limiter = current_app.extensions["providers"].rate_limiter
        if not limiter.allow(f"prospect:{request.remote_addr}", RATE_LIMIT, RATE_WINDOW):
            raise R.RateLimitedError("Too many requests. Try again later.", retry_after=RATE_WINDOW)
        db = get_session()
        since = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
        again = db.scalar(select(Prospect.id).where(Prospect.email == body.email, Prospect.created_at >= since).limit(1))
        if again is None:
            db.add(Prospect(name=body.name.strip(), email=body.email, phone=body.phone.strip(), message=(body.message or "").strip() or None))
            db.commit()
        return _ok()

    @bp.get("/prospects")
    @api.validate(resp=SpecResponse(HTTP_200=ProspectList), tags=["prospects"])
    @R.admin_required
    def list_prospects() -> Response:
        status = request.args.get("status")
        stmt = select(Prospect).order_by(desc(Prospect.created_at)).limit(500)
        if status in STATUSES:
            stmt = stmt.where(Prospect.status == status)
        rows = get_session().scalars(stmt).all()
        return R._out(ProspectList(items=[ProspectOut.model_validate(p) for p in rows]))

    @bp.patch("/prospects/<uuid:prospect_id>")
    @api.validate(json=ProspectPatch, resp=SpecResponse(HTTP_200=ProspectOut), tags=["prospects"])
    @R.admin_required
    def update_prospect(prospect_id: uuid.UUID) -> Response:
        body: ProspectPatch = request.context.json  # type: ignore[attr-defined]
        db = get_session()
        p = db.get(Prospect, prospect_id)
        if p is None:
            raise NotFoundError("Prospect not found")
        if body.status is not None:
            p.status = body.status
        if body.notes is not None:
            p.notes = body.notes.strip() or None
        p.updated_at = dt.datetime.now(dt.UTC)
        R._audit("prospect.updated", "prospect", str(p.id), None, status=p.status)  # the id and the status only, never the person's details
        db.commit()
        return R._out(ProspectOut.model_validate(p))

    @bp.delete("/prospects/<uuid:prospect_id>")
    @api.validate(tags=["prospects"])
    @R.admin_required
    def delete_prospect(prospect_id: uuid.UUID) -> Response:
        """Removes the person's details for good (the person asked, or the contact is over)."""
        db = get_session()
        p = db.get(Prospect, prospect_id)
        if p is None:
            raise NotFoundError("Prospect not found")
        db.delete(p)
        R._audit("prospect.deleted", "prospect", str(prospect_id), None)
        db.commit()
        return jsonify({"deleted": True})
