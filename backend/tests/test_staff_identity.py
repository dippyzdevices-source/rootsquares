"""Staff identity (ADR 083, stage 1): accounts, password, TOTP, recovery codes, the command line, the migration that copies today's admins. SQLite."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from cryptography.fernet import Fernet
from flask import Flask
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.main import create_app
from app.platform import staff
from app.platform.models import AuditLog, StaffSession, StaffUser
from app.shared.config import Settings
from app.shared.crypto import Encryptor
from app.shared.db import Base
from app.shared.migrations import alembic_config
from tests.conftest import make_settings

PASSWORD = "a-long-staff-password"


@pytest.fixture
def app(tmp_path: Path) -> Flask:
    a = create_app(make_settings(DATABASE_URL=f"sqlite:///{tmp_path / 's.db'}", SEED_ADMIN_EMAIL="Root@Example.com", SEED_ADMIN_PASSWORD="seed-password-123"))
    Base.metadata.create_all(a.extensions["db_engine"]())
    return a


@pytest.fixture
def db(app: Flask) -> Iterator[Session]:
    with app.extensions["db_factory"]()() as s:
        yield s


@pytest.fixture
def enc() -> Encryptor:
    return Encryptor(Fernet.generate_key().decode())


def test_totp_matches_the_rfc_6238_vector() -> None:
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # the RFC's "12345678901234567890"
    assert staff.totp_code(secret, at=59) == "287082"  # RFC 6238 gives 94287082 for 8 digits
    assert staff.matching_step(secret, "287082", at=59) == 1
    assert staff.matching_step(secret, "287082", at=59 + 3 * staff.TOTP_STEP) is None  # outside the window
    assert staff.matching_step(secret, "12345", at=59) is None
    assert staff.matching_step(secret, "abcdef", at=59) is None


def test_create_checks_the_rules_and_keeps_no_plain_password(db: Session) -> None:
    with pytest.raises(staff.StaffError):
        staff.create_staff(db, "no-at-sign", PASSWORD)
    with pytest.raises(staff.StaffError):
        staff.create_staff(db, "a@example.com", "short")
    m = staff.create_staff(db, "  A@Example.com ", PASSWORD, name=" Ann ")
    db.commit()
    assert m.email == "a@example.com" and m.name == "Ann"
    assert PASSWORD not in m.password_hash and m.password_hash.startswith("$argon2")
    with pytest.raises(staff.StaffError):
        staff.create_staff(db, "A@example.com", PASSWORD)
    assert db.scalar(select(AuditLog).where(AuditLog.action == "staff.created")) is not None


def test_password_check_and_disable(db: Session) -> None:
    m = staff.create_staff(db, "a@example.com", PASSWORD)
    db.commit()
    assert staff.check_password(db, "A@example.com", PASSWORD) is m
    assert staff.check_password(db, "a@example.com", "wrong-password-xx") is None
    assert staff.check_password(db, "nobody@example.com", PASSWORD) is None
    db.add(StaffSession(staff_id=m.id, expires_at=staff.dt.datetime.now(staff.dt.UTC)))
    staff.set_disabled(db, m, True)
    db.commit()
    assert staff.check_password(db, "a@example.com", PASSWORD) is None
    assert all(s.revoked_at is not None for s in db.scalars(select(StaffSession)))
    staff.set_disabled(db, m, False)
    assert staff.check_password(db, "a@example.com", PASSWORD) is m


def test_enrolment_second_step_replay_and_recovery_codes(db: Session, enc: Encryptor) -> None:
    m = staff.create_staff(db, "a@example.com", PASSWORD)
    secret, uri = staff.begin_enrolment(db, enc, m)
    assert m.totp_secret and m.totp_secret != secret  # stored encrypted
    assert uri.startswith("otpauth://totp/") and f"secret={secret}" in uri
    assert not staff.verify_second_step(db, enc, m, staff.totp_code(secret, at=1000), at=1000)  # not on until confirmed
    with pytest.raises(staff.StaffError):
        staff.confirm_enrolment(db, enc, m, "000000", at=1000)
    codes = staff.confirm_enrolment(db, enc, m, staff.totp_code(secret, at=1000), at=1000)
    assert m.totp_enabled and len(codes) == staff.RECOVERY_CODES
    assert all(c not in str(m.recovery_codes) for c in codes)  # only hashes are kept
    assert not staff.verify_second_step(db, enc, m, staff.totp_code(secret, at=1000), at=1000)  # the code of the enrolment step is used
    later = 1000 + 2 * staff.TOTP_STEP
    assert staff.verify_second_step(db, enc, m, staff.totp_code(secret, at=later), at=later)
    assert not staff.verify_second_step(db, enc, m, staff.totp_code(secret, at=later), at=later)  # a replay
    assert not staff.verify_second_step(db, enc, m, "not-a-code", at=later)
    assert staff.verify_second_step(db, enc, m, codes[0].upper(), at=later)  # a recovery code, any case
    assert not staff.verify_second_step(db, enc, m, codes[0], at=later)  # used up
    assert len(m.recovery_codes) == staff.RECOVERY_CODES - 1


def test_reset_second_step_ends_the_logins(db: Session, enc: Encryptor) -> None:
    m = staff.create_staff(db, "a@example.com", PASSWORD)
    secret, _ = staff.begin_enrolment(db, enc, m)
    staff.confirm_enrolment(db, enc, m, staff.totp_code(secret, at=1000), at=1000)
    db.add(StaffSession(staff_id=m.id, expires_at=staff.dt.datetime.now(staff.dt.UTC)))
    staff.reset_second_step(db, m)
    db.commit()
    assert not m.totp_enabled and m.totp_secret is None and m.recovery_codes == []
    assert all(s.revoked_at is not None for s in db.scalars(select(StaffSession)))


def test_the_command_line(app: Flask) -> None:
    run = app.test_cli_runner().invoke
    assert "no staff accounts" in run(args=["staff-list"]).output
    r = run(args=["staff-create", "Ann@Example.com", "--name", "Ann"], input=f"{PASSWORD}\n{PASSWORD}\n")
    assert r.exit_code == 0, r.output
    assert PASSWORD not in r.output
    assert run(args=["staff-create", "ann@example.com"], input=f"{PASSWORD}\n{PASSWORD}\n").exit_code != 0  # exists
    listed = run(args=["staff-list"]).output
    assert "ann@example.com" in listed and "active" in listed and "not set up" in listed and PASSWORD not in listed
    assert "disabled" in run(args=["staff-disable", "ann@example.com"]).output
    assert "disabled" in run(args=["staff-list"]).output
    assert "enabled" in run(args=["staff-disable", "ann@example.com", "--enable"]).output
    assert "removed" in run(args=["staff-reset-2fa", "ann@example.com"]).output
    assert run(args=["staff-disable", "nobody@example.com"]).exit_code != 0


def test_seed_staff_creates_then_leaves_alone_then_updates(app: Flask) -> None:
    run = app.test_cli_runner().invoke
    assert "created" in run(args=["seed-staff"]).output
    assert "unchanged" in run(args=["seed-staff"]).output  # dev.ps1 runs it on every start
    with app.extensions["db_factory"]()() as db:
        m = staff.get_staff(db, "root@example.com")
        assert m is not None
        db.add(StaffSession(staff_id=m.id, expires_at=staff.dt.datetime.now(staff.dt.UTC)))
        staff.set_password(db, m, "another-long-password")  # the seed password now differs from the stored one
        db.commit()
    out = run(args=["seed-staff"]).output
    assert "updated" in out and "seed-password-123" not in out
    with app.extensions["db_factory"]()() as db:
        assert all(s.revoked_at is not None for s in db.scalars(select(StaffSession)))


def test_the_migration_copies_admins_with_a_password(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    settings: Settings = Settings(_env_file=None, ENV="test", DATABASE_URL=url)  # type: ignore[call-arg]
    engine = create_engine(url)
    cfg = alembic_config(settings)
    command.upgrade(cfg, "0028")  # the migration opens its own connection: nothing of ours may be open meanwhile
    with engine.begin() as conn:
        for email, admin, pw in (("a@example.com", True, "$argon2id$hash"), ("b@example.com", True, None), ("c@example.com", False, "$argon2id$other")):
            conn.execute(
                text("INSERT INTO users (id, email, password_hash, name, is_platform_admin) VALUES (:i, :e, :p, 'n', :a)"),
                {"i": uuid.uuid4().hex, "e": email, "p": pw, "a": admin},
            )
    command.upgrade(cfg, "0029")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT email, password_hash, totp_enabled FROM staff_users")).all()
    assert [(r[0], r[1], bool(r[2])) for r in rows] == [("a@example.com", "$argon2id$hash", False)]  # no password: not copied; not an admin: not copied
    assert StaffUser.__tablename__ == "staff_users"
