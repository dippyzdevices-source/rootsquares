"""Platform routes of analytics (ADR 090, W23-R77): the owner's switch and the owner's numbers.

This is the one exception to ADR 038 (the platform learns no numbers from a square): the numbers of the square's visits pass through here to the square's
OWN organisation, already reduced by the square server (figures under 5 hidden), only the fields of `AnalyticsOut` are passed on, and **nothing is stored**:
the only thing the platform keeps is the owner's switch (`squares.analytics_enabled`). There is no staff route: platform staff cannot see a square's visit
numbers (a test keeps it so). The handlers are registered on the platform blueprint by `register()` (called at the end of routes.py).
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import Response, g, request
from spectree import Response as SpecResponse
from sqlalchemy import select

from app.platform.models import Membership, MembershipRole, Square
from app.platform.module_status import fetch_square_analytics
from app.platform.schemas import (
    AnalyticsDayOut,
    AnalyticsEventOut,
    AnalyticsOut,
    AnalyticsPageOut,
    AnalyticsSourceOut,
    AnalyticsSwitchIn,
    AnalyticsTotalsOut,
)
from app.shared.db import get_session
from app.shared.errors import ForbiddenError, NotFoundError

RANGES = (7, 30, 90)


def _num(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _few(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _totals(raw: object) -> AnalyticsTotalsOut:
    d = raw if isinstance(raw, dict) else {}
    return AnalyticsTotalsOut(visits=_num(d.get("visits")), views=_num(d.get("views")), visitors=_num(d.get("visitors")))


def _rows(answer: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = answer.get(key)
    return [r for r in raw if isinstance(r, dict)] if isinstance(raw, list) else []


def _shape(answer: dict[str, Any], enabled: bool, days: int) -> AnalyticsOut:
    """Only the known fields of the square's answer, each checked for its type: anything else the square sent is dropped here."""
    rows, pages, sources, events = (_rows(answer, k) for k in ("daily", "pages", "sources", "events"))
    return AnalyticsOut(
        enabled=enabled,
        counting=bool(answer.get("enabled")),
        days=days,
        start=str(answer.get("from") or "") or None,
        end=str(answer.get("to") or "") or None,
        daily=[
            AnalyticsDayOut(day=str(r.get("day", "")), visits=_num(r.get("visits")), views=_num(r.get("views")), visitors=_num(r.get("visitors"))) for r in rows
        ],
        totals=_totals(answer.get("totals")),
        previous=_totals(answer.get("previous")),
        pages=[AnalyticsPageOut(path=str(r.get("path", "")), views=_few(r.get("views")), few=bool(r.get("few"))) for r in pages[:10]],
        sources=[AnalyticsSourceOut(source=str(r.get("source", "")), visits=_few(r.get("visits")), few=bool(r.get("few"))) for r in sources[:10]],
        events=[
            AnalyticsEventOut(
                slug=str(r.get("slug", "")),
                title=str(r.get("title", "")),
                views=_few(r.get("views")),
                views_few=bool(r.get("views_few")),
                tickets=_few(r.get("tickets")),
                tickets_few=bool(r.get("tickets_few")),
            )
            for r in events[:10]
        ],
    )


def register() -> None:
    from app.platform import routes as R

    bp, api = R.bp, R.api

    def _own(square_id: uuid.UUID) -> tuple[Square, bool]:
        """A square of the signed-in customer's organisation (never staff, ADR 038), and whether they are its owner."""
        db = get_session()
        sq = db.get(Square, square_id)
        if sq is None or sq.org_id not in R._member_org_ids(db, g.user):
            raise NotFoundError("Square not found")
        owner = db.scalar(select(Membership).where(Membership.org_id == sq.org_id, Membership.user_id == g.user.id, Membership.role == MembershipRole.OWNER))
        return sq, owner is not None

    @bp.get("/squares/<uuid:square_id>/analytics")
    @api.validate(resp=SpecResponse(HTTP_200=AnalyticsOut), tags=["analytics"])
    @R.login_required
    def square_analytics(square_id: uuid.UUID) -> Response:
        """The Analytics card of the Health tab. Off (the owner has not switched counting on): only the switch, the square is not asked."""
        sq, _owner = _own(square_id)
        try:
            days = int(request.args.get("days", "30"))
        except ValueError:
            days = 30
        days = days if days in RANGES else 30
        if not sq.analytics_enabled:
            return R._out(AnalyticsOut(enabled=False, days=days))
        answer = fetch_square_analytics(R._settings(), sq, days)
        if answer is None:
            return R._out(AnalyticsOut(enabled=True, reachable=False, days=days))
        if answer.get("resting"):
            return R._out(AnalyticsOut(enabled=True, resting=True, days=days))
        return R._out(_shape(answer, True, days))

    @bp.put("/squares/<uuid:square_id>/analytics")
    @api.validate(json=AnalyticsSwitchIn, resp=SpecResponse(HTTP_200=AnalyticsOut), tags=["analytics"])
    @R.login_required
    def switch_square_analytics(square_id: uuid.UUID) -> Response:
        """The owner switches counting on or off. Off: counting stops within a minute (the square reads the switch); what was counted stays in the square."""
        body: AnalyticsSwitchIn = request.context.json  # type: ignore[attr-defined]
        sq, owner = _own(square_id)
        if not owner:
            raise ForbiddenError("Only the owner of the square can switch visit counting on or off", code="owner_only")
        db = get_session()
        if sq.analytics_enabled != body.enabled:
            sq.analytics_enabled = body.enabled
            R._audit("analytics.switch", "square", str(sq.id), sq.org_id, square_id=str(sq.id), enabled=body.enabled)
            db.commit()
        return R._out(AnalyticsOut(enabled=sq.analytics_enabled))
