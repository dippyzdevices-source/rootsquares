"""Platform API: auth (signup, login, logout, me, refresh, password-reset stub), squares, owner (platform admin) and the audit log.

Sessions are JWTs in httpOnly cookies (SameSite=Lax). Mutating requests must carry `X-Requested-With: rootsquares` (CSRF defence together
with SameSite and the CORS allow-list). Passwords are hashed with argon2. Login is rate limited per (ip, email)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any, cast

import httpx
import structlog
from flask import Blueprint, Flask, Response, current_app, g, jsonify, request
from pydantic import BaseModel
from spectree import Response as SpecResponse
from spectree import SpecTree
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.platform import admin_auth, email_html, square_auth, starter_sets, theme_overrides
from app.platform import attention as attention_list
from app.platform import billing as billing_service
from app.platform import event_pass as event_pass_service
from app.platform import modules as square_modules
from app.platform import notify as notify_service
from app.platform import plans as square_plans
from app.platform import sleep as sleep_service
from app.platform import subscriptions as subscriptions_service
from app.platform import trial as trial_service
from app.platform import vouchers as voucher_service
from app.platform.health_checks import environment, run_checks
from app.platform.identity import resolve_user_from_token
from app.platform.lifecycle import delete_account, delete_square, export_user
from app.platform.models import AuditLog, AuthSession, BillingOrder, Membership, MembershipRole, Organization, PlanPrice, Square, SquareStatus, StaffUser, User
from app.platform.module_status import fetch_module_status, fetch_square_health
from app.platform.provisioning import NeonApiError, NeonProvisioner, Owner, neon_target, provision_square
from app.platform.public import public_auth_config, square_database_check
from app.platform.reserved_slugs import is_reserved
from app.platform.schemas import (
    AccountDeleted,
    AccountDeleteIn,
    Ack,
    BillingIntervalIn,
    CheckoutIn,
    CheckoutOut,
    CorePartOut,
    EventPassOut,
    FakeConfirmIn,
    GoogleIn,
    HealthCheckOut,
    LoggedOutOut,
    LoginIn,
    MailContactIn,
    ModuleList,
    ModuleOut,
    ModulesIn,
    ModuleStatusList,
    ModuleStatusOut,
    OrderList,
    OrderOut,
    OrganizationIn,
    OrganizationOut,
    OwnerAttentionList,
    OwnerAuditItem,
    OwnerAuditPage,
    OwnerHealth,
    OwnerOrderOut,
    OwnerOrgList,
    OwnerOrgOut,
    OwnerOverview,
    OwnerSquareDetail,
    OwnerSquareList,
    OwnerSquareOut,
    OwnerSquareRef,
    OwnerSubscriptions,
    OwnerTimelineItem,
    OwnerUserDetail,
    OwnerUserList,
    OwnerUserOrg,
    OwnerUserOut,
    OwnerWeek,
    PasswordResetIn,
    PlanChangeIn,
    PlanIn,
    PortalAttentionList,
    PortalOut,
    PriceIn,
    PriceList,
    PriceOut,
    PublicSquareOut,
    RefundIn,
    RunningPlanIn,
    SignupIn,
    SquareCheckOut,
    SquareDeleteIn,
    SquareHealthCheckOut,
    SquareHealthOut,
    SquareIn,
    SquareList,
    SquareMeOut,
    SquareOut,
    StarterSetList,
    StarterSetOut,
    SuspendIn,
    ThemeDraftIn,
    ThemeIn,
    ThemeSeasonsIn,
    UserOut,
)
from app.platform.square_verifier import SquareAuthError
from app.shared.config import Settings
from app.shared.crypto import DUMMY_HASH, Encryptor, hash_password, make_token, read_token, verify_password
from app.shared.db import get_session
from app.shared.errors import AppError, BadRequestError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ValidationFailedError
from app.shared.request_context import get_request_id

API_PREFIX = "/api/platform/v1"
ACCESS_COOKIE, REFRESH_COOKIE = "rs_access", "rs_refresh"
CSRF_HEADER, CSRF_VALUE = "X-Requested-With", "rootsquares"


class RateLimitedError(AppError):
    status, code, title = 429, "rate_limited", "Too many attempts"


def _validation_hook(req: Any, resp: Any, req_validation_error: Any, instance: Any, *_: Any) -> None:
    if req_validation_error is not None:
        # location, message and type only: never echo submitted values (passwords, emails)
        errors = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in req_validation_error.errors()]
        raise ValidationFailedError(errors=errors)


api = SpecTree(
    "flask",
    title="rootsquares platform API",
    version="0.1.0",
    path="apidoc",
    validation_error_status=422,
    before=_validation_hook,
)
log = structlog.get_logger("app.auth")

bp = Blueprint("platform", __name__, url_prefix=API_PREFIX)


def _settings() -> Settings:
    s: Settings = current_app.extensions["settings"]
    return s


def _out(model: BaseModel, status: int = 200) -> Response:
    resp = jsonify(model.model_dump(mode="json"))
    resp.status_code = status
    return resp


def _audit(
    action: str,
    entity: str = "",
    entity_id: str = "",
    org_id: uuid.UUID | None = None,
    actor: uuid.UUID | None = None,
    **data: Any,
) -> None:
    db = get_session()
    staff = getattr(g, "staff", None)
    db.add(
        AuditLog(
            action=action,
            entity=entity,
            entity_id=entity_id,
            org_id=org_id,
            actor_user_id=None if staff is not None else (actor or getattr(g, "user_id", None)),
            actor_staff_id=staff.id if staff is not None else None,  # a staff member is never written as a customer id (ADR 083)
            request_id=get_request_id(),
            data=data,
        )
    )


def _is_staff() -> bool:
    """True on the staff API for a signed-in staff member (ADR 083). On the customer API nobody is staff: no flag on a customer account exists."""
    return getattr(g, "staff", None) is not None


def _email_tag(email: str) -> str:
    return hashlib.sha256(email.lower().encode()).hexdigest()[:12]  # audit log keeps a tag, not the address


# ---- cookies and current user ---------------------------------------------------------------------------------------------------------
def _new_session(user_id: uuid.UUID) -> AuthSession:
    """A server-side record of one login (revocable). Old finished sessions of the same user are removed on the way."""
    db = get_session()
    now = dt.datetime.now(dt.UTC)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id, (AuthSession.expires_at < now) | (AuthSession.revoked_at.is_not(None))))
    sess = AuthSession(user_id=user_id, refresh_jti=secrets.token_hex(16), expires_at=now + dt.timedelta(days=_settings().REFRESH_TTL_DAYS))
    db.add(sess)
    db.flush()
    return sess


def _set_session(resp: Response, sess: AuthSession) -> None:
    s = _settings()
    user_id = sess.user_id
    access = make_token(s.jwt_secret, str(user_id), "access", dt.timedelta(minutes=s.ACCESS_TTL_MINUTES), sid=str(sess.id))
    refresh = make_token(s.jwt_secret, str(user_id), "refresh", dt.timedelta(days=s.REFRESH_TTL_DAYS), sid=str(sess.id), jti=sess.refresh_jti)
    common = {"httponly": True, "samesite": "Lax", "secure": s.COOKIE_SECURE}
    resp.set_cookie(ACCESS_COOKIE, access, max_age=s.ACCESS_TTL_MINUTES * 60, path="/", **common)  # type: ignore[arg-type]
    resp.set_cookie(REFRESH_COOKIE, refresh, max_age=s.REFRESH_TTL_DAYS * 86400, path=f"{API_PREFIX}/auth", **common)  # type: ignore[arg-type]


def _clear_session(resp: Response) -> None:
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie(REFRESH_COOKIE, path=f"{API_PREFIX}/auth")


def _user_from_cookie(cookie: str, kind: str) -> User | None:
    """The user behind a valid cookie whose session is still active. Tokens without a session id (issued before sessions existed) do not count."""
    token = request.cookies.get(cookie)
    claims = read_token(_settings().jwt_secret, token, kind) if token else None
    if not claims:
        return None
    db = get_session()
    try:
        sess = db.get(AuthSession, uuid.UUID(str(claims.get("sid"))))
        user = db.get(User, uuid.UUID(claims["sub"]))
    except ValueError:
        return None
    now = dt.datetime.now(dt.UTC)
    if (
        sess is None
        or user is None
        or sess.user_id != user.id
        or sess.revoked_at is not None
        or sess.expires_at.replace(tzinfo=sess.expires_at.tzinfo or dt.UTC) < now
    ):
        return None
    if kind == "refresh" and claims.get("jti") != sess.refresh_jti:
        sess.revoked_at = now  # an old refresh token came back: someone kept a copy, end the whole login
        _audit("auth.refresh_reuse", "user", str(user.id), None, actor=user.id)
        db.commit()
        return None
    g.user_id, g.auth_session = user.id, sess
    return user


def _bearer_token() -> str | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token.strip() or None if scheme.lower() == "bearer" else None


def _user_from_bearer() -> User | None:
    """A Supabase/Neon JWT (ADR 028). None when no provider is configured, no header was sent or the token is invalid."""
    token, provider = _bearer_token(), current_app.extensions["providers"].auth
    if not token or provider is None:
        return None
    user = resolve_user_from_token(get_session(), provider, token)
    if user is not None:
        g.user_id = user.id
    return user


def login_required(fn: Callable[..., Response]) -> Callable[..., Response]:
    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Response:
        if admin_auth.on_admin_api():  # the same handler mounted on the staff API (admin_api.py): staff cookie only, never the customer's
            if admin_auth.authenticate() is None:
                raise UnauthorizedError("Sign in to continue")
            return fn(*args, **kwargs)
        user = _user_from_bearer() or _user_from_cookie(ACCESS_COOKIE, "access")  # an explicit Authorization header wins over the cookie
        if user is None:
            log.info("sign_in_required", path=request.path, bearer=_bearer_token() is not None, cookie=request.cookies.get(ACCESS_COOKIE) is not None)
            raise UnauthorizedError("Sign in to continue")
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn: Callable[..., Response]) -> Callable[..., Response]:
    """A route for staff. It is served on the staff API only (admin_api.mount_shared_routes mounts it there); the customer API answers 404, signed in or not."""
    inner = login_required(fn)

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Response:
        if not admin_auth.on_admin_api():
            raise NotFoundError("Not found")
        return inner(*args, **kwargs)

    wrapper.admin_only = True  # type: ignore[attr-defined]  # admin_api.mount_shared_routes mounts every such route on the staff API
    return wrapper


def _user_out(db: Session, user: User) -> UserOut:
    rows = db.execute(select(Organization, Membership.role).join(Membership, Membership.org_id == Organization.id).where(Membership.user_id == user.id)).all()
    orgs = [OrganizationOut(id=o.id, name=o.name, role=str(role), billing_country=o.billing_country) for o, role in rows]
    return UserOut(id=user.id, email=user.email, name=user.name, organizations=orgs)


@bp.before_request
def _csrf() -> None:
    if request.endpoint and request.endpoint.endswith("billing_webhook"):
        return  # the payment provider calls this one, with no cookie; its signature is checked instead (W10-R42)
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise ForbiddenError(f"Send the header {CSRF_HEADER}: {CSRF_VALUE}", code="csrf_header_required")


# ---- auth ---------------------------------------------------------------------------------------------------------------------------
@bp.post("/auth/signup")
@api.validate(json=SignupIn, resp=SpecResponse(HTTP_201=UserOut), tags=["auth"])
def signup() -> Response:
    body: SignupIn = request.context.json  # type: ignore[attr-defined]
    db = get_session()
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise ConflictError("An account with this email already exists", code="email_taken")
    org = Organization(name=body.organization_name.strip())
    user = User(email=body.email, password_hash=hash_password(body.password), name=body.name.strip())
    db.add_all([org, user])
    db.flush()
    db.add(Membership(user_id=user.id, org_id=org.id, role=MembershipRole.OWNER))
    _audit("auth.signup", "user", str(user.id), org.id, actor=user.id)
    sess = _new_session(user.id)
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent signup with the same email
        db.rollback()
        raise ConflictError("An account with this email already exists", code="email_taken") from exc
    resp = _out(_user_out(db, user), 201)
    _set_session(resp, sess)
    return resp


@bp.post("/auth/login")
@api.validate(json=LoginIn, resp=SpecResponse(HTTP_200=UserOut), tags=["auth"])
def login() -> Response:
    body: LoginIn = request.context.json  # type: ignore[attr-defined]
    s = _settings()
    limiter = current_app.extensions["providers"].rate_limiter
    if not limiter.allow(f"login:{request.remote_addr}:{body.email}", s.LOGIN_RATE_LIMIT, s.LOGIN_RATE_WINDOW_SECONDS):
        raise RateLimitedError("Too many sign-in attempts. Wait a minute and try again.", retry_after=s.LOGIN_RATE_WINDOW_SECONDS)
    db = get_session()
    user = db.scalar(select(User).where(User.email == body.email))
    ok = verify_password(user.password_hash if user and user.password_hash else DUMMY_HASH, body.password)
    if not (user and user.password_hash and ok):  # provider-only accounts (no password) cannot use this route
        _audit("auth.login_failed", "user", "", None, actor=None, email_tag=_email_tag(body.email))
        db.commit()
        raise UnauthorizedError("Email or password is wrong", code="invalid_credentials")
    _audit("auth.login", "user", str(user.id), None, actor=user.id)
    sess = _new_session(user.id)
    db.commit()
    resp = _out(_user_out(db, user))
    _set_session(resp, sess)
    return resp


@bp.post("/auth/logout")
@api.validate(resp=SpecResponse(HTTP_200=Ack), tags=["auth"])
def logout() -> Response:
    user = _user_from_cookie(ACCESS_COOKIE, "access") or _user_from_cookie(REFRESH_COOKIE, "refresh")
    if user:
        g.auth_session.revoked_at = dt.datetime.now(dt.UTC)  # the login ends on the server, not only in this browser
        _audit("auth.logout", "user", str(user.id), None, actor=user.id)
        get_session().commit()
    resp = _out(Ack())
    _clear_session(resp)
    return resp


@bp.get("/auth/me")
@api.validate(resp=SpecResponse(HTTP_200=UserOut), tags=["auth"])
@login_required
def me() -> Response:
    return _out(_user_out(get_session(), g.user))


@bp.post("/auth/refresh")
@api.validate(resp=SpecResponse(HTTP_200=UserOut), tags=["auth"])
def refresh() -> Response:
    user = _user_from_cookie(REFRESH_COOKIE, "refresh")
    if user is None:
        raise UnauthorizedError("Session expired", code="session_expired")
    sess: AuthSession = g.auth_session
    sess.refresh_jti = secrets.token_hex(16)  # the refresh token is single use: this one is replaced
    sess.last_used_at = dt.datetime.now(dt.UTC)
    get_session().commit()
    resp = _out(_user_out(get_session(), user))
    _set_session(resp, sess)
    return resp


@bp.post("/auth/logout-all")
@api.validate(resp=SpecResponse(HTTP_200=Ack), tags=["auth"])
@login_required
def logout_all() -> Response:
    """End every cookie login of the signed-in user, on all devices (sessions of the identity provider are ended at the provider)."""
    db = get_session()
    db.execute(update(AuthSession).where(AuthSession.user_id == g.user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=dt.datetime.now(dt.UTC)))
    _audit("auth.logout_all", "user", str(g.user.id), None, actor=g.user.id)
    db.commit()
    resp = _out(Ack())
    _clear_session(resp)
    return resp


@bp.get("/me/export")
@api.validate(tags=["account"])
@login_required
def export_me() -> Response:
    """Everything the platform holds about the signed-in person, as one JSON file (GDPR access)."""
    db = get_session()
    data = export_user(db, g.user)
    _audit("account.export", "user", str(g.user.id), None, actor=g.user.id)
    db.commit()
    resp = jsonify(data)
    resp.headers["Content-Disposition"] = f'attachment; filename="rootsquares-my-data-{dt.date.today().isoformat()}.json"'
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.delete("/me")
@api.validate(json=AccountDeleteIn, resp=SpecResponse(HTTP_200=AccountDeleted), tags=["account"])
@login_required
def delete_me() -> Response:
    """Delete the signed-in person's account (GDPR erasure). Refused while their organisations still have squares."""
    body = AccountDeleteIn.model_validate(request.get_json(silent=True) or {})  # spectree does not parse the body of a DELETE
    user: User = g.user
    if body.confirm_email.lower() != user.email.lower():
        raise ValidationFailedError("The address does not match your account", code="confirm_mismatch")
    db = get_session()
    removed = delete_account(db, _settings(), user)
    db.commit()
    resp = _out(AccountDeleted(provider_account_removed=removed))
    _clear_session(resp)
    return resp


@bp.post("/auth/password-reset")
@api.validate(json=PasswordResetIn, resp=SpecResponse(HTTP_202=Ack), tags=["auth"])
def password_reset() -> Response:
    """Stub: always answers 202 and sends nothing (no email provider yet). The audit log keeps a tag of the address, not the address."""
    body: PasswordResetIn = request.context.json  # type: ignore[attr-defined]
    _audit("auth.password_reset_requested", "user", "", None, actor=None, email_tag=_email_tag(body.email), stub=True)
    get_session().commit()
    return _out(Ack(), 202)


# ---- organizations ------------------------------------------------------------------------------------------------------------------
@bp.post("/organizations")
@api.validate(json=OrganizationIn, resp=SpecResponse(HTTP_200=UserOut, HTTP_201=UserOut), tags=["organizations"])
@login_required
def create_organization() -> Response:
    """Onboarding for a user who signed in through an auth provider (no organization yet): create one and make the caller its owner.
    Asking again with the same name returns the user unchanged (a double click must not create a second organization)."""
    body: OrganizationIn = request.context.json  # type: ignore[attr-defined]
    db = get_session()
    name = body.name.strip()
    user: User = g.user
    owned = db.scalars(select(Organization).join(Membership, Membership.org_id == Organization.id).where(Membership.user_id == user.id)).all()
    if any(o.name.casefold() == name.casefold() for o in owned):
        return _out(_user_out(db, user))
    org = Organization(name=name)
    db.add(org)
    db.flush()
    db.add(Membership(user_id=user.id, org_id=org.id, role=MembershipRole.OWNER))
    _audit("org.created", "organization", str(org.id), org.id, actor=user.id)
    db.commit()
    return _out(_user_out(db, user), 201)


# ---- squares ------------------------------------------------------------------------------------------------------------------------
def _square_modules(sq: Square) -> list[str]:
    stored = None if sq.modules is None else cast(list[str], json.loads(sq.modules))
    return square_modules.effective(stored)


def _auth_callback_url(sq: Square) -> str | None:
    """The Google redirect URI of the square's own sign-in project: Supabase's, or the square's Neon Auth address plus /callback/google."""
    if sq.provider_project_ref:
        return f"https://{sq.provider_project_ref}.supabase.co/auth/v1/callback"
    target = neon_target(sq, Encryptor(_settings().fernet_key))
    return square_auth.neon_callback_url(target[2]) if target and target[2] else None


def _square_out(sq: Square) -> SquareOut:
    return SquareOut(
        id=sq.id,
        org_id=sq.org_id,
        org_name=sq.organization.name if sq.organization is not None else "",
        name=sq.name,
        slug=sq.slug,
        theme_id=sq.theme_id,
        theme_overrides=theme_overrides.from_json(sq.theme_overrides),
        look_seasons=theme_overrides.seasons_out(sq.theme_overrides),
        look_draft=theme_overrides.draft_out(sq.theme_overrides, dt.datetime.now(dt.UTC)),
        currency=sq.currency,
        phone_country=sq.phone_country,
        billing_country=sq.organization.billing_country if sq.organization is not None else None,
        tax_percent=billing_service.tax_percent(_settings(), sq.organization.billing_country if sq.organization is not None else None),
        modules=_square_modules(sq),
        launch_package=sq.launch_package or square_plans.LEGACY_PACKAGE,
        voucher_code=sq.voucher_code,
        group_type=sq.group_type,
        running_plan=sq.running_plan or square_plans.DEFAULT_RUNNING,
        allowed_modules=square_plans.allowed_modules(sq.launch_package, sq.custom_modules),
        core_modules=square_plans.custom_core_of(sq.custom_modules) if sq.launch_package == square_plans.CUSTOM else list(square_modules.CORE_KEYS),
        custom_amount_minor=sq.custom_amount_minor if sq.launch_package == square_plans.CUSTOM else None,
        custom_interval=sq.custom_interval if sq.launch_package == square_plans.CUSTOM else None,
        paid_until=sq.paid_until,
        sleep_state=sq.sleep_state or "awake",
        mail_contact_email=sq.mail_contact_email,
        archived_at=sq.archived_at,
        event_pass=(lambda s: EventPassOut(**s) if s else None)(event_pass_service.summary(sq, _settings())),
        subscription=("ending" if sq.renewal_cancelled else "renewing") if sq.stripe_subscription_id else None,
        first_payment_due=billing_service.first_payment_due(get_session(), sq),
        payment_failed=sq.payment_failed_at is not None,
        pending_plan=sq.pending_running_plan,
        grace_ends=(sq.paid_until + dt.timedelta(days=_settings().BILLING_GRACE_DAYS)) if sq.payment_failed_at is not None and sq.paid_until else None,
        payment_required=billing_service.payment_before_build(_settings()),
        can_manage_billing=current_app.extensions["billing"].name == "stripe"
        and bool(getattr(get_session().get(Organization, sq.org_id), "stripe_customer_id", None)),
        awaiting_payment=event_pass_service.awaiting_payment(sq),
        billing_interval=sq.billing_interval or "month",
        logo_url=sq.logo_url,
        logo_dark_url=sq.logo_dark_url,
        status=str(sq.status),
        domain=sq.domain,
        url=f"https://{sq.domain}",
        has_database=bool(sq.db_connection),
        error=sq.error,
        created_at=sq.created_at,
        google_login=sq.google_login or "requested",
        auth_callback_url=_auth_callback_url(sq),
    )


def _member_org_ids(db: Session, user: User) -> list[uuid.UUID]:
    return list(db.scalars(select(Membership.org_id).where(Membership.user_id == user.id)))


@bp.get("/squares")
@api.validate(resp=SpecResponse(HTTP_200=SquareList), tags=["squares"])
@login_required
def list_squares() -> Response:
    db = get_session()
    rows = db.scalars(select(Square).where(Square.org_id.in_(_member_org_ids(db, g.user))).order_by(Square.created_at.desc())).all()
    return _out(SquareList(items=[_square_out(x) for x in rows]))


@bp.get("/attention")
@api.validate(resp=SpecResponse(HTTP_200=PortalAttentionList), tags=["squares"])
@login_required
def my_attention() -> Response:
    """What waits for the person as owner of squares (W25-R35): the portal's "Needs your attention" strip and the count in its side bar."""
    items = attention_list.for_owner(get_session(), g.user.id)
    return _out(PortalAttentionList(items=items, count=len(items)))


@bp.post("/squares")
@api.validate(json=SquareIn, resp=SpecResponse(HTTP_202=SquareOut), tags=["squares"])
@login_required
def create_square() -> Response:
    body: SquareIn = request.context.json  # type: ignore[attr-defined]
    s = _settings()
    db = get_session()
    if body.theme_id not in s.enabled_theme_ids:
        raise ValidationFailedError("Theme is not available", errors=[{"loc": ["theme_id"], "msg": "theme is not enabled", "type": "value_error"}])
    org_ids = _member_org_ids(db, g.user)
    if not org_ids:
        raise ForbiddenError("No organization", code="no_organization")
    if is_reserved(body.slug):
        raise ConflictError("This address is not available", code="slug_reserved")  # names the platform uses itself (ADR 092)
    if db.scalar(select(Square.id).where(Square.slug == body.slug)) is not None:
        raise ConflictError("This address is taken", code="slug_taken")
    org = db.get(Organization, org_ids[0])
    if org is not None and body.billing_country:
        org.billing_country = body.billing_country
    if billing_service.payment_before_build(s) and (org is None or not org.billing_country):
        raise ValidationFailedError(
            "Your country is needed",
            errors=[{"loc": ["billing_country"], "msg": "your country is required for billing and tax", "type": "value_error"}],
        )
    voucher_code = None
    if body.voucher_code and body.voucher_code.strip() and body.launch_package != square_plans.EVENT:
        # a code given at creation lowers the first payment when the trial ends: it is checked now, so a wrong one is told at once (W14-R30)
        launch, month = billing_service.price_of(db, f"launch.{body.launch_package}"), billing_service.price_of(db, f"running.{square_plans.LIVE}.month")
        voucher_code = voucher_service.evaluate_codes(
            db, body.voucher_code, kind="first", package=body.launch_package, org_id=org_ids[0], list_minor=launch + month, launch_minor=launch
        ).codes
    chosen_modules = body.modules if body.modules is not None else square_plans.starting_modules(body.launch_package, body.group_type)
    outside = square_plans.outside_package(body.launch_package, chosen_modules)
    if outside:
        raise ValidationFailedError(
            "These modules are not in the launch package",
            errors=[{"loc": ["modules"], "msg": f"not in the {body.launch_package} package: {', '.join(outside)}", "type": "value_error"}],
        )
    # the free trial of Live (W10-R45): a new square has its first days paid; an event pass has none
    trial_until = None if body.launch_package == square_plans.EVENT else dt.datetime.now(dt.UTC) + dt.timedelta(days=s.BILLING_TRIAL_DAYS)
    sq = Square(
        org_id=org_ids[0],
        name=body.name.strip(),
        slug=body.slug,
        theme_id=body.theme_id,
        currency=body.currency,
        phone_country=body.phone_country,
        modules=json.dumps(chosen_modules),
        launch_package=body.launch_package,
        voucher_code=voucher_code,
        group_type=None if body.launch_package == square_plans.EVENT else body.group_type,
        running_plan=square_plans.EVENT_RUN if body.launch_package == square_plans.EVENT else square_plans.DEFAULT_RUNNING,
        paid_until=trial_until,
        status=SquareStatus.PROVISIONING,
        domain=f"{body.slug}.{s.SQUARE_DOMAIN_SUFFIX}",
    )
    pay_first = body.launch_package == square_plans.EVENT and billing_service.event_pass_payment_required(s)
    if body.launch_package == square_plans.EVENT and not pay_first:
        event_pass_service.start(sq, s)  # the clock of an Event pass: from payment; with the fake provider and no enforcing, from now (ADR 044)
    db.add(sq)
    db.flush()
    _audit("square.create", "square", str(sq.id), sq.org_id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("This address is taken", code="slug_taken") from exc
    if pay_first:
        return _out(_square_out(sq), 202)  # W12-R6: built and started when the $25 is paid (`_after_paid`); the page sends the owner to checkout
    owner = Owner(email=g.user.email, name=g.user.name, password_hash=g.user.password_hash)
    current_app.extensions["executor"].submit(provision_square, current_app.extensions["db_factory"](), s, sq.id, owner)
    return _out(_square_out(sq), 202)


@bp.get("/modules")
@api.validate(resp=SpecResponse(HTTP_200=ModuleList), tags=["squares"])
@login_required
def list_modules() -> Response:
    """The optional modules a square can have, with their tier (recommended or good to have) and what each needs (W8-R9)."""
    return _out(
        ModuleList(
            items=[
                ModuleOut(key=m.key, label=m.label, description=m.description, tier=m.tier, needs=list(m.needs), parent=m.parent, starts_off=m.starts_off)
                for m in square_modules.MODULES
            ],
            core=[CorePartOut(key=c.key, label=c.label, description=c.description, needs=list(c.needs)) for c in square_modules.CORE_PARTS],
            module_core_needs={k: list(v) for k, v in square_modules.MODULE_CORE_NEEDS.items()},
        )
    )


@bp.get("/starter-sets")
@api.validate(resp=SpecResponse(HTTP_200=StarterSetList), tags=["squares"])
@login_required
def list_starter_sets() -> Response:
    """The kinds of group a new square can be, each with the modules that start on (W14-R10)."""
    return _out(
        StarterSetList(
            items=[
                StarterSetOut(key=s.key, label=s.label, description=s.description, modules=starter_sets.starter_modules(s.key))
                for s in starter_sets.STARTER_SETS
            ]
        )
    )


@bp.get("/squares/<uuid:square_id>/modules/status")
@api.validate(resp=SpecResponse(HTTP_200=ModuleStatusList), tags=["squares"])
@login_required
def square_modules_status(square_id: uuid.UUID) -> Response:
    """Does each module hold data (yes or no) and what is pending (W8-R27, ADR 038); `available` false = the square server could not be asked."""
    sq = _own_square(square_id)
    if sq.org_id not in _member_org_ids(get_session(), g.user):
        raise NotFoundError("Square not found")  # the square's own organisation only, not platform staff (ADR 038)
    items = fetch_module_status(_settings(), sq)
    if items is None:
        return _out(ModuleStatusList(available=False, items=[]))
    return _out(
        ModuleStatusList(
            available=True,
            items=[
                ModuleStatusOut(
                    key=str(i.get("key", "")),
                    holds_data=bool(i.get("holds_data", False)),
                    pending=[str(m) for m in i.get("pending", [])],
                )
                for i in items
            ],
        )
    )


@bp.get("/squares/<uuid:square_id>/health")
@api.validate(resp=SpecResponse(HTTP_200=SquareHealthOut), tags=["squares"])
@login_required
def square_health(square_id: uuid.UUID) -> Response:
    """The owner's view of the square's health (W10-R19, ADR 038): states and plain sentences from the square server, plus the logo."""
    sq = _own_square(square_id)
    if sq.org_id not in _member_org_ids(get_session(), g.user):
        raise NotFoundError("Square not found")  # the square's own organisation only, not platform staff (ADR 038)
    logo = bool(sq.logo_url)
    site = [SquareHealthCheckOut(key="site_logo", group="setup", state="ok" if logo else "warn", text="A logo is set." if logo else "No logo is set yet.")]
    report = fetch_square_health(_settings(), sq)
    if report is None:
        down = SquareHealthCheckOut(key="reachable", group="system", state="fail", text="The site's server did not answer.")
        return _out(SquareHealthOut(reachable=False, checks=[down, *site]))
    ok = SquareHealthCheckOut(key="reachable", group="system", state="ok", text="The site's server answers.")
    theirs = [
        SquareHealthCheckOut(key=str(c.get("key", "")), group=str(c.get("group", "system")), state=str(c.get("state", "ok")), text=str(c.get("text", "")))
        for c in report["checks"]
        if isinstance(c, dict)
    ]
    return _out(SquareHealthOut(reachable=True, version=str(report.get("version", "")), checks=[ok, *theirs, *site]))


@bp.put("/squares/<uuid:square_id>/modules")
@api.validate(json=ModulesIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def set_square_modules(square_id: uuid.UUID) -> Response:
    """The owner turns modules on or off (W8-R9). The list is completed with what the chosen modules need; nothing is deleted when one is turned off."""
    body: ModulesIn = request.context.json  # type: ignore[attr-defined]
    sq = _own_square(square_id)
    outside = [] if _is_staff() else square_plans.outside_package(sq.launch_package, body.modules, sq.custom_modules)
    if outside:
        raise ForbiddenError(f"Not in your launch package: {', '.join(outside)}", code="module_not_in_package")
    before = _square_modules(sq)
    sq.modules = json.dumps(body.modules)
    _audit("square.modules", "square", str(sq.id), sq.org_id, on=body.modules, was=before)
    get_session().commit()
    return _out(_square_out(sq))


@bp.put("/squares/<uuid:square_id>/plan")
@api.validate(json=PlanIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def set_square_plan(square_id: uuid.UUID) -> Response:
    """Platform admin only (support, testing) until billing exists: change a square's launch package and running plan (W10-R40). Modules on stay on."""
    if not _is_staff():
        raise ForbiddenError("Platform admin only")
    body: PlanIn = request.context.json  # type: ignore[attr-defined]
    sq = _own_square(square_id)
    was = {"launch_package": sq.launch_package, "running_plan": sq.running_plan}
    if body.launch_package is not None:
        sq.launch_package = body.launch_package
    if body.running_plan is not None:
        sq.running_plan = body.running_plan
    _audit("square.plan", "square", str(sq.id), sq.org_id, launch_package=sq.launch_package, running_plan=sq.running_plan, was=was)
    get_session().commit()
    return _out(_square_out(sq))


@bp.put("/squares/<uuid:square_id>/running-plan")
@api.validate(json=RunningPlanIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def set_square_running_plan(square_id: uuid.UUID) -> Response:
    """The owner puts the square to sleep (Keep) or wakes it (Live), W10-R41, W10-R44. Keep is a true sleep: the public contact details are copied here,
    the site shows the back-soon page at once, nobody can sign in to the square, and its project at the provider is paused in the background (only with
    PROVIDER_SLEEP). Wake starts the project again (a minute or two) and the square is awake when it answers. Nothing is deleted. An Event pass stays."""
    body: RunningPlanIn = request.context.json  # type: ignore[attr-defined]
    sq = _own_square(square_id)
    if sq.running_plan == square_plans.EVENT_RUN:
        raise ConflictError("An event pass cannot be switched this way", code="event_pass")
    if sq.launch_package == square_plans.CUSTOM and body.running_plan != square_plans.LIVE:
        raise ConflictError("A custom package stays Live; ask us to change it", code="custom_package")  # W19-R20
    if sq.stripe_subscription_id and (body.running_plan == square_plans.KEEP or sq.running_plan == square_plans.KEEP):
        raise ConflictError("Use the plan change: it moves the renewing payment with it", code="plan_change_required")  # W18-R34
    _switch_running_plan(sq, body.running_plan, check_payment=True)
    return _out(_square_out(sq))


def _switch_running_plan(sq: Square, plan: str, check_payment: bool) -> None:
    """Move a square to Keep (true sleep) or Live (wake). Used by the owner's switch and, with the payment already made, by a paid Keep or Live period
    (W10-R44: paying for Keep puts the square to sleep, paying for Live wakes it). Idempotent."""
    s = _settings()
    db = get_session()
    before = sq.running_plan
    if plan == square_plans.KEEP:
        if sq.running_plan == square_plans.KEEP and sq.sleep_state == sleep_service.SLEEPING:
            return  # already asleep
        contact = sleep_service.fetch_contact(s, sq) if sq.sleep_state == sleep_service.AWAKE else None
        sq.running_plan = square_plans.KEEP
        sq.sleep_state = sleep_service.SLEEPING
        sleep_service.mark_asleep(sq)
        if contact is not None or not sq.sleep_contact:
            sq.sleep_contact = json.dumps(contact or {})
        _audit("square.running_plan", "square", str(sq.id), sq.org_id, running_plan=plan, was=before)
        db.commit()
        current_app.extensions["executor"].submit(sleep_service.run_pause, current_app.extensions["db_factory"](), s, sq.id)
        return
    if sq.running_plan == square_plans.LIVE and sq.sleep_state == sleep_service.AWAKE:
        return  # already live
    if sq.archived_at is not None:
        raise ConflictError("This square was archived: its project was deleted after 12 months asleep with nothing paid", code="archived")
    if check_payment and sq.running_plan == square_plans.KEEP and billing_service.wake_needs_payment(s, sq):
        raise billing_service.PaymentRequired("Choose a running period to wake the site")
    sq.running_plan = square_plans.LIVE
    if s.PROVIDER_SLEEP and (sq.provider_project_ref or sq.neon_project_id):
        sq.sleep_state = sleep_service.WAKING
        _audit("square.running_plan", "square", str(sq.id), sq.org_id, running_plan=plan, was=before)
        db.commit()
        current_app.extensions["executor"].submit(sleep_service.run_wake, current_app.extensions["db_factory"](), s, sq.id)
    else:
        sq.sleep_state = sleep_service.AWAKE
        sq.sleep_contact = None
        sleep_service.mark_awake(sq)
        _audit("square.running_plan", "square", str(sq.id), sq.org_id, running_plan=plan, was=before)
        db.commit()


def _after_paid(order: Any) -> None:
    """A paid running period carries its plan with it: Keep puts the square to sleep, Live wakes it (W10-R44)."""
    if order is not None and order.status == "paid" and order.kind == "event_pass" and getattr(order, "newly_paid", False):
        db = get_session()
        sq, user = db.get(Square, order.square_id), db.get(User, order.created_by) if order.created_by else None
        if sq is not None and user is not None and str(sq.status) == "provisioning":
            owner = Owner(email=user.email, name=user.name, password_hash=user.password_hash)
            current_app.extensions["executor"].submit(provision_square, current_app.extensions["db_factory"](), _settings(), sq.id, owner)
    if order is not None and order.status == "paid" and order.kind in ("running", "first") and order.running_plan:
        sq = get_session().get(Square, order.square_id)
        if sq is not None and sq.running_plan != square_plans.EVENT_RUN and sq.archived_at is None:
            _switch_running_plan(sq, order.running_plan, check_payment=False)


def _order_out(order: Any) -> OrderOut:
    return OrderOut.model_validate(order)


@bp.put("/squares/<uuid:square_id>/billing-interval")
@api.validate(json=BillingIntervalIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["billing"])
@login_required
def set_billing_interval(square_id: uuid.UUID) -> Response:
    """The owner's default billing period, monthly or yearly (W10-R46): what the plan cards and checkout offer first. Nothing is charged by this."""
    body: BillingIntervalIn = request.context.json  # type: ignore[attr-defined]
    sq = _billing_square(square_id)
    sq.billing_interval = body.interval
    _audit("billing.interval", "square", str(sq.id), sq.org_id, interval=body.interval)
    get_session().commit()
    return _out(_square_out(sq))


@bp.get("/prices")
@api.validate(resp=SpecResponse(HTTP_200=PriceList), tags=["billing"])
def list_prices() -> Response:
    """The prices, as data (W10-R42). Public: the Pricing page shows them. Whole numbers of cents, US dollars."""
    db = get_session()
    rows = billing_service.list_prices(db)
    items = [PriceOut(key=p.key, amount_minor=p.amount_minor, currency=p.currency, interval=p.interval) for p in rows]
    return _out(PriceList(items=items, tax_rates=billing_service.tax_rates(_settings())))


@bp.put("/prices/<string:key>")
@api.validate(json=PriceIn, resp=SpecResponse(HTTP_200=PriceOut), tags=["billing"])
@admin_required
def set_price(key: str) -> Response:
    """A platform admin changes a price (W10-R42). It applies to new orders; orders already made keep their amount."""
    body: PriceIn = request.context.json  # type: ignore[attr-defined]
    db = get_session()
    if key not in billing_service.PRICE_KEYS:
        raise NotFoundError("Unknown price")
    existing = db.get(PlanPrice, key)
    was = existing.amount_minor if existing is not None else None
    row = billing_service.set_price(db, key, body.amount_minor)
    _audit("billing.price", "price", key, None, amount_minor=body.amount_minor, was=was)
    db.commit()
    return _out(PriceOut(key=row.key, amount_minor=row.amount_minor, currency=row.currency, interval=row.interval))


def _billing_square(square_id: uuid.UUID) -> Square:
    sq = _own_square(square_id)
    if sq.org_id not in _member_org_ids(get_session(), g.user):
        raise NotFoundError("Square not found")  # the owner's organisation only, not platform staff (they use the plan route)
    return sq


@bp.post("/squares/<uuid:square_id>/event-pass/confirm-export")
@api.validate(resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def confirm_event_pass_export(square_id: uuid.UUID) -> Response:
    """The owner of an Event pass says the reports are saved (a plain yes; nothing about their content is learned, ADR 038, ADR 044)."""
    sq = _billing_square(square_id)
    if not event_pass_service.is_event_pass(sq):
        raise ConflictError("This square is not an Event pass", code="not_event_pass")
    event_pass_service.confirm_export(sq)
    _audit("event_pass.export_confirmed", "square", str(sq.id), sq.org_id)
    get_session().commit()
    return _out(_square_out(sq))


@bp.post("/squares/<uuid:square_id>/billing/checkout")
@api.validate(json=CheckoutIn, resp=SpecResponse(HTTP_201=CheckoutOut), tags=["billing"])
@login_required
def start_checkout(square_id: uuid.UUID) -> Response:
    """The owner starts a payment: an upgrade of the launch package (the difference) or a running period (Live or Keep, monthly or yearly), W10-R42.
    The plan changes only when the provider confirms (the fake checkout page now, a Stripe webhook later)."""
    body: CheckoutIn = request.context.json  # type: ignore[attr-defined]
    sq = _billing_square(square_id)
    db = get_session()
    provider = current_app.extensions["billing"]
    order = _make_order(db, sq, body, provider)
    base = _settings().PLATFORM_FRONTEND_URL.rstrip("/")
    launch_minor = billing_service.price_of(db, f"launch.{order.launch_package}") if order.kind == "first" else 0
    typed = (body.voucher_code or "").strip()
    kept = (
        sq.voucher_code if not typed and order.kind == "first" else None
    )  # the code given at creation (W14-R30): used when nothing is typed, dropped quietly if it no longer fits
    applied = None
    if typed:
        applied = voucher_service.apply_codes_to_order(db, order, typed, sq.org_id, launch_minor)
    elif kept:
        try:
            applied = voucher_service.apply_codes_to_order(db, order, kept, sq.org_id, launch_minor)
        except voucher_service.VoucherRejected:
            applied = None
    if applied is not None:
        launch_minor = max(0, launch_minor - applied.discount_minor)  # a first payment: only the package part is lowered, the Live period stays whole
        _audit(
            "billing.voucher_applied",
            "order",
            str(order.id),
            sq.org_id,
            code=applied.codes,
            list_minor=applied.list_minor,
            discount_minor=applied.discount_minor,
        )
        if order.amount_minor == 0:  # a free payment needs no card: settle it at once (W14-R27)
            order.provider_ref = "voucher_free"
            done = billing_service.apply_event(db, billing_service.PaymentEvent(order_id=order.id, paid=True), settings=_settings())
            _audit("billing.checkout", "order", str(order.id), sq.org_id, kind=order.kind, amount_minor=0)
            db.commit()
            _after_paid(done)
            return _out(CheckoutOut(order_id=order.id, url=f"{base}/squares/{sq.id}/billing?paid=1"), 201)
    org = db.get(Organization, sq.org_id)
    customer = None
    if org is not None:
        org.stripe_customer_id = provider.ensure_customer(org.stripe_customer_id, org.name, g.user.email, org.billing_country)
        customer = org.stripe_customer_id
    percent = billing_service.tax_percent(_settings(), org.billing_country if org is not None else None)
    checkout = provider.create_checkout(
        order, f"{base}/squares/{sq.id}/billing?paid=1", f"{base}/squares/{sq.id}/billing?cancelled=1", launch_minor, customer, percent
    )
    order.provider_ref = checkout.ref
    _audit("billing.checkout", "order", str(order.id), sq.org_id, kind=order.kind, amount_minor=order.amount_minor)
    db.commit()
    return _out(CheckoutOut(order_id=order.id, url=checkout.url), 201)


def _make_order(db: Session, sq: Square, body: CheckoutIn, provider: Any) -> BillingOrder:
    """The order a checkout would start, with the rules that go with it (also used to price a voucher before the customer pays)."""
    if sq.archived_at is not None:
        raise ConflictError("This square was archived: its project was deleted after 12 months asleep with nothing paid", code="archived")
    if body.kind in ("upgrade", "running"):
        _first_payment_comes_first(db, sq)
    if body.kind == "upgrade":
        if body.launch_package not in square_plans.PACKAGES:
            raise ValidationFailedError("Unknown launch package", errors=[{"loc": ["launch_package"], "msg": "unknown launch package", "type": "value_error"}])
        return billing_service.new_upgrade_order(db, sq, body.launch_package, g.user.id, provider.name)
    if body.kind == "first":
        _no_second_subscription(sq, provider)
        return billing_service.new_first_order(db, sq, body.interval or "", g.user.id, provider.name, body.launch_package)
    if body.kind == "event_pass":
        return billing_service.new_event_pass_order(db, sq, g.user.id, provider.name)
    if body.kind == "event_upgrade":
        return billing_service.new_event_upgrade_order(db, sq, body.launch_package or "", body.interval or "", g.user.id, provider.name)
    _no_second_subscription(sq, provider)
    return billing_service.new_running_order(db, sq, body.running_plan or "", body.interval or "", g.user.id, provider.name)


def _first_payment_comes_first(db: Session, sq: Square) -> None:
    """With money on, a launch package that has not made its first payment cannot buy a package upgrade or a running period on its own: the first
    payment (package plus first Live period) comes first, so the package is never skipped (W12-R16)."""
    if billing_service.payment_before_build(_settings()) and billing_service.first_payment_due(db, sq):
        raise ConflictError("Pay your launch package and first Live period first", code="first_payment_due")


def _no_second_subscription(sq: Square, provider: Any) -> None:
    if provider.name == "stripe" and sq.stripe_subscription_id:
        raise ConflictError("This square already renews; cancel the renewal first to choose another period", code="already_subscribed")


@bp.post("/squares/<uuid:square_id>/billing/portal")
@api.validate(resp=SpecResponse(HTTP_200=PortalOut), tags=["billing"])
@login_required
def billing_portal(square_id: uuid.UUID) -> Response:
    """Where the owner changes the card and downloads receipts (W12-R17): the payment provider's own page; we hold no card data."""
    sq = _billing_square(square_id)
    org = get_session().get(Organization, sq.org_id)
    if org is None or not org.stripe_customer_id:
        raise ConflictError("There is no payment on record yet", code="no_customer")
    base = _settings().PLATFORM_FRONTEND_URL.rstrip("/")
    url = current_app.extensions["billing"].create_portal(org.stripe_customer_id, f"{base}/squares/{sq.id}/payments")
    if url is None:
        raise ConflictError("This payment setup has no card page", code="no_customer")
    return _out(PortalOut(url=url))


@bp.post("/squares/<uuid:square_id>/billing/cancel-renewal")
@api.validate(resp=SpecResponse(HTTP_200=SquareOut), tags=["billing"])
@login_required
def cancel_renewal(square_id: uuid.UUID) -> Response:
    """The owner stops the automatic renewal (W12-R13): the plan stays until the paid time ends; nothing is refunded here."""
    return _set_renewal(square_id, renew=False)


@bp.post("/squares/<uuid:square_id>/billing/resume-renewal")
@api.validate(resp=SpecResponse(HTTP_200=SquareOut), tags=["billing"])
@login_required
def resume_renewal(square_id: uuid.UUID) -> Response:
    return _set_renewal(square_id, renew=True)


def _set_renewal(square_id: uuid.UUID, renew: bool) -> Response:
    sq = _billing_square(square_id)
    if not sq.stripe_subscription_id:
        raise ConflictError("This square has no renewing payment", code="no_subscription")
    current_app.extensions["billing"].set_renewal(sq.stripe_subscription_id, renew)
    sq.renewal_cancelled = not renew
    _audit("billing.renewal_resumed" if renew else "billing.renewal_cancelled", "square", str(sq.id), sq.org_id)
    get_session().commit()
    return _out(_square_out(sq))


@bp.post("/squares/<uuid:square_id>/billing/plan-change")
@api.validate(json=PlanChangeIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["billing"])
@login_required
def change_running_plan(square_id: uuid.UUID) -> Response:
    """Live to Keep or Keep to Live (W18-R34, docs/plans/plan-changes-plan.md, ADR 079). A downgrade starts at the next renewal: the site stays live, the
    renewing payment is put to the Keep price now (nothing charged or credited) and the square is marked; the renewal after it is a Keep period and puts the
    site to sleep. An upgrade starts at once and is charged for the rest of the period; a downgrade still waiting is cancelled (the price goes back)."""
    body: PlanChangeIn = request.context.json  # type: ignore[attr-defined]
    sq = _billing_square(square_id)
    plan = body.plan
    if plan not in (square_plans.LIVE, square_plans.KEEP):
        raise BadRequestError("Choose Live or Keep", code="bad_plan")
    if sq.running_plan == square_plans.EVENT_RUN:
        raise ConflictError("An event pass has no plan to change", code="event_pass")
    if sq.launch_package == square_plans.CUSTOM:
        raise ConflictError("A custom package has one agreed amount; ask us to change it", code="custom_package")  # W19-R20
    if sq.archived_at is not None:
        raise ConflictError("This square was archived: its project was deleted after 12 months asleep with nothing paid", code="archived")
    db = get_session()
    provider = current_app.extensions["billing"]
    org = db.get(Organization, sq.org_id)
    percent = billing_service.tax_percent(_settings(), org.billing_country if org is not None else None)
    renewing = bool(sq.stripe_subscription_id) and not sq.renewal_cancelled  # a price can be changed only on a subscription that will renew
    if plan == square_plans.KEEP:
        if sq.running_plan == square_plans.KEEP or sq.pending_running_plan == square_plans.KEEP:
            raise ConflictError("This square is already on Keep or going there", code="same_plan")
        if sq.payment_failed_at is not None:
            raise ConflictError("Update your card first: the last renewal did not go through", code="payment_failed")
        if renewing:
            billing_service.change_plan_now(db, sq, provider, square_plans.KEEP, percent)
        sq.pending_running_plan = square_plans.KEEP
        _audit("billing.plan_downgrade_scheduled", "square", str(sq.id), sq.org_id, running_plan=square_plans.KEEP, renewing=renewing)
    elif sq.running_plan == square_plans.LIVE:
        if sq.pending_running_plan != square_plans.KEEP:
            raise ConflictError("This square is already on Live", code="same_plan")
        if renewing:
            billing_service.change_plan_now(db, sq, provider, square_plans.LIVE, percent)  # back to normal: the Live price again, nothing charged
        sq.pending_running_plan = None
        _audit("billing.plan_downgrade_cancelled", "square", str(sq.id), sq.org_id, renewing=renewing)
    else:
        if sq.stripe_subscription_id:
            if sq.renewal_cancelled:
                raise ConflictError("Resume the renewal first, then change the plan", code="resume_first")
            if sq.payment_failed_at is not None:
                raise ConflictError("Update your card first: the last renewal did not go through", code="payment_failed")
            result = billing_service.change_plan_now(db, sq, provider, square_plans.LIVE, percent, immediate=True)
            _audit("billing.plan_upgraded", "square", str(sq.id), sq.org_id, amount_minor=result.amount_minor)
            _switch_running_plan(sq, square_plans.LIVE, check_payment=False)
        else:
            _switch_running_plan(sq, square_plans.LIVE, check_payment=True)  # a paid period is left: wake; otherwise 402 and the owner pays a Live period
            _audit("billing.plan_upgraded", "square", str(sq.id), sq.org_id, amount_minor=0)
        sq.pending_running_plan = None
    db.commit()
    return _out(_square_out(sq))


@bp.get("/squares/<uuid:square_id>/billing/orders")
@api.validate(resp=SpecResponse(HTTP_200=OrderList), tags=["billing"])
@login_required
def list_orders(square_id: uuid.UUID) -> Response:
    sq = _billing_square(square_id)
    rows = get_session().scalars(select(BillingOrder).where(BillingOrder.square_id == sq.id).order_by(BillingOrder.created_at.desc()).limit(50))
    return _out(OrderList(items=[_order_out(o) for o in rows]))


@bp.post("/squares/<uuid:square_id>/billing/orders/<uuid:order_id>/confirm")
@api.validate(resp=SpecResponse(HTTP_200=OrderOut), tags=["billing"])
@login_required
def confirm_order(square_id: uuid.UUID, order_id: uuid.UUID) -> Response:
    """The Billing page asks us to look again at an order that is still pending after the owner came back from the checkout (W25-R27). We ask the payment
    provider; if it says the checkout was paid (or expired) the order is applied exactly as the webhook would apply it (the same idempotent function), so a
    webhook that never came (the forwarder was not running) cannot leave a paid order pending. Anything else changes nothing. The row is locked so that a
    webhook arriving at the same moment cannot apply it twice."""
    sq = _billing_square(square_id)
    db = get_session()
    order = db.get(BillingOrder, order_id, with_for_update=True)
    if order is None or order.square_id != sq.id:
        raise NotFoundError("Order not found")
    if order.status == "pending" and order.provider != "fake":
        event = current_app.extensions["billing"].check_checkout(order)
        if event is not None:
            done = billing_service.apply_event(db, event, settings=_settings())
            _audit("billing.confirm_on_return", "order", str(order.id), sq.org_id, paid=event.paid)
            db.commit()
            _after_paid(done)
            order = done or order
    return _out(_order_out(order))


@bp.get("/billing/orders/<uuid:order_id>")
@api.validate(resp=SpecResponse(HTTP_200=OrderOut), tags=["billing"])
@login_required
def get_order(order_id: uuid.UUID) -> Response:
    order = get_session().get(BillingOrder, order_id)
    if order is None:
        raise NotFoundError("Order not found")
    _billing_square(order.square_id)
    return _out(_order_out(order))


@bp.post("/billing/orders/<uuid:order_id>/fake-confirm")
@api.validate(json=FakeConfirmIn, resp=SpecResponse(HTTP_200=OrderOut), tags=["billing"])
@login_required
def fake_confirm(order_id: uuid.UUID) -> Response:
    """The test checkout page pays or cancels an order (W10-R42). Only with the fake provider, never in production; no money moves."""
    body: FakeConfirmIn = request.context.json  # type: ignore[attr-defined]
    if _settings().BILLING_PROVIDER != "fake":
        raise NotFoundError("Not found")
    db = get_session()
    order = db.get(BillingOrder, order_id)
    if order is None or order.provider != "fake":
        raise NotFoundError("Order not found")
    _billing_square(order.square_id)
    done = billing_service.apply_event(db, billing_service.PaymentEvent(order_id=order.id, paid=body.outcome == "paid"), settings=_settings())
    db.flush()
    _audit("billing.fake_confirm", "order", str(order.id), None, outcome=body.outcome)
    db.commit()
    _after_paid(done)
    return _out(_order_out(done or order))


@bp.post("/billing/webhook")
def billing_webhook() -> Response:
    """The payment provider tells us an order was paid or failed (W10-R42). Not for browsers: the provider's signature is checked by the adapter.
    Answers 200 for events we do not use, so the provider stops retrying them."""
    provider = current_app.extensions["billing"]
    event = provider.read_webhook(dict(request.headers), request.get_data())
    if event is not None and event.failed:
        db = get_session()
        failed_sq = billing_service.record_failure(db, event)
        if failed_sq is not None:
            _audit("billing.payment_failed", "square", str(failed_sq.id), failed_sq.org_id)
        db.commit()
        if failed_sq is not None:
            subject, text = notify_service.payment_failed_text(_settings(), failed_sq)
            mail = email_html.from_text(
                text, site_url=_settings().PLATFORM_FRONTEND_URL, eyebrow="Payment", heading="We could not take your payment", button_label="Update your card"
            )
            notify_service.send_to_owner(current_app, db, failed_sq, subject, text, **mail)
    elif event is not None:
        db = get_session()
        done = billing_service.apply_event(db, event, settings=_settings())
        db.commit()
        _after_paid(done)
        if done is not None and done.kind == "running" and done.running_plan == square_plans.KEEP and event.invoice_id:
            _tell_keep_started(db)  # a renewal that started a downgrade the owner chose (W18-R34)
    return jsonify({"received": True})


def _tell_keep_started(db: Any) -> None:
    """E-mail the owner that Keep has started, for every downgrade not told yet (best effort: not recorded when refused, so the daily job tries again)."""

    def notify(session: Any, sq: Square, _reason: str) -> bool:
        subject, text = trial_service.keep_started_text(session, _settings(), sq)
        site = _settings().PLATFORM_FRONTEND_URL
        mail = email_html.from_text(text, site_url=site, eyebrow="Your plan", heading="Your plan is now Keep", button_label="Go to Billing")
        return notify_service.send_to_owner(current_app, session, sq, subject, text, **mail)

    trial_service.send_keep_notices(db, dt.datetime.now(dt.UTC), notify)
    db.commit()


@bp.put("/squares/<uuid:square_id>/theme")
@api.validate(json=ThemeIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def set_square_theme(square_id: uuid.UUID) -> Response:
    """The owner changes the square's theme (W9-R5) and, from the Square package up, its own colours and font pair on top of it (W18-R18).
    Only the look changes: content, modules and data stay; the square site reads it on its next load. A theme that is missing stays; overrides missing stay.
    A retired theme (not in the offered list, W18-R25) can only be kept, not chosen."""
    body: ThemeIn = request.context.json  # type: ignore[attr-defined]
    sq = _own_square(square_id)
    if body.theme_id is not None and body.theme_id != sq.theme_id and body.theme_id not in _settings().enabled_theme_ids:
        raise ValidationFailedError("Theme is not available", errors=[{"loc": ["theme_id"], "msg": "theme is not enabled", "type": "value_error"}])
    clean: dict[str, Any] | None = None
    if "overrides" in body.model_fields_set:
        try:
            clean = theme_overrides.parse(body.overrides)
        except ValueError as exc:
            raise ValidationFailedError("Colours or fonts are not valid", errors=[{"loc": ["overrides"], "msg": str(exc), "type": "value_error"}]) from exc
    if clean is not None and not theme_overrides.allowed(sq.launch_package):
        raise ForbiddenError("Own colours and fonts are in the Square package and above", code="package_required")
    before = sq.theme_id
    if body.theme_id is not None:
        sq.theme_id = body.theme_id
    if "overrides" in body.model_fields_set:
        sq.theme_overrides = theme_overrides.with_live(sq.theme_overrides, clean)  # the shared draft, if any, stays
    _audit("square.theme", "square", str(sq.id), sq.org_id, theme=sq.theme_id, was=before, own_look=bool(sq.theme_overrides))
    get_session().commit()
    return _out(_square_out(sq))


@bp.put("/squares/<uuid:square_id>/mail-contact")
@api.validate(json=MailContactIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def set_square_mail_contact(square_id: uuid.UUID) -> Response:
    """The owner sets where the square's contact-form messages and payment notices go and where replies to its customer mails go (ADR 093, W25-R9).
    Empty clears it. Any package. The address itself is never written to the audit log or to logs."""
    body: MailContactIn = request.context.json  # type: ignore[attr-defined]
    sq = _own_square(square_id)
    sq.mail_contact_email = str(body.email).strip().lower() if body.email else None
    _audit("square.mail_contact", "square", str(sq.id), sq.org_id, set=sq.mail_contact_email is not None)
    get_session().commit()
    return _out(_square_out(sq))


def _draft_square(square_id: uuid.UUID) -> Square:
    sq = _own_square(square_id)
    if not theme_overrides.allowed(sq.launch_package):
        raise ForbiddenError("Own colours and fonts are in the Square package and above", code="package_required")
    return sq


@bp.put("/squares/<uuid:square_id>/theme/draft")
@api.validate(json=ThemeDraftIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def set_square_draft(square_id: uuid.UUID) -> Response:
    """Save the owner's draft look (W18-R47) and answer with the link's token:
    the committee opens the square with `?look=<token>` and sees the draft; the public sees the live look.
    The same link stays until `renew_link`; each save starts the 14 days again; an optional passcode is asked for on top of the link."""
    body: ThemeDraftIn = request.context.json  # type: ignore[attr-defined]
    sq = _draft_square(square_id)
    if body.theme_id is not None and body.theme_id != sq.theme_id and body.theme_id not in _settings().enabled_theme_ids:
        raise ValidationFailedError("Theme is not available", errors=[{"loc": ["theme_id"], "msg": "theme is not enabled", "type": "value_error"}])
    try:
        sq.theme_overrides = theme_overrides.make_draft(sq.theme_overrides, body.look, body.passcode, body.renew_link, dt.datetime.now(dt.UTC), body.theme_id)
    except ValueError as exc:
        raise ValidationFailedError("The draft is not valid", errors=[{"loc": ["look"], "msg": str(exc), "type": "value_error"}]) from exc
    _audit("square.theme_draft", "square", str(sq.id), sq.org_id, what="saved", passcode=body.passcode is not None, renewed=body.renew_link)
    get_session().commit()
    return _out(_square_out(sq))


@bp.put("/squares/<uuid:square_id>/theme/seasons")
@api.validate(json=ThemeSeasonsIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def set_square_seasons(square_id: uuid.UUID) -> Response:
    """Save the list of seasonal looks (W18-R49): between its two dates a season's look (and theme) replaces the live one on the public site.
    The whole list is sent each time; an empty list removes all seasons. Square package and above."""
    body: ThemeSeasonsIn = request.context.json  # type: ignore[attr-defined]
    sq = _draft_square(square_id)
    try:
        clean = theme_overrides.parse_seasons(body.seasons)
    except ValueError as exc:
        raise ValidationFailedError("A seasonal look is not valid", errors=[{"loc": ["seasons"], "msg": str(exc), "type": "value_error"}]) from exc
    for season in clean:
        theme = season.get("theme_id")
        if theme and theme != sq.theme_id and theme not in _settings().enabled_theme_ids:
            raise ValidationFailedError("Theme is not available", errors=[{"loc": ["seasons"], "msg": "theme is not enabled", "type": "value_error"}])
    sq.theme_overrides = theme_overrides.with_seasons(sq.theme_overrides, clean)
    _audit("square.theme_seasons", "square", str(sq.id), sq.org_id, seasons=len(clean))
    get_session().commit()
    return _out(_square_out(sq))


@bp.delete("/squares/<uuid:square_id>/theme/draft")
@api.validate(resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def delete_square_draft(square_id: uuid.UUID) -> Response:
    """Take the draft down: the link stops working at once. The live look is not touched."""
    sq = _own_square(square_id)
    sq.theme_overrides = theme_overrides.drop_draft(sq.theme_overrides)
    _audit("square.theme_draft", "square", str(sq.id), sq.org_id, what="removed")
    get_session().commit()
    return _out(_square_out(sq))


@bp.post("/squares/<uuid:square_id>/theme/draft/publish")
@api.validate(resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def publish_square_draft(square_id: uuid.UUID) -> Response:
    """The draft look goes live (it replaces the live own look) and the link is gone."""
    sq = _draft_square(square_id)
    shared = theme_overrides.draft_out(sq.theme_overrides, dt.datetime.now(dt.UTC))
    if shared is None:
        raise NotFoundError("There is no draft to publish")
    theme = shared["theme_id"]
    if theme and theme != sq.theme_id and theme in _settings().enabled_theme_ids:
        sq.theme_id = theme  # the draft's theme goes live with its look
    sq.theme_overrides = theme_overrides.publish_draft(sq.theme_overrides)
    _audit("square.theme_draft", "square", str(sq.id), sq.org_id, what="published")
    get_session().commit()
    return _out(_square_out(sq))


LOGO_TYPES = {"image/png": ("png", b"\x89PNG\r\n\x1a\n"), "image/jpeg": ("jpg", b"\xff\xd8\xff"), "image/webp": ("webp", b"RIFF")}
LOGO_MAX_BYTES = 1_000_000


def _own_square(square_id: uuid.UUID) -> Square:
    sq = get_session().get(Square, square_id)
    if sq is None or not (_is_staff() or sq.org_id in _member_org_ids(get_session(), g.user)):
        raise NotFoundError("Square not found")
    return sq


LOGO_VARIANTS = {"light": "logo_url", "dark": "logo_dark_url"}  # light: for light backgrounds (header); dark: for dark ones (footer, dark mode)


def _logo_variant() -> str:
    variant = (request.args.get("variant") or "light").lower()
    if variant not in LOGO_VARIANTS:
        raise ValidationFailedError("variant must be light or dark", code="logo_variant")
    return variant


@bp.post("/squares/<uuid:square_id>/logo")
@api.validate(resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def upload_square_logo(square_id: uuid.UUID) -> Response:
    """The square's logo (W6-R53, light and dark variant W6-R65): the image itself as the request body (PNG, JPEG or WebP, at most 1 MB), with
    `?variant=dark` for the logo on dark backgrounds. SVG is refused because it can carry script. It goes to the platform's public bucket; the
    square site reads its address from the platform database. Replaces the earlier logo of that variant."""
    sq = _own_square(square_id)
    variant = _logo_variant()
    column = LOGO_VARIANTS[variant]
    kind = (request.mimetype or "").lower()
    if kind not in LOGO_TYPES:
        raise ValidationFailedError("The logo must be a PNG, JPEG or WebP image", code="logo_type")
    if (request.content_length or 0) > LOGO_MAX_BYTES:
        raise ValidationFailedError("The logo must be at most 1 MB", code="logo_too_large")
    data = request.get_data()
    extension, magic = LOGO_TYPES[kind]
    if not data or len(data) > LOGO_MAX_BYTES or not data.startswith(magic) or (kind == "image/webp" and data[8:12] != b"WEBP"):
        raise ValidationFailedError("The file is not a valid image of that type (at most 1 MB)", code="logo_invalid")
    storage = current_app.extensions["providers"].storage
    current = getattr(sq, column)
    old_key = storage.key_from_url(current) if current else None
    key = f"square-logos/{sq.id}/{variant}-{secrets.token_hex(8)}.{extension}"
    storage.upload(key, data, kind)
    setattr(sq, column, storage.url_for(key))
    if old_key:
        storage.delete(old_key)
    _audit("square.logo", "square", str(sq.id), sq.org_id)
    get_session().commit()
    return _out(_square_out(sq))


@bp.delete("/squares/<uuid:square_id>/logo")
@api.validate(resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def delete_square_logo(square_id: uuid.UUID) -> Response:
    """Remove a logo (`?variant=dark` for the dark one): the site then uses the other variant, or the letter mark."""
    sq = _own_square(square_id)
    column = LOGO_VARIANTS[_logo_variant()]
    current = getattr(sq, column)
    if current:
        storage = current_app.extensions["providers"].storage
        key = storage.key_from_url(current)
        if key:
            storage.delete(key)
        setattr(sq, column, None)
        _audit("square.logo_removed", "square", str(sq.id), sq.org_id)
        get_session().commit()
    return _out(_square_out(sq))


@bp.post("/squares/<uuid:square_id>/retry")
@api.validate(resp=SpecResponse(HTTP_202=SquareOut), tags=["squares"])
@login_required
def retry_square(square_id: uuid.UUID) -> Response:
    """Provision a failed square again. Only a failed square qualifies; the status is claimed with one conditional UPDATE, so a double click
    cannot start two provisioning jobs. The organisation's owner is seeded as the first admin (not necessarily the caller)."""
    db = get_session()
    sq = db.get(Square, square_id)
    if sq is None or not (_is_staff() or sq.org_id in _member_org_ids(db, g.user)):
        raise NotFoundError("Square not found")
    result = db.execute(update(Square).where(Square.id == sq.id, Square.status == SquareStatus.FAILED).values(status=SquareStatus.PROVISIONING, error=None))
    claimed = cast("CursorResult[Any]", result).rowcount
    if not claimed:
        raise ConflictError("Only a failed square can be tried again", code="not_failed")
    _audit("square.retry", "square", str(sq.id), sq.org_id)
    db.commit()
    db.refresh(sq)
    owner_user = (
        db.scalar(select(User).join(Membership, Membership.user_id == User.id).where(Membership.org_id == sq.org_id, Membership.role == MembershipRole.OWNER))
        or g.user
    )
    owner = Owner(email=owner_user.email, name=owner_user.name, password_hash=owner_user.password_hash)
    current_app.extensions["executor"].submit(provision_square, current_app.extensions["db_factory"](), _settings(), sq.id, owner)
    return _out(_square_out(sq), 202)


@bp.delete("/squares/<uuid:square_id>")
@api.validate(json=SquareDeleteIn, resp=SpecResponse(HTTP_200=Ack), tags=["squares"])
@login_required
def delete_square_endpoint(square_id: uuid.UUID) -> Response:
    """Delete a square for good: its project at the provider first, then the row. The slug is typed to confirm."""
    body = SquareDeleteIn.model_validate(request.get_json(silent=True) or {})  # spectree does not parse the body of a DELETE
    db = get_session()
    sq = db.get(Square, square_id)
    if sq is None or not (_is_staff() or sq.org_id in _member_org_ids(db, g.user)):
        raise NotFoundError("Square not found")
    if sq.status == SquareStatus.PROVISIONING and not event_pass_service.awaiting_payment(sq):  # an unpaid Event pass has nothing being built (W13-R26)
        raise ConflictError("The square is still being set up", code="still_provisioning")
    if body.confirm_slug.strip().lower() != sq.slug:
        raise ValidationFailedError("The address does not match the square", code="confirm_mismatch")
    if body.force and not _is_staff():
        raise ForbiddenError("Only a platform admin can force a deletion")
    delete_square(db, _settings(), sq, g.user.id, body.force)
    db.commit()
    return _out(Ack())


def _ready_square(slug: str) -> Square:
    sq = get_session().scalar(select(Square).where(Square.slug == slug.strip().lower()))
    if sq is None or sq.status != SquareStatus.READY or sq.suspended_at is not None:
        raise NotFoundError("Square not found")
    return sq


@bp.get("/public/squares/<slug>")
@api.validate(resp=SpecResponse(HTTP_200=PublicSquareOut), tags=["public"])
def public_square(slug: str) -> Response:
    """Public hello-world data of a ready square (no sign-in): its name, theme and one fact read from its own database."""
    return _public_square_response(_ready_square(slug))


@bp.get("/public/hosts/<host>")
@api.validate(resp=SpecResponse(HTTP_200=PublicSquareOut), tags=["public"])
def public_host(host: str) -> Response:
    """Which square is served on this host name? The square's own domain (its default <slug>.<suffix> or a custom domain), or <slug>.localhost
    on a developer machine. 404 for any other host."""
    name = host.strip().lower().split(":")[0]
    sq = get_session().scalar(
        select(Square).where((Square.domain == name) | (Square.site_domain == name), Square.status == SquareStatus.READY, Square.suspended_at.is_(None))
    )
    if sq is not None and sq.domain != name:
        from app.platform.site_domain import allowed as site_domain_allowed

        sq = sq if site_domain_allowed(sq) else None  # an own domain stops being served when the package no longer has it (the data is kept)
    if sq is None and name.endswith(".localhost") and _settings().ENV in ("local", "test"):
        sq = _ready_square(name.removesuffix(".localhost"))
    if sq is None:
        raise NotFoundError("No square is served on this host")
    return _public_square_response(sq)


def _public_square_response(sq: Square) -> Response:
    auth_url, auth_key = public_auth_config(_settings(), sq)
    return _out(
        PublicSquareOut(
            name=sq.name,
            slug=sq.slug,
            theme_id=sq.theme_id,
            theme_overrides=theme_overrides.from_json(sq.theme_overrides),
            domain=sq.domain,
            google_login=sq.google_login or "requested",
            has_auth_project=bool(sq.provider_project_ref),
            database=square_database_check(_settings(), sq),
            auth_url=auth_url,
            auth_public_key=auth_key,
        )
    )


@bp.get("/public/squares/<slug>/me")
@api.validate(resp=SpecResponse(HTTP_200=SquareMeOut), tags=["public"])
def public_square_me(slug: str) -> Response:
    """Who is signed in to THIS square: the Authorization header carries a token of the square's own auth project (not the platform's), verified
    against that project's keys; the role comes from the square's own admins table."""
    sq = _ready_square(slug)
    token = _bearer_token()
    if not token:
        raise UnauthorizedError("Sign in to this square")
    try:
        who = current_app.extensions["square_auth"].authenticate(sq.id, token)
    except SquareAuthError as exc:
        raise ConflictError(str(exc), code=exc.code) from exc
    if who is None:
        raise UnauthorizedError("The sign-in is invalid or has expired", code="invalid_token")
    return _out(SquareMeOut(email=who.email, name=who.name, role=who.admin.role if who.admin else None, is_admin=who.admin is not None))


@bp.get("/squares/<uuid:square_id>")
@api.validate(resp=SpecResponse(HTTP_200=SquareOut), tags=["squares"])
@login_required
def get_square(square_id: uuid.UUID) -> Response:
    db = get_session()
    sq = db.get(Square, square_id)
    # 404 (not 403) for squares of other organizations so their existence is not revealed
    if sq is None or not (_is_staff() or sq.org_id in _member_org_ids(db, g.user)):
        raise NotFoundError("Square not found")
    return _out(_square_out(sq))


# ---- owner (platform admin) -----------------------------------------------------------------------------------------------------------
OVERVIEW_WEEKS = 8


@bp.get("/owner/attention")
@api.validate(resp=SpecResponse(HTTP_200=OwnerAttentionList), tags=["owner"])
@admin_required
def owner_attention() -> Response:
    """What waits for a person (W25-R33): the admin application's "Needs attention" page and the badge in its side bar."""
    items = attention_list.collect(get_session(), dt.datetime.now(dt.UTC))
    return _out(OwnerAttentionList(items=items, count=len(items)))


@bp.get("/owner/overview")
@api.validate(resp=SpecResponse(HTTP_200=OwnerOverview), tags=["owner"])
@admin_required
def owner_overview() -> Response:
    """Counts, signups per week and what needs a person's attention. Platform data only; nothing from inside a square."""
    db = get_session()
    now = dt.datetime.now(dt.UTC)
    counts = dict(db.execute(select(Square.status, func.count()).group_by(Square.status)).all())
    this_monday = (now - dt.timedelta(days=now.weekday())).date()
    starts = [this_monday - dt.timedelta(weeks=i) for i in range(OVERVIEW_WEEKS - 1, -1, -1)]
    since = dt.datetime.combine(starts[0], dt.time.min, tzinfo=dt.UTC)
    users = {w: 0 for w in starts}
    squares = {w: 0 for w in starts}
    for model, bucket in ((User, users), (Square, squares)):
        for (created,) in db.execute(select(model.created_at).where(model.created_at >= since)):
            created = created if created.tzinfo else created.replace(tzinfo=dt.UTC)
            bucket[(created - dt.timedelta(days=created.weekday())).date()] += 1
    attention = attention_list.collect(db, now)
    awaiting_payment = sum(1 for sq in db.scalars(select(Square).where(Square.status == SquareStatus.PROVISIONING)) if event_pass_service.awaiting_payment(sq))
    return _out(
        OwnerOverview(
            squares_total=sum(counts.values()),
            squares_ready=counts.get(SquareStatus.READY, 0),
            squares_provisioning=counts.get(SquareStatus.PROVISIONING, 0) - awaiting_payment,
            squares_awaiting_payment=awaiting_payment,
            squares_failed=counts.get(SquareStatus.FAILED, 0),
            users_total=db.scalar(select(func.count()).select_from(User)) or 0,
            organizations_total=db.scalar(select(func.count()).select_from(Organization)) or 0,
            weeks=[OwnerWeek(week_start=w, users=users[w], squares=squares[w]) for w in starts],
            attention=attention,
        )
    )


@bp.get("/owner/squares")
@api.validate(resp=SpecResponse(HTTP_200=OwnerSquareList), tags=["owner"])
@admin_required
def owner_squares() -> Response:
    db = get_session()
    rows = db.execute(
        select(Square, Organization.name, User.email)
        .join(Organization, Organization.id == Square.org_id)
        .outerjoin(Membership, (Membership.org_id == Organization.id) & (Membership.role == MembershipRole.OWNER))
        .outerjoin(User, User.id == Membership.user_id)
        .order_by(Square.created_at.desc())
    ).all()
    items = [
        OwnerSquareOut(**_square_out(sq).model_dump(), organization_name=org_name, owner_email=email, suspended_at=sq.suspended_at)
        for sq, org_name, email in rows
    ]
    return _out(OwnerSquareList(items=items))


@bp.post("/owner/squares/<uuid:square_id>/google")
@api.validate(json=GoogleIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["owner"])
@admin_required
def owner_set_google(square_id: uuid.UUID) -> Response:
    """The platform admin marks Google sign-in of a square as enabled (after adding its callback URL in Google Cloud Console) or back to requested."""
    body: GoogleIn = request.context.json  # type: ignore[attr-defined]
    db = get_session()
    sq = db.get(Square, square_id)
    if sq is None:
        raise NotFoundError("Square not found")
    if body.apply and sq.neon_project_id:
        settings = _settings()
        target = neon_target(sq, Encryptor(settings.fernet_key))
        if target is None or not settings.NEON_API_KEY:
            raise ConflictError("This square has no Neon project of its own, or the Neon key is not set", code="provider_unavailable")
        try:  # with the platform's Google OAuth client when it is set, else Neon's shared development credentials
            NeonProvisioner(settings.NEON_API_KEY, settings.NEON_REGION).set_google_login(
                target[0], target[1], settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET, body.enabled
            )
        except (NeonApiError, httpx.HTTPError) as exc:
            raise ConflictError("The provider did not accept the change", code="provider_error") from exc
    elif body.apply:
        settings = _settings()
        if not sq.provider_project_ref or not settings.SUPABASE_ACCESS_TOKEN:
            raise ConflictError("This square has no provider project, or the provider token is not set", code="provider_unavailable")
        if body.enabled and not (settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET):
            raise ConflictError("The platform's Google OAuth client is not set", code="google_client_missing")
        try:
            square_auth.set_google_login(
                settings.SUPABASE_ACCESS_TOKEN, sq.provider_project_ref, settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET, body.enabled
            )
        except httpx.HTTPError as exc:
            raise ConflictError("The provider did not accept the change", code="provider_error") from exc
    sq.google_login = "enabled" if body.enabled else "requested"
    _audit("square.google_login", "square", str(sq.id), sq.org_id, enabled=body.enabled, applied=body.apply)
    db.commit()
    return _out(_square_out(sq))


def _owner_square(db: Session, square_id: uuid.UUID) -> Square:
    sq = db.get(Square, square_id)
    if sq is None:
        raise NotFoundError("Square not found")
    return sq


@bp.get("/owner/squares/<uuid:square_id>")
@api.validate(resp=SpecResponse(HTTP_200=OwnerSquareDetail), tags=["owner"])
@admin_required
def owner_square(square_id: uuid.UUID) -> Response:
    """One square for the platform admin: owner, provider project, dashboard link and what happened to it (audit actions and times only)."""
    db = get_session()
    sq = _owner_square(db, square_id)
    org = db.get(Organization, sq.org_id)
    org_name = org.name if org is not None else ""
    owner_email = db.scalar(
        select(User.email).join(Membership, Membership.user_id == User.id).where(Membership.org_id == sq.org_id, Membership.role == MembershipRole.OWNER)
    )
    events = db.execute(
        select(AuditLog.at, AuditLog.action).where(AuditLog.entity == "square", AuditLog.entity_id == str(sq.id)).order_by(AuditLog.at.desc()).limit(50)
    ).all()
    return _out(
        OwnerSquareDetail(
            **_square_out(sq).model_dump(),
            organization_name=org_name,
            owner_email=owner_email,
            suspended_at=sq.suspended_at,
            provider=sq.provider,
            provider_project_ref=sq.provider_project_ref or sq.neon_project_id,  # a Neon square has no Supabase ref: show its Neon project id (W27-R4)
            dashboard_url=f"https://supabase.com/dashboard/project/{sq.provider_project_ref}"
            if sq.provider == "supabase" and sq.provider_project_ref
            else f"https://console.neon.tech/app/projects/{sq.neon_project_id}"
            if sq.provider == "neon" and sq.neon_project_id
            else None,
            timeline=[OwnerTimelineItem(at=at, action=action) for at, action in events],
            orders=[
                OwnerOrderOut(
                    **OrderOut.model_validate(o).model_dump(),
                    refundable=billing_service.refundable(o, _settings()),
                    refundable_minor=billing_service.refundable_minor(o, _settings()),
                )
                for o in db.scalars(select(BillingOrder).where(BillingOrder.square_id == sq.id).order_by(BillingOrder.created_at.desc()).limit(30))
            ],
        )
    )


@bp.get("/owner/subscriptions")
@api.validate(resp=SpecResponse(HTTP_200=OwnerSubscriptions), tags=["owner"])
@admin_required
def owner_subscriptions() -> Response:
    """Money and plan state across squares for the owner console (W12-R20): recurring revenue, who pays, trials, failures, what renews next."""
    return _out(OwnerSubscriptions(**subscriptions_service.overview(get_session())))


@bp.post("/owner/billing/orders/<uuid:order_id>/refund")
@api.validate(resp=SpecResponse(HTTP_200=OrderOut), tags=["owner"])
@admin_required
def owner_refund(order_id: uuid.UUID) -> Response:
    """Refund a payment (W12-R19, W13-R31): a first payment, a renewal or an Event pass, platform admin only, inside `BILLING_REFUND_DAYS` of the payment.
    No amount = the whole payment goes back and its effects follow: a first payment or renewal ends the paid time and the renewal and the site goes to
    sleep; an Event pass ends at once and its archive starts. An amount = a goodwill refund of part of it: money only, nothing else changes. Whether the
    site was published is the admin's call (no square content is read)."""
    body = RefundIn.model_validate(request.get_json(silent=True) or {})
    db = get_session()
    order = db.get(BillingOrder, order_id)
    if order is None:
        raise NotFoundError("Order not found")
    settings = _settings()
    if not billing_service.refundable(order, settings):
        raise ConflictError(
            "This payment cannot be refunded (not a paid first payment, renewal or Event pass, past the refund days, or nothing left)", code="not_refundable"
        )
    sq = db.get(Square, order.square_id)
    if sq is None:
        raise NotFoundError("Square not found")
    provider = current_app.extensions["billing"]
    left = billing_service.remaining_minor(order)
    full = body.amount_minor is None or (body.amount_minor == order.amount_minor and order.refunded_minor == 0)
    if full:
        if order.refunded_minor:
            raise ConflictError("Part of this payment was refunded already: refund the rest as an amount", code="partly_refunded")
        provider.refund(order)  # the money first (the whole payment, tax included); a repeat is safe (same idempotency key)
        if sq.stripe_subscription_id and order.kind != "event_pass":
            provider.end_subscription(sq.stripe_subscription_id)
        billing_service.mark_refunded(order, sq, settings=settings)
        _audit("billing.refund", "square", str(sq.id), sq.org_id, order_id=str(order.id), amount_minor=order.amount_minor, kind=order.kind)
        db.commit()
        if order.kind != "event_pass" and sq.running_plan == square_plans.LIVE:
            _switch_running_plan(sq, square_plans.KEEP, check_payment=False)  # nothing is paid any more: it goes to sleep
        return _out(_order_out(order))
    amount = int(body.amount_minor or 0)
    if amount > left:
        raise ValidationFailedError(f"At most {left} (minor units) is left to refund", code="bad_amount")
    provider.refund(order, amount)
    billing_service.record_partial_refund(order, amount)
    _audit("billing.refund", "square", str(sq.id), sq.org_id, order_id=str(order.id), amount_minor=amount, kind=order.kind, partial=True)
    db.commit()
    return _out(_order_out(order))


@bp.post("/owner/squares/<uuid:square_id>/suspend")
@api.validate(json=SuspendIn, resp=SpecResponse(HTTP_200=SquareOut), tags=["owner"])
@admin_required
def owner_suspend(square_id: uuid.UUID) -> Response:
    """Stop (or resume) serving a square's public site. Nothing is deleted."""
    body: SuspendIn = request.context.json  # type: ignore[attr-defined]
    db = get_session()
    sq = _owner_square(db, square_id)
    sq.suspended_at = dt.datetime.now(dt.UTC) if body.suspended else None
    _audit("square.suspended" if body.suspended else "square.unsuspended", "square", str(sq.id), sq.org_id)
    db.commit()
    return _out(_square_out(sq))


@bp.post("/owner/squares/<uuid:square_id>/sync-auth")
@api.validate(resp=SpecResponse(HTTP_200=Ack), tags=["owner"])
@admin_required
def owner_sync_auth(square_id: uuid.UUID) -> Response:
    """Set the Site URL and redirect list of the square's auth project again (what `flask sync-square-auth` does)."""
    db = get_session()
    sq = _owner_square(db, square_id)
    settings = _settings()
    if sq.neon_project_id:
        target = neon_target(sq, Encryptor(settings.fernet_key))
        if target is None or not settings.NEON_API_KEY:
            raise ConflictError("This square has no Neon project of its own, or the Neon key is not set", code="provider_unavailable")
        try:
            addresses = square_auth.trusted_addresses(sq.slug, settings.SQUARE_DOMAIN_SUFFIX, list(settings.square_extra_redirects))
            NeonProvisioner(settings.NEON_API_KEY, settings.NEON_REGION).set_redirects(target[0], target[1], addresses)
        except (NeonApiError, httpx.HTTPError) as exc:
            raise ConflictError("The provider did not accept the change", code="provider_error") from exc
        _audit("square.auth_synced", "square", str(sq.id), sq.org_id)
        db.commit()
        return _out(Ack())
    if not sq.provider_project_ref or not settings.SUPABASE_ACCESS_TOKEN:
        raise ConflictError("This square has no provider project, or the provider token is not set", code="provider_unavailable")
    try:
        square_auth.set_redirects(
            settings.SUPABASE_ACCESS_TOKEN,
            sq.provider_project_ref,
            f"https://{sq.slug}.{settings.SQUARE_DOMAIN_SUFFIX}",
            [u.replace("{slug}", sq.slug) for u in settings.square_extra_redirects],
        )
    except httpx.HTTPError as exc:
        raise ConflictError("The provider did not accept the change", code="provider_error") from exc
    _audit("square.auth_synced", "square", str(sq.id), sq.org_id)
    db.commit()
    return _out(Ack())


@bp.post("/owner/squares/<uuid:square_id>/check")
@api.validate(resp=SpecResponse(HTTP_200=SquareCheckOut), tags=["owner"])
@admin_required
def owner_check(square_id: uuid.UUID) -> Response:
    """Can the platform reach the square's own database right now?"""
    sq = _owner_square(get_session(), square_id)
    result = square_database_check(_settings(), sq)
    admins = result.get("admins")
    return _out(SquareCheckOut(ok=bool(result.get("ok")), admins=admins if isinstance(admins, int) else None))


# ---- owner: people and organisations ------------------------------------------------------------------------------------------------
def _owner_user_out(db: Session, user: User, orgs: int, sessions: int) -> OwnerUserOut:
    return OwnerUserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        sign_in=user.auth_provider or "password",
        organizations=orgs,
        active_sessions=sessions,
        created_at=user.created_at,
    )


def _active_sessions(db: Session, user_id: uuid.UUID) -> int:
    now = dt.datetime.now(dt.UTC)
    stmt = select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)
    return db.scalar(stmt) or 0


def _square_refs(db: Session, org_id: uuid.UUID) -> list[OwnerSquareRef]:
    rows = db.scalars(select(Square).where(Square.org_id == org_id).order_by(Square.created_at))
    return [OwnerSquareRef(id=s.id, name=s.name, slug=s.slug, status=str(s.status), awaiting_payment=event_pass_service.awaiting_payment(s)) for s in rows]


@bp.get("/owner/users")
@api.validate(resp=SpecResponse(HTTP_200=OwnerUserList), tags=["owner"])
@admin_required
def owner_users() -> Response:
    db = get_session()
    org_counts = dict(db.execute(select(Membership.user_id, func.count()).group_by(Membership.user_id)).all())
    now = dt.datetime.now(dt.UTC)
    session_counts = dict(
        db.execute(
            select(AuthSession.user_id, func.count()).where(AuthSession.revoked_at.is_(None), AuthSession.expires_at > now).group_by(AuthSession.user_id)
        ).all()
    )
    users = db.scalars(select(User).order_by(User.created_at.desc()).limit(1000))
    return _out(OwnerUserList(items=[_owner_user_out(db, u, org_counts.get(u.id, 0), session_counts.get(u.id, 0)) for u in users]))


def _owner_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


@bp.get("/owner/users/<uuid:user_id>")
@api.validate(resp=SpecResponse(HTTP_200=OwnerUserDetail), tags=["owner"])
@admin_required
def owner_user(user_id: uuid.UUID) -> Response:
    db = get_session()
    user = _owner_user(db, user_id)
    rows = db.execute(select(Organization, Membership.role).join(Membership, Membership.org_id == Organization.id).where(Membership.user_id == user.id)).all()
    orgs = [OwnerUserOrg(id=o.id, name=o.name, role=str(role), squares=_square_refs(db, o.id)) for o, role in rows]
    base = _owner_user_out(db, user, len(orgs), _active_sessions(db, user.id))
    return _out(OwnerUserDetail(**base.model_dump(), orgs=orgs))


@bp.post("/owner/users/<uuid:user_id>/logout-all")
@api.validate(resp=SpecResponse(HTTP_200=LoggedOutOut), tags=["owner"])
@admin_required
def owner_logout_all(user_id: uuid.UUID) -> Response:
    """End every cookie login of a person at once. Sessions held by the identity provider (Google, email link) are not touched."""
    db = get_session()
    user = _owner_user(db, user_id)
    result = db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=dt.datetime.now(dt.UTC)))
    revoked = cast("CursorResult[Any]", result).rowcount
    _audit("auth.logout_all", "user", str(user.id), None, actor=g.user.id, by="platform_admin")
    db.commit()
    return _out(LoggedOutOut(revoked=revoked))


@bp.get("/owner/organizations")
@api.validate(resp=SpecResponse(HTTP_200=OwnerOrgList), tags=["owner"])
@admin_required
def owner_organizations() -> Response:
    db = get_session()
    members = dict(db.execute(select(Membership.org_id, func.count()).group_by(Membership.org_id)).all())
    owners = dict(
        db.execute(select(Membership.org_id, User.email).join(User, User.id == Membership.user_id).where(Membership.role == MembershipRole.OWNER)).all()
    )
    orgs = db.scalars(select(Organization).order_by(Organization.created_at.desc()).limit(1000))
    items = [
        OwnerOrgOut(id=o.id, name=o.name, owner_email=owners.get(o.id), members=members.get(o.id, 0), created_at=o.created_at, squares=_square_refs(db, o.id))
        for o in orgs
    ]
    return _out(OwnerOrgList(items=items))


@bp.get("/owner/audit")
@api.validate(resp=SpecResponse(HTTP_200=OwnerAuditPage), tags=["owner"])
@admin_required
def owner_audit() -> Response:
    """The platform audit log, newest first. Filters: action_prefix (e.g. `square.`), square_id, actor_id; paging: before (a timestamp), limit (max 200)."""
    args = request.args
    try:
        limit = min(max(int(args.get("limit", "50")), 1), 200)
        before_at, _, before_id = args["before"].partition("|") if args.get("before") else ("", "", "")
        before = (dt.datetime.fromisoformat(before_at), uuid.UUID(before_id)) if before_at else None
        actor_id = uuid.UUID(args["actor_id"]) if args.get("actor_id") else None
        square_id = str(uuid.UUID(args["square_id"])) if args.get("square_id") else None
    except ValueError as exc:
        raise ValidationFailedError("A filter is not valid", code="bad_filter") from exc
    db = get_session()
    stmt = (
        select(AuditLog, User.email, StaffUser.email)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .outerjoin(StaffUser, StaffUser.id == AuditLog.actor_staff_id)
        .order_by(AuditLog.at.desc(), AuditLog.id.desc())
    )
    if args.get("action_prefix"):
        prefix = args["action_prefix"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(AuditLog.action.like(f"{prefix}%", escape="\\"))
    if square_id:
        stmt = stmt.where(AuditLog.entity == "square", AuditLog.entity_id == square_id)
    if actor_id:
        stmt = stmt.where(or_(AuditLog.actor_user_id == actor_id, AuditLog.actor_staff_id == actor_id))
    if before:
        at = before[0].replace(tzinfo=None) if db.get_bind().dialect.name == "sqlite" else before[0]  # sqlite keeps no time zone
        stmt = stmt.where((AuditLog.at < at) | ((AuditLog.at == at) & (AuditLog.id < before[1])))
    rows = db.execute(stmt.limit(limit + 1)).all()
    page = rows[:limit]
    items = [
        OwnerAuditItem(
            id=row.id,
            at=row.at,
            action=row.action,
            entity=row.entity,
            entity_id=row.entity_id,
            actor_id=row.actor_staff_id or row.actor_user_id,
            actor_email=email or staff_email,
            actor_kind="staff" if row.actor_staff_id else ("user" if row.actor_user_id else None),
            request_id=row.request_id,
            data=dict(row.data or {}),
        )
        for row, email, staff_email in page
    ]
    return _out(OwnerAuditPage(items=items, next_before=f"{page[-1][0].at.isoformat()}|{page[-1][0].id}" if len(rows) > limit else None))


@bp.get("/owner/health")
@api.validate(resp=SpecResponse(HTTP_200=OwnerHealth), tags=["owner"])
@admin_required
def owner_health() -> Response:
    """What is configured and whether each outside service answers now (database, sign-in keys, provider token, storage). No secret values."""
    settings = _settings()
    checks = run_checks(settings, current_app.extensions["providers"], get_session(), current_app.extensions.get("health_http_client"))
    return _out(OwnerHealth(environment=environment(settings), checks=[HealthCheckOut(id=c.id, status=c.status, detail=c.detail) for c in checks]))


from app.platform.voucher_routes import register as _register_voucher_routes  # noqa: E402  (the routes need everything defined above)

_register_voucher_routes()

from app.platform.opex_routes import register as _register_opex_routes  # noqa: E402

_register_opex_routes()


def register_platform(app: Flask) -> None:
    """Mounts what this process serves (settings API_SURFACE, ADR 084): the customer API, the staff API, or both (development and tests)."""
    from app.platform.admin_api import build_blueprint

    s: Settings = app.extensions["settings"]
    if s.serves_customer:
        app.register_blueprint(bp)
    if s.serves_admin:
        if s.serves_customer:
            app.register_blueprint(build_blueprint(app))  # reads the customer routes from the app, so it comes after them
        else:
            # The admin service mounts no customer address. The handlers staff share with the customer API are read from a scratch app that holds the
            # customer blueprint, and only the staff blueprint built from it is registered here.
            scratch = Flask("surface-scratch")
            scratch.register_blueprint(bp)
            app.register_blueprint(build_blueprint(scratch))
    api.register(app)


from app.platform.invoice_routes import register as _register_invoice_routes  # noqa: E402

_register_invoice_routes()

from app.platform.custom_routes import register as _register_custom_routes  # noqa: E402

_register_custom_routes()

from app.platform.prospect_routes import register as _register_prospect_routes  # noqa: E402

_register_prospect_routes()

from app.platform.support_routes import register as _register_support_routes  # noqa: E402

_register_support_routes()

from app.platform.analytics_routes import register as _register_analytics_routes  # noqa: E402

_register_analytics_routes()

from app.platform.mail_domain import register as _register_mail_domain_routes  # noqa: E402
from app.platform.site_domain import register as _register_site_domain_routes  # noqa: E402

_register_mail_domain_routes()
_register_site_domain_routes()
