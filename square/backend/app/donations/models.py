from sqlalchemy import func

from app.extensions import db


class Donation(db.Model):
    """One gift to the square (the Donations module, wave 14). Money is integer minor units. The payment itself is a `payments` row
    (payment_type "donation") so every method that exists for tickets works here too: Vipps app (automatic), Vipps QR and cash (an admin confirms)."""

    __tablename__ = "donations"

    id = db.Column(db.Integer, primary_key=True)
    # "DON-2026-000012", built after flush like Order.order_number.
    reference = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    donor_name = db.Column(db.String(200), nullable=False)
    donor_email = db.Column(db.String(255), nullable=False, index=True)
    # The donor asked not to be named in anything shown to other people.
    anonymous = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    message = db.Column(db.Text, nullable=True)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    # pending | pending_verification (donor says "I paid") | paid | rejected | cancelled
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    confirmed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Donation {self.reference} {self.status}>"
