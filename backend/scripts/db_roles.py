"""Prints the SQL that gives the two services their own database roles (ADR 084, database option B). It changes nothing by itself.

What it is:   The grants for `customer_app` (the customer service) and `admin_app` (the admin service) on the platform database, written from the models so a
              new table cannot be forgotten: every table is either staff-only, append-only or shared, and a test (tests/test_db_roles.py) keeps the lists true.
What it does: Revokes everything from both roles, then grants the least each service needs: the customer role has NO right on the staff tables; the audit log is
              insert and select for both (history is never edited or deleted; the customer role may only blank `actor_user_id` when a person erases
              their account). Every platform table has row level security switched on and no policy (so that Supabase's open REST door stays
              shut); only the owner bypasses it. So each role also gets one policy per table it may touch ("all rows"): the grants decide WHAT a role may
              do, the policy only opens the rows.
How to run:   Follow docs/setup/36-database-roles.md sections 3 and 4 (the exact commands). In short, from `backend`: create the two roles, then
              `.venv/Scripts/python.exe scripts/db_roles.py | Out-File -Encoding ascii roles.sql` (PowerShell 5.1: `>` would write UTF-16, which psql
              refuses), read it, run it with the owner's login through `psql -f roles.sql` (it is one
              transaction and can be run again), and run `scripts/db_roles_check.py`. `--revert` prints the undo. Run it again after every migration that adds
              a table. Nothing here connects to a database.
Read before:  docs/setup/36-database-roles.md, docs/plans/admin-separation-plan.md section 8.
Read after:   scripts/db_roles_check.py (the check), backend/app/shared/config.py (API_SURFACE, STAFF_JWT_SECRET, STAFF_FERNET_KEY).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.platform import models  # noqa: E402,F401  (registers every table on Base.metadata)
from app.shared.db import Base  # noqa: E402

CUSTOMER_ROLE = "customer_app"
ADMIN_ROLE = "admin_app"

# Rights only the admin service has: staff accounts and their logins. The customer service gets nothing on them.
STAFF_ONLY = {"staff_users", "staff_sessions"}
# Customer logins: the customer service reads and writes them; the admin service may only read.
CUSTOMER_SESSIONS = {"auth_sessions"}
# History: insert and select for both services, never update or delete (except the one column named below).
APPEND_ONLY = {"audit_log"}
# The one exception: erasing a person's account blanks who did something, the history stays (lifecycle.erase).
APPEND_ONLY_CUSTOMER_UPDATE = {"audit_log": ["actor_user_id"]}
# Support access (ADR 089): each service holds only the rights of its own side. The owner (customer service) creates and revokes grants and answers requests;
# staff (admin service) make requests and open sessions. Neither can do the other's part, so a stolen service login cannot forge a grant or a session.
# {table: {role: table-level rights}} and {table: {role: columns it may update}} (a column-level UPDATE is not a table-level one).
SUPPORT_RIGHTS = {
    "support_grants": {"customer_app": ("SELECT", "INSERT", "UPDATE", "DELETE"), "admin_app": ("SELECT",)},
    "support_requests": {"customer_app": ("SELECT",), "admin_app": ("SELECT", "INSERT")},
    "support_sessions": {"customer_app": ("SELECT",), "admin_app": ("SELECT", "INSERT")},
}
SUPPORT_COLUMN_UPDATE = {
    "support_grants": {"admin_app": ["ending_notice_at"]},  # the job `support-run` records that the "ends soon" mail went out
    "support_requests": {"customer_app": ["answered_at", "grant_id"]},  # creating a grant answers the requests waiting
    "support_sessions": {"customer_app": ["ended_at", "ended_by"], "admin_app": ["ended_at", "ended_by"]},  # a revoke or an expiry ends a session
}
SUPPORT = set(SUPPORT_RIGHTS)


def classify() -> dict[str, list[str]]:
    tables = sorted(Base.metadata.tables)
    return {
        "staff": [t for t in tables if t in STAFF_ONLY],
        "append_only": [t for t in tables if t in APPEND_ONLY],
        "customer_sessions": [t for t in tables if t in CUSTOMER_SESSIONS],
        "support": [t for t in tables if t in SUPPORT],
        "shared": [t for t in tables if t not in STAFF_ONLY | APPEND_ONLY | CUSTOMER_SESSIONS | SUPPORT],
    }


def tables_of(role: str) -> list[str]:
    """The tables `role` has any right on: the customer service has none on the staff tables, the admin service has all."""
    groups = classify()
    mine = groups["shared"] + groups["customer_sessions"] + groups["append_only"] + groups["support"]
    return sorted(mine + groups["staff"]) if role == ADMIN_ROLE else sorted(mine)


def policy_name(role: str) -> str:
    return f"{role}_all"


def sql(schema: str = "public") -> str:
    c = classify()
    q = lambda names: ", ".join(f'{schema}."{n}"' for n in names)  # noqa: E731
    out = [
        "-- Generated by backend/scripts/db_roles.py (ADR 084). Run as the owner of the tables (the migrator role), after the roles exist (docs/setup/36).",
        f"-- Run it again after every migration that adds a table. Tables: {sum(len(v) for v in c.values())}.",
        "BEGIN;",
        f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {CUSTOMER_ROLE}, {ADMIN_ROLE};",
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM {CUSTOMER_ROLE}, {ADMIN_ROLE};",
        f"GRANT USAGE ON SCHEMA {schema} TO {CUSTOMER_ROLE}, {ADMIN_ROLE};",
        "",
        "-- Shared tables: both services read and write.",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {q(c['shared'])} TO {CUSTOMER_ROLE}, {ADMIN_ROLE};",
        "",
        "-- Customer logins: the customer service owns them, the admin service only reads.",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {q(c['customer_sessions'])} TO {CUSTOMER_ROLE};",
        f"GRANT SELECT ON TABLE {q(c['customer_sessions'])} TO {ADMIN_ROLE};",
        "",
        "-- History is append-only for both: insert and select. The customer service may blank who did it when a person erases their account.",
        f"GRANT SELECT, INSERT ON TABLE {q(c['append_only'])} TO {CUSTOMER_ROLE}, {ADMIN_ROLE};",
    ]
    for table, cols in APPEND_ONLY_CUSTOMER_UPDATE.items():
        out.append(f'GRANT UPDATE ({", ".join(cols)}) ON TABLE {schema}."{table}" TO {CUSTOMER_ROLE};')
    out += ["", "-- Support access (ADR 089): each service holds only the rights of its own side."]
    for table, by_role in SUPPORT_RIGHTS.items():
        for role, rights in by_role.items():
            out.append(f'GRANT {", ".join(rights)} ON TABLE {schema}."{table}" TO {role};')
        for role, cols in SUPPORT_COLUMN_UPDATE.get(table, {}).items():
            out.append(f'GRANT UPDATE ({", ".join(cols)}) ON TABLE {schema}."{table}" TO {role};')
    out += [
        "",
        "-- Staff accounts and logins: the admin service only. The customer role has no right on them at all.",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {q(c['staff'])} TO {ADMIN_ROLE};",
        "",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {CUSTOMER_ROLE}, {ADMIN_ROLE};",
        "",
        "-- Row level security is on for every platform table with no policy: without one a role sees no row and may not insert.",
        "-- One policy per role and table it may touch ('all rows'); the grants above still decide what it may do.",
        "-- Safe to run again: the old policy is dropped first.",
    ]
    for role in (CUSTOMER_ROLE, ADMIN_ROLE):
        for table in tables_of(role):
            out.append(f'DROP POLICY IF EXISTS {policy_name(role)} ON {schema}."{table}";')
            out.append(f'CREATE POLICY {policy_name(role)} ON {schema}."{table}" AS PERMISSIVE FOR ALL TO {role} USING (true) WITH CHECK (true);')
    out += ["COMMIT;", ""]
    return "\n".join(out)


def revert_sql(schema: str = "public") -> str:
    """The undo: drops the policies this script made, takes every right away from both roles and drops the roles. Run it as the owner."""
    out = [
        "-- Generated by backend/scripts/db_roles.py --revert (ADR 084). Undoes db_roles.py: run as the owner, after both services stopped using the roles.",
        "BEGIN;",
    ]
    for role in (CUSTOMER_ROLE, ADMIN_ROLE):
        out += [f'DROP POLICY IF EXISTS {policy_name(role)} ON {schema}."{table}";' for table in tables_of(role)]
    out += [
        f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {CUSTOMER_ROLE}, {ADMIN_ROLE};",
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM {CUSTOMER_ROLE}, {ADMIN_ROLE};",
        f"REVOKE ALL ON SCHEMA {schema} FROM {CUSTOMER_ROLE}, {ADMIN_ROLE};",
        f"DROP ROLE IF EXISTS {CUSTOMER_ROLE};",
        f"DROP ROLE IF EXISTS {ADMIN_ROLE};",
        "COMMIT;",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the grants for the customer and admin database roles (or, with --revert, the SQL that undoes them).")
    parser.add_argument("--schema", default="public")
    parser.add_argument("--revert", action="store_true", help="print the undo instead of the grants")
    args = parser.parse_args()
    sys.stdout.write(revert_sql(args.schema) if args.revert else sql(args.schema))


if __name__ == "__main__":
    main()
