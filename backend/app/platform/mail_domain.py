"""A Grove square's own sending domain (ADR 091, 095): the owner REQUESTS a domain and the name before the @, staff set it up in the admin
application (the domain is
registered at Resend), the owner adds the DNS records Resend asks for (or sends them to their web person), an hourly job checks and e-mails the owner
when Resend says
`verified`; then the square's mail is sent from `<name>@<domain>` and its Newsletter may send.

The owner may read it, request, withdraw a request, change the name before the @, check, remove, send the records to a web person and ask for IT
help. Staff (the admin
application) approve or reject a request, check and remove. Only the Grove package and a custom package that has the Messages module have it
(`allowed`); nothing is
deleted when a package is lost: the square server just stops using the domain. The platform stores the domain, Resend's id and status, the DNS
records (not secret),
the chosen name and the request; a domain is never a person's data. The handlers are registered on the platform blueprint by `register()` (called at the end of
routes.py); the staff ones are `admin_required` and are served by the staff API only.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from email.utils import parseaddr
from typing import Any

from flask import Response, current_app, g, request
from spectree import Response as SpecResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import email_html, mail_domain_mail, notify, plans
from app.platform.models import Membership, MembershipRole, Square
from app.platform.schemas import (
    MailDomainApproveIn,
    MailDomainInstructionsIn,
    MailDomainNameIn,
    MailDomainOut,
    MailDomainRecordOut,
    MailDomainRejectIn,
    MailDomainRequestIn,
)
from app.providers.resend_domains import DomainApiError, ResendDomains
from app.shared.config import Settings
from app.shared.db import get_session
from app.shared.errors import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationFailedError

DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
LOCAL_RE = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,62}$")
DEFAULT_LOCAL = "hello"
VERIFIED = "verified"


class MailNotReady(AppError):
    status, code, title = 503, "mail_domain_not_ready", "Own sending domains are not switched on yet"


class MailProviderError(AppError):
    status, code, title = 502, "mail_provider_error", "The e-mail service refused the request"


def allowed(sq: Square) -> bool:
    """Grove and a custom package that has the Messages module (the module the feature belongs to); a square made before packages counts as Grove."""
    package = sq.launch_package or plans.LEGACY_PACKAGE
    if package == plans.GROVE:
        return True
    return package == plans.CUSTOM and "messages" in plans.allowed_modules(package, sq.custom_modules)


def clean_domain(raw: str, settings: Settings) -> str:
    value = (raw or "").strip().lower().rstrip(".")
    if value.startswith(("http://", "https://")) or "/" in value or "@" in value or " " in value:
        raise ValidationFailedError("Type only the domain, for example mail.theirassociation.org", code="mail_domain_invalid")
    if not DOMAIN_RE.match(value):
        raise ValidationFailedError("This is not a domain name. Example: mail.theirassociation.org", code="mail_domain_invalid")
    ours = {settings.SQUARE_DOMAIN_SUFFIX.strip().lower().lstrip(".")}
    sender_domain = parseaddr(settings.EMAIL_FROM)[1].rpartition("@")[2].lower()
    if sender_domain:
        ours.add(sender_domain)
    if any(value == d or value.endswith("." + d) for d in ours if d):
        raise ValidationFailedError("This domain belongs to rootsquares: use your own", code="mail_domain_ours")
    return value


def clean_local(raw: str | None) -> str:
    value = (raw or DEFAULT_LOCAL).strip().lower()
    if not LOCAL_RE.match(value):
        raise ValidationFailedError(
            "The name before the @ may have letters, digits, dots, hyphens and underscores, for example hello or tickets", code="mail_local_invalid"
        )
    return value


def _records(raw: str | None) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw or "[]")
    except ValueError:
        return []
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _pack(records: object) -> str:
    keep = ("record", "type", "name", "value", "priority", "status")
    rows = [{k: r[k] for k in keep if k in r} for r in records if isinstance(r, dict)] if isinstance(records, list) else []
    return json.dumps(rows)


def is_verified(sq: Square) -> bool:
    return bool(sq.mail_domain and sq.mail_domain_status == VERIFIED)


def _state(sq: Square) -> str:
    if is_verified(sq):
        return "verified"
    if sq.mail_domain and sq.mail_domain_id:
        return "registered"
    return "requested" if sq.mail_domain_request else "none"


def describe(sq: Square) -> MailDomainOut:
    local = sq.mail_from_local or DEFAULT_LOCAL
    return MailDomainOut(
        allowed=allowed(sq),
        available=current_app.extensions.get("resend_domains") is not None,
        domain=sq.mail_domain,
        local_part=local,
        status=sq.mail_domain_status if sq.mail_domain else None,
        verified=is_verified(sq),
        from_address=f"{local}@{sq.mail_domain}" if is_verified(sq) else None,
        records=[
            MailDomainRecordOut(
                record=str(r.get("record", "")),
                type=str(r.get("type", "")),
                name=str(r.get("name", "")),
                value=str(r.get("value", "")),
                priority=r["priority"] if isinstance(r.get("priority"), int) else None,
                status=str(r.get("status", "")),
            )
            for r in _records(sq.mail_domain_records)
        ],
        state=_state(sq),
        requested_domain=sq.mail_domain_request,
        requested_local=sq.mail_domain_request_local,
        requested_at=sq.mail_domain_requested_at,
        help_requested=sq.mail_domain_help_at is not None,
        auto_approve=bool(current_app.extensions["settings"].MAIL_DOMAIN_AUTO_APPROVE),
    )


def _client() -> ResendDomains:
    client = current_app.extensions.get("resend_domains")
    if client is None:
        raise MailNotReady("The e-mail service key for domains is not set (RESEND_DOMAINS_API_KEY)")
    return client  # type: ignore[no-any-return]


def _delete_quietly(client: ResendDomains, domain_id: str) -> None:
    """A domain that Resend no longer knows (404) is already gone; any other refusal stops the change so nothing is left behind unseen."""
    try:
        client.delete(domain_id)
    except DomainApiError as exc:
        if exc.status != 404:
            raise MailProviderError(str(exc), provider_status=exc.status) from exc


def _taken(db: Session, sq: Square, domain: str) -> bool:
    other = db.scalar(select(Square.id).where(Square.id != sq.id, (Square.mail_domain == domain) | (Square.mail_domain_request == domain)))
    return other is not None


def _tell_staff(subject: str, text: str) -> None:
    """Best effort: no address set or no e-mail service means nothing is sent and nothing breaks."""
    settings: Settings = current_app.extensions["settings"]
    email = current_app.extensions["providers"].email
    if email is None or not settings.STAFF_NOTICE_EMAIL:
        return
    mail = email_html.from_text(text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Staff", heading=subject, button_label="Open")
    try:
        email.send(settings.STAFF_NOTICE_EMAIL, subject, text, **mail)
    except Exception:  # noqa: BLE001 - a refused mail must not undo the owner's request
        current_app.logger.warning("mail_domain_staff_notice_failed")


def _tell_owner(db: Session, sq: Square, subject: str, text: str, button: str = "Open Settings") -> bool:
    settings: Settings = current_app.extensions["settings"]
    mail = email_html.from_text(text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Your sending domain", heading=subject, button_label=button)
    return notify.send_to_owner(current_app, db, sq, subject, text, **mail)


def register_domain(db: Session, sq: Square, domain: str, local: str, client: ResendDomains) -> None:
    """Register the domain at Resend (deleting the square's earlier one) and keep what Resend answers.
    The same domain again only changes the name before the @."""
    if not (sq.mail_domain == domain and sq.mail_domain_id):
        if sq.mail_domain_id:
            _delete_quietly(client, sq.mail_domain_id)
        try:
            created = client.create(domain)
        except DomainApiError as exc:
            raise MailProviderError(str(exc), provider_status=exc.status) from exc
        sq.mail_domain = domain
        sq.mail_domain_id = str(created.get("id") or "") or None
        sq.mail_domain_status = str(created.get("status") or "not_started")
        sq.mail_domain_records = _pack(created.get("records"))
        sq.mail_domain_notified = None
    sq.mail_from_local = local


def refresh(sq: Square, client: ResendDomains, ask: bool = True) -> None:
    """Ask Resend to look at the DNS again (`ask`) and read the status and the records."""
    assert sq.mail_domain_id
    try:
        if ask:
            client.verify(sq.mail_domain_id)
        data = client.get(sq.mail_domain_id)
    except DomainApiError as exc:
        raise MailProviderError(str(exc), provider_status=exc.status) from exc
    sq.mail_domain_status = str(data.get("status") or sq.mail_domain_status or "pending")
    if data.get("records"):
        sq.mail_domain_records = _pack(data.get("records"))


def remove_domain(sq: Square, client: ResendDomains | None) -> None:
    if sq.mail_domain_id and client is not None:
        _delete_quietly(client, sq.mail_domain_id)
    sq.mail_domain = sq.mail_domain_id = sq.mail_domain_status = sq.mail_domain_records = sq.mail_from_local = sq.mail_domain_notified = None
    sq.mail_domain_help_at = None  # a help request belongs to the domain it was asked for


def run(db: Session, client: ResendDomains, settings: Settings, apply: bool) -> list[dict[str, str]]:
    """The hourly job (`flask mail-domain-run`): read every registered domain from Resend, keep its status, and tell the owner once when it becomes
    verified and once
    when Resend gives up (failed). A verified domain that Resend can no longer see changes status too, so the square stops sending from it. Dry run
    unless `apply`."""
    actions: list[dict[str, str]] = []
    for sq in db.scalars(select(Square).where(Square.mail_domain_id.is_not(None))):
        was = sq.mail_domain_status or ""
        domain_id = sq.mail_domain_id or ""
        try:
            if was != VERIFIED:
                client.verify(domain_id)
            data = client.get(domain_id)
        except DomainApiError as exc:
            actions.append({"slug": sq.slug, "action": "error", "detail": str(exc)[:80]})
            continue
        now = str(data.get("status") or was)
        notice = ""
        if now == VERIFIED and sq.mail_domain_notified != "ready":
            notice = "ready"
        elif now == "failed" and sq.mail_domain_notified != "failed":
            notice = "failed"
        if now == was and not notice:
            continue
        actions.append({"slug": sq.slug, "action": "status", "was": was, "now": now, "notice": notice})
        if not apply:
            continue
        sq.mail_domain_status = now
        if data.get("records"):
            sq.mail_domain_records = _pack(data.get("records"))
        if notice:
            subject, text = (mail_domain_mail.owner_ready if notice == "ready" else mail_domain_mail.owner_failed)(settings, sq)
            if _tell_owner(db, sq, subject, text):
                sq.mail_domain_notified = notice
    return actions


def register() -> None:
    from app.platform import routes as R

    bp, api = R.bp, R.api

    def _own(square_id: uuid.UUID, need_owner: bool) -> Square:
        db = get_session()
        sq = db.get(Square, square_id)
        if sq is None or sq.org_id not in R._member_org_ids(db, g.user):
            raise NotFoundError("Square not found")
        if need_owner:
            owner = db.scalar(
                select(Membership).where(Membership.org_id == sq.org_id, Membership.user_id == g.user.id, Membership.role == MembershipRole.OWNER)
            )
            if owner is None:
                raise ForbiddenError("Only the owner of the square can change its sending domain", code="owner_only")
            if not allowed(sq):
                raise ForbiddenError("An own sending domain is in the Grove package", code="package_required")
        return sq

    def _any(square_id: uuid.UUID) -> Square:
        sq = get_session().get(Square, square_id)
        if sq is None:
            raise NotFoundError("Square not found")
        return sq

    # ---- the owner ------------------------------------------------------------------------------------------------------------------

    @bp.get("/squares/<uuid:square_id>/mail-domain")
    @api.validate(resp=SpecResponse(HTTP_200=MailDomainOut), tags=["squares"])
    @R.login_required
    def get_mail_domain(square_id: uuid.UUID) -> Response:
        return R._out(describe(_own(square_id, False)))

    @bp.post("/squares/<uuid:square_id>/mail-domain/request")
    @api.validate(json=MailDomainRequestIn, resp=SpecResponse(HTTP_200=MailDomainOut), tags=["squares"])
    @R.login_required
    def request_mail_domain(square_id: uuid.UUID) -> Response:
        """The owner asks for a domain. With MAIL_DOMAIN_AUTO_APPROVE (the default) it is set up at once;
        otherwise staff are told by e-mail and set it up (or turn it down)."""
        body: MailDomainRequestIn = request.context.json  # type: ignore[attr-defined]
        sq = _own(square_id, True)
        db = get_session()
        if sq.mail_domain:
            raise ConflictError("Remove the sending domain you have before asking for another", code="mail_domain_exists")
        domain, local = clean_domain(body.domain, R._settings()), clean_local(body.local_part)
        if _taken(db, sq, domain):
            raise ConflictError("This domain is already used by another square", code="mail_domain_taken")
        client = current_app.extensions.get("resend_domains")
        if R._settings().MAIL_DOMAIN_AUTO_APPROVE and client is not None:
            # the plan allows it: set it up at once (as staff would). If Resend refuses, nothing is saved and the owner is shown Resend's own sentence.
            register_domain(db, sq, domain, local, client)
            R._audit("square.mail_domain_approve", "square", str(sq.id), sq.org_id, auto=True)
            db.commit()
            _tell_owner(db, sq, *mail_domain_mail.owner_approved(R._settings(), sq))
            _tell_staff(*mail_domain_mail.staff_auto(R._settings(), sq))
            return R._out(describe(sq))
        sq.mail_domain_request, sq.mail_domain_request_local = domain, local
        sq.mail_domain_requested_at = dt.datetime.now(dt.UTC)
        R._audit("square.mail_domain_request", "square", str(sq.id), sq.org_id)
        db.commit()
        _tell_staff(*mail_domain_mail.staff_request(R._settings(), sq))
        return R._out(describe(sq))

    @bp.delete("/squares/<uuid:square_id>/mail-domain/request")
    @api.validate(resp=SpecResponse(HTTP_200=MailDomainOut), tags=["squares"])
    @R.login_required
    def withdraw_mail_domain_request(square_id: uuid.UUID) -> Response:
        sq = _own(square_id, True)
        sq.mail_domain_request = sq.mail_domain_request_local = sq.mail_domain_requested_at = sq.mail_domain_help_at = None
        R._audit("square.mail_domain_withdraw", "square", str(sq.id), sq.org_id)
        get_session().commit()
        return R._out(describe(sq))

    @bp.put("/squares/<uuid:square_id>/mail-domain/name")
    @api.validate(json=MailDomainNameIn, resp=SpecResponse(HTTP_200=MailDomainOut), tags=["squares"])
    @R.login_required
    def set_mail_from_name(square_id: uuid.UUID) -> Response:
        """The name before the @ of a registered domain (a request's name is part of the request: withdraw and ask again)."""
        body: MailDomainNameIn = request.context.json  # type: ignore[attr-defined]
        sq = _own(square_id, True)
        if not sq.mail_domain:
            raise ConflictError("There is no sending domain yet", code="mail_domain_missing")
        sq.mail_from_local = clean_local(body.local_part)
        R._audit("square.mail_domain_name", "square", str(sq.id), sq.org_id)
        get_session().commit()
        return R._out(describe(sq))

    @bp.post("/squares/<uuid:square_id>/mail-domain/check")
    @api.validate(resp=SpecResponse(HTTP_200=MailDomainOut), tags=["squares"])
    @R.login_required
    def check_mail_domain(square_id: uuid.UUID) -> Response:
        """Ask Resend to look at the DNS again and read the new status and records (the hourly job does this too)."""
        sq = _own(square_id, True)
        if not sq.mail_domain_id:
            raise ConflictError("There is no registered domain to check yet", code="mail_domain_missing")
        refresh(sq, _client())
        R._audit("square.mail_domain_check", "square", str(sq.id), sq.org_id, status=sq.mail_domain_status)
        get_session().commit()
        return R._out(describe(sq))

    @bp.delete("/squares/<uuid:square_id>/mail-domain")
    @api.validate(resp=SpecResponse(HTTP_200=MailDomainOut), tags=["squares"])
    @R.login_required
    def remove_mail_domain(square_id: uuid.UUID) -> Response:
        """Take the domain off the square and delete it at Resend; the square's mail goes back to the shared sending domain."""
        sq = _own(square_id, True)
        remove_domain(sq, _client() if sq.mail_domain_id else None)
        R._audit("square.mail_domain_remove", "square", str(sq.id), sq.org_id)
        get_session().commit()
        return R._out(describe(sq))

    @bp.post("/squares/<uuid:square_id>/mail-domain/instructions")
    @api.validate(json=MailDomainInstructionsIn, resp=SpecResponse(HTTP_200=MailDomainOut), tags=["squares"])
    @R.login_required
    def send_mail_domain_instructions(square_id: uuid.UUID) -> Response:
        """The owner e-mails the records and plain steps to the person who looks after their domain."""
        body: MailDomainInstructionsIn = request.context.json  # type: ignore[attr-defined]
        sq = _own(square_id, True)
        records = _records(sq.mail_domain_records)
        email = current_app.extensions["providers"].email
        if not sq.mail_domain or not records:
            raise ConflictError("The records are not ready yet: we are setting up your domain", code="mail_domain_missing")
        if email is None:
            raise MailNotReady("This server cannot send e-mail yet (EMAIL_PROVIDER)", code="email_not_ready")
        subject, text = mail_domain_mail.instructions(sq, records)
        mail = email_html.from_text(text, site_url=R._settings().PLATFORM_FRONTEND_URL, eyebrow="E-mail records", heading=subject)
        try:
            email.send(str(body.to), subject, text, **mail)
        except Exception as exc:  # noqa: BLE001 - say that it failed, not why (no address or key in the answer)
            raise MailProviderError("The e-mail could not be sent. Try again, or copy the records by hand.") from exc
        R._audit("square.mail_domain_instructions", "square", str(sq.id), sq.org_id)
        get_session().commit()
        return R._out(describe(sq))

    @bp.post("/squares/<uuid:square_id>/mail-domain/help")
    @api.validate(resp=SpecResponse(HTTP_200=MailDomainOut), tags=["squares"])
    @R.login_required
    def ask_mail_domain_help(square_id: uuid.UUID) -> Response:
        """The owner asks staff to help with the domain (a small one-time support fee applies: agreed and invoiced by hand for now)."""
        sq = _own(square_id, True)
        sq.mail_domain_help_at = dt.datetime.now(dt.UTC)
        R._audit("square.mail_domain_help", "square", str(sq.id), sq.org_id)
        db = get_session()
        db.commit()
        _tell_staff(*mail_domain_mail.staff_help(R._settings(), sq, sq.mail_contact_email))
        return R._out(describe(sq))

    # ---- staff (the admin application) ------------------------------------------------------------------------------------------------

    @bp.get("/owner/squares/<uuid:square_id>/mail-domain")
    @api.validate(resp=SpecResponse(HTTP_200=MailDomainOut), tags=["owner"])
    @R.admin_required
    def owner_mail_domain_get(square_id: uuid.UUID) -> Response:
        return R._out(describe(_any(square_id)))

    @bp.post("/owner/squares/<uuid:square_id>/mail-domain/approve")
    @api.validate(json=MailDomainApproveIn, resp=SpecResponse(HTTP_200=MailDomainOut), tags=["owner"])
    @R.admin_required
    def owner_mail_domain_approve(square_id: uuid.UUID) -> Response:
        """Set up the requested domain: register it at Resend and tell the owner to add the records. Staff may correct the domain or the name."""
        body: MailDomainApproveIn = request.context.json  # type: ignore[attr-defined]
        sq = _any(square_id)
        db = get_session()
        if not allowed(sq):
            raise ConflictError("The square's package does not have an own sending domain", code="package_required")
        domain = clean_domain(body.domain or sq.mail_domain_request or "", R._settings())
        local = clean_local(body.local_part or sq.mail_domain_request_local)
        if _taken(db, sq, domain):
            raise ConflictError("This domain is already used by another square", code="mail_domain_taken")
        register_domain(db, sq, domain, local, _client())
        sq.mail_domain_request = sq.mail_domain_request_local = sq.mail_domain_requested_at = None
        R._audit("square.mail_domain_approve", "square", str(sq.id), sq.org_id)
        db.commit()
        _tell_owner(db, sq, *mail_domain_mail.owner_approved(R._settings(), sq))
        return R._out(describe(sq))

    @bp.post("/owner/squares/<uuid:square_id>/mail-domain/reject")
    @api.validate(json=MailDomainRejectIn, resp=SpecResponse(HTTP_200=MailDomainOut), tags=["owner"])
    @R.admin_required
    def owner_mail_domain_reject(square_id: uuid.UUID) -> Response:
        body: MailDomainRejectIn = request.context.json  # type: ignore[attr-defined]
        sq = _any(square_id)
        if not sq.mail_domain_request:
            raise ConflictError("There is no request to turn down", code="mail_domain_missing")
        asked = sq.mail_domain_request
        sq.mail_domain_request = sq.mail_domain_request_local = sq.mail_domain_requested_at = sq.mail_domain_help_at = None
        R._audit("square.mail_domain_reject", "square", str(sq.id), sq.org_id)
        db = get_session()
        db.commit()
        _tell_owner(db, sq, *mail_domain_mail.owner_rejected(R._settings(), sq, asked, body.note))
        return R._out(describe(sq))

    @bp.post("/owner/squares/<uuid:square_id>/mail-domain/check")
    @api.validate(resp=SpecResponse(HTTP_200=MailDomainOut), tags=["owner"])
    @R.admin_required
    def owner_mail_domain_check(square_id: uuid.UUID) -> Response:
        sq = _any(square_id)
        if not sq.mail_domain_id:
            raise ConflictError("There is no registered domain to check yet", code="mail_domain_missing")
        refresh(sq, _client())
        R._audit("square.mail_domain_check", "square", str(sq.id), sq.org_id, status=sq.mail_domain_status)
        get_session().commit()
        return R._out(describe(sq))

    @bp.delete("/owner/squares/<uuid:square_id>/mail-domain")
    @api.validate(resp=SpecResponse(HTTP_200=MailDomainOut), tags=["owner"])
    @R.admin_required
    def owner_mail_domain_remove(square_id: uuid.UUID) -> Response:
        sq = _any(square_id)
        remove_domain(sq, _client() if sq.mail_domain_id else None)
        R._audit("square.mail_domain_remove", "square", str(sq.id), sq.org_id, by="staff")
        get_session().commit()
        return R._out(describe(sq))
