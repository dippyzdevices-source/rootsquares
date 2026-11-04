"""Tests for membership model (2 tests), e.g. membership has expected defaults; a member can have multiple memberships over time."""
from datetime import date

from app import create_app
from app.auth.models import User
from app.members.models import Member
from app.memberships.models import Membership
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def test_membership_has_expected_defaults():
    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="a@b.com")
        db.session.add(user)
        db.session.commit()
        member = Member(user_id=user.id, name="Priya Das")
        db.session.add(member)
        db.session.commit()

        membership = Membership(
            member_id=member.id, membership_type="individual", start_date=date(2026, 1, 1)
        )
        db.session.add(membership)
        db.session.commit()

        saved = Membership.query.filter_by(member_id=member.id).one()
        assert saved.status == "pending"
        assert saved.end_date is None
        assert saved.created_at is not None

        db.drop_all()


def test_a_member_can_have_multiple_memberships_over_time():
    app = _new_app()
    with app.app_context():
        user = User(auth_user_id="sb-1", auth_provider="supabase", email="a@b.com")
        db.session.add(user)
        db.session.commit()
        member = Member(user_id=user.id, name="Priya Das")
        db.session.add(member)
        db.session.commit()

        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="expired",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
            )
        )
        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="active",
                start_date=date(2026, 1, 1),
            )
        )
        db.session.commit()

        assert Membership.query.filter_by(member_id=member.id).count() == 2

        db.drop_all()
