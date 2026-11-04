"""Background jobs run for every square, each with its own database (rootsquares W6-R44)."""

import pytest

from app.common.urls import frontend_base_url
from app.jobs.squares import for_each_square, run_everywhere
from app.jobs.vipps_sweep import run_sweep
from app.tenancy import current_tenant
from tests.test_tenancy import server  # noqa: F401  (the fixture: a fake platform database with squares A and B, C not ready, D suspended)


def test_every_ready_square_is_visited_once_with_its_own_context(server):
    app, _ = server
    seen = []

    def work():
        seen.append((current_tenant().slug, frontend_base_url()))  # a background job: no request, so the square's own domain
        return current_tenant().slug

    assert sorted(for_each_square(app, work)) == ["square-a", "square-b"]  # not the provisioning one, not the suspended one
    assert sorted(seen) == [("square-a", "https://square-a.rootsquares.com"), ("square-b", "https://club-b.example.org")]


def test_one_squares_failure_does_not_stop_the_others(server, caplog):
    app, _ = server

    def work():
        if current_tenant().slug == "square-a":
            raise RuntimeError("boom")
        return 7

    assert for_each_square(app, work) == [7]
    assert "Job failed for square square-a" in caplog.text


def test_the_vipps_job_totals_its_work_over_all_squares(server, monkeypatch):
    app, _ = server
    monkeypatch.setattr("app.payments.vipps.sweep_initiated_payments", lambda: 3)
    assert run_sweep(app) == 6


def test_without_many_squares_the_jobs_run_once_in_the_single_database():
    from app import create_app

    app = create_app("testing")
    assert run_everywhere(app, lambda: 5) == 5
    with pytest.raises(RuntimeError, match="many-squares"):
        for_each_square(app, lambda: 1)
