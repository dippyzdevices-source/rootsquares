"""Tests for import batch model (1 tests), e.g. import batch has expected defaults."""
from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_import_batch_has_expected_defaults():
    from app.auth.models import User
    from app.imports.models import ImportBatch

    app = _new_app()
    with app.app_context():
        admin = User(auth_user_id="sb-admin", auth_provider="supabase", email="admin@example.com", role="admin")
        db.session.add(admin)
        db.session.commit()

        batch = ImportBatch(
            admin_user_id=admin.id,
            filename="members.xlsx",
            total_rows=10,
            members_created=3,
            memberships_created=8,
            failed_rows=2,
        )
        db.session.add(batch)
        db.session.commit()

        saved = ImportBatch.query.one()
        assert saved.filename == "members.xlsx"
        assert saved.total_rows == 10
        assert saved.members_created == 3
        assert saved.memberships_created == 8
        assert saved.failed_rows == 2
        assert saved.created_at is not None
        db.drop_all()
