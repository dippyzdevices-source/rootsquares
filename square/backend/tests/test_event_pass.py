"""The Event pass on the square server (rootsquares W11, ADR 044): the archive (owner only, read-only, nothing bought), the one-event rule, the export zip and
the message to every ticket buyer."""

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text

from app import create_app
from app.accounting.models import Expense
from app.config import TestingConfig
from app.events.models import Event
from app.extensions import db
from app.orders.models import Order
from app.tenancy import event_phase_of
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_tenancy import _enc, _square_db

NOW = datetime.now(timezone.utc)


def _iso(days: float) -> str:
    return (NOW + timedelta(days=days)).isoformat()


# ---- the phase and the archive guard (tenancy mode, unauthenticated requests are enough to see what the guard lets through) ------------------------
@pytest.fixture
def server(tmp_path: Path):
    url = _square_db(tmp_path / "s.db", "s@example.org")
    platform_url = f"sqlite:///{tmp_path / 'platform.db'}"
    platform = create_engine(platform_url)
    with platform.begin() as conn:
        conn.execute(
            text(
                "create table squares (slug text, name text, theme_id text, domain text, status text, suspended_at text, db_connection text, provider_secrets text, "
                "currency text, phone_country text, logo_url text, logo_dark_url text, modules text, running_plan text, sleep_state text, sleep_contact text, "
                "launch_package text, event_live_until text, event_archive_until text)"
            )
        )
        for slug, package, live, archive in (
            ("live", "event", _iso(20), _iso(65)),
            ("archive", "event", _iso(-5), _iso(40)),
            ("late", "event", _iso(-60), _iso(-10)),  # past the archive, the daily job has not removed it yet: never live again
            ("normal", "grove", None, None),
        ):
            conn.execute(
                text(
                    "insert into squares values (:slug, :name, 'paper-brick', :domain, 'ready', null, :url, :sec, 'NOK', 'NO', null, null, null, :plan, 'awake', null, :pkg, :live, :archive)"
                ),
                {
                    "slug": slug,
                    "name": slug,
                    "domain": f"{slug}.rootsquares.com",
                    "url": _enc(url),
                    "sec": _enc(json.dumps({})),
                    "plan": "event" if package == "event" else "live",
                    "pkg": package,
                    "live": live,
                    "archive": archive,
                },
            )
    platform.dispose()
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", platform_url):
        return create_app("testing")


def _host(slug: str) -> dict[str, str]:
    return {"Host": f"{slug}.rootsquares.com"}


def test_the_phase_comes_from_the_dates() -> None:
    assert event_phase_of("event", _iso(5), _iso(50)) == "live"
    assert event_phase_of("event", _iso(-1), _iso(44)) == "archive"
    assert event_phase_of("event", _iso(-50), _iso(-5)) == "archive"  # never live again
    assert event_phase_of("grove", None, None) == "" and event_phase_of("", None, None) == ""
    assert event_phase_of("event", None, None) == "live"  # an older platform database without the dates


def test_the_config_tells_the_phase_of_a_pass(server) -> None:
    c = server.test_client()
    live = c.get("/api/square/config", headers=_host("live")).get_json()["event_pass"]
    assert live["phase"] == "live" and live["archive_until"]
    assert c.get("/api/square/config", headers=_host("archive")).get_json()["event_pass"]["phase"] == "archive"
    assert c.get("/api/square/config", headers=_host("normal")).get_json()["event_pass"] is None


def test_in_the_archive_nothing_is_bought_changed_or_reached_by_helpers(server) -> None:
    c = server.test_client()
    for slug in ("archive", "late"):
        for method, path in (
            ("get", "/api/events"),
            ("post", "/api/orders"),
            ("post", "/api/contact"),
            ("get", "/api/members/me"),
            ("get", "/api/admin/checkin/events"),  # door staff
            ("post", "/api/admin/events"),  # even the owner changes nothing
            ("patch", "/api/admin/settings"),
            ("delete", "/api/admin/events/1"),
            ("post", "/api/admin/tickets/message-buyers"),
        ):
            r = getattr(c, method)(path, headers=_host(slug))
            assert r.status_code == 403 and r.get_json()["code"] == "event_over", (slug, method, path)


def test_in_the_archive_the_owners_admin_area_can_be_read_and_signed_into(server) -> None:
    c = server.test_client()
    headers = _host("archive")
    assert c.get("/api/settings", headers=headers).status_code == 200
    assert c.get("/api/square/config", headers=headers).status_code == 200
    assert c.get("/api/health", headers=headers).status_code == 200
    for path in ("/api/admin/orders", "/api/admin/members", "/api/admin/event-pass", "/api/admin/accounting/events/1/report"):
        r = c.get(path, headers=headers)
        assert r.status_code != 403 or r.get_json().get("code") != "event_over", path  # the guard lets it through; sign-in is the next gate
    assert c.get("/api/auth/me", headers=headers).status_code != 403


def test_live_and_other_squares_are_untouched(server) -> None:
    c = server.test_client()
    for slug in ("live", "normal"):
        assert c.get("/api/events", headers=_host(slug)).status_code == 200
        assert c.post("/api/orders", json={}, headers=_host(slug)).get_json().get("code") != "event_over"


# ---- the routes of the pass (single-tenant app, the tenant patched in) -------------------------------------------------------------------------------
def _pass_tenant(package: str = "event") -> SimpleNamespace:
    return SimpleNamespace(package=package, event_phase="archive", event_live_until=_iso(-5), event_archive_until=_iso(40), name="Gala")


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _get(app, path, headers):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().get(path, headers=headers)


def _post(app, path, headers, body=None):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().post(path, headers=headers, json=body or {})


def _event(title="Gala Night", slug="gala-night") -> Event:
    event = Event(title=title, slug=slug, event_type="festival", start_datetime=NOW)
    db.session.add(event)
    db.session.commit()
    return event


def _paid_order(event: Event, number: int, email: str, status: str = "paid") -> Order:
    order = Order(order_number=f"X-{number:06d}", event_id=event.id, customer_name="Buyer", customer_email=email, total_amount=15000, payment_status=status)
    db.session.add(order)
    db.session.commit()
    return order


def test_the_pass_routes_do_not_exist_on_other_squares() -> None:
    app = _new_app()
    with app.app_context():
        h = _admin()
        with patch("app.event_pass.current_tenant", return_value=_pass_tenant("grove")):
            assert _get(app, "/api/admin/event-pass", h).status_code == 404
            assert _get(app, "/api/admin/event-pass/export", h).status_code == 404
        assert _get(app, "/api/admin/event-pass", h).status_code == 404  # single-tenant: no tenant at all
        db.drop_all()


def test_a_pass_holds_one_event() -> None:
    app = _new_app()
    with app.app_context():
        h = _admin()
        _event()
        with patch("app.event_pass.current_tenant", return_value=_pass_tenant()):
            refused = _post(app, "/api/admin/events", h, {"title": "A second one"})
            assert refused.status_code == 409 and refused.get_json()["code"] == "event_pass_limit"
            copy = _post(app, "/api/admin/events/1/duplicate", h)
            assert copy.status_code == 409 and copy.get_json()["code"] == "event_pass_limit"
        with patch("app.event_pass.current_tenant", return_value=_pass_tenant("grove")):
            assert _post(app, "/api/admin/events", h, {"title": ""}).get_json().get("code") != "event_pass_limit"  # other squares: as before
        assert Event.query.count() == 1
        db.drop_all()


def test_the_summary_lists_the_event_and_what_the_export_holds() -> None:
    app = _new_app()
    with app.app_context():
        h = _admin()
        _event()
        with patch("app.event_pass.current_tenant", return_value=_pass_tenant()):
            body = _get(app, "/api/admin/event-pass", h).get_json()
        assert body["phase"] == "archive" and body["events"] == [{"id": 1, "title": "Gala Night", "slug": "gala-night"}]
        assert any("accounting report" in x.lower() for x in body["export"]) and any("people list" in x.lower() for x in body["export"])
        db.drop_all()


def test_the_export_is_one_zip_with_the_reports_the_lists_and_the_receipts() -> None:
    app = _new_app()
    with app.app_context():
        h = _admin()
        event = _event()
        _paid_order(event, 1, "a@example.com")
        expense = Expense(event_id=event.id, date=NOW.date(), description="Hall hire", category="venue", amount=50000, receipt_key="receipts/hall.jpg")
        db.session.add(expense)
        db.session.commit()
        app.extensions["private_storage"].upload("receipts/hall.jpg", b"JPEGDATA", "image/jpeg")
        with patch("app.event_pass.current_tenant", return_value=_pass_tenant()):
            r = _get(app, "/api/admin/event-pass/export", h)
        assert r.status_code == 200 and r.mimetype == "application/zip" and "gala-night-event-export.zip" in r.headers["Content-Disposition"]
        names = set(zipfile.ZipFile(io.BytesIO(r.data)).namelist())
        assert {"gala-night/accounting-report.pdf", "gala-night/buyers.xlsx", "gala-night/expenses.xlsx", "orders.xlsx", "tickets.xlsx", "people.xlsx", "README.txt"} <= names
        assert any(n.startswith("receipts/expense-") and n.endswith("hall.jpg") for n in names)
        z = zipfile.ZipFile(io.BytesIO(r.data))
        assert z.read("gala-night/accounting-report.pdf")[:4] == b"%PDF"
        readme = z.read("README.txt").decode()
        assert "Keep this file" in readme and "could not be included" not in readme
        db.drop_all()


def test_a_receipt_that_cannot_be_fetched_is_listed_not_hidden() -> None:
    app = _new_app()
    with app.app_context():
        h = _admin()
        event = _event()
        db.session.add(Expense(event_id=event.id, date=NOW.date(), description="Lost", category="venue", amount=100, receipt_key="receipts/gone.jpg"))
        db.session.commit()
        with patch("app.event_pass.current_tenant", return_value=_pass_tenant()):
            r = _get(app, "/api/admin/event-pass/export", h)
        z = zipfile.ZipFile(io.BytesIO(r.data))
        assert "could not be included" in z.read("README.txt").decode() and "gone.jpg" in z.read("README.txt").decode()
        db.drop_all()


# ---- the message to every ticket buyer ----------------------------------------------------------------------------------------------------------
def test_the_message_reaches_each_paid_buyer_once() -> None:
    app = _new_app()
    with app.app_context():
        h = _admin()
        event = _event()
        _paid_order(event, 1, "A@Example.com")
        _paid_order(event, 2, "a@example.com")  # the same person again
        _paid_order(event, 3, "b@example.com")
        _paid_order(event, 4, "never-paid@example.com", status="pending")
        counted = _get(app, f"/api/admin/tickets/buyers/count?event_id={event.id}", h).get_json()
        assert counted["count"] == 2
        r = _post(app, "/api/admin/tickets/message-buyers", h, {"event_id": event.id, "subject": "Doors open at 7", "message": "See you <b>there</b>\nBring your ticket."})
        assert r.status_code == 200 and r.get_json() == {"sent": 2, "failed": 0}
        sent = app.extensions["email_service"].sent_emails
        assert sorted(m["to"] for m in sent) == ["a@example.com", "b@example.com"] and all(m["subject"] == "Doors open at 7" for m in sent)
        assert "&lt;b&gt;" in sent[0]["html"] and "<b>there" not in sent[0]["html"]  # the organiser's text is escaped
        assert "Bring your ticket." in sent[0]["text"]
        db.drop_all()


def test_the_message_checks_its_input_and_the_buyers() -> None:
    app = _new_app()
    with app.app_context():
        h = _admin()
        event = _event()
        bad = _post(app, "/api/admin/tickets/message-buyers", h, {"event_id": event.id, "subject": " ", "message": ""})
        assert bad.status_code == 400 and {"subject", "message"} <= set(bad.get_json()["errors"])
        assert _post(app, "/api/admin/tickets/message-buyers", h, {"event_id": 999, "subject": "x", "message": "y"}).status_code == 400
        none = _post(app, "/api/admin/tickets/message-buyers", h, {"event_id": event.id, "subject": "x", "message": "y"})
        assert none.status_code == 409 and none.get_json()["code"] == "no_buyers"
        assert app.extensions["email_service"].sent_emails == []
        db.drop_all()
