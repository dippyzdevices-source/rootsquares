from flask import Blueprint, g, jsonify

from app.auth.decorators import require_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.get("/me")
@require_auth
def get_me():
    user = g.current_user
    body = {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
    }
    support = g.get("support")
    if support is not None:  # a rootsquares support session: the page shows a banner and locks what the owner did not allow (ADR 089)
        body["support"] = {"name": support.name, "scopes": list(support.scopes), "allow_changes": support.allow_changes, "ends_at": support.ends_at}
    return jsonify(body)
