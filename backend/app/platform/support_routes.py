"""Platform routes of support access (ADR 089, W23-R64).

Owner side (the customer API, only the square's owner): see the state of a square's support access, create a grant, revoke it.
Staff side (the staff API only, `admin_required`): the overview of active grants and requests, the state for one square, a request with a note, opening a
session (this is the one gate: it opens only on an active grant and returns the short-lived token), ending a session.
Every step is written to the audit log with the square, never with the square's content. The handlers are registered on the platform blueprint by `register()`
(called at the end of routes.py).
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import Response, current_app, g, request
from spectree import Response as SpecResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.platform import email_html, support
from app.platform import notify as notify_service
from app.platform.models import AuditLog, Membership, MembershipRole, Square, SupportGrant, SupportRequest, SupportSession, User
from app.platform.schemas import (
    SupportActivityOut,
    SupportAuditOut,
    SupportGrantIn,
    SupportGrantOut,
    SupportOverviewOut,
    SupportOverviewRequest,
    SupportOverviewRow,
    SupportRequestIn,
    SupportRequestOut,
    SupportSessionOut,
    SupportSessionStartOut,
    SupportStaffStateOut,
    SupportStateOut,
)
from app.shared.db import get_session
from app.shared.errors import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationFailedError

AUDIT_ACTIONS = ("support.grant", "support.revoke", "support.request", "support.session_start", "support.session_end", "support.denied")


def _grant_out(db: Session, grant: SupportGrant) -> SupportGrantOut:
    sessions = list(db.scalars(select(SupportSession).where(SupportSession.grant_id == grant.id).order_by(desc(SupportSession.started_at))))
    return SupportGrantOut(
        id=grant.id,
        created_at=grant.created_at,
        expires_at=grant.expires_at,
        duration_minutes=grant.duration_minutes,
        scopes=list(grant.scopes),
        allow_changes=grant.allow_changes,
        note=grant.note,
        sessions=[SupportSessionOut.model_validate(s) for s in sessions],
    )


def _staff_name() -> str:
    staff = g.staff
    return (staff.name or staff.email.split("@")[0]).strip() or "support"


def register() -> None:
    from app.platform import routes as R

    bp, api = R.bp, R.api

    def _square_of_owner(square_id: uuid.UUID) -> tuple[Square, bool]:
        """A square of the signed-in customer's organisation, and whether they are its owner. Anything else is a 404 (nothing about others is revealed)."""
        db = get_session()
        sq = db.get(Square, square_id)
        if sq is None or sq.org_id not in R._member_org_ids(db, g.user):
            raise NotFoundError("Square not found")
        owner = db.scalar(select(Membership).where(Membership.org_id == sq.org_id, Membership.user_id == g.user.id, Membership.role == MembershipRole.OWNER))
        return sq, owner is not None

    def _only_owner(square_id: uuid.UUID) -> Square:
        sq, owner = _square_of_owner(square_id)
        if not owner:
            raise ForbiddenError("Only the owner of the square can grant or end support access", code="owner_only")
        return sq

    def _link(sq: Square) -> str:
        return f"{R._settings().PLATFORM_FRONTEND_URL.rstrip('/')}/squares/{sq.id}/support"

    def _mail(sq: Square, subject: str, text: str, heading: str) -> None:
        db = get_session()
        mail = email_html.from_text(
            text, site_url=R._settings().PLATFORM_FRONTEND_URL, eyebrow="Support access", heading=heading, button_label="Open Support access"
        )
        notify_service.send_to_owner(current_app, db, sq, subject, text, **mail)

    # ---- owner ---------------------------------------------------------------------------------------------------------------------------
    @bp.get("/squares/<uuid:square_id>/support")
    @api.validate(resp=SpecResponse(HTTP_200=SupportStateOut), tags=["support"])
    @R.login_required
    def support_state(square_id: uuid.UUID) -> Response:
        """The Support access page: the active grant with its sessions, the requests waiting and the log of every use."""
        sq, owner = _square_of_owner(square_id)
        return _state(sq, owner)

    def _state(sq: Square, owner: bool) -> Response:
        db = get_session()
        if support.close_expired(db):
            db.commit()
        grant = support.active_grant(db, sq.id)
        reqs = list(db.scalars(select(SupportRequest).where(SupportRequest.square_id == sq.id).order_by(desc(SupportRequest.created_at)).limit(20)))
        return R._out(
            SupportStateOut(
                grant=_grant_out(db, grant) if grant else None,
                requests=[SupportRequestOut.model_validate(r) for r in reqs],
                can_manage=owner,
            )
        )

    @bp.get("/squares/<uuid:square_id>/support/activity")
    @api.validate(resp=SpecResponse(HTTP_200=SupportActivityOut), tags=["support"])
    @R.login_required
    def support_activity(square_id: uuid.UUID) -> Response:
        """The Activity tab: the log of every use, newest first, one page at a time (`page`, `per_page`: 15 by default, 50 at most)."""
        sq, _owner = _square_of_owner(square_id)
        try:
            page = max(1, int(request.args.get("page", "1")))
            per_page = min(50, max(1, int(request.args.get("per_page", "15"))))
        except ValueError:
            raise ValidationFailedError(
                "page and per_page must be numbers", errors=[{"loc": ["query"], "msg": "not a number", "type": "value_error"}]
            ) from None
        db = get_session()
        # the log is kept per organisation; the square a row belongs to is in its data, so the rows of this organisation are read and filtered here
        rows = db.scalars(select(AuditLog).where(AuditLog.org_id == sq.org_id, AuditLog.action.in_(AUDIT_ACTIONS)).order_by(desc(AuditLog.at)))
        mine: list[SupportAuditOut] = []
        people: dict[uuid.UUID, str] = {}  # the name (else the e-mail) of each person of the organisation who acted, read once
        for a in rows:
            d: dict[str, Any] = a.data or {}
            if d.get("square_id") != str(sq.id):
                continue
            who = str(d.get("staff") or "")  # a rootsquares staff member (the name they work under)
            by_you = False
            if not who and a.actor_user_id is not None:  # a person of the organisation: an owner who allowed or ended access
                if a.actor_user_id not in people:
                    person = db.get(User, a.actor_user_id)
                    people[a.actor_user_id] = ((person.name or person.email) if person is not None else "").strip()
                who = people[a.actor_user_id]
                by_you = a.actor_user_id == g.user.id
            mine.append(
                SupportAuditOut(
                    at=a.at,
                    action=a.action,
                    who=who,  # empty when the person has erased their account: the page says "Someone"
                    by_you=by_you,
                    scopes=list(d.get("scopes") or []),
                    allow_changes=d.get("allow_changes"),
                    ended_by=d.get("ended_by"),
                )
            )
        start = (page - 1) * per_page
        return R._out(SupportActivityOut(items=mine[start : start + per_page], page=page, per_page=per_page, total=len(mine)))

    @bp.post("/squares/<uuid:square_id>/support/grants")
    @api.validate(json=SupportGrantIn, resp=SpecResponse(HTTP_201=SupportGrantOut), tags=["support"])
    @R.login_required
    def create_support_grant(square_id: uuid.UUID) -> Response:
        """The owner lets rootsquares staff in for a while: one grant at a time, changes only for content and settings, members confirmed twice."""
        body: SupportGrantIn = request.context.json  # type: ignore[attr-defined]
        sq = _only_owner(square_id)
        db = get_session()
        grant = support.create_grant(db, sq, g.user.id, body.duration_minutes, body.scopes, body.allow_changes, body.members_confirmed, body.note)
        R._audit(
            "support.grant",
            "support_grant",
            str(grant.id),
            sq.org_id,
            square_id=str(sq.id),
            scopes=list(grant.scopes),
            allow_changes=grant.allow_changes,
            minutes=grant.duration_minutes,
        )
        db.commit()
        return R._out(_grant_out(db, grant), 201)

    @bp.post("/squares/<uuid:square_id>/support/revoke")
    @api.validate(resp=SpecResponse(HTTP_200=SupportStateOut), tags=["support"])
    @R.login_required
    def revoke_support_grant(square_id: uuid.UUID) -> Response:
        """The owner ends the active grant now; every open session ends with it, and the square server refuses the staff member's next request."""
        sq = _only_owner(square_id)
        db = get_session()
        grant = support.active_grant(db, sq.id)
        if grant is None:
            raise NotFoundError("There is no active support grant")
        open_sessions = list(db.scalars(select(SupportSession).where(SupportSession.grant_id == grant.id, SupportSession.ended_at.is_(None))))
        support.revoke_grant(db, grant)
        R._audit("support.revoke", "support_grant", str(grant.id), sq.org_id, square_id=str(sq.id), scopes=list(grant.scopes))
        for s in open_sessions:
            R._audit("support.session_end", "support_session", str(s.id), sq.org_id, square_id=str(sq.id), staff=s.staff_name, ended_by="revoked")
        db.commit()
        return _state(sq, True)

    # ---- staff ---------------------------------------------------------------------------------------------------------------------------
    def _staff_square(square_id: uuid.UUID) -> Square:
        sq = get_session().get(Square, square_id)
        if sq is None:
            raise NotFoundError("Square not found")
        return sq

    @bp.get("/support/overview")
    @api.validate(resp=SpecResponse(HTTP_200=SupportOverviewOut), tags=["support"])
    @R.admin_required
    def support_overview() -> Response:
        """Staff: every square with an active grant, and the requests made (newest first). Never the owner's note or any content."""
        db = get_session()
        if support.close_expired(db):
            db.commit()
        now = support.now_utc()
        active: list[SupportOverviewRow] = []
        for grant in db.scalars(select(SupportGrant).where(SupportGrant.revoked_at.is_(None)).order_by(SupportGrant.expires_at)):
            if not support.is_active(grant, now):
                continue
            sq = db.get(Square, grant.square_id)
            if sq is None:
                continue
            open_n = len(list(db.scalars(select(SupportSession.id).where(SupportSession.grant_id == grant.id, SupportSession.ended_at.is_(None)))))
            active.append(
                SupportOverviewRow(
                    square_id=sq.id,
                    square_name=sq.name,
                    domain=sq.domain,
                    scopes=list(grant.scopes),
                    allow_changes=grant.allow_changes,
                    expires_at=grant.expires_at,
                    open_sessions=open_n,
                )
            )
        reqs: list[SupportOverviewRequest] = []
        for r in db.scalars(select(SupportRequest).order_by(desc(SupportRequest.created_at)).limit(50)):
            sq = db.get(Square, r.square_id)
            if sq is not None:
                reqs.append(
                    SupportOverviewRequest(
                        square_id=sq.id, square_name=sq.name, staff_name=r.staff_name, note=r.note, created_at=r.created_at, answered_at=r.answered_at
                    )
                )
        return R._out(SupportOverviewOut(active=active, requests=reqs))

    @bp.get("/support/squares/<uuid:square_id>")
    @api.validate(resp=SpecResponse(HTTP_200=SupportStaffStateOut), tags=["support"])
    @R.admin_required
    def support_staff_state(square_id: uuid.UUID) -> Response:
        sq = _staff_square(square_id)
        grant = support.active_grant(get_session(), sq.id)
        return R._out(
            SupportStaffStateOut(
                square_id=sq.id,
                square_name=sq.name,
                domain=sq.domain,
                active=grant is not None,
                scopes=list(grant.scopes) if grant else [],
                allow_changes=grant.allow_changes if grant else False,
                expires_at=grant.expires_at if grant else None,
            )
        )

    @bp.post("/support/squares/<uuid:square_id>/request")
    @api.validate(json=SupportRequestIn, resp=SpecResponse(HTTP_201=SupportRequestOut), tags=["support"])
    @R.admin_required
    def support_request(square_id: uuid.UUID) -> Response:
        """Staff ask the owner for access, with the reason. Nothing opens; the owner is mailed and answers by creating a grant."""
        body: SupportRequestIn = request.context.json  # type: ignore[attr-defined]
        sq = _staff_square(square_id)
        db = get_session()
        if support.active_grant(db, sq.id) is not None:
            raise ConflictError("Access is already granted for this square", code="grant_active")
        waiting = db.scalar(
            select(SupportRequest.id)
            .where(SupportRequest.square_id == sq.id, SupportRequest.staff_id == g.staff.id, SupportRequest.answered_at.is_(None))
            .limit(1)
        )
        if waiting is not None:
            raise ConflictError("You already asked for this square and the owner has not answered", code="request_waiting")
        req = SupportRequest(square_id=sq.id, staff_id=g.staff.id, staff_name=_staff_name()[:120], note=body.note.strip())
        db.add(req)
        db.flush()
        R._audit("support.request", "support_request", str(req.id), sq.org_id, square_id=str(sq.id), staff=req.staff_name)
        db.commit()
        subject, text = support.mail_requested(sq, req.staff_name, req.note, _link(sq))
        _mail(sq, subject, text, "Support asks for access")
        return R._out(SupportRequestOut.model_validate(req), 201)

    @bp.post("/support/squares/<uuid:square_id>/session")
    @api.validate(resp=SpecResponse(HTTP_201=SupportSessionStartOut), tags=["support"])
    @R.admin_required
    def support_start_session(square_id: uuid.UUID) -> Response:
        """The one gate: a session opens only on an active grant of the owner. Returns the token for the square's own admin (the admin app puts it in the
        address fragment, never in a query string). A refused start is audited too."""
        sq = _staff_square(square_id)
        db = get_session()
        name = _staff_name()
        try:
            sess, grant, is_new = support.start_session(db, sq, g.staff.id, name)
        except AppError as exc:
            R._audit("support.denied", "square", str(sq.id), sq.org_id, square_id=str(sq.id), staff=name, reason=exc.code)
            db.commit()
            raise
        token, token_end = support.sign_session(R._settings(), sess, grant, sq)
        if is_new:  # a session that was already open is only given a fresh token: no new log line, no new mail
            R._audit(
                "support.session_start",
                "support_session",
                str(sess.id),
                sq.org_id,
                square_id=str(sq.id),
                staff=name,
                scopes=list(grant.scopes),
                allow_changes=grant.allow_changes,
            )
            db.commit()
            subject, text = support.mail_session_started(sq, grant, name, _link(sq))
            _mail(sq, subject, text, "Support used your access")
        return R._out(
            SupportSessionStartOut(
                session_id=sess.id,
                token=token,
                token_expires_at=token_end,
                grant_expires_at=support._aware(grant.expires_at) or grant.expires_at,
                domain=sq.domain,
                scopes=list(grant.scopes),
                allow_changes=grant.allow_changes,
            ),
            201,
        )

    @bp.post("/support/sessions/<uuid:session_id>/renew")
    @api.validate(resp=SpecResponse(HTTP_200=SupportSessionStartOut), tags=["support"])
    @R.admin_required
    def support_renew_session(session_id: uuid.UUID) -> Response:
        """A new token for a running session, while its grant is still active (a token lives 8 hours at most)."""
        db = get_session()
        sess = db.get(SupportSession, session_id)
        if sess is None or sess.staff_id != g.staff.id or sess.ended_at is not None:
            raise NotFoundError("Session not found")
        grant = db.get(SupportGrant, sess.grant_id)
        sq = db.get(Square, grant.square_id) if grant else None
        if grant is None or sq is None or not support.is_active(grant):
            support.close_expired(db)
            db.commit()
            raise ForbiddenError("The support access has ended", code="no_active_grant")
        token, token_end = support.sign_session(R._settings(), sess, grant, sq)
        return R._out(
            SupportSessionStartOut(
                session_id=sess.id,
                token=token,
                token_expires_at=token_end,
                grant_expires_at=support._aware(grant.expires_at) or grant.expires_at,
                domain=sq.domain,
                scopes=list(grant.scopes),
                allow_changes=grant.allow_changes,
            )
        )

    @bp.post("/support/sessions/<uuid:session_id>/end")
    @api.validate(tags=["support"])
    @R.admin_required
    def support_end_session(session_id: uuid.UUID) -> Response:
        db = get_session()
        sess = db.get(SupportSession, session_id)
        if sess is None or sess.staff_id != g.staff.id:
            raise NotFoundError("Session not found")
        if sess.ended_at is None:
            sess.ended_at, sess.ended_by = support.now_utc(), "staff"
            grant = db.get(SupportGrant, sess.grant_id)
            sq = db.get(Square, grant.square_id) if grant else None
            R._audit(
                "support.session_end",
                "support_session",
                str(sess.id),
                sq.org_id if sq else None,
                square_id=str(sq.id) if sq else "",
                staff=sess.staff_name,
                ended_by="staff",
            )
            db.commit()
        return R._out(SupportSessionOut.model_validate(sess))
