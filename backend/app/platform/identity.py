"""Bearer-token identity (ADR 028): verify a Supabase/Neon JWT and return the matching platform user, creating the row on first sight.

Adapted from bca-oslo's resolve_user_from_token (backend/app/auth/service.py). Difference: no silent account linking by email. If the email
already belongs to another identity (for example the platform admin's password account), the request is refused instead of merged, so a
provider account can never take over an existing account."""

from __future__ import annotations

import jwt
import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.platform.models import AuditLog, User
from app.shared.errors import ConflictError
from app.shared.interfaces import AuthProvider

log = structlog.get_logger("app.auth")


def resolve_user_from_token(db: Session, provider: AuthProvider, token: str) -> User | None:
    """None for an invalid or expired token. Raises ConflictError when the token's email belongs to a different account."""
    try:
        claims = provider.verify(token)
    except jwt.PyJWTError as exc:
        log.warning("token_rejected", error=type(exc).__name__)  # the type only, never the token (W13-R7: sign-in sent back to /login)
        return None

    sub = claims["sub"]
    user = db.scalar(select(User).where(User.auth_user_id == sub, User.auth_provider == provider.name))
    if user is not None:
        return user

    email = claims.get("email", "").strip().lower()
    if not email:
        return None  # the platform needs an address; a token without one cannot sign in
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("An account with this email already exists. Sign in with it instead.", code="account_exists")

    user = User(email=email, password_hash=None, name=claims.get("name", "").strip(), auth_user_id=sub, auth_provider=provider.name)
    db.add(user)
    try:
        db.flush()
        db.add(AuditLog(action="auth.provider_signup", entity="user", entity_id=str(user.id), actor_user_id=user.id, data={"provider": provider.name}))
        db.commit()
    except IntegrityError:  # two first requests raced; the other one won
        db.rollback()
        return db.scalar(select(User).where(User.auth_user_id == sub, User.auth_provider == provider.name))
    return user
