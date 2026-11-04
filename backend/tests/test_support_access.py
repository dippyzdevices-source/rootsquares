# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""Support access (ADR 089, W23-R64): the owner's grant, the staff request and session, the token, expiry, revoke, the audit and the mails. SQLite."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import jwt
import pytest
from flask import Flask

from app.platform import support
from app.platform.models import AuditLog, SupportGrant, SupportSession
from tests.staff_client import ADMIN, STAFF_HEADERS, staff_client
from tests.test_auth_storage import HEADERS, PREFIX, api  # noqa: F401  (api: the app fixture)
from tests.test_square_module_status import _square


class Mailbox:
    """A recording e-mail provider: the platform sends the owner a mail when a request comes in, a session starts or a grant ends soon."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str, **_: Any) -> None:
        self.sent.append((to, subject, body))


def _setup(api: Flask) -> tuple[Any, dict[str, str], dict[str, Any], Any, Mailbox]:
    box = Mailbox()
    api.extensions["providers"].email = box
    c, h, sq = _square(api)
    return c, h, sq, staff_client(api), box


def _grant(c: Any, h: dict[str, str], sq: dict[str, Any], **over: Any) -> Any:
    body = {"duration_minutes": 60, "scopes": ["content", "settings"], "allow_changes": False, "members_confirmed": False, **over}
    return c.post(f"{PREFIX}/squares/{sq['id']}/support/grants", json=body, headers=h)


def _start(s: Any, sq: dict[str, Any]) -> Any:
    return s.post(f"{ADMIN}/support/squares/{sq['id']}/session", headers=STAFF_HEADERS)


def _actions(api: Flask) -> list[str]:
    with api.extensions["db_factory"]()() as db:
        return [a.action for a in db.query(AuditLog).filter(AuditLog.action.like("support.%")).order_by(AuditLog.at)]


# ---- the owner's grant -------------------------------------------------------------------------------------------------------------------
def test_the_page_starts_empty_and_the_owner_can_manage(api: Flask) -> None:
    c, h, sq, _, _ = _setup(api)
    body = c.get(f"{PREFIX}/squares/{sq['id']}/support", headers=h).json
    assert body == {"grant": None, "requests": [], "can_manage": True}
    assert c.get(f"{PREFIX}/squares/{sq['id']}/support/activity", headers=h).json == {"items": [], "page": 1, "per_page": 15, "total": 0}


@pytest.mark.parametrize(
    "over",
    [
        {"duration_minutes": 30},  # not one of 1 hour, 24 hours, 7 days
        {"scopes": ["billing"]},  # not a scope that exists
        {"scopes": ["content", "content"]},  # twice
        {"allow_changes": True, "scopes": ["health"]},  # nothing there can be changed
        {"allow_changes": True, "scopes": ["members"], "members_confirmed": True},  # members stay read only
        {"scopes": ["members"], "members_confirmed": False},  # the second confirmation is missing
    ],
)
def test_a_grant_that_breaks_a_rule_is_refused(api: Flask, over: dict[str, Any]) -> None:
    c, h, sq, _, _ = _setup(api)
    assert _grant(c, h, sq, **over).status_code == 422
    assert c.get(f"{PREFIX}/squares/{sq['id']}/support", headers=h).json["grant"] is None


def test_a_grant_is_created_once_and_shown_with_its_scopes_in_a_fixed_order(api: Flask) -> None:
    c, h, sq, _, _ = _setup(api)
    r = _grant(c, h, sq, duration_minutes=1440, scopes=["settings", "members", "content"], members_confirmed=True, allow_changes=True, note="  call at 14:00  ")
    assert r.status_code == 201
    assert r.json["scopes"] == ["content", "settings", "members"] and r.json["allow_changes"] is True and r.json["note"] == "call at 14:00"
    assert _grant(c, h, sq).status_code == 409  # one active grant at a time
    state = c.get(f"{PREFIX}/squares/{sq['id']}/support", headers=h).json
    assert state["grant"]["id"] == r.json["id"]
    assert [a["action"] for a in c.get(f"{PREFIX}/squares/{sq['id']}/support/activity", headers=h).json["items"]] == ["support.grant"]


def test_somebody_else_sees_nothing_and_cannot_grant(api: Flask) -> None:
    c, h, sq, _, _ = _setup(api)
    other = {**HEADERS, "Authorization": "Bearer fake:u-oth3:oth3@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": "Other club"}, headers=other).status_code == 201
    assert c.get(f"{PREFIX}/squares/{sq['id']}/support", headers=other).status_code == 404
    assert _grant(c, other, sq).status_code == 404
    assert c.post(f"{PREFIX}/squares/{sq['id']}/support/revoke", headers=other).status_code == 404


# ---- the staff side ----------------------------------------------------------------------------------------------------------------------
def test_staff_routes_do_not_exist_on_the_customer_api(api: Flask) -> None:
    c, h, sq, _, _ = _setup(api)
    assert c.get(f"{PREFIX}/support/overview", headers=h).status_code == 404
    assert c.post(f"{PREFIX}/support/squares/{sq['id']}/session", headers=h).status_code == 404


def test_without_a_grant_no_session_opens_and_the_try_is_audited(api: Flask) -> None:
    c, h, sq, s, _ = _setup(api)
    r = _start(s, sq)
    assert r.status_code == 403 and r.json["code"] == "no_active_grant"
    assert _actions(api) == ["support.denied"]


def test_a_session_opens_on_a_grant_with_a_token_that_names_the_limits(api: Flask) -> None:
    c, h, sq, s, box = _setup(api)
    assert _grant(c, h, sq, scopes=["content", "health"]).status_code == 201
    r = _start(s, sq)
    assert r.status_code == 201
    claims = jwt.decode(r.json["token"], api.extensions["settings"].support_session_key, algorithms=["HS256"], audience=support.AUDIENCE, issuer=support.ISSUER)
    assert claims["sq"] == sq["id"] and claims["scopes"] == ["content", "health"] and claims["rw"] is False and claims["sid"] == r.json["session_id"]
    assert claims["exp"] - claims["iat"] <= support.SESSION_TTL_MINUTES * 60  # short lived
    assert r.json["scopes"] == ["content", "health"] and r.json["domain"] == sq["domain"]
    assert [m[1] for m in box.sent] == ["Support access used on First"]  # the owner is told
    assert "read only" in box.sent[0][2]
    assert _actions(api) == ["support.grant", "support.session_start"]


def test_a_token_is_not_valid_with_another_key(api: Flask) -> None:
    c, h, sq, s, _ = _setup(api)
    _grant(c, h, sq)
    token = _start(s, sq).json["token"]
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "another-key-another-key-another-key", algorithms=["HS256"], audience=support.AUDIENCE, issuer=support.ISSUER)


def test_the_token_never_outlives_the_grant(api: Flask) -> None:
    c, h, sq, s, _ = _setup(api)
    _grant(c, h, sq)
    with api.extensions["db_factory"]()() as db:  # the grant has 5 minutes left
        g = db.query(SupportGrant).one()
        g.expires_at = support.now_utc() + dt.timedelta(minutes=5)
        db.commit()
    r = _start(s, sq).json
    assert dt.datetime.fromisoformat(r["token_expires_at"]) <= dt.datetime.fromisoformat(r["grant_expires_at"])


def test_revoking_ends_the_running_session_and_nothing_renews(api: Flask) -> None:
    c, h, sq, s, _ = _setup(api)
    _grant(c, h, sq)
    sid = _start(s, sq).json["session_id"]
    assert s.post(f"{ADMIN}/support/sessions/{sid}/renew", headers=STAFF_HEADERS).status_code == 200
    state = c.post(f"{PREFIX}/squares/{sq['id']}/support/revoke", headers=h)
    assert state.status_code == 200 and state.json["grant"] is None
    assert s.post(f"{ADMIN}/support/sessions/{sid}/renew", headers=STAFF_HEADERS).status_code == 404  # the session is closed
    assert _start(s, sq).status_code == 403
    with api.extensions["db_factory"]()() as db:
        row = db.query(SupportSession).one()
        assert row.ended_by == "revoked"
    assert _actions(api) == ["support.grant", "support.session_start", "support.revoke", "support.session_end", "support.denied"]
    assert c.post(f"{PREFIX}/squares/{sq['id']}/support/revoke", headers=h).status_code == 404  # nothing left to revoke


def test_an_expired_grant_opens_nothing_and_closes_its_sessions(api: Flask) -> None:
    c, h, sq, s, _ = _setup(api)
    _grant(c, h, sq)
    sid = _start(s, sq).json["session_id"]
    with api.extensions["db_factory"]()() as db:
        db.query(SupportGrant).one().expires_at = support.now_utc() - dt.timedelta(minutes=1)
        db.commit()
    assert s.post(f"{ADMIN}/support/sessions/{sid}/renew", headers=STAFF_HEADERS).status_code == 403
    assert _start(s, sq).status_code == 403
    state = c.get(f"{PREFIX}/squares/{sq['id']}/support", headers=h).json
    assert state["grant"] is None
    with api.extensions["db_factory"]()() as db:
        assert db.query(SupportSession).one().ended_by == "expired"


def test_a_staff_member_ends_their_own_session_only(api: Flask) -> None:
    c, h, sq, s, _ = _setup(api)
    _grant(c, h, sq)
    sid = _start(s, sq).json["session_id"]
    other = staff_client(api)
    assert other.post(f"{ADMIN}/support/sessions/{sid}/end", headers=STAFF_HEADERS).status_code == 404
    assert s.post(f"{ADMIN}/support/sessions/{sid}/end", headers=STAFF_HEADERS).json["ended_by"] == "staff"


def test_opening_again_gives_the_same_session_a_fresh_token_and_starts_nothing_new(api: Flask) -> None:
    c, h, sq, s, box = _setup(api)
    _grant(c, h, sq)
    first = _start(s, sq).json
    again = _start(s, sq).json
    assert again["session_id"] == first["session_id"]  # the same session
    assert len(box.sent) == 1 and _actions(api) == ["support.grant", "support.session_start"]  # one mail, one log line
    with api.extensions["db_factory"]()() as db:
        assert db.query(SupportSession).count() == 1


def test_at_most_ten_new_sessions_an_hour_for_one_staff_member(api: Flask) -> None:
    c, h, sq, s, _ = _setup(api)
    _grant(c, h, sq)
    codes = []
    for _ in range(support.SESSIONS_PER_HOUR):
        r = _start(s, sq)
        codes.append(r.status_code)
        s.post(f"{ADMIN}/support/sessions/{r.json['session_id']}/end", headers=STAFF_HEADERS)  # ended, so the next start is a new session
    assert codes == [201] * support.SESSIONS_PER_HOUR
    r = _start(s, sq)
    assert r.status_code == 403 and r.json["code"] == "rate_limited"


# ---- requests ----------------------------------------------------------------------------------------------------------------------------
def test_a_request_reaches_the_owner_and_is_answered_by_a_grant(api: Flask) -> None:
    c, h, sq, s, box = _setup(api)
    r = s.post(f"{ADMIN}/support/squares/{sq['id']}/request", json={"note": "The ticket page shows an error"}, headers=STAFF_HEADERS)
    assert r.status_code == 201
    assert s.post(f"{ADMIN}/support/squares/{sq['id']}/request", json={"note": "Again please"}, headers=STAFF_HEADERS).status_code == 409
    assert "asks for access" in box.sent[0][1] and "The ticket page shows an error" in box.sent[0][2]
    state = c.get(f"{PREFIX}/squares/{sq['id']}/support", headers=h).json
    assert [x["note"] for x in state["requests"]] == ["The ticket page shows an error"] and state["requests"][0]["answered_at"] is None
    _grant(c, h, sq)
    assert c.get(f"{PREFIX}/squares/{sq['id']}/support", headers=h).json["requests"][0]["answered_at"] is not None
    assert s.post(f"{ADMIN}/support/squares/{sq['id']}/request", json={"note": "More access"}, headers=STAFF_HEADERS).status_code == 409  # already granted


def test_staff_see_the_overview_without_the_owners_note(api: Flask) -> None:
    c, h, sq, s, _ = _setup(api)
    _grant(c, h, sq, note="private words")
    over = s.get(f"{ADMIN}/support/overview", headers=STAFF_HEADERS).json
    assert [(r["square_name"], r["scopes"]) for r in over["active"]] == [("First", ["content", "settings"])]
    assert "private words" not in str(over) and "private words" not in str(s.get(f"{ADMIN}/support/squares/{sq['id']}", headers=STAFF_HEADERS).json)


# ---- the ends-soon rule ------------------------------------------------------------------------------------------------------------------
def test_ends_soon_is_true_once_only_in_the_last_half_hour() -> None:
    now = support.now_utc()
    g = SupportGrant(duration_minutes=60, scopes=["content"], expires_at=now + dt.timedelta(minutes=29))
    assert support.ends_soon(g, now) is True
    g.ending_notice_at = now
    assert support.ends_soon(g, now) is False
    assert support.ends_soon(SupportGrant(duration_minutes=60, scopes=["content"], expires_at=now + dt.timedelta(hours=2)), now) is False
    assert support.ends_soon(SupportGrant(duration_minutes=60, scopes=["content"], expires_at=now - dt.timedelta(minutes=1)), now) is False  # already over


# ---- the job `support-run` ---------------------------------------------------------------------------------------------------------------
def test_the_job_mails_the_owner_once_when_a_grant_ends_soon_and_closes_old_sessions(api: Flask) -> None:
    c, h, sq, s, _ = _setup(api)
    _grant(c, h, sq)
    sid = _start(s, sq).json["session_id"]
    told: list[str] = []
    with api.extensions["db_factory"]()() as db:
        db.query(SupportGrant).one().expires_at = support.now_utc() + dt.timedelta(minutes=20)
        db.commit()
        now = support.now_utc()
        dry = support.run(db, now, lambda sq_, g_: told.append(sq_.slug) or True, apply=False)
        assert [a["action"] for a in dry] == ["ends_soon_mail"] and told == []  # a dry run changes and sends nothing
        done = support.run(db, now, lambda sq_, g_: told.append(sq_.slug) or True, apply=True)
        db.commit()
        assert [a["action"] for a in done] == ["ends_soon_mail"] and told == [sq["slug"]]
        assert support.run(db, now, lambda sq_, g_: told.append("again") or True, apply=True) == [] and told == [sq["slug"]]  # once per grant
        db.query(SupportGrant).one().expires_at = now - dt.timedelta(minutes=1)
        db.commit()
        closing = support.run(db, now, lambda sq_, g_: True, apply=True)
        db.commit()
        assert [a["action"] for a in closing] == ["close_session"] and closing[0]["session"] == sid
        assert db.query(SupportSession).one().ended_by == "expired"


def test_a_refused_mail_is_tried_again_on_the_next_run(api: Flask) -> None:
    c, h, sq, _, _ = _setup(api)
    _grant(c, h, sq)
    with api.extensions["db_factory"]()() as db:
        db.query(SupportGrant).one().expires_at = support.now_utc() + dt.timedelta(minutes=10)
        db.commit()
        now = support.now_utc()
        support.run(db, now, lambda sq_, g_: False, apply=True)  # no e-mail service: not recorded
        assert db.query(SupportGrant).one().ending_notice_at is None
        assert [a["action"] for a in support.run(db, now, lambda sq_, g_: True, apply=True)] == ["ends_soon_mail"]
        assert db.query(SupportGrant).one().ending_notice_at is not None


# ---- the Activity tab: a page of fifteen -------------------------------------------------------------------------------------------------
def test_the_activity_log_is_paged_fifteen_at_a_time_newest_first_and_only_for_this_square(api: Flask) -> None:
    c, h, sq, _, _ = _setup(api)
    for _ in range(11):  # 11 grants and 11 revokes = 22 rows
        assert _grant(c, h, sq).status_code == 201
        assert c.post(f"{PREFIX}/squares/{sq['id']}/support/revoke", headers=h).status_code == 200
    url = f"{PREFIX}/squares/{sq['id']}/support/activity"
    first = c.get(url, headers=h).json
    assert first["total"] == 22 and first["page"] == 1 and first["per_page"] == 15 and len(first["items"]) == 15
    second = c.get(url + "?page=2", headers=h).json
    assert len(second["items"]) == 7
    times = [a["at"] for a in first["items"] + second["items"]]
    assert times == sorted(times, reverse=True)  # newest first (SQLite times have whole seconds, so the order inside one second is not asserted)
    assert sorted(a["action"] for a in first["items"] + second["items"]) == ["support.grant"] * 11 + ["support.revoke"] * 11
    assert c.get(url + "?page=3", headers=h).json["items"] == []  # past the end: an empty page, not an error
    assert len(c.get(url + "?per_page=5&page=5", headers=h).json["items"]) == 2
    assert c.get(url + "?page=x", headers=h).status_code == 422
    other = {**HEADERS, "Authorization": "Bearer fake:u-oth4:oth4@example.com"}  # another organisation gets nothing
    assert c.post(f"{PREFIX}/organizations", json={"name": "Other club"}, headers=other).status_code == 201
    assert c.get(url, headers=other).status_code == 404


def test_the_log_names_who_of_the_owners_allowed_or_ended_access_and_marks_your_own(api: Flask) -> None:
    """A square can have more than one person who may manage it: each line says who, and "by you" for the person who is looking."""
    from app.platform.models import Membership, MembershipRole, User

    c, h, sq, s, _ = _setup(api)
    second = {**HEADERS, "Authorization": "Bearer fake:u-two:two@example.com"}
    assert c.get(f"{PREFIX}/squares", headers=second).status_code == 200  # the second person signs in for the first time
    with api.extensions["db_factory"]()() as db:
        user = db.query(User).filter_by(email="two@example.com").one()
        user.name = "Siv Aasen"
        db.add(Membership(org_id=uuid.UUID(sq["org_id"]), user_id=user.id, role=MembershipRole.OWNER))
        db.commit()
    assert _grant(c, h, sq).status_code == 201  # the first owner allows access
    sid = _start(s, sq).json["session_id"]  # staff come in
    assert c.post(f"{PREFIX}/squares/{sq['id']}/support/revoke", headers=second).status_code == 200  # the second owner ends it
    url = f"{PREFIX}/squares/{sq['id']}/support/activity"
    by_first = {(a["action"], a["who"]): a["by_you"] for a in c.get(url, headers=h).json["items"]}
    assert by_first[("support.grant", "ms@example.com")] is True  # the first owner sees their own allowing as theirs
    assert by_first[("support.revoke", "Siv Aasen")] is False  # and the other owner's ending with their name
    by_second = {(a["action"], a["who"]): a["by_you"] for a in c.get(url, headers=second).json["items"]}
    assert by_second[("support.revoke", "Siv Aasen")] is True and by_second[("support.grant", "ms@example.com")] is False
    staff_lines = [a for a in c.get(url, headers=h).json["items"] if a["action"] in ("support.session_start", "support.session_end")]
    assert staff_lines and all(a["who"] == "Test staff" and a["by_you"] is False for a in staff_lines)
    assert sid
