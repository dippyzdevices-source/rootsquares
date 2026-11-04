"""The two doors of analytics (rootsquares ADR 090, W23-R76).

`POST /api/analytics/hit`: public, the beacon of the square's site. It answers 204 whether it counted or not (a visitor learns nothing from the answer).
`GET /api/internal/analytics`: protected by the platform's shared key like the other internal calls; the platform passes the answer on to the square's own owner and keeps
nothing (ADR 090: the one exception to ADR 038, aggregates only).
"""

from flask import Blueprint, g, jsonify, request

from app.analytics import service
from app.module_status import _key_ok

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")
analytics_internal_bp = Blueprint("analytics_internal", __name__, url_prefix="/api/internal")


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.remote_addr) or ""


@analytics_bp.post("/hit")
def hit():
    if not service.enabled():
        return "", 204
    if request.headers.get("DNT") == "1" or request.headers.get("Sec-GPC") == "1":
        return "", 204  # Do Not Track and Global Privacy Control: nothing is counted
    if request.content_length is not None and request.content_length > 2048:
        return "", 204
    body = request.get_json(silent=True, force=True) or {}  # sendBeacon sends text/plain
    if isinstance(body, dict):
        service.record_hit(body.get("path"), body.get("referrer"), request.headers.get("User-Agent", ""), _client_ip(), request.host)
    return "", 204


@analytics_internal_bp.get("/analytics")
def internal_analytics():
    if not _key_ok():
        return jsonify({"error": "Not found"}), 404  # the same answer for a missing and a wrong key
    tenant = g.get("tenant")
    if tenant is not None and tenant.sleeping:
        return jsonify({"resting": True})  # asleep: its project may be paused, nothing is read
    try:
        days = int(request.args.get("days", "30"))
    except ValueError:
        days = 30
    return jsonify(service.report(days))
