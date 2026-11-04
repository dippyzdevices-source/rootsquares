"""Test helper (ADR 083): a client that calls the customer API like a customer and the staff-only routes like a staff member.

Since the admin console moved to its own API, a customer client can no longer call `/owner/...`, `/opex/...`, `/vouchers/...` and the other
staff routes (the customer API answers 404 for them). Many billing tests exercise those handlers right after making a square, so
`as_admin(app, client)` wraps the customer client: every call to a route that only staff may use goes to `/api/admin/v1` with a freshly
signed-in staff member (password and second step, like the real sign-in); everything else goes through unchanged. The staff transport
itself (sign-in, cookie, headers, origin) is tested in `test_admin_api.py`.
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import Flask
from werkzeug.exceptions import HTTPException

from app.platform import staff

API = "/api/platform/v1"
ADMIN = "/api/admin/v1"
STAFF_HEADERS = {"X-Requested-With": "rootsquares-admin"}
PASSWORD = "a-long-staff-password"
# customer routes that are staff-only by an inline check, not by `admin_required`
STAFF_ONLY_ENDPOINTS = {"admin_v1.set_custom_package", "admin_v1.set_square_plan"}


def staff_client(app: Flask) -> Any:
    """A test client that is signed in as a new staff member (first sign-in: the second step is set up and used at once)."""
    email = f"staff-{uuid.uuid4().hex[:8]}@example.com"
    with app.extensions["db_factory"]()() as db:
        staff.create_staff(db, email, PASSWORD, name="Test staff")
        db.commit()
    c = app.test_client()
    assert c.post(f"{ADMIN}/auth/login", json={"email": email, "password": PASSWORD}, headers=STAFF_HEADERS).status_code == 200
    secret = c.post(f"{ADMIN}/auth/enrol/start", headers=STAFF_HEADERS).json["secret"]
    done = c.post(f"{ADMIN}/auth/enrol/confirm", json={"code": staff.totp_code(secret)}, headers=STAFF_HEADERS)
    assert done.status_code == 200, done.json
    return c


class AdminRouting:
    """The customer client plus a staff client; see the module note."""

    def __init__(self, app: Flask, customer: Any, staff_side: Any) -> None:
        self._app, self._customer, self._staff = app, customer, staff_side

    def _staff_path(self, method: str, path: str) -> str | None:
        if not path.startswith(API + "/"):
            return None
        tail, _, query = path[len(API) :].partition("?")
        if tail.startswith("/owner/"):
            tail = tail[len("/owner") :]
        try:
            endpoint, _args = self._app.url_map.bind("localhost").match(ADMIN + tail, method=method)
        except HTTPException:
            return None
        view = self._app.view_functions[endpoint]
        if endpoint.startswith("admin_v1.staff_") or not (getattr(view, "admin_only", False) or endpoint in STAFF_ONLY_ENDPOINTS):
            return None
        return ADMIN + tail + (f"?{query}" if query else "")

    def open(self, path: str, *args: Any, **kwargs: Any) -> Any:
        method = str(kwargs.get("method", "GET")).upper()
        target = self._staff_path(method, path)
        if target is None:
            return self._customer.open(path, *args, **kwargs)
        kwargs["headers"] = dict(STAFF_HEADERS)
        return self._staff.open(target, *args, **kwargs)

    def get(self, path: str, **kw: Any) -> Any:
        return self.open(path, method="GET", **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self.open(path, method="POST", **kw)

    def put(self, path: str, **kw: Any) -> Any:
        return self.open(path, method="PUT", **kw)

    def patch(self, path: str, **kw: Any) -> Any:
        return self.open(path, method="PATCH", **kw)

    def delete(self, path: str, **kw: Any) -> Any:
        return self.open(path, method="DELETE", **kw)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._customer, name)


def as_admin(app: Flask, client: Any) -> AdminRouting:
    """`client` keeps working as a customer; calls to staff-only routes are made as a signed-in staff member."""
    return AdminRouting(app, client, staff_client(app))
