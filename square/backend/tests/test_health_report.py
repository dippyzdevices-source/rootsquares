"""The owner's health report (rootsquares W10-R19): protected, states and sentences only."""

from app.jobs import heartbeat
from tests.test_module_status import KEY, _app


def _get(app):
    return app.test_client().get("/api/internal/health", headers={"X-Internal-Key": KEY})


def test_health_needs_the_key() -> None:
    c = _app().test_client()
    assert c.get("/api/internal/health").status_code == 404
    assert c.get("/api/internal/health", headers={"X-Internal-Key": "wrong"}).status_code == 404


def test_health_has_states_and_sentences_only() -> None:
    body = _get(_app()).get_json()
    assert {"version", "checks"} <= set(body)
    for c in body["checks"]:
        assert set(c) == {"key", "group", "state", "text"}
        assert c["state"] in {"ok", "warn", "fail", "off"}
    assert any(c["key"] == "database" and c["state"] == "ok" for c in body["checks"])


def test_a_failed_job_run_shows_as_failing() -> None:
    heartbeat.record("messages", False)
    try:
        checks = {c["key"]: c for c in _get(_app()).get_json()["checks"]}
        assert checks["job_messages"]["state"] == "fail"
    finally:
        heartbeat.record("messages", True)
