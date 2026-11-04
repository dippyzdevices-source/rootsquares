import jwt
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.auth.emails import send_welcome_email
from app.auth.models import User
from app.auth.providers import get_auth_provider
from app.extensions import db
from app.tenancy import current_tenant


def _promote_square_owner(user: User) -> User:
    """In a square (rootsquares W6-R26) the person the platform created as the square's owner is listed in the square's own `admins` table with
    their sign-in id. That person is an admin of the BCA app too: bca-oslo has no such table, so this only runs while a square is being served."""
    if current_tenant() is None or user.role == "admin":
        return user
    try:
        owner = db.session.execute(text("select 1 from admins where auth_user_id = :sub limit 1"), {"sub": user.auth_user_id}).first()
    except SQLAlchemyError:
        db.session.rollback()  # no admins table: nothing to map
        return user
    if owner is not None:
        user.role = "admin"
        db.session.commit()
    return user


def resolve_user_from_token(token: str) -> User | None:
    """Verify a bearer token against whichever AuthProvider is active (see
    app/auth/providers.py) and return the matching local User, JIT-provisioning
    one on first sight. Returns None for any invalid/expired token — never raises.
    """
    try:
        claims = get_auth_provider().verify(token)
    except jwt.PyJWTError:
        return None

    auth_user_id = claims["sub"]
    email = claims.get("email", "")

    user = User.query.filter_by(auth_user_id=auth_user_id).first()
    if user is None:
        user = User(
            auth_user_id=auth_user_id,
            email=email,
            role="member",
            auth_provider=get_auth_provider().name,
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            # Two first-ever requests raced (the frontend fires several /api/auth/me at once and
            # auth_user_id is unique): the other one won. Use its row, and stay quiet so the
            # welcome email goes out exactly once — from the request that actually created it.
            db.session.rollback()
            return User.query.filter_by(auth_user_id=auth_user_id).first()
        send_welcome_email(user)

    if user.disabled_at is not None:
        return None

    return _promote_square_owner(user)
