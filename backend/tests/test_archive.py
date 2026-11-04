# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""The archive of an abandoned sleeping square (W13-R48, ADR 059): three reminders (9 months, 11 months, 7 days before), then, only with SLEEP_ARCHIVE_PURGE,
the project is deleted and the row is kept with `archived_at`. A square that is paid for, awake, or an Event pass is never touched."""

import datetime as dt
import uuid

from flask import Flask

from app.platform import archive
from app.platform.models import AuditLog, Square, SquareStatus
from tests.conftest import make_settings
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)

ON = make_settings(BILLING_ENFORCE=True)
PURGE = make_settings(BILLING_ENFORCE=True, SLEEP_ARCHIVE_PURGE=True)
T0 = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.UTC)


def _db(api: Flask):
    return api.extensions["db_factory"]()()


def _asleep(api: Flask, who: str, *, since: dt.datetime = T0, paid_until: dt.datetime | None = None, plan: str = "keep", state: str = "sleeping"):
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": f"Bearer fake:u-{who}:{who}@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": f"Club {who}"}, headers=h).status_code == 201
    sq = c.post(f"{PREFIX}/squares", json={"name": f"Hall {who}", "slug": f"hall-{who}", "theme_id": "paper-brick", "launch_package": "square"}, headers=h).json
    with _db(api) as db:
        row = db.get(Square, uuid.UUID(sq["id"]))
        assert row is not None
        row.status, row.sleep_state, row.running_plan = SquareStatus.READY, state, plan
        row.asleep_since, row.paid_until = since, paid_until
        db.commit()
    return c, h, sq


def _run(api: Flask, now: dt.datetime, settings=ON, sent=None, archived=None):
    sent = sent if sent is not None else []
    archived = archived if archived is not None else []
    with _db(api) as db:
        actions = archive.run(
            db,
            settings,
            now,
            apply=True,
            remind=lambda s, sq, n, on: sent.append((sq.slug, n)) or True,
            archive=lambda s, sq: archived.append(sq.slug),
        )
        db.commit()
    return actions


def _days(n: int) -> dt.datetime:
    return T0 + dt.timedelta(days=n)


def _notices(api: Flask, sq_id: str, ago_days: int) -> None:
    """Pretend all three reminders went out `ago_days` days ago."""
    with _db(api) as db:
        row = db.get(Square, uuid.UUID(sq_id))
        assert row is not None
        for n in (1, 2, 3):
            at = dt.datetime.now(dt.UTC) - dt.timedelta(days=ago_days)
            db.add(AuditLog(action=archive.NOTICE_ACTION, entity="square", entity_id=sq_id, org_id=row.org_id, data={"n": n}, at=at))
        db.commit()


def test_the_thresholds_are_nine_months_eleven_months_and_a_week_before() -> None:
    assert archive.thresholds(ON) == (270, 330, 353)


def test_a_reminder_goes_out_at_each_threshold_one_per_run_and_only_once(api: Flask) -> None:
    _asleep(api, "ar1")
    sent: list = []
    assert _run(api, _days(269), sent=sent) == []
    assert _run(api, _days(270), sent=sent) == [{"slug": "hall-ar1", "action": "reminder", "n": 1}]
    assert _run(api, _days(271), sent=sent) == []  # already told
    assert _run(api, _days(330), sent=sent)[0]["n"] == 2
    assert _run(api, _days(353), sent=sent)[0]["n"] == 3
    assert sent == [("hall-ar1", 1), ("hall-ar1", 2), ("hall-ar1", 3)]


def test_a_missing_email_service_records_nothing_so_the_reminder_is_retried(api: Flask) -> None:
    _asleep(api, "ar2")
    with _db(api) as db:
        archive.run(db, ON, _days(270), apply=True, remind=lambda s, sq, n, on: False)
        db.commit()
    sent: list = []
    assert _run(api, _days(271), sent=sent)[0]["n"] == 1 and sent == [("hall-ar2", 1)]


def test_the_archive_needs_all_three_reminders_a_week_old_and_the_purge_switch(api: Flask) -> None:
    c, h, sq = _asleep(api, "ar3", since=dt.datetime.now(dt.UTC) - dt.timedelta(days=361))
    archived: list = []
    # reminders only three days old: not yet
    _notices(api, sq["id"], 3)
    assert _run(api, dt.datetime.now(dt.UTC), PURGE, archived=archived) == []
    with _db(api) as db:
        for log in db.query(AuditLog).filter(AuditLog.action == archive.NOTICE_ACTION):
            log.at = dt.datetime.now(dt.UTC) - dt.timedelta(days=8)
        db.commit()
    now = dt.datetime.now(dt.UTC)
    off = _run(api, now, ON, archived=archived)  # purge off: reported, not done
    assert off == [{"slug": "hall-ar3", "action": "archive", "enabled": False}] and archived == []
    done = _run(api, now, PURGE, archived=archived)
    assert done[0]["action"] == "archive" and archived == ["hall-ar3"]
    with _db(api) as db:
        row = db.get(Square, uuid.UUID(sq["id"]))
        assert row is not None and row.archived_at is not None
        assert db.query(AuditLog).filter(AuditLog.action == archive.ARCHIVED_ACTION).count() == 1
    assert _run(api, now, PURGE, archived=archived) == []  # an archived square is left alone


def test_without_all_three_reminders_nothing_is_archived(api: Flask) -> None:
    _asleep(api, "ar11", since=dt.datetime.now(dt.UTC) - dt.timedelta(days=500))
    archived: list = []
    actions = _run(api, dt.datetime.now(dt.UTC), PURGE, archived=archived)
    assert actions[0]["action"] == "reminder" and archived == []  # reminder 1 first, the archive is a long way off


def test_a_failed_deletion_is_audited_and_tried_again(api: Flask) -> None:
    c, h, sq = _asleep(api, "ar4", since=dt.datetime.now(dt.UTC) - dt.timedelta(days=400))
    _notices(api, sq["id"], 9)

    def boom(_s, _sq):
        raise RuntimeError("provider down")

    with _db(api) as db:
        archive.run(db, PURGE, apply=True, remind=lambda *a: True, archive=boom)
        db.commit()
    with _db(api) as db:
        row = db.get(Square, uuid.UUID(sq["id"]))
        assert row is not None and row.archived_at is None
        assert db.query(AuditLog).filter(AuditLog.action == archive.FAILED_ACTION).count() == 1


def test_squares_that_are_paid_awake_or_event_passes_are_never_touched(api: Flask) -> None:
    _asleep(api, "ar5", paid_until=dt.datetime.now(dt.UTC) + dt.timedelta(days=20), since=T0)  # a Keep period still paid for
    _asleep(api, "ar6", state="awake")
    _asleep(api, "ar7", plan="event")
    assert _run(api, _days(400)) == []


def test_a_square_paid_up_recently_counts_from_the_end_of_that_paid_time(api: Flask) -> None:
    _asleep(api, "ar8", paid_until=_days(200))
    assert _run(api, _days(400)) == []  # 200 days unpaid, not 400
    assert _run(api, _days(470))[0]["n"] == 1


def test_nothing_happens_without_billing_enforce(api: Flask) -> None:
    _asleep(api, "ar9")
    assert _run(api, _days(400), make_settings(BILLING_ENFORCE=False)) == []


def test_an_archived_square_cannot_be_woken_or_paid_for(api: Flask) -> None:
    c, h, sq = _asleep(api, "ar10")
    with _db(api) as db:
        row = db.get(Square, uuid.UUID(sq["id"]))
        assert row is not None
        row.archived_at = dt.datetime.now(dt.UTC)
        db.commit()
    got = c.get(f"{PREFIX}/squares/{sq['id']}", headers=h).json
    assert got["archived_at"] is not None
    woke = c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "live"}, headers=h)
    assert woke.status_code == 409 and woke.json["code"] == "archived"
    pay = c.post(f"{PREFIX}/squares/{sq['id']}/billing/checkout", json={"kind": "running", "running_plan": "live", "interval": "month"}, headers=h)
    assert pay.status_code == 409 and pay.json["code"] == "archived"


def test_the_notice_text_names_the_date_and_the_square() -> None:
    class S:
        name = "Hall X"

    subject, text = archive.notice_text(S(), 3, dt.datetime(2027, 1, 5, tzinfo=dt.UTC), "https://x.example/billing")  # type: ignore[arg-type]
    assert "05 Jan 2027" in subject and "Hall X" in text and "https://x.example/billing" in text and "deleted for good" in text
