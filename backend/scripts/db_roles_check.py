"""Checks that the two database roles of the two services have exactly the rights they should (ADR 084, database option B). Read-only.

What it is:   The repeatable check of guide 36. It connects as `customer_app` and as `admin_app` and asks Postgres what each role may do (the privilege
              functions
              `has_table_privilege` and friends; nothing is read from or written to any table). The expected rights come from the same lists that
              `db_roles.py` writes the grants from, so the check and the grants cannot drift apart (tests/test_db_roles_check.py proves it).
What it does: Prints one line per problem (FAIL = a right that is wrong or missing, WARN = something to look at) and a summary per role. Exit code 0 = no FAIL,
              1 = at least one FAIL, 2 = it could not run (a connection string is missing or a connection failed). It never prints a connection string.
How to run:   Put the two role connection strings in the environment of the terminal (never in a file of the repository), then, from `backend`:
              `$env:CUSTOMER_APP_URL = "postgresql://customer_app...."` and `$env:ADMIN_APP_URL = "postgresql://admin_app...."`, then
              `.venv\\Scripts\\python.exe scripts\\db_roles_check.py`. Run it after creating the roles, after every `db_roles.py` run,
              and after every migration that adds a table.
Read before:  docs/setup/36-database-roles.md (what the roles are and how to create them), backend/scripts/db_roles.py (the grants).
Read after:   docs/setup/36-database-roles.md section 8 (what to do with a FAIL).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import db_roles  # noqa: E402

RIGHTS = ("SELECT", "INSERT", "UPDATE", "DELETE")
ALL_RIGHTS = frozenset(RIGHTS)
READ_WRITE_NO_DELETE = frozenset({"SELECT", "INSERT"})
ROLE_VARS = {db_roles.CUSTOMER_ROLE: "CUSTOMER_APP_URL", db_roles.ADMIN_ROLE: "ADMIN_APP_URL"}


# ---- what each role should be allowed to do (the same lists as db_roles.py) ---------------------------------------------------------
def expected_rights(role: str, table: str) -> frozenset[str]:
    """The table-level rights `role` should hold on `table`."""
    groups = db_roles.classify()
    if table in groups["staff"]:
        return ALL_RIGHTS if role == db_roles.ADMIN_ROLE else frozenset()
    if table in groups["append_only"]:
        return READ_WRITE_NO_DELETE  # insert and select, never update or delete (the one column exception is below)
    if table in groups["customer_sessions"]:
        return ALL_RIGHTS if role == db_roles.CUSTOMER_ROLE else frozenset({"SELECT"})
    if table in groups["support"]:
        return frozenset(db_roles.SUPPORT_RIGHTS[table].get(role, ()))
    return ALL_RIGHTS


def expected_column_updates(role: str, table: str) -> frozenset[str]:
    """The columns of an append-only or support table that `role` may update although it has no table-level UPDATE."""
    if table in db_roles.SUPPORT_COLUMN_UPDATE:
        return frozenset(db_roles.SUPPORT_COLUMN_UPDATE[table].get(role, []))
    if role == db_roles.CUSTOMER_ROLE:
        return frozenset(db_roles.APPEND_ONLY_CUSTOMER_UPDATE.get(table, []))
    return frozenset()


# ---- the questions asked of Postgres ----------------------------------------------------------------------------------------------
class Oracle(Protocol):
    def current_user(self) -> str: ...
    def database(self) -> str: ...
    def role_flags(self) -> dict[str, bool]: ...
    def table_exists(self, table: str) -> bool: ...
    def table_right(self, table: str, right: str) -> bool: ...
    def column_update(self, table: str, column: str) -> bool: ...
    def schema_create(self) -> bool: ...
    def rls_enabled(self, table: str) -> bool: ...
    def has_policy(self, table: str) -> bool: ...


@dataclass(frozen=True)
class Result:
    status: str  # PASS, FAIL or WARN
    message: str


def evaluate(role: str, oracle: Oracle) -> list[Result]:
    """Every check for one role. Pure: the oracle answers, nothing is printed or connected here."""
    out: list[Result] = []

    def check(ok: bool, good: str, bad: str, status: str = "FAIL") -> None:
        out.append(Result("PASS", good) if ok else Result(status, bad))

    check(
        oracle.current_user() == role,
        f"connected as {role}",
        f"connected as {oracle.current_user()!r}, not {role!r}: the connection string names the wrong role",
    )
    flags = oracle.role_flags()
    for flag, meaning in (
        ("rolsuper", "superuser"),
        ("rolbypassrls", "bypass row level security"),
        ("rolcreaterole", "create roles"),
        ("rolcreatedb", "create databases"),
    ):
        check(not flags.get(flag, False), f"{role} may not {meaning}", f"{role} may {meaning} (create it with plain LOGIN and nothing else)")
    check(
        not oracle.schema_create(),
        f"{role} may not create tables",
        f"{role} may create objects in the schema: REVOKE CREATE ON SCHEMA public FROM {role} (and FROM PUBLIC if it is granted there)",
        "WARN",
    )
    for table in sorted(db_roles.Base.metadata.tables):
        if not oracle.table_exists(table):
            out.append(Result("FAIL", f"table {table} does not exist in this database (run the migrations as the owner first)"))
            continue
        want = expected_rights(role, table)
        for right in RIGHTS:
            has = oracle.table_right(table, right)
            if has == (right in want):
                out.append(Result("PASS", f"{role}: {right} on {table} is {'allowed' if has else 'refused'}"))
            else:
                out.append(Result("FAIL", f"{role} {'may' if has else 'may NOT'} {right} {table}, expected the opposite" + _hint(role, table, right, has)))
        for column in sorted(expected_column_updates(role, table)):
            has = oracle.column_update(table, column)
            check(
                has,
                f"{role}: UPDATE ({column}) on {table} is allowed",
                f"{role} may NOT update {table}.{column}: GRANT UPDATE ({column}) ON TABLE {table} TO {role}",
            )
        # Row level security: with it on and no policy a role sees no row and may not insert, whatever the grants say.
        if table in db_roles.tables_of(role) and oracle.rls_enabled(table):
            check(
                oracle.has_policy(table),
                f"{role}: a row level security policy opens {table}",
                f"row level security is on for {table} and no policy opens it to {role}: run the output of db_roles.py again (it writes the policies)",
            )
    return out


def _hint(role: str, table: str, right: str, has: bool) -> str:
    if has:
        return f" (too much: REVOKE {right} ON TABLE {table} FROM {role}, or run db_roles.py again)"
    return " (missing: run the output of db_roles.py again as the owner)"


# ---- the real database ------------------------------------------------------------------------------------------------------------
def to_psycopg_url(url: str) -> str:
    """The URLs of the application name the driver (postgresql+psycopg://); libpq does not know that part."""
    for prefix in ("postgresql+psycopg://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix) :]
    return url


def scrub(message: str, *secrets: str) -> str:
    """The first line of an error with every connection string taken out."""
    line = message.strip().splitlines()[0] if message.strip() else ""
    for s in secrets:
        if s:
            line = line.replace(s, "<connection string>")
    return line


class PgOracle:
    def __init__(self, conn: object, schema: str = "public") -> None:
        self._conn = conn
        self._schema = schema

    def _one(self, sql: str, *params: object) -> object:
        with self._conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(sql, params)
            row = cur.fetchone()
        return row[0] if row else None

    def current_user(self) -> str:
        return str(self._one("SELECT current_user"))

    def database(self) -> str:
        return str(self._one("SELECT current_database()"))

    def role_flags(self) -> dict[str, bool]:
        with self._conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user")
            row = cur.fetchone()
        return dict(zip(("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb"), (bool(x) for x in row), strict=True)) if row else {}

    def _qualified(self, table: str) -> str:
        return f'{self._schema}."{table}"'

    def table_exists(self, table: str) -> bool:
        return bool(self._one("SELECT to_regclass(%s) IS NOT NULL", self._qualified(table)))

    def table_right(self, table: str, right: str) -> bool:
        return bool(self._one("SELECT has_table_privilege(current_user, %s, %s)", self._qualified(table), right))

    def column_update(self, table: str, column: str) -> bool:
        return bool(self._one("SELECT has_column_privilege(current_user, %s, %s, 'UPDATE')", self._qualified(table), column))

    def schema_create(self) -> bool:
        return bool(self._one("SELECT has_schema_privilege(current_user, %s, 'CREATE')", self._schema))

    def rls_enabled(self, table: str) -> bool:
        return bool(self._one("SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass(%s)", self._qualified(table)))

    def has_policy(self, table: str) -> bool:
        return bool(
            self._one(
                "SELECT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = %s AND tablename = %s AND (current_user = ANY(roles) OR 'public' = ANY(roles)))",
                self._schema,
                table,
            )
        )


def connect(url: str) -> object:
    import psycopg

    return psycopg.connect(
        to_psycopg_url(url), autocommit=True, connect_timeout=15, prepare_threshold=None
    )  # no prepared statements: works through a transaction pooler


def run(environ: dict[str, str], connector: Callable[[str], object] = connect, out: Callable[[str], None] = print) -> int:
    missing = [var for var in ROLE_VARS.values() if not environ.get(var)]
    if missing:
        out(f"Cannot run: set {' and '.join(missing)} in this terminal (the roles' connection strings; see docs/setup/36-database-roles.md section 6).")
        return 2
    databases: dict[str, str] = {}
    failed = 0
    for role, var in ROLE_VARS.items():
        url = environ[var]
        try:
            conn = connector(url)
            oracle = PgOracle(conn)
            results = evaluate(role, oracle)
            databases[role] = oracle.database()
            conn.close()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 - any failure to connect or ask is "could not run", never a pass
            out(f"{role}: could not check ({type(exc).__name__}: {scrub(str(exc), url, to_psycopg_url(url))})")
            return 2
        bad = [r for r in results if r.status == "FAIL"]
        warn = [r for r in results if r.status == "WARN"]
        for r in bad + warn:
            out(f"{r.status} {r.message}")
        out(f"{role}: {len(results)} checks, {len(bad)} failed, {len(warn)} to look at")
        failed += len(bad)
    if len(set(databases.values())) > 1:
        out(f"FAIL the two connection strings point at different databases ({databases}): both services must use the same platform database")
        failed += 1
    out("RESULT: " + ("all rights are as expected" if not failed else f"{failed} problem(s), see the FAIL lines above and guide 36 section 8"))
    return 1 if failed else 0


def main() -> None:
    sys.exit(run(dict(os.environ)))


if __name__ == "__main__":
    main()
