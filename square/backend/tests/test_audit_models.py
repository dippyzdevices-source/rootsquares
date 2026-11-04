"""Tests for audit models (3 tests), e.g. audit log defaults; log action creates a row with the given fields; log action records target type and id."""
from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_audit_log_defaults():
    from app.auth.models import User
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="admin@example.com", role="admin")
        db.session.add(user)
        db.session.commit()

        entry = AuditLog(actor_user_id=user.id, action="settings_updated", description="test")
        db.session.add(entry)
        db.session.commit()

        saved = AuditLog.query.one()
        assert saved.target_type is None
        assert saved.target_id is None
        assert saved.created_at is not None
        db.drop_all()


def test_log_action_creates_a_row_with_the_given_fields():
    from app.auth.models import User
    from app.audit.models import AuditLog
    from app.audit.service import log_action

    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="admin@example.com", role="admin")
        db.session.add(user)
        db.session.commit()

        log_action(user, "settings_updated", "Updated site contact settings")

        saved = AuditLog.query.one()
        assert saved.actor_user_id == user.id
        assert saved.action == "settings_updated"
        assert saved.description == "Updated site contact settings"
        assert saved.target_type is None
        assert saved.target_id is None
        db.drop_all()


def test_log_action_records_target_type_and_id():
    from app.auth.models import User
    from app.audit.models import AuditLog
    from app.audit.service import log_action

    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="admin@example.com", role="admin")
        db.session.add(user)
        db.session.commit()

        log_action(user, "event_deleted", 'Deleted event "Durga Puja 2026"',
                  target_type="event", target_id=42)

        saved = AuditLog.query.one()
        assert saved.target_type == "event"
        assert saved.target_id == 42
        db.drop_all()
