"""Platform database: plain SQLAlchemy 2 sessions (no Flask-SQLAlchemy). One session per request, committed explicitly by the route,
rolled back and closed on teardown. The engine is created lazily so the app starts (and /healthz works) without a database."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, g
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.shared.config import Settings
from app.shared.errors import AppError


class Base(DeclarativeBase):
    pass


class DatabaseUnavailableError(AppError):
    status, code, title = 503, "database_unavailable", "Database not configured"


def engine_options(url: str) -> dict[str, Any]:
    """Supabase's transaction pooler (port 6543) cannot keep prepared statements, which psycopg 3 creates after a few repeats of a query."""
    pooled = "pooler.supabase.com" in url or ":6543/" in url
    return {"pool_pre_ping": True, **({"connect_args": {"prepare_threshold": None}} if pooled else {})}


def add_missing_columns(engine: Engine) -> list[str]:
    """No migrations yet (ADR 027): create_all never alters an existing table, so add nullable columns that the models have and the database lacks.
    Returns the added columns as table.column. Anything else (types, NOT NULL, renames) is still a manual change."""
    added: list[str] = []
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            have = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have and col.nullable and not col.primary_key:
                    ddl = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}'))
                    added.append(f"{table.name}.{col.name}")
    return added


def init_db(app: Flask, settings: Settings) -> None:
    holder: dict[str, object] = {}

    def engine() -> Engine:
        if not settings.DATABASE_URL:
            raise DatabaseUnavailableError("DATABASE_URL is not set")
        if "engine" not in holder:
            eng = create_engine(settings.DATABASE_URL, **engine_options(settings.DATABASE_URL))
            holder["engine"] = eng
            holder["factory"] = sessionmaker(bind=eng, expire_on_commit=False)
        return holder["engine"]  # type: ignore[return-value]

    def factory() -> sessionmaker[Session]:
        engine()
        return holder["factory"]  # type: ignore[return-value]

    app.extensions["db_engine"] = engine
    app.extensions["db_factory"] = factory

    @app.teardown_appcontext
    def _close(_exc: BaseException | None) -> None:
        session: Session | None = g.pop("db", None)
        if session is not None:
            session.rollback()  # anything not committed explicitly is discarded
            session.close()

    if settings.DATABASE_URL:

        def ready() -> None:
            with engine().connect() as conn:
                conn.execute(text("select 1"))

        app.extensions.setdefault("readiness_checks", {})["platform_database"] = ready


def get_session() -> Session:
    from flask import current_app

    if "db" not in g:
        factory: Callable[[], sessionmaker[Session]] = current_app.extensions["db_factory"]
        g.db = factory()()
    return g.db  # type: ignore[no-any-return]
