"""Tests for membership period generation (6 tests), e.g. monthly type generates twelve periods; yearly type generates one period; quarterly type generates four periods."""
from datetime import date

from app import create_app
from app.extensions import db


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _make_membership(billing_frequency="monthly", price=200, contact_for_price=False, start_date=None):
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipType

    type_name = f"type-{billing_frequency}-{contact_for_price}"
    db.session.add(
        MembershipType(
            name=type_name, price=price, billing_frequency=billing_frequency,
            contact_for_price=contact_for_price,
        )
    )
    member = Member(name="Priya Das", email="priya@example.com")
    db.session.add(member)
    db.session.commit()
    membership = Membership(
        member_id=member.id, membership_type=type_name, status="active",
        start_date=start_date or date(2027, 6, 15),
    )
    db.session.add(membership)
    db.session.commit()
    return membership


def test_monthly_type_generates_twelve_periods():
    from app.memberships.models import MembershipPeriod
    from app.memberships.service import generate_periods_for_membership

    app = _new_app()
    with app.app_context():
        membership = _make_membership(billing_frequency="monthly", price=200)

        created = generate_periods_for_membership(membership)

        assert len(created) == 12
        periods = MembershipPeriod.query.order_by(MembershipPeriod.period_start).all()
        assert len(periods) == 12
        assert periods[0].period_start == date(2027, 1, 1)
        assert periods[0].period_end == date(2027, 1, 31)
        assert periods[0].label == "January 2027"
        assert periods[0].amount == 20000
        # February is calendar-correct even in a non-leap year.
        assert periods[1].period_start == date(2027, 2, 1)
        assert periods[1].period_end == date(2027, 2, 28)
        assert periods[-1].period_start == date(2027, 12, 1)
        assert periods[-1].period_end == date(2027, 12, 31)
        db.drop_all()


def test_yearly_type_generates_one_period():
    from app.memberships.models import MembershipPeriod
    from app.memberships.service import generate_periods_for_membership

    app = _new_app()
    with app.app_context():
        membership = _make_membership(billing_frequency="yearly", price=2400)

        created = generate_periods_for_membership(membership)

        assert len(created) == 1
        period = MembershipPeriod.query.one()
        assert period.period_start == date(2027, 1, 1)
        assert period.period_end == date(2027, 12, 31)
        assert period.label == "2027"
        assert period.amount == 240000
        db.drop_all()


def test_quarterly_type_generates_four_periods():
    from app.memberships.models import MembershipPeriod
    from app.memberships.service import generate_periods_for_membership

    app = _new_app()
    with app.app_context():
        membership = _make_membership(billing_frequency="quarterly", price=600)

        created = generate_periods_for_membership(membership)

        assert len(created) == 4
        periods = MembershipPeriod.query.order_by(MembershipPeriod.period_start).all()
        assert periods[0].period_start == date(2027, 1, 1)
        assert periods[0].period_end == date(2027, 3, 31)
        assert periods[0].label == "Q1 2027"
        assert periods[0].amount == 60000
        assert periods[1].period_start == date(2027, 4, 1)
        assert periods[1].period_end == date(2027, 6, 30)
        assert periods[1].label == "Q2 2027"
        assert periods[2].period_start == date(2027, 7, 1)
        assert periods[2].period_end == date(2027, 9, 30)
        assert periods[2].label == "Q3 2027"
        assert periods[3].period_start == date(2027, 10, 1)
        assert periods[3].period_end == date(2027, 12, 31)
        assert periods[3].label == "Q4 2027"
        db.drop_all()


def test_lifetime_type_generates_no_periods():
    from app.memberships.models import MembershipPeriod
    from app.memberships.service import generate_periods_for_membership

    app = _new_app()
    with app.app_context():
        membership = _make_membership(billing_frequency="yearly", contact_for_price=True)

        created = generate_periods_for_membership(membership)

        assert created == []
        assert MembershipPeriod.query.count() == 0
        db.drop_all()


def test_generation_is_idempotent():
    from app.memberships.models import MembershipPeriod
    from app.memberships.service import generate_periods_for_membership

    app = _new_app()
    with app.app_context():
        membership = _make_membership(billing_frequency="monthly", price=200)

        generate_periods_for_membership(membership)
        second_call_created = generate_periods_for_membership(membership)

        assert second_call_created == []
        assert MembershipPeriod.query.count() == 12
        db.drop_all()


def test_generation_does_not_alter_an_existing_period_after_a_price_change():
    from app.memberships.models import MembershipPeriod, MembershipType
    from app.memberships.service import generate_periods_for_membership

    app = _new_app()
    with app.app_context():
        membership = _make_membership(billing_frequency="monthly", price=200)
        generate_periods_for_membership(membership)

        membership_type = db.session.get(MembershipType, membership.membership_type)
        membership_type.price = 999
        db.session.commit()

        generate_periods_for_membership(membership)

        january = MembershipPeriod.query.filter_by(period_start=date(2027, 1, 1)).one()
        assert january.amount == 20000  # unchanged despite the price bump
        db.drop_all()
