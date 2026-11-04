"""Staff identity (ADR 083, stage 1): the people who run rootsquares are their own accounts, not customer accounts with a flag.

What it does: creates staff, checks the password, and the second step (a TOTP code or a recovery code, RFC 6238 with the standard library: no new
dependency). Nothing here knows about HTTP; the staff API (stage 2) and the command line (`flask staff-*`) call it.
Secrets: the TOTP secret is stored Fernet-encrypted, recovery codes only as argon2 hashes; plain values are returned once and never logged.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.platform.models import AuditLog, StaffSession, StaffUser
from app.shared.crypto import DUMMY_HASH, Encryptor, hash_password, verify_password

TOTP_STEP = 30  # seconds
TOTP_DIGITS = 6
TOTP_WINDOW = 1  # one step either side, for a clock a little off
RECOVERY_CODES = 8
MIN_PASSWORD = 12  # staff passwords are longer than the customers' 10
LOCK_AFTER = 8  # wrong passwords in a row, then the account is locked...
LOCK_MINUTES = 15  # ...for this long (a right password after that starts the count again)
MAX_SECOND_STEP_FAILURES = 5  # wrong codes in one login, then that login ends and the password is asked again
ISSUER = "rootsquares admin"


class StaffError(ValueError):
    """A rule of the staff model was broken (the message is for the person at the command line or the admin screen)."""


def normalise_email(email: str) -> str:
    return email.strip().lower()


# ---- TOTP (RFC 6238, HMAC-SHA1, 30 s, 6 digits: what every authenticator app does) ---------------------------------------------------------


def new_secret() -> str:
    """A fresh base32 secret (160 bits)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**TOTP_DIGITS)
    return str(value).zfill(TOTP_DIGITS)


def totp_code(secret: str, at: float | None = None) -> str:
    return _hotp(secret, int((time.time() if at is None else at) // TOTP_STEP))


def matching_step(secret: str, code: str, at: float | None = None) -> int | None:
    """The time step the code belongs to (within the window), or None. Constant-time compare on every step."""
    code = code.strip().replace(" ", "")
    if len(code) != TOTP_DIGITS or not code.isdigit():
        return None
    now = int((time.time() if at is None else at) // TOTP_STEP)
    found: int | None = None
    for step in range(now - TOTP_WINDOW, now + TOTP_WINDOW + 1):
        if hmac.compare_digest(_hotp(secret, step), code):
            found = step
    return found


def otpauth_uri(email: str, secret: str) -> str:
    """The address an authenticator app reads from a QR code."""
    return f"otpauth://totp/{quote(ISSUER)}:{quote(email)}?secret={secret}&issuer={quote(ISSUER)}&digits={TOTP_DIGITS}&period={TOTP_STEP}"


# ---- accounts ------------------------------------------------------------------------------------------------------------------------------


def get_staff(db: Session, email: str) -> StaffUser | None:
    return db.scalar(select(StaffUser).where(StaffUser.email == normalise_email(email)))


def create_staff(db: Session, email: str, password: str, name: str = "") -> StaffUser:
    email = normalise_email(email)
    if "@" not in email or len(email) > 320:
        raise StaffError("That is not an e-mail address.")
    if len(password) < MIN_PASSWORD:
        raise StaffError(f"The password needs at least {MIN_PASSWORD} characters.")
    if get_staff(db, email) is not None:
        raise StaffError("A staff member with this e-mail address exists already.")
    staff = StaffUser(email=email, name=name.strip(), password_hash=hash_password(password))
    db.add(staff)
    db.flush()
    db.add(AuditLog(action="staff.created", entity="staff", entity_id=str(staff.id), data={}))
    return staff


def set_password(db: Session, staff: StaffUser, password: str) -> None:
    """A new password ends every login of this person."""
    if len(password) < MIN_PASSWORD:
        raise StaffError(f"The password needs at least {MIN_PASSWORD} characters.")
    staff.password_hash = hash_password(password)
    revoke_sessions(db, staff)


def check_password(db: Session, email: str, password: str, at: dt.datetime | None = None) -> StaffUser | None:
    """The staff member when the password is right, the account is active and not locked; None otherwise (the caller says the same thing for every reason).
    Takes about the same time either way. LOCK_AFTER wrong passwords in a row lock the account for LOCK_MINUTES, whoever tries;
    a right password resets the count."""
    t = at or dt.datetime.now(dt.UTC)
    staff = get_staff(db, email)
    ok = verify_password(staff.password_hash if staff else DUMMY_HASH, password)
    if staff is None:
        return None
    if staff.locked_until is not None and staff.locked_until.replace(tzinfo=staff.locked_until.tzinfo or dt.UTC) > t:
        return None
    if not ok:
        staff.failed_attempts += 1
        if staff.failed_attempts >= LOCK_AFTER:
            staff.locked_until = t + dt.timedelta(minutes=LOCK_MINUTES)
            staff.failed_attempts = 0
            db.add(AuditLog(action="staff.locked", entity="staff", entity_id=str(staff.id), data={"minutes": LOCK_MINUTES}))
        return None
    if staff.disabled_at is not None:
        return None
    staff.failed_attempts = 0
    staff.locked_until = None
    return staff


def set_disabled(db: Session, staff: StaffUser, disabled: bool) -> None:
    staff.disabled_at = dt.datetime.now(dt.UTC) if disabled else None
    if not disabled:
        staff.failed_attempts, staff.locked_until = 0, None
    if disabled:
        revoke_sessions(db, staff)
    db.add(AuditLog(action="staff.disabled" if disabled else "staff.enabled", entity="staff", entity_id=str(staff.id), data={}))


def revoke_sessions(db: Session, staff: StaffUser) -> None:
    db.execute(update(StaffSession).where(StaffSession.staff_id == staff.id, StaffSession.revoked_at.is_(None)).values(revoked_at=dt.datetime.now(dt.UTC)))


# ---- the second step -----------------------------------------------------------------------------------------------------------------------


def begin_enrolment(db: Session, enc: Encryptor, staff: StaffUser) -> tuple[str, str]:
    """A new secret, stored (encrypted) but not yet counting. Returns (secret, otpauth address) to show once as text and QR code."""
    secret = new_secret()
    staff.totp_secret = enc.encrypt(secret)
    staff.totp_enabled = False
    staff.totp_last_step = None
    return secret, otpauth_uri(staff.email, secret)


def _new_recovery_codes() -> list[str]:
    return [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(RECOVERY_CODES)]


def confirm_enrolment(db: Session, enc: Encryptor, staff: StaffUser, code: str, at: float | None = None) -> list[str]:
    """The first correct code switches the second step on and returns the recovery codes (plain, shown once; only hashes are kept)."""
    if not staff.totp_secret:
        raise StaffError("Start the enrolment first.")
    step = matching_step(enc.decrypt(staff.totp_secret), code, at)
    if step is None:
        raise StaffError("That code is not right.")
    staff.totp_enabled = True
    staff.totp_last_step = step
    codes = _new_recovery_codes()
    staff.recovery_codes = [hash_password(c) for c in codes]
    db.add(AuditLog(action="staff.totp_enabled", entity="staff", entity_id=str(staff.id), data={}))
    return codes


def verify_second_step(db: Session, enc: Encryptor, staff: StaffUser, code: str, at: float | None = None) -> bool:
    """A TOTP code (each time step once) or an unused recovery code (then used up)."""
    if not staff.totp_enabled or not staff.totp_secret:
        return False
    step = matching_step(enc.decrypt(staff.totp_secret), code, at)
    if step is not None:
        if staff.totp_last_step is not None and step <= staff.totp_last_step:
            return False  # already used: a replay
        staff.totp_last_step = step
        return True
    plain = code.strip().lower()
    for stored in list(staff.recovery_codes or []):
        if verify_password(stored, plain):
            staff.recovery_codes = [h for h in staff.recovery_codes if h != stored]
            db.add(AuditLog(action="staff.recovery_code_used", entity="staff", entity_id=str(staff.id), data={"left": len(staff.recovery_codes)}))
            return True
    return False


def reset_second_step(db: Session, staff: StaffUser) -> None:
    """Lost phone: the person enrols again at the next sign-in. Ends every login."""
    staff.totp_secret = None
    staff.totp_enabled = False
    staff.totp_last_step = None
    staff.recovery_codes = []
    revoke_sessions(db, staff)
    db.add(AuditLog(action="staff.totp_reset", entity="staff", entity_id=str(staff.id), data={}))
