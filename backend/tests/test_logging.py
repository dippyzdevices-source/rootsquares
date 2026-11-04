"""Tests for logging (2 tests), e.g. every line has request id and no query string; context does not leak between requests."""
from __future__ import annotations

import io
import json

from app.main import create_app
from app.shared.logging import configure_logging
from tests.conftest import make_settings


def _lines(buf: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line.startswith("{")]


def test_every_line_has_request_id_and_no_query_string() -> None:
    app = create_app(make_settings())
    buf = io.StringIO()
    configure_logging("INFO", buf)  # redirect after create_app configured stdout

    @app.get("/_t/log")
    def _t() -> str:
        import structlog

        structlog.get_logger("test").info("inside", detail="x")
        return "ok"

    r = app.test_client().get("/_t/log?email=ola@example.com", headers={"X-Request-ID": "req-12345678"})
    assert r.status_code == 200
    lines = _lines(buf)
    inside = next(x for x in lines if x["event"] == "inside")
    request_line = next(x for x in lines if x["event"] == "request")
    for line in (inside, request_line):
        assert line["request_id"] == "req-12345678"
    assert request_line["path"] == "/_t/log" and request_line["status"] == 200
    assert "ola@example.com" not in buf.getvalue()


def test_context_does_not_leak_between_requests() -> None:
    app = create_app(make_settings())
    buf = io.StringIO()
    configure_logging("INFO", buf)
    c = app.test_client()
    c.get("/healthz", headers={"X-Request-ID": "first-12345678"})
    c.get("/healthz", headers={"X-Request-ID": "second-1234567"})
    ids = [x["request_id"] for x in _lines(buf) if x["event"] == "request"]
    assert ids == ["first-12345678", "second-1234567"]
