"""Tests for membership period model (2 tests), e.g. membership period defaults; membership period unique constraint on membership and period start."""
from datetime import date

from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _make_membership():
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipType

    db.session.add(MembershipType(name="individual", price=200, billing_frequency="monthly"))
    member = Member(name="Priya Das", email="priya@example.com")
    db.session.add(member)
    db.session.commit()
    membership = Membership(
        member_id=member.id, membership_type="individual", status="active",
        start_date=date(2027, 1, 1),
    )
    db.session.add(membership)
    db.session.commit()
    return membership


def test_membership_period_defaults():
    from app.memberships.models import MembershipPeriod

    app = _new_app()
    with app.app_context():
        membership = _make_membership()
        period = MembershipPeriod(
            membership_id=membership.id, period_start=date(2027, 1, 1),
            period_end=date(2027, 1, 31), label="January 2027", amount=20000,
        )
        db.session.add(period)
        db.session.commit()

        saved = MembershipPeriod.query.one()
        assert saved.status == "unpaid"
        assert saved.currency == "NOK"
        assert saved.paid_at is None
        db.drop_all()


def test_membership_period_unique_constraint_on_membership_and_period_start():
    from sqlalchemy.exc import IntegrityError

    from app.memberships.models import MembershipPeriod

    app = _new_app()
    with app.app_context():
        membership = _make_membership()
        db.session.add(
            MembershipPeriod(
                membership_id=membership.id, period_start=date(2027, 1, 1),
                period_end=date(2027, 1, 31), label="January 2027", amount=20000,
            )
        )
        db.session.commit()

        db.session.add(
            MembershipPeriod(
                membership_id=membership.id, period_start=date(2027, 1, 1),
                period_end=date(2027, 1, 31), label="January 2027 (dup)", amount=20000,
            )
        )
        try:
            db.session.commit()
            assert False, "expected an IntegrityError"
        except IntegrityError:
            db.session.rollback()
        db.drop_all()
