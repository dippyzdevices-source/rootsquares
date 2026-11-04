"""Platform route of the custom package (W19-R20, ADR 082): a platform admin agrees modules and one amount per period with one square.

Nothing here is for sale: the pricing page only says "speak to us". The admin sets the package on the square page of the owner console; the owner then pays the
agreed amount through the normal checkout (a Live period priced from the square, billing.new_running_order). The Event pass is fixed and is never made custom.
The handler is registered on the platform blueprint by `register()` (called at the end of routes.py).
"""

from __future__ import annotations

import json
import uuid

from flask import Response, request
from spectree import Response as SpecResponse

from app.platform import modules as square_modules
from app.platform import plans as square_plans
from app.platform.models import PlatformSetting
from app.platform.schemas import CustomGuide, CustomPackageIn, SquareOut
from app.shared.db import get_session
from app.shared.errors import ConflictError, ForbiddenError, ValidationFailedError

GUIDE_STEPS = 5
GUIDE_KEY = "custom.guide.{}"  # platform_settings: the guiding minimum per month for each step of the hierarchy (USD minor units)


def get_guide(db) -> list[int]:  # type: ignore[no-untyped-def]
    """The five guiding minimums as the platform owner set them; 0 = none."""
    out = []
    for i in range(GUIDE_STEPS):
        row = db.get(PlatformSetting, GUIDE_KEY.format(i))
        try:
            out.append(max(0, int(row.value)) if row and row.value else 0)
        except ValueError:
            out.append(0)
    return out


def register() -> None:
    from app.platform import routes as R

    bp, api = R.bp, R.api

    @bp.put("/squares/<uuid:square_id>/custom-package")
    @api.validate(json=CustomPackageIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
    @R.login_required
    def set_custom_package(square_id: uuid.UUID) -> Response:
        """Platform admin only: the square becomes (or stays) a custom package with these modules and this one amount per period. Modules that were on and are
        no longer in the list are switched off at the next save of the Modules page; nothing is deleted (data is kept, ADR 037)."""
        if not R._is_staff():
            raise ForbiddenError("Platform admin only")
        body: CustomPackageIn = request.context.json  # type: ignore[attr-defined]
        sq = R._own_square(square_id)
        if sq.launch_package == square_plans.EVENT or sq.running_plan == square_plans.EVENT_RUN:
            raise ConflictError("The Event pass is fixed and cannot be made a custom package", code="event_pass")
        unknown = [k for k in body.modules if k not in square_modules.KEYS and k not in square_modules.CORE_KEYS]
        if unknown:
            raise ValidationFailedError("Check the modules", errors=[{"loc": ["modules"], "msg": f"unknown module: {unknown[0]}", "type": "value_error"}])
        optional = square_modules.normalize([k for k in body.modules if k in square_modules.KEYS])  # a module comes with what it needs
        chosen = optional + square_modules.normalize_core([k for k in body.modules if k in square_modules.CORE_KEYS], optional)  # and so does an always-on part
        was = {"launch_package": sq.launch_package, "custom_amount_minor": sq.custom_amount_minor, "custom_interval": sq.custom_interval}
        sq.launch_package = square_plans.CUSTOM
        sq.custom_modules = json.dumps(chosen)
        sq.custom_amount_minor = body.amount_minor
        sq.custom_interval = body.interval
        R._audit(
            "square.custom_package", "square", str(sq.id), sq.org_id,
            amount_minor=body.amount_minor, interval=body.interval, modules=len(optional), core=len(chosen) - len(optional), was=was,
        )  # fmt: skip
        get_session().commit()
        return R._out(R._square_out(sq))

    @bp.get("/custom-guide")
    @api.validate(resp=SpecResponse(HTTP_200=CustomGuide), tags=["squares"])
    @R.admin_required
    def get_custom_guide() -> Response:
        return R._out(CustomGuide(steps=get_guide(get_session())))

    @bp.put("/custom-guide")
    @api.validate(json=CustomGuide, resp=SpecResponse(HTTP_200=CustomGuide), tags=["squares"])
    @R.admin_required
    def put_custom_guide() -> Response:
        body: CustomGuide = request.context.json  # type: ignore[attr-defined]
        db = get_session()
        for i, amount in enumerate(body.steps):
            key = GUIDE_KEY.format(i)
            row = db.get(PlatformSetting, key)
            if row is None:
                db.add(PlatformSetting(key=key, value=str(amount)))
            else:
                row.value = str(amount)
        R._audit("custom.guide", "platform", "custom_guide", None)
        db.commit()
        return R._out(CustomGuide(steps=get_guide(db)))
