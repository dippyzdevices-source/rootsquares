"""Tests for database (1 tests), e.g. database connection executes a query."""
from sqlalchemy import text

from app import create_app
from app.extensions import db


def test_database_connection_executes_a_query():
    app = create_app("testing")

    with app.app_context():
        result = db.session.execute(text("SELECT 1")).scalar()

        assert result == 1
