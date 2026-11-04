from sqlalchemy import func

from app.extensions import db


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    # "BCA-2026-000001" — built as f"BCA-{year}-{id:06d}" AFTER a flush gives the row its
    # id, so uniqueness is free (no separate counter, no race condition).
    order_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    # Optional — set automatically when the buyer was logged in. Guest checkout always works.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_email = db.Column(db.String(255), nullable=False, index=True)
    customer_phone = db.Column(db.String(50), nullable=True)
    # Minor units, always server-calculated — never trust a client-supplied amount.
    total_amount = db.Column(db.Integer, nullable=False)
    # Coupon applied at checkout (app/coupons/) — nullable, no relationship declared (mirrors
    # Ticket.checked_in_by_user_id's own no-relationship precedent). coupon_code is a snapshot
    # of Coupon.code at purchase time so history reads correctly even if the coupon is later
    # edited/deactivated; discount_amount (minor units) is the amount total_amount was reduced
    # by, always server-calculated, never trusted from the client.
    coupon_id = db.Column(db.Integer, db.ForeignKey("coupons.id"), nullable=True)
    coupon_code = db.Column(db.String(50), nullable=True)
    discount_amount = db.Column(db.Integer, nullable=False, default=0)
    status_choices = (
        "pending", "pending_verification", "paid", "failed", "cancelled", "refunded", "rejected"
    )
    payment_status = db.Column(db.String(20), nullable=False, default="pending")
    # "cancelled" is a valid value but nothing sets it yet — see spec Non-goals.
    order_status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    # Who/when an admin approved (mark-paid) or rejected a payment-verification claim — FK
    # only, no relationship declared, mirroring Ticket.checked_in_by_user_id's own precedent
    # (app/checkin/admin_routes.py looks the User up directly by id rather than eager-loading
    # a relationship never needed elsewhere).
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejected_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rejected_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    # Who/when an admin cancelled an already-paid, tickets-issued order (distinct from
    # rejected_* above, which is a pre-payment "I don't believe this was paid" decision) — see
    # app/orders/admin_routes.py's admin_cancel_order.
    cancelled_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)

    items = db.relationship(
        "OrderItem", backref="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )

    def __repr__(self) -> str:
        return f"<Order {self.order_number!r}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_type_id = db.Column(
        db.Integer, db.ForeignKey("ticket_types.id"), nullable=False, index=True
    )
    quantity = db.Column(db.Integer, nullable=False)
    # Snapshot of TicketType.price at purchase time — order history reflects what was
    # actually paid, not today's price if it's since changed.
    unit_price = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Integer, nullable=False)

    tickets = db.relationship(
        "Ticket", backref="order_item", cascade="all, delete-orphan", order_by="Ticket.id"
    )
    ticket_type = db.relationship("TicketType")

    def __repr__(self) -> str:
        return f"<OrderItem order_id={self.order_id} qty={self.quantity}>"
