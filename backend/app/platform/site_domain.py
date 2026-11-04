"""A Grove square's own website domain (ADR 098, W26-R4): the owner REQUESTS a domain such as www.theirassociation.org and points it with a CNAME at
`CUSTOM_DOMAIN_TARGET` (squares.rootsquares.com, a name rootsquares owns, so the owner never sees the host's address); staff add the domain on the
host by hand and then ACTIVATE it here, after which the square is served on it as well as on its default address (`squares.domain`).

The owner may read it, request, withdraw a request, check the DNS and remove the domain. Staff (the admin application) activate, turn down, and remove.
Only Grove and a square made before packages have it (`allowed`). Nothing is deleted when a package is lost: the platform just stops serving the domain
(`active_domain`). The platform stores only the domain names, which are not a person's data. The handlers are registered on the platform blueprint by
`register()` (called at the end of routes.py); the staff ones are `admin_required` and served by the staff API only.
"""

from __future__ import annotations

import datetime as dt
import socket
import uuid

from flask import Response, current_app, g, request
from spectree import Response as SpecResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import email_html, notify, plans
from app.platform.mail_domain import DOMAIN_RE, _tell_staff
from app.platform.models import Membership, MembershipRole, Square
from app.platform.schemas import SiteDomainActivateIn, SiteDomainOut, SiteDomainRejectIn, SiteDomainRequestIn
from app.providers.render_domains import RenderApiError, RenderDomains
from app.shared.config import Settings
from app.shared.db import get_session
from app.shared.errors import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationFailedError


class HostError(AppError):
    status, code, title = 502, "site_domain_host_error", "The host (Render) refused the request"


def allowed(sq: Square) -> bool:
    """Grove, and a square made before packages (they count as Grove). A custom package does not have it yet (decided with the package, ADR 082)."""
    return (sq.launch_package or plans.LEGACY_PACKAGE) == plans.GROVE


def clean_domain(raw: str, settings: Settings) -> str:
    value = (raw or "").strip().lower().rstrip(".")
    if value.startswith(("http://", "https://")) or "/" in value or "@" in value or " " in value or ":" in value:
        raise ValidationFailedError("Type only the domain, for example www.theirassociation.org", code="site_domain_invalid")
    if not DOMAIN_RE.match(value):
        raise ValidationFailedError("This is not a domain name. Example: www.theirassociation.org", code="site_domain_invalid")
    suffix = settings.SQUARE_DOMAIN_SUFFIX.strip().lower().lstrip(".")
    target = settings.CUSTOM_DOMAIN_TARGET.strip().lower()
    if value == target or (suffix and (value == suffix or value.endswith("." + suffix))):
        raise ValidationFailedError("This domain belongs to rootsquares: use your own", code="site_domain_ours")
    return value


def active_domain(sq: Square) -> str | None:
    """The own domain the square is served on: set, and the package still has the feature."""
    return sq.site_domain if sq.site_domain and allowed(sq) else None


def _state(sq: Square) -> str:
    if sq.site_domain:
        return "active"
    return "requested" if sq.site_domain_request else "none"


def describe(sq: Square, dns: str = "unchecked", render: str = "off") -> SiteDomainOut:
    settings: Settings = current_app.extensions["settings"]
    return SiteDomainOut(
        allowed=allowed(sq),
        target=settings.CUSTOM_DOMAIN_TARGET,
        state=_state(sq),
        domain=sq.site_domain,
        requested_domain=sq.site_domain_request,
        requested_at=sq.site_domain_requested_at,
        default_domain=sq.domain,
        help_requested=sq.site_domain_help_at is not None,
        dns=dns,
        render=render,
    )


def _client() -> RenderDomains | None:
    """Render's Custom Domains API, only on the service that holds the key (the admin service); None = staff add domains on Render by hand."""
    client = current_app.extensions.get("render_domains")
    return client if isinstance(client, RenderDomains) or hasattr(client, "create") else None


def twin(domain: str) -> str:
    """The other form Render may add beside a domain: the www name for a bare one, the bare name for a www one."""
    return domain[4:] if domain.startswith("www.") else "www." + domain


def render_state(client: RenderDomains | None, domain: str | None) -> str:
    """off | not_added | unverified | verified | unknown: what Render says about the domain (a read; nothing changes)."""
    if client is None or not domain:
        return "off"
    try:
        found = client.get(domain)
    except RenderApiError as exc:
        return "not_added" if exc.status == 404 else "unknown"
    return "verified" if found.get("verificationStatus") == "verified" else "unverified"


def _add_on_host(client: RenderDomains, domain: str) -> None:
    """Add the domain on Render (it may already be there: a 409 is fine) and ask Render to look at the DNS. A refusal is shown to staff in Render's words."""
    try:
        client.create(domain)
    except RenderApiError as exc:
        if exc.status != 409:
            raise HostError(str(exc)) from exc
    try:
        client.verify(domain)
    except RenderApiError:
        pass  # Render checks the DNS by itself as well; the staff card shows the state


def _remove_on_host(client: RenderDomains, db: Session, sq: Square, domain: str) -> None:
    """Delete the domain on Render, and its twin unless another square uses it. Already gone (404) is fine."""
    names = [domain]
    other = twin(domain)
    if not db.scalar(select(Square.id).where(Square.id != sq.id, (Square.site_domain == other) | (Square.site_domain_request == other))):
        names.append(other)
    for name in names:
        try:
            client.delete(name)
        except RenderApiError as exc:
            if exc.status != 404:
                raise HostError(str(exc)) from exc


def _addresses(host: str) -> set[str] | None:
    try:
        return {str(info[4][0]) for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)}
    except OSError:
        return None


def dns_state(domain: str, target: str) -> str:
    """Does `domain` lead to the same addresses as the target? `pointing` | `not_pointing` | `unknown` (the name does not resolve yet, or the lookup failed).
    A lookup, not a promise: a name can resolve here and still be wrong elsewhere while the DNS spreads."""
    mine, ours = _addresses(domain), _addresses(target)
    if mine is None or ours is None:
        return "unknown"
    return "pointing" if mine & ours else "not_pointing"


def _taken(db: Session, sq: Square, domain: str) -> bool:
    other = db.scalar(select(Square.id).where(Square.id != sq.id, (Square.site_domain == domain) | (Square.site_domain_request == domain)))
    return other is not None


def _tell_owner(db: Session, sq: Square, subject: str, text: str) -> bool:
    settings: Settings = current_app.extensions["settings"]
    mail = email_html.from_text(text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Your own domain", heading=subject, button_label="Open Domain")
    return notify.send_to_owner(current_app, db, sq, subject, text, **mail)


def _owner_link(settings: Settings, sq: Square) -> str:
    return f"{settings.PLATFORM_FRONTEND_URL.rstrip('/')}/squares/{sq.id}/domain"


def _staff_link(settings: Settings, sq: Square) -> str:
    base = (settings.admin_origins or [settings.PLATFORM_FRONTEND_URL])[0].rstrip("/")
    return f"{base}/squares/{sq.id}?tab=actions"


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
                raise ForbiddenError("Only the owner of the square can change its domain", code="owner_only")
            if not allowed(sq):
                raise ForbiddenError("An own website domain is in the Grove package", code="package_required")
        return sq

    def _any(square_id: uuid.UUID) -> Square:
        sq = get_session().get(Square, square_id)
        if sq is None:
            raise NotFoundError("Square not found")
        return sq

    # ---- the owner ------------------------------------------------------------------------------------------------------------------

    @bp.get("/squares/<uuid:square_id>/site-domain")
    @api.validate(resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["squares"])
    @R.login_required
    def get_site_domain(square_id: uuid.UUID) -> Response:
        return R._out(describe(_own(square_id, False)))

    @bp.post("/squares/<uuid:square_id>/site-domain/request")
    @api.validate(json=SiteDomainRequestIn, resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["squares"])
    @R.login_required
    def request_site_domain(square_id: uuid.UUID) -> Response:
        """The owner asks for a domain; staff are told by e-mail and add it on the host (then activate it)."""
        body: SiteDomainRequestIn = request.context.json  # type: ignore[attr-defined]
        sq = _own(square_id, True)
        db = get_session()
        if sq.site_domain or sq.site_domain_request:
            raise ConflictError("Remove the domain you have, or withdraw the request, before asking for another", code="site_domain_exists")
        domain = clean_domain(body.domain, R._settings())
        if _taken(db, sq, domain):
            raise ConflictError("This domain is already used by another square", code="site_domain_taken")
        sq.site_domain_request = domain
        sq.site_domain_requested_at = dt.datetime.now(dt.UTC)
        R._audit("square.site_domain_request", "square", str(sq.id), sq.org_id)
        db.commit()
        settings = R._settings()
        _tell_staff(
            f"Own website domain requested: {sq.name}",
            f"{sq.name} asks for its own website domain.\n\nDomain: {domain}\n\n"
            f"Add it as a custom domain on the square site in Render, then activate it in the admin application (Actions, Own website domain):\n"
            f"{_staff_link(settings, sq)}\n",
        )
        return R._out(describe(sq))

    @bp.delete("/squares/<uuid:square_id>/site-domain/request")
    @api.validate(resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["squares"])
    @R.login_required
    def withdraw_site_domain_request(square_id: uuid.UUID) -> Response:
        sq = _own(square_id, True)
        sq.site_domain_request = sq.site_domain_requested_at = sq.site_domain_help_at = None
        R._audit("square.site_domain_withdraw", "square", str(sq.id), sq.org_id)
        get_session().commit()
        return R._out(describe(sq))

    @bp.post("/squares/<uuid:square_id>/site-domain/check")
    @api.validate(resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["squares"])
    @R.login_required
    def check_site_domain(square_id: uuid.UUID) -> Response:
        """Look the DNS up: does the owner's domain lead to the rootsquares address? Nothing is stored."""
        sq = _own(square_id, True)
        domain = sq.site_domain or sq.site_domain_request
        if not domain:
            raise ConflictError("There is no domain to check yet", code="site_domain_missing")
        return R._out(describe(sq, dns_state(domain, R._settings().CUSTOM_DOMAIN_TARGET)))

    @bp.post("/squares/<uuid:square_id>/site-domain/help")
    @api.validate(resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["squares"])
    @R.login_required
    def ask_site_domain_help(square_id: uuid.UUID) -> Response:
        """The owner asks staff to help with the domain (a small one-time support fee applies: agreed and invoiced by hand for now)."""
        sq = _own(square_id, True)
        sq.site_domain_help_at = dt.datetime.now(dt.UTC)
        R._audit("square.site_domain_help", "square", str(sq.id), sq.org_id)
        get_session().commit()
        _tell_staff(
            f"IT help asked (website domain): {sq.name}",
            f"{sq.name} asked for help with its own website domain. The owner was told that a small one-time support fee applies.\n\n"
            f"Domain: {sq.site_domain or sq.site_domain_request or 'not chosen yet'}\n"
            f"E-mail contact of the square: {sq.mail_contact_email or 'not set'}\n\n"
            f"Open the square in the admin application:\n{_staff_link(R._settings(), sq)}\n",
        )
        return R._out(describe(sq))

    @bp.delete("/squares/<uuid:square_id>/site-domain")
    @api.validate(resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["squares"])
    @R.login_required
    def remove_site_domain(square_id: uuid.UUID) -> Response:
        """The square stops being served on the domain at once; staff are told to remove it on the host."""
        sq = _own(square_id, True)
        if not sq.site_domain:
            raise ConflictError("There is no active domain to remove", code="site_domain_missing")
        gone = sq.site_domain
        sq.site_domain = sq.site_domain_help_at = None
        R._audit("square.site_domain_remove", "square", str(sq.id), sq.org_id, by="owner")
        get_session().commit()
        _tell_staff(
            f"Own website domain removed: {sq.name}",
            f"{sq.name} removed its own website domain {gone}. It is no longer served.\n"
            "Remove it as a custom domain in Render (it counts against the included domains).\n",
        )
        return R._out(describe(sq))

    # ---- staff (the admin application) ------------------------------------------------------------------------------------------------

    @bp.get("/owner/squares/<uuid:square_id>/site-domain")
    @api.validate(resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["owner"])
    @R.admin_required
    def owner_site_domain_get(square_id: uuid.UUID) -> Response:
        sq = _any(square_id)
        domain = sq.site_domain or sq.site_domain_request
        return R._out(describe(sq, dns_state(domain, R._settings().CUSTOM_DOMAIN_TARGET) if domain else "unchecked", render_state(_client(), domain)))

    @bp.post("/owner/squares/<uuid:square_id>/site-domain/check")
    @api.validate(resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["owner"])
    @R.admin_required
    def owner_site_domain_check(square_id: uuid.UUID) -> Response:
        """Staff ask Render to look at the DNS again, then read the DNS and Render's answer."""
        sq = _any(square_id)
        domain = sq.site_domain or sq.site_domain_request
        if not domain:
            raise ConflictError("There is no domain to check yet", code="site_domain_missing")
        client = _client()
        if client is not None:
            try:
                client.verify(domain)
            except RenderApiError:
                pass  # not added yet, or Render busy: the state below says which
        return R._out(describe(sq, dns_state(domain, R._settings().CUSTOM_DOMAIN_TARGET), render_state(client, domain)))

    @bp.post("/owner/squares/<uuid:square_id>/site-domain/activate")
    @api.validate(json=SiteDomainActivateIn, resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["owner"])
    @R.admin_required
    def owner_site_domain_activate(square_id: uuid.UUID) -> Response:
        """Staff added the domain on the host: the square is served on it from now on. Staff may correct the domain of the request."""
        body: SiteDomainActivateIn = request.context.json  # type: ignore[attr-defined]
        sq = _any(square_id)
        db = get_session()
        if not allowed(sq):
            raise ConflictError("The square's package does not have an own website domain", code="package_required")
        domain = clean_domain(body.domain or sq.site_domain_request or "", R._settings())
        if _taken(db, sq, domain):
            raise ConflictError("This domain is already used by another square", code="site_domain_taken")
        client = _client()
        if client is not None:
            _add_on_host(client, domain)  # before anything is saved: if Render refuses, the request stays and staff see why
        sq.site_domain, sq.site_domain_request, sq.site_domain_requested_at = domain, None, None
        R._audit("square.site_domain_activate", "square", str(sq.id), sq.org_id, host="render" if client is not None else "by hand")
        db.commit()
        _tell_owner(
            db,
            sq,
            "Your own domain is ready",
            f"{sq.name} is now served on {domain}. Your address {sq.domain} keeps working.\n\nIf the page does not open yet, the DNS may still be spreading: "
            f"it can take a few hours. Open the Domain page to check:\n{_owner_link(R._settings(), sq)}\n",
        )
        return R._out(describe(sq, render=render_state(client, domain)))

    @bp.post("/owner/squares/<uuid:square_id>/site-domain/reject")
    @api.validate(json=SiteDomainRejectIn, resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["owner"])
    @R.admin_required
    def owner_site_domain_reject(square_id: uuid.UUID) -> Response:
        body: SiteDomainRejectIn = request.context.json  # type: ignore[attr-defined]
        sq = _any(square_id)
        if not sq.site_domain_request:
            raise ConflictError("There is no request to turn down", code="site_domain_missing")
        asked = sq.site_domain_request
        sq.site_domain_request = sq.site_domain_requested_at = sq.site_domain_help_at = None
        R._audit("square.site_domain_reject", "square", str(sq.id), sq.org_id)
        db = get_session()
        db.commit()
        note = f"\n\n{body.note.strip()}" if body.note.strip() else ""
        link = _owner_link(R._settings(), sq)
        _tell_owner(db, sq, "Your own domain request", f"We could not set up {asked} for {sq.name}.{note}\n\nOpen the Domain page to ask again:\n{link}\n")
        return R._out(describe(sq))

    @bp.delete("/owner/squares/<uuid:square_id>/site-domain")
    @api.validate(resp=SpecResponse(HTTP_200=SiteDomainOut), tags=["owner"])
    @R.admin_required
    def owner_site_domain_remove(square_id: uuid.UUID) -> Response:
        sq = _any(square_id)
        db = get_session()
        client = _client()
        if client is not None and sq.site_domain:
            _remove_on_host(client, db, sq, sq.site_domain)  # before anything is cleared: if Render refuses, the domain stays and staff see why
        sq.site_domain = sq.site_domain_request = sq.site_domain_requested_at = sq.site_domain_help_at = None
        R._audit("square.site_domain_remove", "square", str(sq.id), sq.org_id, by="staff")
        db.commit()
        return R._out(describe(sq))
