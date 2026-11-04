# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""The life of an Event pass (rootsquares W11, ADR 044): 45 days live, 45 days archive, removal at day 90, deletion 14 days later, reminders, the owner's
export confirmation and the upgrade to a launch package plus Live with the $25 credited."""

import datetime as dt
import uuid

from flask import Flask

from app.platform import event_pass, plans
from app.platform.models import AuditLog, Square, SquareStatus
from tests.conftest import make_settings
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)

SETTINGS = make_settings()
T0 = dt.datetime(2026, 11, 1, 12, 0, tzinfo=dt.UTC)


def _pass(api: Flask, who: str, package: str = "event"):
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": f"Bearer fake:u-{who}:{who}@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": f"Club {who}"}, headers=h).status_code == 201
    sq = c.post(f"{PREFIX}/squares", json={"name": f"Gala {who}", "slug": f"gala-{who}", "theme_id": "paper-brick", "launch_package": package}, headers=h).json
    return c, h, sq


def _db(api: Flask):
    return api.extensions["db_factory"]()()


def _start_at(api: Flask, square_id: str, when: dt.datetime = T0) -> None:
    """Move the pass to a known start (the route starts it 'now') and make it ready, so the daily job looks at it."""
    with _db(api) as db:
        sq = db.get(Square, uuid.UUID(square_id))
        assert sq is not None
        event_pass.start(sq, SETTINGS, when)
        sq.status = SquareStatus.READY
        db.commit()


def _row(api: Flask, square_id: str) -> Square:
    with _db(api) as db:
        sq = db.get(Square, uuid.UUID(square_id))
        assert sq is not None
        db.expunge(sq)
        return sq


# ---- creation and phases ----------------------------------------------------------------------------------------------------------------
def test_a_new_pass_starts_its_clock_and_has_the_events_modules(api: Flask) -> None:
    c, h, sq = _pass(api, "ep1")
    assert sq["launch_package"] == "event" and sq["running_plan"] == "event"
    assert set(sq["modules"]) == set(plans.allowed_modules("event"))
    assert (
        "gallery" not in sq["modules"]
        and "memberships" not in sq["modules"]
        and {"members", "volunteering", "checkin", "coupons", "sponsors"} <= set(sq["modules"])
    )
    ep = sq["event_pass"]
    assert ep["phase"] == "live" and ep["days_left"] in (44, 45) and ep["export_confirmed_at"] is None and ep["reminders_sent"] == []
    row = _row(api, sq["id"])
    live, archive, started = row.event_live_until, row.event_archive_until, row.event_started_at
    assert live is not None and archive is not None and started is not None
    assert (live - started).days == 45 and (archive - live).days == 45


def test_other_squares_have_no_event_pass(api: Flask) -> None:
    c, h, sq = _pass(api, "ep2", "square")
    assert sq["event_pass"] is None and event_pass.phase(_row(api, sq["id"])) is None


def test_the_phases_follow_the_days_since_payment(api: Flask) -> None:
    c, h, sq = _pass(api, "ep3")
    _start_at(api, sq["id"])
    row = _row(api, sq["id"])
    day = lambda n: T0 + dt.timedelta(days=n)  # noqa: E731
    assert event_pass.phase(row, day(0)) == "live" and event_pass.phase(row, day(44)) == "live"
    assert event_pass.phase(row, day(45)) == "archive" and event_pass.phase(row, day(89)) == "archive"
    assert event_pass.phase(row, day(90)) == "removed"
    assert event_pass.summary(row, SETTINGS, day(10))["days_left"] == 35
    assert event_pass.summary(row, SETTINGS, day(50))["days_left"] == 40
    assert event_pass.summary(row, SETTINGS, day(95))["purge_at"] == T0 + dt.timedelta(days=90 + 14)


def test_reminders_are_due_on_days_40_60_80_85_and_only_once(api: Flask) -> None:
    c, h, sq = _pass(api, "ep4")
    _start_at(api, sq["id"])
    row = _row(api, sq["id"])
    assert event_pass.due_reminders(row, T0 + dt.timedelta(days=39)) == []
    assert event_pass.due_reminders(row, T0 + dt.timedelta(days=41)) == [40]
    assert event_pass.due_reminders(row, T0 + dt.timedelta(days=86)) == [40, 60, 80, 85]
    with _db(api) as db:
        event_pass.run(db, SETTINGS, T0 + dt.timedelta(days=61), apply=True)
        db.commit()
    row = _row(api, sq["id"])
    assert event_pass.sent_reminders(row) == [40, 60] and event_pass.due_reminders(row, T0 + dt.timedelta(days=61)) == []
    with _db(api) as db:
        assert db.query(AuditLog).filter(AuditLog.action == "event_pass.reminder").count() == 2


# ---- the daily job -----------------------------------------------------------------------------------------------------------------------
def test_a_dry_run_changes_nothing_and_says_what_it_would_do(api: Flask) -> None:
    c, h, sq = _pass(api, "ep5")
    _start_at(api, sq["id"])
    with _db(api) as db:
        actions = event_pass.run(db, SETTINGS, T0 + dt.timedelta(days=91), apply=False)
        db.rollback()
    assert {"slug": "gala-ep5", "action": "remove"} in actions and {"slug": "gala-ep5", "action": "reminder", "day": 85} in actions
    row = _row(api, sq["id"])
    assert row.event_deleted_at is None and row.suspended_at is None and event_pass.sent_reminders(row) == []


def test_at_day_90_the_square_leaves_service_and_14_days_later_it_is_purged_only_when_allowed(api: Flask) -> None:
    c, h, sq = _pass(api, "ep6")
    _start_at(api, sq["id"])
    purged: list[str] = []
    with _db(api) as db:
        event_pass.run(db, SETTINGS, T0 + dt.timedelta(days=90), apply=True)
        db.commit()
    row = _row(api, sq["id"])
    assert row.event_deleted_at is not None and row.suspended_at is not None  # no longer served, still there
    assert event_pass.phase(row, T0 + dt.timedelta(days=100)) == "removed"
    with _db(api) as db:  # 13 days after the removal: nothing yet
        assert not [
            a for a in event_pass.run(db, SETTINGS, T0 + dt.timedelta(days=103), apply=True, purge=lambda s, x: purged.append(x.slug)) if a["action"] == "purge"
        ]
    with _db(api) as db:  # 14 days after, purge switched off (the default): reported, not done
        actions = event_pass.run(db, SETTINGS, T0 + dt.timedelta(days=104), apply=True, purge=lambda s, x: purged.append(x.slug))
        assert [a for a in actions if a["action"] == "purge"] == [{"slug": "gala-ep6", "action": "purge", "enabled": False}] and purged == []
    on = make_settings(EVENT_PASS_PURGE=True)
    with _db(api) as db:
        event_pass.run(db, on, T0 + dt.timedelta(days=104), apply=True, purge=lambda s, x: purged.append(x.slug))
    assert purged == ["gala-ep6"]


def test_the_command_is_a_dry_run_unless_apply_is_given(api: Flask) -> None:
    c, h, sq = _pass(api, "ep7")
    _start_at(api, sq["id"], dt.datetime.now(dt.UTC) - dt.timedelta(days=95))
    runner = api.test_cli_runner()
    dry = runner.invoke(args=["event-pass-run"])
    assert dry.exit_code == 0 and "would: slug=gala-ep7 action=remove" in dry.output and "dry run" in dry.output
    assert _row(api, sq["id"]).event_deleted_at is None
    done = runner.invoke(args=["event-pass-run", "--apply"])
    assert done.exit_code == 0 and "done: slug=gala-ep7 action=remove" in done.output
    assert _row(api, sq["id"]).event_deleted_at is not None


# ---- the owner ------------------------------------------------------------------------------------------------------------------------------
def test_the_owner_confirms_the_export(api: Flask) -> None:
    c, h, sq = _pass(api, "ep8")
    out = c.post(f"{PREFIX}/squares/{sq['id']}/event-pass/confirm-export", headers=h)
    assert out.status_code == 200 and out.json["event_pass"]["export_confirmed_at"] is not None
    other_c, other_h, other = _pass(api, "ep8b", "square")
    assert other_c.post(f"{PREFIX}/squares/{other['id']}/event-pass/confirm-export", headers=other_h).status_code == 409
    assert other_c.post(f"{PREFIX}/squares/{sq['id']}/event-pass/confirm-export", headers=other_h).status_code == 404  # not their square


def test_upgrading_a_pass_credits_the_15_dollars_and_ends_its_lifecycle(api: Flask) -> None:
    c, h, sq = _pass(api, "ep9")
    _start_at(api, sq["id"], dt.datetime.now(dt.UTC) - dt.timedelta(days=60))  # in the archive
    made = c.post(f"{PREFIX}/squares/{sq['id']}/billing/checkout", json={"kind": "event_upgrade", "launch_package": "square", "interval": "month"}, headers=h)
    assert made.status_code == 201
    orders = c.get(f"{PREFIX}/squares/{sq['id']}/billing/orders", headers=h).json["items"]
    assert orders[0]["kind"] == "event_upgrade" and orders[0]["amount_minor"] == 29_900 - 2_500 + 2_500  # package minus the pass plus the first Live month
    assert c.post(f"{PREFIX}/billing/orders/{made.json['order_id']}/fake-confirm", json={"outcome": "paid"}, headers=h).status_code == 200
    row = _row(api, sq["id"])
    assert row.launch_package == "square" and row.running_plan == "live" and row.paid_until is not None
    assert row.event_started_at is None and row.event_live_until is None and row.event_archive_until is None
    assert c.get(f"{PREFIX}/squares", headers=h).json["items"][0]["event_pass"] is None


def test_only_a_running_pass_can_be_upgraded(api: Flask) -> None:
    c, h, sq = _pass(api, "ep10", "square")
    no = c.post(f"{PREFIX}/squares/{sq['id']}/billing/checkout", json={"kind": "event_upgrade", "launch_package": "grove", "interval": "year"}, headers=h)
    assert no.status_code == 409 and no.json["code"] == "not_event_pass"
    c2, h2, sq2 = _pass(api, "ep11")
    _start_at(api, sq2["id"], dt.datetime.now(dt.UTC) - dt.timedelta(days=120))  # already past the end
    gone = c2.post(f"{PREFIX}/squares/{sq2['id']}/billing/checkout", json={"kind": "event_upgrade", "launch_package": "grove", "interval": "year"}, headers=h2)
    assert gone.status_code == 409
    bad = c2.post(f"{PREFIX}/squares/{sq2['id']}/billing/checkout", json={"kind": "event_upgrade", "launch_package": "event", "interval": "month"}, headers=h2)
    assert bad.status_code in (400, 409, 422)
