"""Alembic environment for the platform database. The URL comes from the config object that app/shared/migrations.py fills from Settings;
the tables are the SQLAlchemy models of the platform."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from app.platform import models  # noqa: F401  (registers the tables on Base.metadata)
from app.shared.db import Base, engine_options

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url") or ""
    engine = create_engine(url, **engine_options(url))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
