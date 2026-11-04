"""Data export and deletion (auth item G, GDPR): a platform user's data in one JSON file, deleting a square (and its project at the provider) and
deleting the account.

Rules: a square holds an association's data, so an account with squares cannot be deleted until its squares are deleted (409 `has_squares`).
Deleting a square removes its project first; only when the provider confirmed does the row go. The audit log is anonymised, not erased."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import httpx
from sqlalchemy import delete, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.platform.models import AuditLog, AuthSession, Membership, Organization, Square, User
from app.platform.provisioning import LocalProvisioner, NeonProvisioner, SupabaseApiError, SupabaseProvisioner
from app.shared.config import Settings
from app.shared.crypto import Encryptor
from app.shared.errors import AppError, ConflictError


class DestroyFailedError(AppError):
    status, code, title = 502, "destroy_failed", "Could not remove the resources of the square"


class ProviderRemovalFailedError(AppError):
    status, code, title = 502, "provider_removal_failed", "Could not remove the sign-in account at the identity provider"


def _iso(d: dt.datetime | None) -> str | None:
    return d.isoformat() if d else None


# ---- export -------------------------------------------------------------------------------------------------------------------------
def export_user(db: Session, user: User) -> dict[str, Any]:
    """Everything the platform holds about one user, readable. No secrets (connection strings, keys, password hash) and nobody else's data."""
    orgs = db.execute(select(Organization, Membership.role).join(Membership, Membership.org_id == Organization.id).where(Membership.user_id == user.id)).all()
    org_ids = [o.id for o, _ in orgs]
    squares = db.scalars(select(Square).where(Square.org_id.in_(org_ids)).order_by(Square.created_at)).all() if org_ids else []
    sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id).order_by(AuthSession.created_at)).all()
    audit = db.scalars(select(AuditLog).where(AuditLog.actor_user_id == user.id).order_by(AuditLog.at).limit(5000)).all()
    return {
        "exported_at": dt.datetime.now(dt.UTC).isoformat(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "sign_in": user.auth_provider or "password",
            "created_at": _iso(user.created_at),
        },
        "organizations": [{"id": str(o.id), "name": o.name, "role": str(role), "created_at": _iso(o.created_at)} for o, role in orgs],
        "squares": [
            {
                "id": str(s.id),
                "organization_id": str(s.org_id),
                "name": s.name,
                "slug": s.slug,
                "domain": s.domain,
                "theme": s.theme_id,
                "status": str(s.status),
                "google_login": s.google_login or "requested",
                "created_at": _iso(s.created_at),
            }
            for s in squares
        ],
        "password_logins": [
            {"created_at": _iso(x.created_at), "last_used_at": _iso(x.last_used_at), "expires_at": _iso(x.expires_at), "revoked_at": _iso(x.revoked_at)}
            for x in sessions
        ],
        "activity": [{"at": _iso(a.at), "action": a.action, "entity": a.entity, "entity_id": a.entity_id, "data": a.data} for a in audit],
    }


# ---- deleting a square -------------------------------------------------------------------------------------------------------------
def destroy_square_resources(settings: Settings, sq: Square, force: bool = False, client: httpx.Client | None = None) -> None:
    """Remove the square's project or database at its provider. 404 at the provider is not taken as 'gone' (the token may belong to another
    account) unless `force` is set by a platform admin."""
    try:
        gone = _destroy(settings, sq, client)
    except (SupabaseApiError, httpx.HTTPError) as exc:
        raise DestroyFailedError(str(exc) if isinstance(exc, SupabaseApiError) else f"The provider could not be reached ({type(exc).__name__})") from exc
    if not gone and not force:
        raise ConflictError(
            "The project was not found with the current access token (it may belong to another account). Remove it there, then delete again with force.",
            code="project_not_found",
        )


def _destroy(settings: Settings, sq: Square, client: httpx.Client | None) -> bool:
    """True = removed (or nothing to remove), False = the provider does not know the project."""
    enc = Encryptor(settings.fernet_key)
    gone = True
    if sq.provider_project_ref:
        if not settings.SUPABASE_ACCESS_TOKEN:
            raise DestroyFailedError("SUPABASE_ACCESS_TOKEN is not set, so the Supabase project cannot be removed")
        gone = SupabaseProvisioner(settings.SUPABASE_ACCESS_TOKEN, settings.SUPABASE_ORG_SLUG, settings.SUPABASE_REGION, client=client).destroy_project(
            sq.provider_project_ref
        )
    elif sq.neon_project_id:
        if not settings.NEON_API_KEY:
            raise DestroyFailedError("NEON_API_KEY is not set, so the Neon project cannot be removed")
        gone = NeonProvisioner(settings.NEON_API_KEY, settings.NEON_REGION, client=client).destroy_project(sq.neon_project_id)
    elif sq.db_connection:
        name = make_url(enc.decrypt(sq.db_connection)).database or ""
        try:
            LocalProvisioner(settings.DATABASE_URL).drop_database(name)
        except RuntimeError as exc:
            raise DestroyFailedError(str(exc)) from exc
    return gone


def delete_square(db: Session, settings: Settings, sq: Square, actor_id: uuid.UUID | None, force: bool = False, client: httpx.Client | None = None) -> None:
    destroy_square_resources(settings, sq, force, client)
    db.add(
        AuditLog(
            action="square.deleted",
            entity="square",
            entity_id=str(sq.id),
            org_id=sq.org_id,
            actor_user_id=actor_id,
            data={"slug": sq.slug, "provider": sq.provider or ("supabase" if sq.provider_project_ref else "local"), "forced": force},
        )
    )
    db.delete(sq)


# ---- deleting the account ----------------------------------------------------------------------------------------------------------
def remove_provider_user(settings: Settings, user: User, client: httpx.Client | None = None) -> bool:
    """Delete the person's sign-in account at the identity provider. True = nothing is left there. False = not possible with the current setup
    (no AUTH_ADMIN_KEY, or Neon, which is not wired): the platform data is still deleted and the answer says so."""
    if not user.auth_user_id:
        return True  # a password account lives only here
    if user.auth_provider == "supabase" and settings.AUTH_ADMIN_KEY:
        headers = {"apikey": settings.AUTH_ADMIN_KEY}
        if not settings.AUTH_ADMIN_KEY.startswith("sb_"):
            headers["Authorization"] = f"Bearer {settings.AUTH_ADMIN_KEY}"
        r = (client or httpx).delete(f"{settings.auth_url}/auth/v1/admin/users/{user.auth_user_id}", headers=headers, timeout=30.0)
        if r.status_code in (200, 204, 404):
            return True
        raise ProviderRemovalFailedError(f"The identity provider answered {r.status_code}")
    return False


def delete_account(db: Session, settings: Settings, user: User, client: httpx.Client | None = None) -> bool:
    """Delete the user, their sessions, memberships and organisations they were the only member of. Returns whether the sign-in account at the
    provider was removed too. Refuses (409) for anyone whose organisations still have squares."""
    org_ids = list(db.scalars(select(Membership.org_id).where(Membership.user_id == user.id)))
    squares = db.scalars(select(Square).where(Square.org_id.in_(org_ids))).all() if org_ids else []
    if squares:
        raise ConflictError("Delete your squares first.", code="has_squares", squares=[{"id": str(s.id), "name": s.name, "slug": s.slug} for s in squares])
    provider_removed = remove_provider_user(settings, user, client)  # first: if it fails nothing has been changed here yet
    for org_id in org_ids:
        others = db.scalar(select(Membership.id).where(Membership.org_id == org_id, Membership.user_id != user.id))
        if others is None:
            db.execute(delete(Organization).where(Organization.id == org_id))  # memberships of an organisation go with it
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(Membership).where(Membership.user_id == user.id))
    db.execute(update(AuditLog).where(AuditLog.actor_user_id == user.id).values(actor_user_id=None))  # history stays, the person does not
    db.add(AuditLog(action="account.deleted", entity="user", entity_id=str(user.id), data={"provider_removed": provider_removed}))
    db.delete(user)
    return provider_removed
