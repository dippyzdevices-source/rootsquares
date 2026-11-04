"""/healthz (liveness) and /readyz (readiness). Readiness checks are registered by later stages
(DB pools reachable, both migration histories at head); with none registered the app is ready."""

from __future__ import annotations

from collections.abc import Callable

import structlog
from flask import Blueprint, Flask, current_app, jsonify
from flask.typing import ResponseReturnValue

from app.shared.errors import problem

log = structlog.get_logger("app.health")
ReadinessCheck = Callable[[], None]  # raises on failure

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz() -> ResponseReturnValue:
    return jsonify(status="ok")


@bp.get("/readyz")
def readyz() -> ResponseReturnValue:
    checks: dict[str, ReadinessCheck] = current_app.extensions["readiness_checks"]
    results: dict[str, str] = {}
    for name, check in checks.items():
        try:
            check()
            results[name] = "ok"
        except Exception as exc:  # report the name only, never the error text
            log.warning("readiness_check_failed", check=name, error_type=type(exc).__name__)
            results[name] = "fail"
    if any(v != "ok" for v in results.values()):
        return problem(503, "not_ready", "Service not ready", checks=results)
    return jsonify(status="ready", checks=results)


def register_health(app: Flask) -> None:
    app.extensions.setdefault("readiness_checks", {})
    app.register_blueprint(bp)
