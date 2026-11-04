"""Error format: application/problem+json with a stable `code`, and handlers that never leak internals."""

from __future__ import annotations

from typing import Any

import structlog
from flask import Flask, Response, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from app.shared.request_context import get_request_id

PROBLEM_JSON = "application/problem+json"
log = structlog.get_logger("app.errors")

_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
}


class AppError(Exception):
    """Raise from services and routes. `code` is the stable machine-readable identifier."""

    status = 500
    code = "internal_error"
    title = "Something went wrong"

    def __init__(self, detail: str | None = None, *, code: str | None = None, **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        if code:
            self.code = code
        self.extra = extra


class BadRequestError(AppError):
    status, code, title = 400, "bad_request", "Bad request"


class UnauthorizedError(AppError):
    status, code, title = 401, "unauthorized", "Authentication required"


class ForbiddenError(AppError):
    status, code, title = 403, "forbidden", "Not allowed"


class NotFoundError(AppError):
    status, code, title = 404, "not_found", "Not found"


class ConflictError(AppError):
    status, code, title = 409, "conflict", "Conflict"


class ValidationFailedError(AppError):
    status, code, title = 422, "validation_error", "Validation failed"


def problem(status: int, code: str, title: str, detail: str | None = None, **extra: Any) -> Response:
    body: dict[str, Any] = {
        "type": f"urn:rootsquares:problem:{code}",
        "title": title,
        "status": status,
        "code": code,
        "request_id": get_request_id(),
    }
    if detail:
        body["detail"] = detail
    body.update(extra)
    resp = jsonify(body)
    resp.status_code = status
    resp.headers["Content-Type"] = PROBLEM_JSON
    return resp


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def _app_error(err: AppError) -> Response:
        return problem(err.status, err.code, err.title, err.detail, **err.extra)

    @app.errorhandler(ValidationError)
    def _validation(err: ValidationError) -> Response:
        # Only location, message and type: never echo the submitted values (they may be personal data).
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in err.errors()]
        return problem(422, "validation_error", "Validation failed", errors=errors)

    @app.errorhandler(HTTPException)
    def _http(err: HTTPException) -> Response:
        status = err.code or 500
        code = _HTTP_CODES.get(status, "http_error")
        resp = problem(status, code, err.name, err.description if status < 500 else None)
        for key, value in err.get_headers() or []:
            if key.lower() in ("allow", "retry-after", "www-authenticate"):
                resp.headers[key] = value
        return resp

    @app.errorhandler(Exception)
    def _unexpected(err: Exception) -> Response:
        log.exception("unhandled_error", error_type=type(err).__name__)
        return problem(500, "internal_error", "Something went wrong")
