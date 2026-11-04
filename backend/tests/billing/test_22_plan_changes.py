# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""Live to Keep from the next renewal, Keep to Live at once, a waiting downgrade cancelled (W18-R34, docs/plans/plan-changes-plan.md)."""

import datetime as dt
import uuid
from types import SimpleNamespace

import pytest
import stripe
from flask import Flask
from sqlalchemy import select

from app.platform import billing, trial
from app.platform.models import AuditLog, BillingOrder, Square
from tests.billing.helpers import NOW, PREFIX, RecordingExecutor, _run, _square, api  # noqa: F401

DAY = dt.timedelta(days=1)


def _renewing(api: Flask, who: str, left_days: int = 15):
    """A square with a paid first payment and the subscription `sub_<who>`, paid until `left_days` from now: (client, headers, square, first order id)."""
    c, h, sq = _square(api, who, "roots")
    first = c.post(f"{PREFIX}/squares/{sq['id']}/billing/checkout", json={"kind": "first", "interval": "month"}, headers=h).json["order_id"]
    db = api.extensions["db_factory"]()()
    try:
        billing.apply_event(db, billing.PaymentEvent(order_id=uuid.UUID(first), paid=True, subscription_id=f"sub_{who}"), now=NOW)
        row = db.scalar(select(Square).where(Square.slug == f"sq-{who}"))
        row.paid_until = dt.datetime.now(dt.UTC) + left_days * DAY
        row.status = "ready"
        db.commit()
    finally:
        db.close()
    return c, h, sq, first


def _row(api: Flask, who: str, **set_):
    db = api.extensions["db_factory"]()()
    try:
        row = db.scalar(select(Square).where(Square.slug == f"sq-{who}"))
        for k, v in set_.items():
            setattr(row, k, v)
        db.commit()
        db.refresh(row)
        return {c: getattr(row, c) for c in ("running_plan", "pending_running_plan", "paid_until", "sleep_state", "stripe_subscription_id")}
    finally:
        db.close()


def _change(c, h, sq, plan):
    return c.post(f"{PREFIX}/squares/{sq['id']}/billing/plan-change", json={"plan": plan}, headers=h)


def test_a_downgrade_waits_for_the_renewal_and_the_renewal_is_a_keep_period(api: Flask) -> None:
    c, h, sq, first = _renewing(api, "pc1")
    got = _change(c, h, sq, "keep")
    assert got.status_code == 200 and got.json["pending_plan"] == "keep" and got.json["running_plan"] == "live" and got.json["sleep_state"] == "awake"
    assert _change(c, h, sq, "keep").json["code"] == "same_plan"  # asking twice changes nothing
    ends = _row(api, "pc1")["paid_until"]
    db = api.extensions["db_factory"]()()
    try:
        renewal = billing.PaymentEvent(order_id=uuid.UUID(first), subscription_id="sub_pc1", invoice_id="in_pc1", amount_minor=500)
        order = billing.apply_event(db, renewal, now=dt.datetime.now(dt.UTC) + 16 * DAY)
        db.commit()
        assert order.running_plan == "keep" and order.amount_minor == 500  # the new period is a Keep period
        row = db.scalar(select(Square).where(Square.slug == "sq-pc1"))
        assert row.pending_running_plan is None and row.paid_until.replace(tzinfo=dt.UTC) > ends.replace(tzinfo=dt.UTC)
        assert db.scalar(select(AuditLog.id).where(AuditLog.action == "billing.plan_applied", AuditLog.entity_id == str(row.id)).limit(1)) is not None
    finally:
        db.close()


def test_a_waiting_downgrade_can_be_cancelled_and_then_the_renewal_is_live_again(api: Flask) -> None:
    c, h, sq, first = _renewing(api, "pc2")
    assert _change(c, h, sq, "keep").json["pending_plan"] == "keep"
    back = _change(c, h, sq, "live")
    assert back.status_code == 200 and back.json["pending_plan"] is None and back.json["running_plan"] == "live"
    assert _change(c, h, sq, "live").json["code"] == "same_plan"  # already on Live
    db = api.extensions["db_factory"]()()
    try:
        renewal = billing.PaymentEvent(order_id=uuid.UUID(first), subscription_id="sub_pc2", invoice_id="in_pc2", amount_minor=2500)
        order = billing.apply_event(db, renewal, now=dt.datetime.now(dt.UTC) + 16 * DAY)
        assert order.running_plan == "live"
    finally:
        db.close()


def test_an_upgrade_from_keep_is_charged_for_the_rest_of_the_period_and_wakes_the_site(api: Flask) -> None:
    c, h, sq, _first = _renewing(api, "pc3", left_days=15)
    _row(api, "pc3", running_plan="keep", sleep_state="sleeping")
    got = _change(c, h, sq, "live")
    assert got.status_code == 200 and got.json["running_plan"] == "live" and got.json["pending_plan"] is None
    db = api.extensions["db_factory"]()()
    try:
        order = db.scalars(select(BillingOrder).where(BillingOrder.square_id == uuid.UUID(sq["id"]), BillingOrder.provider_ref.like("fake_inv_%"))).one()
        assert order.running_plan == "live" and order.status == "paid" and 0 < order.amount_minor <= 1000  # about half of the 2000 difference
    finally:
        db.close()
    assert c.get(f"{PREFIX}/squares/{sq['id']}/billing/orders", headers=h).status_code == 200


def test_the_old_instant_switch_is_closed_for_a_square_that_renews(api: Flask) -> None:
    c, h, sq, _first = _renewing(api, "pc4")
    refused = c.put(f"{PREFIX}/squares/{sq['id']}/running-plan", json={"running_plan": "keep"}, headers=h)
    assert refused.status_code == 409 and refused.json["code"] == "plan_change_required"
    c2, h2, sq2 = _square(api, "pc4b", "roots")  # a square with no subscription still sleeps on request
    assert c2.put(f"{PREFIX}/squares/{sq2['id']}/running-plan", json={"running_plan": "keep"}, headers=h2).status_code == 200


def test_the_refusals_say_why(api: Flask) -> None:
    c, h, sq, _first = _renewing(api, "pc5")
    assert _change(c, h, sq, "gold").json["code"] == "bad_plan"
    assert _change(c, h, sq, "live").json["code"] == "same_plan"
    _row(api, "pc5", payment_failed_at=dt.datetime.now(dt.UTC))
    assert _change(c, h, sq, "keep").json["code"] == "payment_failed"
    _row(api, "pc5", payment_failed_at=None, running_plan="keep", renewal_cancelled=True)
    assert _change(c, h, sq, "live").json["code"] == "resume_first"  # a cancelled renewal cannot be upgraded in place
    _row(api, "pc5", running_plan="event")
    assert _change(c, h, sq, "keep").json["code"] == "event_pass"


def test_without_a_subscription_a_downgrade_is_applied_by_the_daily_job_when_the_paid_time_ends(api: Flask) -> None:
    c, h, sq, _first = _renewing(api, "pc6")
    _row(api, "pc6", stripe_subscription_id=None)  # the renewal was never made, or has ended
    assert _change(c, h, sq, "keep").json["pending_plan"] == "keep"
    _row(api, "pc6", paid_until=NOW + 5 * DAY)
    assert _run(api, apply=True, slept=[]) == []  # the paid time is not over: the site stays live
    _row(api, "pc6", paid_until=NOW - DAY)
    slept: list[str] = []
    db = api.extensions["db_factory"]()()  # the job as the command runs it: applied and committed (the helper `_run` rolls back)
    try:
        settings = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})
        actions = trial.run(db, settings, now=NOW, apply=True, sleep=lambda _s, sq: slept.append(sq.slug))
        db.commit()
    finally:
        db.close()
    assert {"slug": "sq-pc6", "action": "sleep", "reason": "plan_change"} in actions and slept == ["sq-pc6"]
    row = _row(api, "pc6")
    assert row["running_plan"] == "keep" and row["pending_running_plan"] is None


def test_the_charge_of_an_upgrade_is_the_difference_for_the_time_left() -> None:
    end = NOW + 15 * DAY
    assert billing.upgrade_charge_minor(500, 2500, end, NOW, "month") == 1000
    assert billing.upgrade_charge_minor(500, 2500, end, NOW + 15 * DAY, "month") == 0  # the period is over
    assert billing.upgrade_charge_minor(5000, 25000, NOW + 365 * DAY, NOW, "year") == 20000
    assert billing.upgrade_charge_minor(2500, 500, end, NOW, "month") == 0  # a cheaper plan is never charged here
    assert billing.upgrade_charge_minor(500, 2500, None, NOW, "month") == 0


# ---- the Stripe adapter (the SDK is stubbed; nothing leaves the machine) ----------------------------------------------------------------


def _stub(monkeypatch, invoice=None, update_error=None):
    seen: dict = {}
    sub = SimpleNamespace(to_dict=lambda: {"items": {"data": [{"id": "si_1"}]}})

    def retrieve(self, sid, params=None, options=None):
        return sub

    def products(self, params=None, options=None):
        seen["product"] = params
        return SimpleNamespace(id="prod_1")

    def update(self, sid, params=None, options=None):
        seen["update"] = params
        if update_error is not None:
            raise update_error
        return SimpleNamespace(to_dict=lambda: {"latest_invoice": invoice})

    monkeypatch.setattr("stripe._subscription_service.SubscriptionService.retrieve", retrieve)
    monkeypatch.setattr("stripe._subscription_service.SubscriptionService.update", update)
    monkeypatch.setattr("stripe._product_service.ProductService.create", products)
    return seen


def _stripe():
    return billing.StripeBillingProvider("sk_test_x", "whsec_x")


def test_stripe_a_change_for_the_next_renewal_leaves_the_paid_period_alone(monkeypatch) -> None:
    seen = _stub(monkeypatch)
    out = _stripe().change_plan("sub_1", "keep", "month", 500, 0.0, immediate=False)
    assert out.amount_minor == 0 and out.invoice_id is None
    up = seen["update"]
    assert up["proration_behavior"] == "none" and "payment_behavior" not in up
    item = up["items"][0]
    price = item["price_data"]
    assert item["id"] == "si_1" and price["unit_amount"] == 500 and price["recurring"] == {"interval": "month"} and price["product"] == "prod_1"
    assert seen["product"]["name"] == "rootsquares Keep (monthly)"


def test_stripe_an_upgrade_is_invoiced_at_once_and_only_a_paid_invoice_counts(monkeypatch) -> None:
    seen = _stub(monkeypatch, invoice={"id": "in_9", "status": "paid", "amount_paid": 1000})
    out = _stripe().change_plan("sub_1", "live", "month", 2500, 0.0, immediate=True)
    assert out.paid and out.amount_minor == 1000 and out.invoice_id == "in_9"
    assert seen["update"]["proration_behavior"] == "always_invoice" and seen["update"]["payment_behavior"] == "error_if_incomplete"
    _stub(monkeypatch, invoice={"id": "in_9", "status": "open", "amount_paid": 0})
    with pytest.raises(billing.PlanChangeDeclined):
        _stripe().change_plan("sub_1", "live", "month", 2500, 0.0, immediate=True)


def test_stripe_a_refused_card_changes_nothing_and_says_so(monkeypatch) -> None:
    _stub(monkeypatch, update_error=stripe.CardError("declined", "card", "card_declined"))
    with pytest.raises(billing.PlanChangeDeclined):
        _stripe().change_plan("sub_1", "live", "month", 2500, 0.0, immediate=True)
    _stub(monkeypatch, update_error=stripe.APIConnectionError("down"))
    with pytest.raises(billing.AppError) as exc:
        _stripe().change_plan("sub_1", "keep", "month", 500, 0.0, immediate=False)
    assert exc.value.code == "provider_error"


def test_the_executor_fixture_is_the_recording_one(api: Flask) -> None:
    api.extensions["executor"] = RecordingExecutor()  # a wake or a sleep is only recorded, never run, in these tests
    assert api.extensions["executor"] is not None


# ---- the e-mail when Keep starts (W18-R34) --------------------------------------------------------------------------------------------


def _applied(api: Flask, who: str, days_ago: int = 0) -> str:
    """The audit entry a started downgrade leaves (`_apply_renewal` and the daily job write it); returns its id."""
    db = api.extensions["db_factory"]()()
    try:
        row = db.scalar(select(Square).where(Square.slug == f"sq-{who}"))
        at = (dt.datetime.now(dt.UTC) - days_ago * DAY).replace(tzinfo=None)
        entry = AuditLog(action=trial.PLAN_ACTION, entity="square", entity_id=str(row.id), org_id=row.org_id, data={"running_plan": "keep"}, at=at)
        db.add(entry)
        db.commit()
        return str(entry.id)
    finally:
        db.close()


def _sweep(api: Flask, notify):
    db = api.extensions["db_factory"]()()
    try:
        out = trial.send_keep_notices(db, dt.datetime.now(dt.UTC), notify)
        db.commit()
        return out
    finally:
        db.close()


def test_the_keep_started_text_says_what_changed_what_it_costs_and_how_to_wake_it(api: Flask) -> None:
    _renewing(api, "pc7")
    db = api.extensions["db_factory"]()()
    try:
        row = db.scalar(select(Square).where(Square.slug == "sq-pc7"))
        subject, text = trial.keep_started_text(db, api.extensions["settings"], row)
        assert subject == f"{row.name} is now on Keep"
        assert "is now Keep, as you chose" in text and "asleep" in text and "Nothing has been deleted" in text
        assert "Keep costs $5.00 a month and renews on " in text and f"/squares/{row.id}/billing" in text
        assert "If you do nothing, Keep carries on." in text
        row.stripe_subscription_id = None
        _, plain = trial.keep_started_text(db, api.extensions["settings"], row)
        assert "Keep costs $5.00 a month." in plain and "renews on" not in plain  # no renewal: no renewal date
    finally:
        db.rollback()
        db.close()


def test_the_owner_is_told_once_that_keep_started_and_a_refused_mail_is_tried_again(api: Flask) -> None:
    _renewing(api, "pc8")
    _row(api, "pc8", running_plan="keep", sleep_state="sleeping")
    _applied(api, "pc8")
    assert _sweep(api, lambda *_a: False) == []  # no e-mail service: nothing recorded
    told: list[tuple[str, str]] = []
    assert _sweep(api, lambda _db, sq, reason: told.append((sq.slug, reason)) or True) == [{"slug": "sq-pc8", "action": "keep_notice"}]
    assert told == [("sq-pc8", "plan_change")]
    assert _sweep(api, lambda *_a: pytest.fail("told twice")) == []  # once per started downgrade


def test_nobody_is_told_for_a_square_back_on_live_or_for_an_old_entry(api: Flask) -> None:
    _renewing(api, "pc9")
    _applied(api, "pc9")  # the plan is Live again: nothing to say
    assert _sweep(api, lambda *_a: pytest.fail("told a Live square")) == []
    _renewing(api, "pc10")
    _row(api, "pc10", running_plan="keep")
    _applied(api, "pc10", days_ago=trial.NOTICE_DAYS + 2)
    assert _sweep(api, lambda *_a: pytest.fail("told long after")) == []


def test_the_daily_job_tells_the_owner_when_it_puts_the_square_to_keep(api: Flask) -> None:
    c, h, sq, _first = _renewing(api, "pc11")
    _row(api, "pc11", stripe_subscription_id=None)
    assert _change(c, h, sq, "keep").json["pending_plan"] == "keep"
    _row(api, "pc11", paid_until=NOW - DAY)
    told: list[str] = []
    db = api.extensions["db_factory"]()()
    try:
        settings = api.extensions["settings"].model_copy(update={"BILLING_ENFORCE": True})

        def sleep(_s, row) -> None:
            row.sleep_state = "sleeping"  # what the command does through the provider

        actions = trial.run(db, settings, now=NOW, apply=True, sleep=sleep, notify_keep=lambda _db, row, reason: told.append(row.slug) or True)
        db.commit()
    finally:
        db.close()
    assert {"slug": "sq-pc11", "action": "keep_notice"} in actions and told == ["sq-pc11"]
