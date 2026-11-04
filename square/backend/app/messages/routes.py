"""Public side of the Messages module: the unsubscribe link in every "update" message. Unauthenticated by design; the signed token (derived from the
address and the server secret) is the only credential, so nobody can opt another person out, and the answer never says whether an address was known."""

from flask import Blueprint, jsonify, request

from app.messages import service

messages_bp = Blueprint("messages", __name__, url_prefix="/api/messages")


@messages_bp.route("/unsubscribe", methods=["GET", "POST"])
def unsubscribe():
    """POST (also the mail client's one-click button, which posts to the link in List-Unsubscribe) opts the address out; GET only checks the link."""
    body = request.get_json(silent=True) or {}
    email = str(request.args.get("e") or body.get("email") or "").strip().lower()
    token = str(request.args.get("t") or body.get("token") or "")
    if not service.valid_unsubscribe(email, token):
        return jsonify({"error": "This link is not valid."}), 400
    if request.method == "POST":
        service.suppress(email)
        return jsonify({"unsubscribed": True})
    return jsonify({"valid": True})
