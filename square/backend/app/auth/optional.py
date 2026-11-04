"""Optional-auth helpers for otherwise-public, unauthenticated endpoints."""

from flask import request

from app.auth.models import User
from app.auth.service import resolve_user_from_token


def optional_admin_user() -> User | None:
    """Returns the requesting user only if the request carries a valid token belonging to an
    `admin`; otherwise None. Used to quietly include hidden/draft content in the response of a
    public endpoint for an admin's own request (so they can preview it before publishing) —
    never for an anonymous visitor or any other role. A missing/invalid token or a non-admin
    role just behaves exactly like an anonymous visitor; this never rejects the request.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    user = resolve_user_from_token(token)
    if user is None or user.role != "admin":
        return None
    return user
