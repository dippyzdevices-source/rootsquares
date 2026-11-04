r"""What it is:   The migration runner for one square's own database.
What it does: Applies the square app's Alembic migrations to one square (found in the platform database) or to a new one (upgrade-env, used by provisioning).
How to run:   From square/backend: python scripts/square_db.py upgrade <slug> | upgrade-env.
Read before:  docs/setup/19-square-app.md and docs/setup/13-environment-variables.md.
Read after:   Restart the square server (5002); docs/setup/18-commands.md.

Apply the square app's database migrations to ONE square's own database (rootsquares W6-R28, W6-R35; not in bca-oslo).

    python scripts/square_db.py upgrade <slug>     a square that already exists: found in the platform database (PLATFORM_DATABASE_URL, FERNET_KEY in .env)
    python scripts/square_db.py upgrade-env        a square being created: the database comes in the environment variable SQUARE_DATABASE_URL

`upgrade-env` is what the platform's provisioning runs for every new square (SQUARE_TEMPLATE_CMD in backend/.env, guide 13). Both run
`flask db upgrade` with that square's own connection string. The connection string only travels through the child process's environment: it is
never printed and never put on a command line.
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / (os.environ.get("ENV_FILE", "").strip() or ".env.local"))  # W26-R51

from app.config import get_config  # noqa: E402
from app.tenancy import TenantDirectory, _sqlalchemy_url  # noqa: E402


# Supabase serves the `public` schema over its REST API with a key that every visitor's browser holds (it is needed for sign-in). Row level security without
# policies shuts that door; the square server's own role bypasses it. Every table gets it, including the ones a later migration adds (W11-R40).
RLS_SQL = """
DO $$ DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
  END LOOP;
END $$;
"""


def _enable_rls(db_url: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text(RLS_SQL))
    finally:
        engine.dispose()


def _upgrade(db_url: str, label: str) -> int:
    print(f"Upgrading the database of square {label}")
    env = {**os.environ, "DATABASE_URL": db_url}
    done = subprocess.run([sys.executable, "-m", "flask", "--app", "wsgi", "db", "upgrade"], cwd=BACKEND, env=env)
    if done.returncode == 0 and db_url.startswith("postgresql"):
        _enable_rls(db_url)
        print("Row level security is on for every table")
    return done.returncode


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "upgrade-env":
        url = os.environ.get("SQUARE_DATABASE_URL", "")
        if not url:
            print("SQUARE_DATABASE_URL is not set")
            return 1
        return _upgrade(_sqlalchemy_url(url), repr(os.environ.get("SQUARE_SLUG", "(new)")))
    if len(argv) == 3 and argv[1] == "upgrade":
        config = get_config()
        if not config.PLATFORM_DATABASE_URL:
            print("PLATFORM_DATABASE_URL is not set in square/backend/.env")
            return 1
        directory = TenantDirectory(config.PLATFORM_DATABASE_URL, config.FERNET_KEY, config.SQUARE_DOMAIN_SUFFIX, allow_localhost=True)
        tenant = directory.lookup(f"{argv[2]}.localhost")
        if tenant is None:
            print(f"No ready square called {argv[2]!r} (or its keys cannot be decrypted).")
            return 1
        return _upgrade(tenant.db_url, f"{tenant.slug!r} ({tenant.name})")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
