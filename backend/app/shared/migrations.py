"""Alembic for the platform database, driven from `flask db ...` (no Flask-Migrate: the app uses plain SQLAlchemy sessions).
A database made by the older `init-db` (tables, no alembic_version) is adopted once: missing columns are added, it is stamped at the baseline
revision, then upgraded."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from app.shared.config import Settings
from app.shared.db import Base, add_missing_columns

BACKEND = Path(__file__).resolve().parents[2]
BASELINE = "0001"


def alembic_config(settings: Settings) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
    return cfg


def enable_rls(engine: Engine) -> None:
    """Supabase serves the public schema over its REST API: row level security without policies shuts that door (the app's own role bypasses it)."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            conn.execute(text(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY'))


def upgrade(settings: Settings, engine: Engine, revision: str = "head") -> list[str]:
    """Bring the database to `revision`. Returns notes about what was adopted from the old init-db."""
    notes: list[str] = []
    cfg = alembic_config(settings)
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables and tables & {t.name for t in Base.metadata.sorted_tables}:
        notes += [f"added column {c}" for c in add_missing_columns(engine)]
        command.stamp(cfg, BASELINE)
        notes.append(f"existing database adopted at revision {BASELINE}")
    command.upgrade(cfg, revision)
    enable_rls(engine)
    return notes
