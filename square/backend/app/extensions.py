from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.session import Session


class TenantSession(Session):
    """db.session, but pointed at the database of the square being served (rootsquares change W6-R26, see app/tenancy.py).
    When no square is being served (single-tenant mode, CLI commands, tests) it behaves exactly like flask-sqlalchemy's own session."""

    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):
        if bind is None:
            from app.tenancy import tenant_engine

            engine = tenant_engine()
            if engine is not None:
                return engine
        return super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)


db = SQLAlchemy(session_options={"class_": TenantSession})
migrate = Migrate()
