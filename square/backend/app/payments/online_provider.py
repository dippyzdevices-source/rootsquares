"""OnlinePaymentProvider — a separate abstraction from app.payments.service's
PaymentProvider/ManualPaymentProvider, which stays exactly as it is for ticket orders. Ticket
checkout is a synchronous, admin-driven flow; real membership payment providers (Vipps/Stripe)
are asynchronous and webhook-driven — forcing both shapes into one interface would be a
premature abstraction. Only FakeOnlinePaymentProvider exists in Phase 1; real
VippsPaymentProvider/StripePaymentProvider implementations are Phase 2.
"""

import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.memberships.models import MembershipPeriod
from app.payments.models import Payment, PaymentAllocation


@dataclass
class PaymentCheckoutInfo:
    already_paid: bool
    redirect_url: str | None = None
    client_secret: str | None = None


class OnlinePaymentProvider(ABC):
    @abstractmethod
    def start_payment(
        self, payment: Payment, periods: list[MembershipPeriod], *, return_url: str
    ) -> PaymentCheckoutInfo: ...

    @abstractmethod
    def handle_webhook(self, raw_body: bytes, headers: dict) -> None:
        """Verifies signature, looks up the Payment by provider_transaction_id, and — if not
        already processed — marks it paid/failed, creates PaymentAllocation rows, and marks
        periods paid. Must be idempotent. Not exercised in Phase 1 — no real provider calls it —
        but the interface exists now so Phase 2 has a clean seam to implement against.
        """


class FakeOnlinePaymentProvider(OnlinePaymentProvider):
    """The only concrete implementation in Phase 1. Completes synchronously and immediately —
    this is what makes the full select -> pay -> allocate -> periods paid flow testable
    end-to-end today with zero external dependency.
    """

    def start_payment(
        self, payment: Payment, periods: list[MembershipPeriod], *, return_url: str
    ) -> PaymentCheckoutInfo:
        payment.provider_transaction_id = f"FAKE-{secrets.token_hex(8)}"
        payment.status = "paid"
        payment.paid_at = datetime.now(timezone.utc)

        for period in periods:
            db.session.add(
                PaymentAllocation(
                    payment_id=payment.id, membership_period_id=period.id, amount=period.amount
                )
            )
            period.status = "paid"
            period.paid_at = payment.paid_at

        db.session.commit()
        return PaymentCheckoutInfo(already_paid=True)

    def handle_webhook(self, raw_body: bytes, headers: dict) -> None:
        # Nothing to do — start_payment() already completed synchronously. Present only so the
        # interface is fully implemented.
        return None


class PaymentProviderNotConfiguredError(Exception):
    """Raised by get_online_payment_provider() for "vipps"/"stripe" outside TESTING, until
    Phase 2 replaces this with a real implementation.
    """


def get_online_payment_provider(name: str) -> OnlinePaymentProvider:
    """name is "vipps" or "stripe" — the provider the member chose. Payment.provider always
    stores this exact value regardless of which class actually handles the call — fakeness is
    purely a test-time implementation detail, never a distinct stored value.
    """
    if current_app.config.get("TESTING"):
        return FakeOnlinePaymentProvider()
    raise PaymentProviderNotConfiguredError(
        f"{name} is not yet configured — real provider integration is a future story."
    )
