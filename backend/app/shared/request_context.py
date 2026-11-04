"""Per-request id: accepted from X-Request-ID when well formed, otherwise generated; returned on every response."""

from __future__ import annotations

import re
import time
import uuid

import structlog
from flask import Flask, Response, g, request
from structlog.contextvars import bind_contextvars, clear_contextvars

REQUEST_ID_HEADER = "X-Request-ID"
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
log = structlog.get_logger("app.request")


def get_request_id() -> str | None:
    try:
        return getattr(g, "request_id", None)
    except RuntimeError:  # outside a request
        return None


def install_request_context(app: Flask) -> None:
    @app.before_request
    def _start() -> None:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        g.request_id = incoming if _VALID.match(incoming) else uuid.uuid4().hex
        g.started = time.perf_counter()
        clear_contextvars()
        bind_contextvars(request_id=g.request_id)

    @app.after_request
    def _finish(resp: Response) -> Response:
        resp.headers[REQUEST_ID_HEADER] = get_request_id() or ""
        started = getattr(g, "started", None)
        # Path only: never the query string, headers or body (they can hold personal data).
        log.info(
            "request",
            method=request.method,
            path=request.path,
            status=resp.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1) if started else None,
        )
        return resp

    @app.teardown_request
    def _end(_exc: BaseException | None) -> None:
        clear_contextvars()
