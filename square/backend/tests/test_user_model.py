"""Tests for user model (2 tests), e.g. user has expected defaults; user requires a unique auth user id."""
from app import create_app
from app.auth.models import User  # noqa: F401  (import registers it on db.metadata)
from app.extensions import db


def test_user_has_expected_defaults():
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        user = User(auth_user_id="sb-123", auth_provider="supabase", email="a@b.com")
        db.session.add(user)
        db.session.commit()

        saved = User.query.filter_by(auth_user_id="sb-123", auth_provider="supabase").one()
        assert saved.email == "a@b.com"
        assert saved.role == "member"
        assert saved.phone is None
        assert saved.created_at is not None

        db.drop_all()


def test_user_requires_a_unique_auth_user_id():
    from sqlalchemy.exc import IntegrityError

    import pytest

    app = create_app("testing")
    with app.app_context():
        db.create_all()

        db.session.add(User(auth_user_id="dup", auth_provider="supabase", email="a@b.com"))
        db.session.commit()

        db.session.add(User(auth_user_id="dup", auth_provider="supabase", email="c@d.com"))
        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()
        db.drop_all()
