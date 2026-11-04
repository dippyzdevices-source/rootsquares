"""Support access (ADR 089, W23-R64): the rules of a grant, a request and a session, kept apart from the routes so they can be tested on their own.

The owner of a square creates a grant (1 hour, 24 hours or 7 days; the scopes content, settings, health, members; whether staff may change things). Staff open
the square's own admin with a short-lived token signed here (`SUPPORT_SESSION_KEY`); the square server checks the grant again on every request. Nothing in this
module reads a square's data: it holds who, when, for how long and which scopes, never content.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Any

import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.platform.models import Square, SupportGrant, SupportRequest, SupportSession
from app.shared.config import Settings
from app.shared.errors import ConflictError, ForbiddenError, ValidationFailedError

DURATIONS = (60, 1440, 10080)  # minutes: 1 hour, 24 hours, 7 days
SCOPES = ("content", "settings", "health", "members")
CHANGEABLE = ("content", "settings")  # the scopes where a change can be allowed; health is always read only and members are always read only (ADR 089)
SESSION_TTL_MINUTES = 480  # a token lives this long at most, never past the grant; the square server reads the grant on every request
SESSIONS_PER_HOUR = 10  # new sessions per staff member (opening a session that is already open again does not count)
ENDING_SOON_MINUTES = 30  # the "ends soon" mail goes out when a grant has this long left (a 1 hour grant: at once after half of it)
ISSUER, AUDIENCE = "rootsquares-admin", "square-support"


def _aware(t: dt.datetime | None) -> dt.datetime | None:
    if t is not None and t.tzinfo is None:
        return t.replace(tzinfo=dt.UTC)  # SQLite hands back naive times (tests); Postgres hands back aware ones
    return t


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def is_active(grant: SupportGrant, now: dt.datetime | None = None) -> bool:
    now = now or now_utc()
    return grant.revoked_at is None and (_aware(grant.expires_at) or now) > now


def active_grant(db: Session, square_id: uuid.UUID, now: dt.datetime | None = None) -> SupportGrant | None:
    """The one grant of a square that is neither revoked nor over, or None."""
    now = now or now_utc()
    for g in db.scalars(
        select(SupportGrant).where(SupportGrant.square_id == square_id, SupportGrant.revoked_at.is_(None)).order_by(SupportGrant.created_at.desc())
    ):
        if is_active(g, now):
            return g
    return None


def create_grant(
    db: Session, sq: Square, owner_id: uuid.UUID, minutes: int, scopes: list[str], allow_changes: bool, members_confirmed: bool, note: str | None
) -> SupportGrant:
    """The owner's grant. Rules (the same ones are checked again by the square server): one allowed duration; at least one known scope; changes only where they
    can
    be allowed (content and settings); members need the owner's second confirmation; one active grant at a time."""
    if minutes not in DURATIONS:
        raise ValidationFailedError("Duration is not allowed", errors=[{"loc": ["duration_minutes"], "msg": "use 60, 1440 or 10080", "type": "value_error"}])
    if not scopes or len(scopes) != len(set(scopes)) or any(s not in SCOPES for s in scopes):  # an unknown or repeated scope is refused, never silently dropped
        raise ValidationFailedError(
            "Choose at least one part, from the list", errors=[{"loc": ["scopes"], "msg": "unknown, repeated or empty scopes", "type": "value_error"}]
        )
    clean = [s for s in SCOPES if s in set(scopes)]  # in a fixed order
    if not clean:
        raise ValidationFailedError(
            "Choose at least one part, from the list", errors=[{"loc": ["scopes"], "msg": "unknown or empty scopes", "type": "value_error"}]
        )
    if allow_changes and not any(s in CHANGEABLE for s in clean):
        raise ValidationFailedError(
            "Changes can only be allowed for site content and settings",
            errors=[{"loc": ["allow_changes"], "msg": "no changeable part chosen", "type": "value_error"}],
        )
    if "members" in clean and not members_confirmed:
        raise ValidationFailedError(
            "Confirm that staff may see the member list", errors=[{"loc": ["members_confirmed"], "msg": "required for the members part", "type": "value_error"}]
        )
    now = now_utc()
    if active_grant(db, sq.id, now) is not None:
        raise ConflictError("A support grant is already active. Revoke it first.", code="grant_active")
    grant = SupportGrant(
        square_id=sq.id,
        granted_by=owner_id,
        duration_minutes=minutes,
        scopes=clean,
        allow_changes=allow_changes,
        note=(note or "").strip()[:300] or None,
        expires_at=now + dt.timedelta(minutes=minutes),
    )
    db.add(grant)
    db.flush()
    # a request that was waiting is answered by this grant
    for r in db.scalars(select(SupportRequest).where(SupportRequest.square_id == sq.id, SupportRequest.answered_at.is_(None))):
        r.answered_at, r.grant_id = now, grant.id
    return grant


def end_sessions(db: Session, grant: SupportGrant, how: str, now: dt.datetime | None = None) -> int:
    """Close every open session of a grant (the owner revoked it, it ran out, or the staff member ended it)."""
    now = now or now_utc()
    n = 0
    for s in db.scalars(select(SupportSession).where(SupportSession.grant_id == grant.id, SupportSession.ended_at.is_(None))):
        s.ended_at, s.ended_by = now, how
        n += 1
    return n


def revoke_grant(db: Session, grant: SupportGrant) -> None:
    now = now_utc()
    if grant.revoked_at is None:
        grant.revoked_at = now
    end_sessions(db, grant, "revoked", now)


def close_expired(db: Session, now: dt.datetime | None = None) -> int:
    """Close the open sessions of every grant that has run out. Run by `flask support-run` (every few minutes) and whenever grants are read."""
    now = now or now_utc()
    n = 0
    for s in db.scalars(select(SupportSession).where(SupportSession.ended_at.is_(None))):
        g = db.get(SupportGrant, s.grant_id)
        if g is None or not is_active(g, now):
            s.ended_at, s.ended_by = now, "revoked" if g is not None and g.revoked_at is not None else "expired"
            n += 1
    return n


def check_session_rate(db: Session, staff_id: uuid.UUID, now: dt.datetime | None = None) -> None:
    now = now or now_utc()
    since = now - dt.timedelta(hours=1)
    n = db.scalar(select(func.count()).select_from(SupportSession).where(SupportSession.staff_id == staff_id, SupportSession.started_at >= since)) or 0
    if n >= SESSIONS_PER_HOUR:
        raise ForbiddenError("Too many support sessions started in the last hour. Try again later.", code="rate_limited")


def start_session(db: Session, sq: Square, staff_id: uuid.UUID, staff_name: str) -> tuple[SupportSession, SupportGrant, bool]:
    """A staff member opens a session on the square's active grant. Without an active grant nothing opens (403): this is the one gate (ADR 089).
    A staff member who already has an open session on this grant gets it again with a fresh token: nothing new is started, counted, logged or mailed.
    Returns the session, the grant and whether the session is new."""
    grant = active_grant(db, sq.id)
    if grant is None:
        raise ForbiddenError("The owner has not granted support access to this square, or the grant has ended.", code="no_active_grant")
    open_one = db.scalar(
        select(SupportSession)
        .where(SupportSession.grant_id == grant.id, SupportSession.staff_id == staff_id, SupportSession.ended_at.is_(None))
        .order_by(SupportSession.started_at.desc())
        .limit(1)
    )
    if open_one is not None:
        return open_one, grant, False
    check_session_rate(db, staff_id)
    sess = SupportSession(grant_id=grant.id, staff_id=staff_id, staff_name=staff_name[:120])
    db.add(sess)
    db.flush()
    return sess, grant, True


def sign_session(settings: Settings, sess: SupportSession, grant: SupportGrant, sq: Square, now: dt.datetime | None = None) -> tuple[str, dt.datetime]:
    """The token a staff member carries to the square: it names the session, the grant, the square, the scopes and whether changes are allowed. It is short
    lived
    and never enough on its own: the square server reads the grant again on every request. Returns the token and when it ends."""
    now = now or now_utc()
    end = min(now + dt.timedelta(minutes=SESSION_TTL_MINUTES), _aware(grant.expires_at) or now)
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(end.timestamp()),
        "sid": str(sess.id),
        "gid": str(grant.id),
        "sq": str(sq.id),
        "scopes": list(grant.scopes),
        "rw": bool(grant.allow_changes),
        "name": sess.staff_name,
    }
    return jwt.encode(claims, settings.support_session_key, algorithm="HS256"), end


def verify_session(settings: Settings, token: str) -> dict[str, Any]:
    """Used by tests; the square server has its own copy of this check (it shares only the key and the claim names)."""
    return jwt.decode(token, settings.support_session_key, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER)


def ends_soon(grant: SupportGrant, now: dt.datetime | None = None) -> bool:
    now = now or now_utc()
    left = (_aware(grant.expires_at) or now) - now
    return is_active(grant, now) and left <= dt.timedelta(minutes=ENDING_SOON_MINUTES) and grant.ending_notice_at is None


def scope_words(scopes: list[str]) -> str:
    names = {"content": "site content", "settings": "settings and theme", "health": "health and logs", "members": "the member list (read only)"}
    return ", ".join(names[s] for s in scopes if s in names)


def mail_session_started(sq: Square, grant: SupportGrant, staff_name: str, link: str) -> tuple[str, str]:
    mode = "and may make changes" if grant.allow_changes else "read only"
    return (
        f"Support access used on {sq.name}",
        f"{staff_name} from rootsquares support opened {sq.name} with your support access ({scope_words(grant.scopes)}; {mode}). "
        "You can see every use and end the access at any time on the Support access page of your square.\n\n"
        f"{link}",
    )


def mail_ends_soon(sq: Square, grant: SupportGrant, link: str) -> tuple[str, str]:
    return (
        f"Support access to {sq.name} ends soon",
        f"The support access you gave rootsquares for {sq.name} ends in less than {ENDING_SOON_MINUTES} minutes. You do not need to do anything. "
        "You can end it now on the Support access page of your square.\n\n"
        f"{link}",
    )


def mail_requested(sq: Square, staff_name: str, note: str, link: str) -> tuple[str, str]:
    return (
        f"rootsquares support asks for access to {sq.name}",
        f"{staff_name} from rootsquares support asks for time-limited access to {sq.name}. Reason given: {note} "
        "Nothing happens until you allow it: open the Support access page of your square, choose how long and which parts.\n\n"
        f"{link}",
    )


def run(db: Session, now: dt.datetime, notify: Callable[[Square, SupportGrant], bool], apply: bool) -> list[dict[str, str]]:
    """The job of the command support-run (every 10 minutes): close the sessions of grants that ran out, mail the owner once when a grant ends soon.
    A mail that was refused (no e-mail service) is not recorded, so it goes out on a later run. Without the option --apply it only says what it would do."""
    actions: list[dict[str, str]] = []
    for s in db.scalars(select(SupportSession).where(SupportSession.ended_at.is_(None))):
        g = db.get(SupportGrant, s.grant_id)
        if g is None or not is_active(g, now):
            actions.append({"action": "close_session", "session": str(s.id)})
    if apply:
        close_expired(db, now)
    for grant in db.scalars(select(SupportGrant).where(SupportGrant.revoked_at.is_(None), SupportGrant.ending_notice_at.is_(None))):
        if not ends_soon(grant, now):
            continue
        sq = db.get(Square, grant.square_id)
        if sq is None:
            continue
        actions.append({"action": "ends_soon_mail", "grant": str(grant.id), "square": sq.slug})
        if apply and notify(sq, grant):
            grant.ending_notice_at = now
    return actions
