# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""The money rules as plain functions (W12-R22): upgrade differences, the Event pass credit, the refund window to the second, who needs to pay first, and the
shape of a refund. No HTTP: these are the rules every flow above is built from."""

import datetime as dt
import uuid
from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy import select

from app.platform import billing, plans
from app.platform.models import BillingOrder, Square
from app.shared.config import Settings
from app.shared.errors import BadRequestError, ConflictError
from tests.billing.helpers import NOW, _square, api  # noqa: F401


@pytest.fixture
def db(api: Flask):
    session = api.extensions["db_factory"]()()
    yield session
    session.close()


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, ENV="test", **kw)  # type: ignore[call-arg]


def _row(api: Flask, slug: str, db) -> Square:
    return db.scalar(select(Square).where(Square.slug == slug))


def test_the_application_holds_no_price_and_a_price_that_is_not_set_cannot_be_charged(tmp_path) -> None:
    from app.main import create_app
    from app.platform.models import Base
    from tests.conftest import make_settings

    app = create_app(make_settings(DATABASE_URL=f"sqlite:///{tmp_path / 'empty.db'}"))
    Base.metadata.create_all(app.extensions["db_engine"]())
    session = app.extensions["db_factory"]()()
    assert billing.list_prices(session) == []  # nothing is created behind the admin's back
    assert set(billing.PRICE_KEYS) == {
        "launch.roots",
        "launch.square",
        "launch.grove",
        "launch.event",
        "running.keep.month",
        "running.keep.year",
        "running.live.month",
        "running.live.year",
    }
    with pytest.raises(billing.PriceNotSet, match="launch.roots is not set"):
        billing.price_of(session, "launch.roots")
    billing.set_price(session, "launch.roots", 9_900)
    assert billing.price_of(session, "launch.roots") == 9_900 and billing.CURRENCY == "USD"
    session.close()


def test_a_changed_price_is_what_new_orders_use(api: Flask, db) -> None:
    next(p for p in billing.list_prices(db) if p.key == "launch.roots").amount_minor = 9_900
    db.commit()
    assert billing.price_of(db, "launch.roots") == 9_900
    with pytest.raises(Exception, match="is not set"):
        billing.price_of(db, "launch.nope")


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        ("roots", "square", 29_900 - 14_900),
        ("roots", "grove", 39_900 - 14_900),
        ("square", "grove", 39_900 - 29_900),
        ("grove", "grove", 0),
        ("grove", "roots", 0),
        ("square", "roots", 0),
        ("roots", "event", 0),  # the Event pass is not on the ladder
        ("event", "grove", 0),
        (None, "grove", 0),  # a square from before the packages counts as Grove (it keeps every module), so there is nothing above it
    ],
)
def test_the_upgrade_difference(db, current, target, expected) -> None:
    assert billing.upgrade_amount(db, current, target) == expected


@pytest.mark.parametrize(("target", "interval", "expected"), [("roots", "month", 14_900 - 2_500 + 2_500), ("grove", "year", 39_900 - 2_500 + 25_000)])
def test_an_event_pass_upgrade_credits_the_fifteen_dollars(db, target, interval, expected) -> None:
    assert billing.event_upgrade_amount(db, target, interval) == expected
    with pytest.raises(BadRequestError):
        billing.event_upgrade_amount(db, "event", "month")
    with pytest.raises(BadRequestError):
        billing.event_upgrade_amount(db, "roots", "week")


@pytest.mark.parametrize(
    ("provider", "enforce", "expected"),
    [("fake", False, False), ("fake", True, True), ("stripe", False, True), ("stripe", True, True)],
)
def test_money_is_on_with_stripe_or_enforcing(provider, enforce, expected) -> None:
    s = _settings(BILLING_PROVIDER=provider, BILLING_ENFORCE=enforce, STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_x")
    assert billing.payment_before_build(s) is expected
    assert billing.event_pass_payment_required(s) is expected


def test_the_refund_window_is_fourteen_days_to_the_second() -> None:
    s = _settings()
    paid = dt.datetime(2026, 10, 1, 9, 0, tzinfo=dt.UTC)
    order = SimpleNamespace(kind="first", status="paid", paid_at=paid)
    assert billing.refundable(order, s, now=paid + dt.timedelta(days=14)) is True
    assert billing.refundable(order, s, now=paid + dt.timedelta(days=14, seconds=1)) is False
    assert billing.refundable(order, _settings(BILLING_REFUND_DAYS=3), now=paid + dt.timedelta(days=4)) is False
    for kind in ("running", "event_pass"):  # renewals and the Event pass can be refunded too (W13-R31)
        assert billing.refundable(SimpleNamespace(kind=kind, status="paid", paid_at=paid), s, now=paid) is True
    for kind in ("upgrade", "event_upgrade"):  # an upgrade cannot be (it would be a free upgrade)
        assert billing.refundable(SimpleNamespace(kind=kind, status="paid", paid_at=paid), s, now=paid) is False
    for status in ("pending", "cancelled", "failed", "refunded"):
        assert billing.refundable(SimpleNamespace(kind="first", status=status, paid_at=paid), s, now=paid) is False
    assert billing.refundable(SimpleNamespace(kind="first", status="paid", paid_at=None), s, now=paid) is False


def test_marking_a_refund_ends_the_paid_time_and_the_subscription(api: Flask, db) -> None:
    _square(api, "mr1", "roots")
    sq = _row(api, "sq-mr1", db)
    sq.stripe_subscription_id, sq.renewal_cancelled, sq.payment_failed_at, sq.paid_until = "sub_1", True, NOW, NOW + dt.timedelta(days=30)
    order = BillingOrder(square_id=sq.id, kind="first", amount_minor=17_400, status="paid", provider="stripe")
    billing.mark_refunded(order, sq, now=NOW)
    assert order.status == "refunded"
    assert (sq.stripe_subscription_id, sq.renewal_cancelled, sq.payment_failed_at) == (None, False, None)
    assert sq.paid_until == NOW
    assert billing.first_payment_due(db, sq) is True  # a refunded first payment is not a payment


def test_who_owes_a_first_payment(api: Flask, db) -> None:
    for who, package in (("fd1", "roots"), ("fd2", "event")):
        _square(api, who, package)
    roots, event = _row(api, "sq-fd1", db), _row(api, "sq-fd2", db)
    assert billing.first_payment_due(db, roots) is True
    assert billing.first_payment_due(db, event) is False  # the Event pass pays at creation
    roots.launch_package = None  # a square from before the packages
    assert billing.first_payment_due(db, roots) is False
    roots.launch_package = "roots"
    db.add(BillingOrder(square_id=roots.id, kind="first", amount_minor=1, status="pending", provider="fake"))
    db.flush()
    assert billing.first_payment_due(db, roots) is True  # an order that is not paid does not count
    db.add(BillingOrder(square_id=roots.id, kind="first", amount_minor=1, status="paid", provider="fake"))
    db.flush()
    assert billing.first_payment_due(db, roots) is False


def test_new_orders_refuse_what_makes_no_sense(api: Flask, db) -> None:
    _square(api, "no1", "roots")
    sq = _row(api, "sq-no1", db)
    uid = uuid.uuid4()
    with pytest.raises(ConflictError):  # nothing above Grove
        sq.launch_package = "grove"
        billing.new_upgrade_order(db, sq, "grove", uid, "fake")
    sq.launch_package = "roots"
    with pytest.raises(BadRequestError):
        billing.new_running_order(db, sq, "gold", "month", uid, "fake")
    with pytest.raises(BadRequestError):
        billing.new_running_order(db, sq, plans.LIVE, "week", uid, "fake")
    with pytest.raises(BadRequestError):
        billing.new_first_order(db, sq, "week", uid, "fake")
    with pytest.raises(ConflictError):
        billing.new_event_pass_order(db, sq, uid, "fake")  # not an Event pass awaiting payment
    with pytest.raises(ConflictError):
        billing.new_event_upgrade_order(db, sq, "grove", "month", uid, "fake")  # not an Event pass at all


def test_paying_early_adds_to_the_time_left_and_a_year_is_365_days(api: Flask, db) -> None:
    _square(api, "pe1", "roots")
    sq = _row(api, "sq-pe1", db)
    sq.paid_until = NOW + dt.timedelta(days=10)
    month = BillingOrder(square_id=sq.id, kind="running", running_plan="live", interval="month", amount_minor=2_500, provider="fake")
    year = BillingOrder(square_id=sq.id, kind="running", running_plan="live", interval="year", amount_minor=25_000, provider="fake")
    billing._apply_paid(sq, month, NOW)
    assert sq.paid_until == NOW + dt.timedelta(days=40)
    billing._apply_paid(sq, year, NOW)
    assert sq.paid_until == NOW + dt.timedelta(days=40 + 365)
    sq.paid_until = NOW - dt.timedelta(days=5)  # lapsed: the new period starts now, not in the past
    billing._apply_paid(sq, month, NOW)
    assert sq.paid_until == NOW + dt.timedelta(days=30)
