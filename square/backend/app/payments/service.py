from abc import ABC, abstractmethod

from app.common.site import site_currency
from app.extensions import db
from app.orders.models import Order
from app.payments.fees import snapshot_processing_fee
from app.payments.methods import BANK, CASH, VIPPS_QR
from app.payments.models import Payment


class PaymentProvider(ABC):
    @abstractmethod
    def create_payment(self, order: Order, method: str = VIPPS_QR) -> Payment: ...

    @abstractmethod
    def confirm_payment(self, payment: Payment) -> None: ...


class ManualPaymentProvider(PaymentProvider):
    """The manual-approval provider (ticket checkout's Vipps QR route). No external network call at all — an admin's own action
    IS the confirmation, so unlike StorageService there's no Fake needed for tests; this
    is always what's active. get_payment_provider() is still the swap point for when
    Stripe/VippsPaymentProvider exist.
    """

    def create_payment(self, order: Order, method: str = VIPPS_QR) -> Payment:
        if method not in (VIPPS_QR, CASH, BANK):
            raise ValueError(f"Not a manual payment method: {method}")
        payment = Payment(
            payment_type="event_ticket",
            order_id=order.id,
            provider=method,
            amount=order.total_amount,
            currency=site_currency(),
            status="pending",
        )
        db.session.add(payment)
        db.session.flush()
        payment.payment_reference = f"PAY-{payment.created_at.year}-{payment.id:06d}"
        return payment

    def confirm_payment(self, payment: Payment) -> None:
        payment.status = "paid"
        snapshot_processing_fee(payment)


def get_payment_provider() -> PaymentProvider:
    return ManualPaymentProvider()
