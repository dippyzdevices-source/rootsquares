# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The billing commands: `flask trial-run` (dry run by default) and the setting that switches it on."""

import datetime as dt

from flask import Flask
from sqlalchemy import select

from app.platform.models import Square
from tests.billing.helpers import _set, _square, api  # noqa: F401

PAST = dt.datetime.now(dt.UTC) - dt.timedelta(days=2)


def _enforcing(api: Flask) -> None:
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})


def _state(api: Flask, slug: str) -> tuple[str, str]:
    db = api.extensions["db_factory"]()()
    try:
        sq = db.scalar(select(Square).where(Square.slug == slug))
        return sq.running_plan, sq.sleep_state
    finally:
        db.close()


def _cli(api: Flask, *args: str):
    # the command reads the settings it was registered with, so it is run on the app as set up for the test
    return api.test_cli_runner().invoke(args=["trial-run", *args])


def test_without_enforcing_the_command_says_nothing_is_put_to_sleep(api: Flask) -> None:
    _square(api, "cm1", "roots")
    _set(api, "sq-cm1", PAST)
    out = _cli(api)
    assert out.exit_code == 0 and "0 action(s)" in out.output and "BILLING_ENFORCE is false" in out.output
    assert _state(api, "sq-cm1") == ("live", "awake")


def test_the_command_is_a_dry_run_unless_apply_is_given(api: Flask) -> None:
    from app.main import create_app
    from tests.conftest import make_settings

    app = create_app(make_settings(DATABASE_URL=api.extensions["settings"].DATABASE_URL, BILLING_ENFORCE=True))
    app.extensions["providers"].auth = api.extensions["providers"].auth
    _square(app, "cm2", "roots", country="NO")
    _set(app, "sq-cm2", PAST)
    dry = app.test_cli_runner().invoke(args=["trial-run"])
    assert dry.exit_code == 0 and "would: slug=sq-cm2 action=sleep reason=trial_ended" in dry.output and "dry run" in dry.output
    assert _state(app, "sq-cm2") == ("live", "awake")
    done = app.test_cli_runner().invoke(args=["trial-run", "--apply"])
    assert done.exit_code == 0 and "done: slug=sq-cm2 action=sleep" in done.output
    assert _state(app, "sq-cm2") == ("keep", "sleeping")  # the owner can wake it by paying; nothing was deleted
    again = app.test_cli_runner().invoke(args=["trial-run", "--apply"])
    assert "0 action(s)" in again.output  # already asleep: nothing to do twice


def test_email_test_says_what_is_missing_and_sends_through_the_service(api: Flask) -> None:
    out = api.test_cli_runner().invoke(args=["email-test", "me@example.com"])
    assert out.exit_code != 0 and "EMAIL_PROVIDER is none" in out.output
    sent = []
    api.extensions["providers"].email = type("M", (), {"send": lambda self, to, subject, body, **_kw: sent.append((to, subject))})()
    ok = api.test_cli_runner().invoke(args=["email-test", "me@example.com"])
    assert ok.exit_code == 0 and "sent a test e-mail to me@example.com" in ok.output and sent == [("me@example.com", "rootsquares test e-mail")]
    api.extensions["providers"].email = type("M", (), {"send": lambda self, to, subject, body, **_kw: (_ for _ in ()).throw(RuntimeError("403"))})()
    bad = api.test_cli_runner().invoke(args=["email-test", "me@example.com"])
    assert bad.exit_code != 0 and "refused" in bad.output
