"""A square that sleeps (rootsquares W10-R41, W10-R44): a true sleep. Its project may be paused, so the server touches no square data: only the config (with the
copied public contact details), the health and the platform's internal calls answer; everything else is 503. Jobs skip it."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text

from app import create_app
from app.config import TestingConfig
from app.jobs.squares import for_each_square
from tests.test_tenancy import _enc, _square_db

KEY = "test-internal-key"
CONTACT = {"contact_email": "hello@club.example", "contact_phone": "+47 123 45 678", "contact_address": "Torget 1, Oslo"}


@pytest.fixture
def server(tmp_path: Path):
    url = _square_db(tmp_path / "s.db", "s@example.org")
    platform_url = f"sqlite:///{tmp_path / 'platform.db'}"
    platform = create_engine(platform_url)
    with platform.begin() as conn:
        conn.execute(
            text(
                "create table squares (slug text, name text, theme_id text, domain text, status text, suspended_at text, "
                "db_connection text, provider_secrets text, currency text, phone_country text, logo_url text, logo_dark_url text, modules text, "
                "running_plan text, sleep_state text, sleep_contact text)"
            )
        )
        for slug, plan, state, contact in (
            ("awake", "live", "awake", None),
            ("asleep", "keep", "sleeping", json.dumps(CONTACT)),
            ("waking", "live", "waking", json.dumps(CONTACT)),  # the project is starting again: still asleep for visitors
        ):
            conn.execute(
                text("insert into squares values (:slug, :name, 'paper-brick', :domain, 'ready', null, :url, :sec, 'NOK', 'NO', null, null, null, :plan, :state, :contact)"),
                {"slug": slug, "name": slug, "domain": f"{slug}.rootsquares.com", "url": _enc(url), "sec": _enc(json.dumps({})), "plan": plan, "state": state, "contact": contact},
            )
    platform.dispose()
    with patch.object(TestingConfig, "PLATFORM_DATABASE_URL", platform_url), patch.object(TestingConfig, "PLATFORM_INTERNAL_KEY", KEY):
        return create_app("testing")


def _host(slug: str) -> dict[str, str]:
    return {"Host": f"{slug}.rootsquares.com"}


def test_the_config_says_whether_the_square_sleeps_and_carries_the_contact_copy(server) -> None:
    c = server.test_client()
    asleep = c.get("/api/square/config", headers=_host("asleep")).get_json()
    assert asleep["sleeping"] is True and asleep["sleep_contact"] == CONTACT
    assert c.get("/api/square/config", headers=_host("waking")).get_json()["sleeping"] is True
    awake = c.get("/api/square/config", headers=_host("awake")).get_json()
    assert awake["sleeping"] is False and awake["sleep_contact"] == {}


def test_a_sleeping_square_answers_nothing_that_needs_its_data(server) -> None:
    c = server.test_client()
    for slug in ("asleep", "waking"):
        for method, path in (("get", "/api/settings"), ("get", "/api/events"), ("get", "/api/admin/settings"), ("post", "/api/auth/me"), ("post", "/api/orders"), ("post", "/api/contact"), ("post", "/api/webhooks/vipps")):
            r = getattr(c, method)(path, headers=_host(slug))
            assert r.status_code == 503 and r.get_json()["code"] == "sleeping", (slug, method, path)
    assert c.get("/api/settings", headers=_host("awake")).status_code == 200  # an awake square is untouched
    assert c.post("/api/orders", json={}, headers=_host("awake")).status_code != 503


def test_the_server_health_and_the_platforms_internal_calls_still_answer(server) -> None:
    c = server.test_client()
    assert c.get("/api/health", headers=_host("asleep")).status_code == 200
    health = c.get("/api/internal/health", headers={**_host("asleep"), "X-Internal-Key": KEY}).get_json()
    assert [x["key"] for x in health["checks"]] == ["sleeping"]  # nothing of the square is read
    assert c.get("/api/internal/modules/status", headers={**_host("asleep"), "X-Internal-Key": KEY}).get_json() == {"items": []}
    assert c.get("/api/internal/health", headers=_host("asleep")).status_code == 404  # still needs the key


def test_the_snapshot_is_the_public_contact_and_nothing_else(server) -> None:
    body = server.test_client().get("/api/internal/sleep-snapshot", headers={**_host("awake"), "X-Internal-Key": KEY}).get_json()
    assert set(body) == {"contact_email", "contact_phone", "contact_address"} and body["contact_email"] == "s@example.org"
    assert server.test_client().get("/api/internal/sleep-snapshot", headers=_host("awake")).status_code == 404


def test_jobs_skip_a_sleeping_square(server) -> None:
    seen: list[str] = []

    def work() -> int:
        from flask import g

        seen.append(g.tenant.slug)
        return 1

    for_each_square(server, work)
    assert seen == ["awake"]
