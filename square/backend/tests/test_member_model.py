"""Tests for member model (3 tests), e.g. member has expected defaults; member requires a unique user id; member can exist without a linked user yet."""
import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.auth.models import User
from app.members.models import Member
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_member_has_expected_defaults():
    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="a@b.com")
        db.session.add(user)
        db.session.commit()

        member = Member(user_id=user.id, name="Priya Das")
        db.session.add(member)
        db.session.commit()

        saved = Member.query.filter_by(user_id=user.id).one()
        assert saved.name == "Priya Das"
        assert saved.address is None
        assert saved.family_info is None
        assert saved.created_at is not None

        db.drop_all()


def test_member_requires_a_unique_user_id():
    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-2", auth_provider="supabase", email="c@d.com")
        db.session.add(user)
        db.session.commit()

        db.session.add(Member(user_id=user.id, name="First"))
        db.session.commit()

        db.session.add(Member(user_id=user.id, name="Second"))
        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()
        db.drop_all()


def test_member_can_exist_without_a_linked_user_yet():
    app = _new_app()
    with app.app_context():
        member = Member(name="Priya Das", email="priya@example.com", phone="+4712345678")
        db.session.add(member)
        db.session.commit()

        saved = Member.query.filter_by(email="priya@example.com").one()
        assert saved.user_id is None
        assert saved.phone == "+4712345678"
        db.drop_all()
