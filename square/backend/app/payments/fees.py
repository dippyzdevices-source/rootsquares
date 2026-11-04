"""Payment fees — one place. Two different things per payment method (Settings -> Payments):

* convenience fee  — what the customer is charged on top of the price (percent of the base).
* processing fee   — what the provider takes from us (percent of the amount charged + a fixed
                     part in øre). An estimate, snapshotted on `Payment.processing_fee_amount`
                     when the payment becomes paid, so later rate changes never rewrite history.

Integer øre only; percentages are Decimals from the settings and rounded half up.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.extensions import db
from app.payments.methods import CASH, STRIPE, VIPPS_APP, VIPPS_QR
from app.settings.models import get_site_settings

FEE_METHODS = (VIPPS_QR, VIPPS_APP, CASH, STRIPE)


def _round_ore(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def convenience_percent(method: str) -> Decimal:
    if method not in FEE_METHODS:
        return Decimal(0)
    return Decimal(getattr(get_site_settings(), f"{method}_convenience_percent") or 0)


def convenience_fee_for(method: str, base_amount: int) -> int:
    """Fee added to the customer's charge for `method`, on a base of `base_amount` øre."""
    return _round_ore(Decimal(base_amount) * convenience_percent(method) / 100)


def processing_fee_for(method: str, charged_total: int) -> int:
    """What the provider takes from a payment of `charged_total` øre (convenience fee included)."""
    if method not in FEE_METHODS or charged_total <= 0:
        return 0
    settings = get_site_settings()
    percent = Decimal(getattr(settings, f"{method}_processing_percent") or 0)
    fixed = int(getattr(settings, f"{method}_processing_fixed_ore") or 0)
    return _round_ore(Decimal(charged_total) * percent / 100) + fixed


def snapshot_processing_fee(payment) -> None:
    """Records the processing fee on a payment that has just become paid. Idempotent: only sets
    it while empty. Call before the commit that marks the payment paid."""
    if payment.processing_fee_amount is None:
        payment.processing_fee_amount = processing_fee_for(payment.provider, payment.amount)
