# ruff: noqa: F811  (the `api` fixture is imported from the helpers, so test arguments shadow it)
"""BILLING_ENFORCE (waking) and the settings rules."""

import datetime as dt
from types import SimpleNamespace

import pytest

from app.platform import billing
from app.shared.config import Settings
from tests.billing.helpers import HEADERS, NOW, PREFIX, RecordingExecutor, _checkout, _run, _set, _square, api  # noqa: F401


def test_waking_needs_a_paid_period_only_when_billing_is_enforced() -> None:
    now = dt.datetime.now(dt.UTC)
    free = SimpleNamespace(BILLING_ENFORCE=False)
    strict = SimpleNamespace(BILLING_ENFORCE=True)
    unpaid = SimpleNamespace(paid_until=None)
    paid = SimpleNamespace(paid_until=now + dt.timedelta(days=3))
    lapsed = SimpleNamespace(paid_until=now - dt.timedelta(days=1))
    assert billing.wake_needs_payment(free, unpaid) is False  # type: ignore[arg-type]
    assert billing.wake_needs_payment(strict, unpaid) is True  # type: ignore[arg-type]
    assert billing.wake_needs_payment(strict, lapsed) is True  # type: ignore[arg-type]
    assert billing.wake_needs_payment(strict, paid) is False  # type: ignore[arg-type]


def test_stripe_needs_its_keys() -> None:
    with pytest.raises(ValueError, match="STRIPE_SECRET_KEY"):
        Settings(BILLING_PROVIDER="stripe", STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="")  # explicit empty: a real .env must not satisfy it


def test_a_test_clock_needs_a_test_key() -> None:
    kw = {"_env_file": None, "ENV": "test", "BILLING_PROVIDER": "stripe", "STRIPE_WEBHOOK_SECRET": "whsec_x", "STRIPE_TEST_CLOCK_ID": "clock_1"}
    with pytest.raises(ValueError, match="STRIPE_TEST_CLOCK_ID"):
        Settings(STRIPE_SECRET_KEY="sk_live_x", **kw)  # type: ignore[arg-type]
    assert Settings(STRIPE_SECRET_KEY="sk_test_x", **kw).STRIPE_TEST_CLOCK_ID == "clock_1"  # type: ignore[arg-type]
