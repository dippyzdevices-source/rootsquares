"""Tests for migrations (2 tests), e.g. migrations build exactly the tables of the models; a database made by init db is adopted not recreated."""
from __future__ import annotations

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.platform import models  # noqa: F401  (registers the tables)
from app.shared.config import Settings
from app.shared.db import Base
from app.shared.migrations import upgrade


def _settings(url: str) -> Settings:
    return Settings(_env_file=None, ENV="test", DATABASE_URL=url)  # type: ignore[call-arg]


def test_migrations_build_exactly_the_tables_of_the_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    engine = create_engine(url)
    upgrade(_settings(url), engine)
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []  # a model change without a migration fails here


def test_a_database_made_by_init_db_is_adopted_not_recreated(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    notes = upgrade(_settings(url), engine)
    assert any("adopted" in n for n in notes)
    assert "alembic_version" in inspect(engine).get_table_names()
    assert upgrade(_settings(url), engine) == []  # running it again changes nothing
