from sqlalchemy import false, func

from app.extensions import db


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    # "PAY-2027-000123" — built as f"PAY-{payment.created_at.year}-{payment.id:06d}" after
    # flush, exact same pattern as Order.order_number.
    payment_reference = db.Column(db.String(30), unique=True, nullable=True, index=True)
    # "event_ticket" | "membership" — existing rows are backfilled to "event_ticket" by the
    # migration below.
    payment_type = db.Column(db.String(20), nullable=False, index=True)
    # Nullable now (was not-null) — set only when payment_type == "event_ticket". 1:many — a
    # retry-capable real provider could produce more than one Payment per Order later; no
    # unique constraint on order_id.
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True, index=True)
    # Set only when payment_type == "donation" (the Donations module).
    donation_id = db.Column(db.Integer, db.ForeignKey("donations.id"), nullable=True, index=True)
    provider = db.Column(db.String(20), nullable=False)
    # Only real providers (Stripe/Vipps, not yet built) ever set this.
    provider_transaction_id = db.Column(db.String(255), nullable=True)
    # øre charged to the customer. For provider "vipps_app" this includes surcharge_amount.
    amount = db.Column(db.Integer, nullable=False)
    # øre — the card/app-payment fee part of `amount` (null = none). Allocations sum to
    # amount - surcharge_amount.
    surcharge_amount = db.Column(db.Integer, nullable=True)
    # øre the provider takes from us (estimate), snapshotted when the payment becomes paid and
    # never rewritten (null = not paid yet / not recorded). See app/payments/fees.py.
    processing_fee_amount = db.Column(db.Integer, nullable=True)
    currency = db.Column(db.String(3), nullable=False, default="NOK")
    # pending | initiated (customer is at Vipps) | authorized | paid | failed | cancelled | refunded | partially_refunded — a
    # plain string column, no DB CHECK constraint, matching every other lifecycle field in this
    # codebase (Order.status, Membership.status, etc.).
    status = db.Column(db.String(20), nullable=False, default="pending")
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Payment {self.payment_type} status={self.status!r}>"


class PaymentAllocation(db.Model):
    """Records exactly which MembershipPeriod a Payment settled — a payment can settle
    several periods at once (e.g. paying 3 months together), and this table is what lets the
    system answer "which months did this payment cover" and "which payment settled this month"
    in both directions. Only ever created for payment_type == "membership" payments in Phase 1.
    """

    __tablename__ = "payment_allocations"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False, index=True)
    membership_period_id = db.Column(
        db.Integer, db.ForeignKey("membership_periods.id"), nullable=False, index=True
    )
    # øre — snapshot of what this allocation settled.
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<PaymentAllocation payment_id={self.payment_id} period_id={self.membership_period_id}>"


class PaymentCredential(db.Model):
    """The square's own keys for one payment provider (rootsquares W16-R4), typed in by its admin on Settings -> Payments.

    `ciphertext` is a Fernet token of a JSON object (see app/payments/credentials.py); the keys are never returned by any
    API, never logged. One row per provider. `hint` holds only non-secret facts for the screen (the last characters of the
    main id, the merchant number). There is no fallback to environment variables: no row means the provider is not connected.
    """

    __tablename__ = "payment_credentials"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), nullable=False, unique=True)  # "vipps" | "stripe"
    ciphertext = db.Column(db.Text, nullable=False)
    mode = db.Column(db.String(12), nullable=False, default="test")  # "test" | "production"
    hint = db.Column(db.JSON, nullable=False, default=dict)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    webhook_registered = db.Column(db.Boolean, nullable=False, default=False, server_default=false())
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<PaymentCredential {self.provider} {self.mode}>"
