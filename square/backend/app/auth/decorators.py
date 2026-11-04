from functools import wraps

from flask import g, jsonify, request

from app.auth.service import resolve_user_from_token


def _authenticate():
    """Verify the request's bearer token and set g.current_user.

    Returns None on success, or a (response, status) tuple to return immediately on failure.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.removeprefix("Bearer ").strip()
    support = g.get("support")
    if support is not None:
        # A rootsquares support session (ADR 089): the guard in app.support already checked the grant, the scope and read only. The support user is an admin
        # only on the admin parts a scope opens (and on /api/auth/me); on any other route it is nobody.
        from app.support import SCOPE_OF, support_user

        if request.blueprint in SCOPE_OF or request.blueprint == "auth":
            g.current_user = support_user()
            return None
        return jsonify({"error": "Invalid or expired token"}), 401
    user = resolve_user_from_token(token)
    if user is None:
        return jsonify({"error": "Invalid or expired token"}), 401

    g.current_user = user
    return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        # CORS preflight requests never carry an Authorization header — let Flask-CORS's
        # own automatic OPTIONS handling answer them instead of rejecting with 401, which
        # makes the browser treat the whole preflight as failed and block the real
        # request. Real auth is still enforced on every non-OPTIONS request.
        if request.method == "OPTIONS":
            return view(*args, **kwargs)
        error = _authenticate()
        if error is not None:
            return error
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if request.method == "OPTIONS":
                return view(*args, **kwargs)
            error = _authenticate()
            if error is not None:
                return error
            if g.current_user.role not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def require_role(*roles):
    """For use as a blueprint before_request hook, e.g.:

    some_bp.before_request(require_role("admin"))
    """

    def check():
        # See require_auth's OPTIONS comment — before_request hooks run for CORS
        # preflight OPTIONS requests too, so this must bypass auth for them the same way.
        if request.method == "OPTIONS":
            return None
        error = _authenticate()
        if error is not None:
            return error
        if g.current_user.role not in roles:
            return jsonify({"error": "Forbidden"}), 403
        return None

    return check
