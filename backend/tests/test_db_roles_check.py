"""The check script of the database roles (guide 36) needs no database to be tested: its questions are answered by a model built from the grants themselves.

If the check and the grants ever disagree, the first test fails; the others prove that the check notices a right that is too wide, missing or absent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import db_roles  # noqa: E402
import db_roles_check as check  # noqa: E402


class ModelOracle:
    """What Postgres would answer for `role` after the generated grants were run (read from the SQL text, not from the lists the grants are written from)."""

    def __init__(self, role: str, sql: str | None = None, **changes: object) -> None:
        self.role = role
        self.table_rights: dict[str, set[str]] = {}
        self.column_rights: set[tuple[str, str]] = set()
        self.policies: set[str] = set()
        for line in (sql if sql is not None else db_roles.sql()).splitlines():
            p = re.match(r'CREATE POLICY \w+ ON public\."(\w+)" AS PERMISSIVE FOR ALL TO (\w+) USING', line)
            if p:
                if p.group(2) == role:
                    self.policies.add(p.group(1))
                continue
            m = re.match(r"GRANT (UPDATE) \(([^)]*)\) ON TABLE public\.\"(\w+)\" TO (.+);", line)
            if m and role in [r.strip() for r in m.group(4).split(",")]:
                self.column_rights |= {(m.group(3), c.strip()) for c in m.group(2).split(",")}
                continue
            m = re.match(r"GRANT ([A-Z, ]+) ON TABLE (.+) TO (.+);", line)
            if m and role in [r.strip() for r in m.group(3).split(",")] and not m.group(1).startswith("USAGE"):
                rights = {r.strip() for r in m.group(1).split(",")}
                for table in re.findall(r'public\."(\w+)"', m.group(2)):
                    self.table_rights.setdefault(table, set()).update(rights)
        self.changes = changes

    def current_user(self) -> str:
        return str(self.changes.get("user", self.role))

    def database(self) -> str:
        return "platform"

    def role_flags(self) -> dict[str, bool]:
        return {"rolsuper": False, "rolbypassrls": False, "rolcreaterole": False, "rolcreatedb": False, **self.changes.get("flags", {})}  # type: ignore[dict-item]

    def table_exists(self, table: str) -> bool:
        return table not in self.changes.get("missing", set())  # type: ignore[operator]

    def table_right(self, table: str, right: str) -> bool:
        extra: set[tuple[str, str]] = self.changes.get("extra", set())  # type: ignore[assignment]
        lost: set[tuple[str, str]] = self.changes.get("lost", set())  # type: ignore[assignment]
        return ((right in self.table_rights.get(table, set())) or (table, right) in extra) and (table, right) not in lost

    def column_update(self, table: str, column: str) -> bool:
        return (table, column) in self.column_rights or "UPDATE" in self.table_rights.get(table, set())

    def schema_create(self) -> bool:
        return bool(self.changes.get("schema_create", False))

    def rls_enabled(self, table: str) -> bool:
        return bool(self.changes.get("rls", True))

    def has_policy(self, table: str) -> bool:
        return table in self.policies and table not in self.changes.get("no_policy", set())  # type: ignore[operator]


def _statuses(role: str, **changes: object) -> list[check.Result]:
    return check.evaluate(role, ModelOracle(role, **changes))


def _failures(role: str, **changes: object) -> list[str]:
    return [r.message for r in _statuses(role, **changes) if r.status == "FAIL"]


def test_the_check_agrees_with_the_generated_grants_for_both_roles() -> None:
    for role in (db_roles.CUSTOMER_ROLE, db_roles.ADMIN_ROLE):
        assert _failures(role) == []
        assert len(_statuses(role)) > 80  # every table, four rights each, the policies, the role flags and the column rights


def test_a_staff_right_for_the_customer_role_is_a_failure() -> None:
    bad = _failures(db_roles.CUSTOMER_ROLE, extra={("staff_users", "SELECT")})
    assert len(bad) == 1 and "staff_users" in bad[0] and "may SELECT" in bad[0]


def test_a_missing_right_for_the_admin_role_is_a_failure() -> None:
    bad = _failures(db_roles.ADMIN_ROLE, lost={("staff_sessions", "UPDATE")})
    assert len(bad) == 1 and "staff_sessions" in bad[0] and "NOT" in bad[0]


def test_deleting_or_updating_the_audit_log_is_a_failure_for_both_roles() -> None:
    for role in (db_roles.CUSTOMER_ROLE, db_roles.ADMIN_ROLE):
        assert any("DELETE audit_log" in m for m in _failures(role, extra={("audit_log", "DELETE")}))
        assert any("UPDATE audit_log" in m for m in _failures(role, extra={("audit_log", "UPDATE")}))


def test_the_customer_role_must_keep_the_one_audit_column_it_may_blank() -> None:
    sql = "\n".join(line for line in db_roles.sql().splitlines() if "UPDATE (actor_user_id)" not in line)
    bad = [r.message for r in check.evaluate(db_roles.CUSTOMER_ROLE, ModelOracle(db_roles.CUSTOMER_ROLE, sql=sql)) if r.status == "FAIL"]
    assert len(bad) == 1 and "actor_user_id" in bad[0]


def test_the_admin_role_may_only_read_the_customer_logins() -> None:
    assert any("auth_sessions" in m for m in _failures(db_roles.ADMIN_ROLE, extra={("auth_sessions", "DELETE")}))


def test_a_privileged_role_the_wrong_user_and_a_missing_table_are_failures() -> None:
    assert any("superuser" in m for m in _failures(db_roles.CUSTOMER_ROLE, flags={"rolsuper": True}))
    assert any("bypass row level security" in m for m in _failures(db_roles.ADMIN_ROLE, flags={"rolbypassrls": True}))
    assert any("not 'customer_app'" in m for m in _failures(db_roles.CUSTOMER_ROLE, user="postgres"))
    assert any("does not exist" in m for m in _failures(db_roles.ADMIN_ROLE, missing={"vouchers"}))


def test_creating_tables_is_a_warning_not_a_failure() -> None:
    results = _statuses(db_roles.CUSTOMER_ROLE, schema_create=True)
    assert [r.status for r in results if r.status != "PASS"] == ["WARN"]


def test_the_expected_rights_follow_the_four_groups() -> None:
    cust, adm = db_roles.CUSTOMER_ROLE, db_roles.ADMIN_ROLE
    assert check.expected_rights(cust, "staff_users") == frozenset() and check.expected_rights(adm, "staff_users") == check.ALL_RIGHTS
    assert check.expected_rights(cust, "audit_log") == check.expected_rights(adm, "audit_log") == frozenset({"SELECT", "INSERT"})
    assert check.expected_rights(cust, "auth_sessions") == check.ALL_RIGHTS and check.expected_rights(adm, "auth_sessions") == frozenset({"SELECT"})
    assert check.expected_rights(cust, "squares") == check.expected_rights(adm, "squares") == check.ALL_RIGHTS
    assert check.expected_column_updates(cust, "audit_log") == frozenset({"actor_user_id"}) and check.expected_column_updates(adm, "audit_log") == frozenset()


# ---- running it ------------------------------------------------------------------------------------------------------------------------
def test_it_refuses_to_run_without_the_two_connection_strings_and_says_which() -> None:
    lines: list[str] = []
    assert check.run({"CUSTOMER_APP_URL": "postgresql://x"}, out=lines.append) == 2
    assert "ADMIN_APP_URL" in lines[0] and "CUSTOMER_APP_URL" not in lines[0].split("set ")[1].split(" in")[0]
    assert check.run({}, out=lines.append) == 2 and "CUSTOMER_APP_URL and ADMIN_APP_URL" in lines[-1]


def test_a_connection_error_is_exit_2_and_never_prints_the_connection_string() -> None:
    secret = "postgresql+psycopg://customer_app:Sup3r-secret@db.example.com:5432/platform"
    lines: list[str] = []

    def broken(url: str) -> object:
        raise OSError(f"could not connect using {url} and {check.to_psycopg_url(url)}")

    assert check.run({"CUSTOMER_APP_URL": secret, "ADMIN_APP_URL": secret}, connector=broken, out=lines.append) == 2
    assert lines and all("Sup3r-secret" not in line for line in lines) and "<connection string>" in lines[0]


def test_the_driver_part_of_the_url_is_removed_for_the_database_library() -> None:
    assert check.to_psycopg_url("postgresql+psycopg://u:p@h/db") == "postgresql://u:p@h/db"
    assert check.to_psycopg_url("postgres://u:p@h/db") == "postgresql://u:p@h/db"
    assert check.to_psycopg_url("postgresql://u:p@h/db") == "postgresql://u:p@h/db"


def test_two_different_databases_are_a_failure() -> None:
    class Conn:
        def __init__(self, url: str) -> None:
            self.url = url

        def close(self) -> None:
            pass

    class Fake(ModelOracle):
        pass

    # the connector hands back a connection object; PgOracle is replaced so no database is needed
    original = check.PgOracle
    try:

        def make(conn: Conn) -> ModelOracle:
            role = db_roles.CUSTOMER_ROLE if "cust" in conn.url else db_roles.ADMIN_ROLE
            oracle = ModelOracle(role)
            oracle.database = lambda: "one" if "cust" in conn.url else "two"  # type: ignore[method-assign]
            return oracle

        check.PgOracle = make  # type: ignore[assignment,misc]
        lines: list[str] = []
        code = check.run({"CUSTOMER_APP_URL": "postgresql://cust", "ADMIN_APP_URL": "postgresql://adm"}, connector=Conn, out=lines.append)  # type: ignore[arg-type]
    finally:
        check.PgOracle = original  # type: ignore[misc]
    assert code == 1 and any("different databases" in line for line in lines)


def test_row_level_security_without_a_policy_is_a_failure() -> None:
    """Every platform table has row level security on and no policy: a role without a policy sees nothing and cannot insert, whatever it was granted."""
    bad = _failures(db_roles.CUSTOMER_ROLE, no_policy={"squares"})
    assert len(bad) == 1 and "row level security is on for squares" in bad[0]
    assert any("staff_users" in m for m in _failures(db_roles.ADMIN_ROLE, no_policy={"staff_users"}))


def test_a_table_without_row_level_security_needs_no_policy() -> None:
    assert _failures(db_roles.CUSTOMER_ROLE, rls=False, no_policy={"squares", "users"}) == []


def test_the_customer_role_gets_no_policy_on_the_staff_tables() -> None:
    sql = db_roles.sql()
    customer = [line for line in sql.splitlines() if line.startswith("CREATE POLICY customer_app_all")]
    assert customer and not [line for line in customer if "staff_" in line]
    assert len([line for line in sql.splitlines() if line.startswith("CREATE POLICY admin_app_all")]) == len(db_roles.tables_of(db_roles.ADMIN_ROLE))
