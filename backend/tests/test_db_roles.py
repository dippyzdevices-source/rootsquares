"""The database roles of the two services (ADR 084, option B): the grants are written from the models, so these tests keep the lists true."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import db_roles  # noqa: E402

from app.shared.db import Base  # noqa: E402


def test_every_table_is_in_exactly_one_group() -> None:
    groups = db_roles.classify()
    listed = [t for names in groups.values() for t in names]
    assert sorted(listed) == sorted(Base.metadata.tables)
    assert len(listed) == len(set(listed))


def test_every_staff_table_is_staff_only() -> None:
    """A new table named staff_* (or linked to the staff accounts) must be added to STAFF_ONLY, or it would be shared with the customer service."""
    staff_like = {
        t
        for t, tab in Base.metadata.tables.items()
        if t.startswith("staff") or any(fk.column.table.name.startswith("staff") for c in tab.columns for fk in c.foreign_keys)
    }
    assert staff_like <= db_roles.STAFF_ONLY
    assert db_roles.STAFF_ONLY <= set(Base.metadata.tables)


def test_the_listed_special_tables_exist() -> None:
    assert (db_roles.APPEND_ONLY | db_roles.CUSTOMER_SESSIONS | db_roles.SUPPORT) <= set(Base.metadata.tables)
    for table, cols in db_roles.APPEND_ONLY_CUSTOMER_UPDATE.items():
        assert table in db_roles.APPEND_ONLY and all(c in Base.metadata.tables[table].columns for c in cols)


@pytest.fixture(scope="module")
def script() -> str:
    return db_roles.sql()


def _grants(script: str, role: str) -> list[str]:
    return [line for line in script.splitlines() if line.startswith("GRANT") and role in [r.strip() for r in line.rsplit(" TO ", 1)[-1].rstrip(";").split(",")]]


def test_the_customer_role_has_no_right_on_the_staff_tables(script: str) -> None:
    for line in _grants(script, db_roles.CUSTOMER_ROLE):
        assert "staff_users" not in line and "staff_sessions" not in line, line
    assert any("staff_users" in line for line in _grants(script, db_roles.ADMIN_ROLE))


def test_the_audit_log_is_append_only_for_both_roles(script: str) -> None:
    for role in (db_roles.CUSTOMER_ROLE, db_roles.ADMIN_ROLE):
        for line in _grants(script, role):
            if '"audit_log"' in line:
                rights = line.split(" ON TABLE ")[0]
                assert "DELETE" not in rights, line
                if "UPDATE (" not in rights:
                    assert "UPDATE" not in rights, line
    column = [line for line in _grants(script, db_roles.CUSTOMER_ROLE) if "UPDATE (actor_user_id)" in line]
    assert len(column) == 1 and not [line for line in _grants(script, db_roles.ADMIN_ROLE) if "UPDATE (" in line and '"audit_log"' in line]


def test_the_admin_service_cannot_write_customer_logins(script: str) -> None:
    lines = [line for line in _grants(script, db_roles.ADMIN_ROLE) if '"auth_sessions"' in line]
    assert lines and all(line.startswith("GRANT SELECT ON") for line in lines)


def test_it_starts_by_taking_everything_away_and_runs_in_one_transaction(script: str) -> None:
    lines = script.splitlines()
    assert "BEGIN;" in lines and "COMMIT;" in lines
    assert (
        lines.index("BEGIN;")
        < next(i for i, line in enumerate(lines) if line.startswith("REVOKE ALL ON ALL TABLES"))
        < next(i for i, line in enumerate(lines) if line.startswith("GRANT SELECT, INSERT, UPDATE, DELETE"))
    )


def test_every_role_gets_one_policy_on_each_table_it_may_touch_and_the_script_can_run_twice(script: str) -> None:
    """The platform tables have row level security on and no policy; without these policies the two roles would see no row (found on the real database)."""
    lines = script.splitlines()
    for role in (db_roles.CUSTOMER_ROLE, db_roles.ADMIN_ROLE):
        for table in db_roles.tables_of(role):
            create = f'CREATE POLICY {role}_all ON public."{table}" AS PERMISSIVE FOR ALL TO {role} USING (true) WITH CHECK (true);'
            drop = f'DROP POLICY IF EXISTS {role}_all ON public."{table}";'
            assert lines.count(create) == 1 and lines.count(drop) == 1
            assert lines.index(drop) < lines.index(create) < lines.index("COMMIT;")
    assert not [line for line in lines if "CREATE POLICY customer_app_all" in line and "staff_" in line]


def test_the_undo_drops_every_policy_the_grants_made_then_the_rights_then_the_roles() -> None:
    undo = db_roles.revert_sql().splitlines()
    made = [line for line in db_roles.sql().splitlines() if line.startswith("DROP POLICY IF EXISTS")]
    assert made and all(line in undo for line in made)
    assert not [line for line in undo if line.startswith(("GRANT", "CREATE"))]
    assert undo[0].startswith("--") and "BEGIN;" in undo and undo[-1] == "COMMIT;"
    drops = [i for i, line in enumerate(undo) if line.startswith("DROP ROLE")]
    revokes = [i for i, line in enumerate(undo) if line.startswith("REVOKE ALL ON SCHEMA")]
    last_policy = max(i for i, line in enumerate(undo) if line.startswith("DROP POLICY"))
    assert len(drops) == 2 and last_policy < revokes[0] < drops[0]


def test_a_support_grant_can_only_be_made_by_the_customer_service_and_a_session_only_by_the_admin_service(script: str) -> None:
    """ADR 089: a stolen login of one service cannot forge the other's part."""
    customer = [line for line in _grants(script, db_roles.CUSTOMER_ROLE) if '"support_' in line]
    admin = [line for line in _grants(script, db_roles.ADMIN_ROLE) if '"support_' in line]
    assert any(line.startswith("GRANT SELECT, INSERT, UPDATE, DELETE ON") and '"support_grants"' in line for line in customer)
    assert not any("INSERT" in line.split(" ON TABLE ")[0] and '"support_grants"' in line for line in admin)  # staff cannot make a grant
    assert not any("INSERT" in line.split(" ON TABLE ")[0] and '"support_sessions"' in line for line in customer)  # the owner cannot make a session
    assert any("INSERT" in line.split(" ON TABLE ")[0] and '"support_sessions"' in line for line in admin)
    assert any("UPDATE (ending_notice_at)" in line and '"support_grants"' in line for line in admin)
    assert any("UPDATE (ended_at, ended_by)" in line and '"support_sessions"' in line for line in customer)
    for line in customer + admin:
        assert "DELETE" not in line.split(" ON TABLE ")[0] or '"support_grants"' in line, line  # only the owner's grants can be deleted
