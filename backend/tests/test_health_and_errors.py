"""Tests for health and errors (8 tests), e.g. healthz; readyz with no checks is ready; readyz failure is problem json without error text."""
from __future__ import annotations

import json

from flask import Flask
from flask.testing import FlaskClient
from pydantic import BaseModel

from app.main import create_app
from app.shared.errors import ConflictError
from tests.conftest import make_settings


def test_healthz(client: FlaskClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_readyz_with_no_checks_is_ready(client: FlaskClient) -> None:
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ready"


def test_readyz_failure_is_problem_json_without_error_text(app: Flask) -> None:
    def broken() -> None:
        raise RuntimeError("password=secret host=db.internal")

    app.extensions["readiness_checks"]["database"] = broken
    r = app.test_client().get("/readyz")
    assert r.status_code == 503
    assert r.mimetype == "application/problem+json"
    body = r.get_json()
    assert body["code"] == "not_ready" and body["checks"] == {"database": "fail"}
    assert "secret" not in r.get_data(as_text=True)


def test_unknown_route_is_problem_json(client: FlaskClient) -> None:
    r = client.get("/nope")
    body = r.get_json()
    assert r.status_code == 404 and r.mimetype == "application/problem+json"
    assert body["code"] == "not_found" and body["status"] == 404
    assert body["type"] == "urn:rootsquares:problem:not_found"
    assert body["request_id"] and r.headers["X-Request-ID"] == body["request_id"]


def test_method_not_allowed_keeps_allow_header(client: FlaskClient) -> None:
    r = client.post("/healthz")
    assert r.status_code == 405 and r.get_json()["code"] == "method_not_allowed"
    assert "GET" in r.headers["Allow"]


def test_request_id_is_echoed_when_valid_and_replaced_when_not(client: FlaskClient) -> None:
    assert client.get("/healthz", headers={"X-Request-ID": "abc-12345678"}).headers["X-Request-ID"] == "abc-12345678"
    replaced = client.get("/healthz", headers={"X-Request-ID": "bad id with spaces"}).headers["X-Request-ID"]
    assert replaced != "bad id with spaces" and len(replaced) == 32


def test_app_error_and_unhandled_error_and_validation_error() -> None:
    app = create_app(make_settings())

    class Body(BaseModel):
        email: str
        age: int

    @app.get("/_t/conflict")
    def _c() -> str:
        raise ConflictError("already exists", code="duplicate_slug", field="slug")

    @app.get("/_t/boom")
    def _b() -> str:
        raise RuntimeError("secret internals: member Ola Nordmann")

    @app.get("/_t/validate")
    def _v() -> str:
        Body.model_validate({"email": "ola@example.com", "age": "not a number"})
        return ""

    c = app.test_client()
    r = c.get("/_t/conflict")
    assert r.status_code == 409 and r.get_json()["code"] == "duplicate_slug" and r.get_json()["field"] == "slug"

    r = c.get("/_t/boom")
    assert r.status_code == 500 and r.get_json()["code"] == "internal_error"
    assert "Nordmann" not in r.get_data(as_text=True)

    r = c.get("/_t/validate")
    body = r.get_json()
    assert r.status_code == 422 and body["code"] == "validation_error"
    assert body["errors"][0]["loc"] == ["age"]
    assert "ola@example.com" not in json.dumps(body) and "not a number" not in json.dumps(body)


def test_providers_container_is_wired(app: Flask) -> None:
    assert app.extensions["providers"].auth is None
    assert app.extensions["settings"].ENV == "test"
