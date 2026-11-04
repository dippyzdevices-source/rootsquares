# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""trial-run: the trial end, the grace days, the day-6 reminder."""

import datetime as dt

from flask import Flask
from sqlalchemy import select

from app.platform import trial
from app.platform.models import Square
from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401


def test_nothing_happens_without_enforcing(api: Flask) -> None:
    _square(api, "tr1", "roots")
    _set(api, "sq-tr1", NOW - dt.timedelta(days=1))
    assert _run(api, enforce=False) == []


def test_an_ended_trial_goes_to_sleep_a_running_one_does_not(api: Flask) -> None:
    _square(api, "tr2", "roots")
    _square(api, "tr3", "square")
    _set(api, "sq-tr2", NOW - dt.timedelta(days=1))
    _set(api, "sq-tr3", NOW + dt.timedelta(days=2))
    assert _run(api) == [{"slug": "sq-tr2", "action": "sleep", "reason": "trial_ended"}]
    slept: list[str] = []
    assert _run(api, apply=True, slept=slept) and slept == ["sq-tr2"]


def test_a_paid_square_gets_the_grace_days(api: Flask) -> None:
    _square(api, "tr4", "grove")
    _set(api, "sq-tr4", NOW - dt.timedelta(days=3), paid_first=True)
    assert _run(api) == []  # 3 days late, grace is 7
    _set(api, "sq-tr4", NOW - dt.timedelta(days=8), paid_first=True)
    assert _run(api) == [{"slug": "sq-tr4", "action": "sleep", "reason": "not_renewed"}]


def test_event_pass_and_old_squares_are_left_alone(api: Flask) -> None:
    _square(api, "tr5", "event")
    _set(api, "sq-tr5", NOW - dt.timedelta(days=30))
    assert _run(api) == []


def test_the_reminder_goes_out_once_in_the_last_day_of_the_trial(api: Flask) -> None:
    _square(api, "rm1", "roots")
    _square(api, "rm2", "square")
    _set(api, "sq-rm1", NOW + dt.timedelta(hours=20))
    _set(api, "sq-rm2", NOW + dt.timedelta(days=3))  # not yet
    assert _run(api) == [{"slug": "sq-rm1", "action": "reminder"}]
    sent: list[str] = []
    settings = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})

    def go(sender):
        db = api.extensions["db_factory"]()()
        try:
            out = trial.run(db, settings, now=NOW, apply=True, remind=sender)
            db.commit()
            return out
        finally:
            db.close()

    assert go(lambda _db, sq: False)  # no e-mail service: tried, not recorded
    assert go(lambda _db, sq: sent.append(sq.slug) or True) and sent == ["sq-rm1"]
    assert go(lambda _db, sq: sent.append(sq.slug) or True) == [] and sent == ["sq-rm1"]  # recorded: never again


def test_the_reminder_text_names_the_trial_end_and_the_price(api: Flask) -> None:
    _square(api, "rm3", "roots")
    _set(api, "sq-rm3", NOW + dt.timedelta(hours=20))
    db = api.extensions["db_factory"]()()
    try:
        sq = db.scalar(select(Square).where(Square.slug == "sq-rm3"))
        subject, body = trial.reminder_text(db, api.extensions["settings"], sq)
    finally:
        db.close()
    assert "Sq rm3" in subject and "21 Oct 2026" in subject
    assert "$149.00" in body and "$25.00" in body and f"/squares/{sq.id}/billing" in body and "Nothing is deleted" in body


def _lapse(api: Flask, notify):
    """One applied pass at NOW in which a lapsed square really goes to sleep (its sleep state changes), with the given notice sender."""
    settings = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})

    def sleep(_db, sq):
        sq.sleep_state = "sleeping"
        sq.running_plan = "keep"

    db = api.extensions["db_factory"]()()
    try:
        out = trial.run(db, settings, now=NOW, apply=True, sleep=sleep, notify=notify)
        db.commit()
        return out
    finally:
        db.close()


def test_the_owner_is_told_once_that_the_square_is_asleep(api: Flask) -> None:
    _square(api, "as1", "roots")
    _set(api, "sq-as1", NOW - dt.timedelta(days=1))
    told: list[tuple[str, str]] = []
    out = _lapse(api, lambda _db, sq, reason: told.append((sq.slug, reason)) or True)
    assert {"slug": "sq-as1", "action": "asleep_notice"} in out and told == [("sq-as1", "trial_ended")]
    again = _lapse(api, lambda _db, sq, reason: told.append((sq.slug, reason)) or True)
    assert again == [] and len(told) == 1  # recorded: never again


def test_a_notice_that_could_not_be_sent_is_tried_again_next_run(api: Flask) -> None:
    _square(api, "as2", "grove")
    _set(api, "sq-as2", NOW - dt.timedelta(days=8), paid_first=True)
    assert [a["action"] for a in _lapse(api, lambda _db, sq, reason: False)] == ["sleep"]  # no e-mail service: slept, not told, not recorded
    told: list[tuple[str, str]] = []
    later = _lapse(api, lambda _db, sq, reason: told.append((sq.slug, reason)) or True)
    assert later == [{"slug": "sq-as2", "action": "asleep_notice"}] and told == [("sq-as2", "not_renewed")]


def test_no_notice_for_a_square_the_owner_has_already_woken(api: Flask) -> None:
    _square(api, "as3", "roots")
    _set(api, "sq-as3", NOW - dt.timedelta(days=1))
    assert [a["action"] for a in _lapse(api, lambda _db, sq, reason: False)] == ["sleep"]
    db = api.extensions["db_factory"]()()
    try:
        sq = db.scalar(select(Square).where(Square.slug == "sq-as3"))
        sq.sleep_state = "awake"  # the owner paid and it woke
        db.commit()
    finally:
        db.close()
    told: list[str] = []
    assert _lapse(api, lambda _db, sq, reason: told.append(sq.slug) or True) == [] and told == []


def test_the_asleep_text_names_the_square_the_reason_and_the_way_back(api: Flask) -> None:
    _square(api, "as4", "roots")
    db = api.extensions["db_factory"]()()
    try:
        sq = db.scalar(select(Square).where(Square.slug == "sq-as4"))
        subject, body = trial.asleep_text(api.extensions["settings"], sq, "trial_ended")
        _, body2 = trial.asleep_text(api.extensions["settings"], sq, "not_renewed")
    finally:
        db.close()
    assert sq.name in subject and "asleep" in subject
    assert "trial" in body and "Nothing has been deleted" in body and f"/squares/{sq.id}/billing" in body
    assert "payment" in body2 and "did not go through" in body2
