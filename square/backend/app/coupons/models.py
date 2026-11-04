from sqlalchemy import func

from app.extensions import db


class Coupon(db.Model):
    """A percentage-off code an admin defines per event, applied at checkout (app/orders/routes.py).

    Still no delete — an admin flips is_active off to stop a code from working, matching
    MembershipType's own no-delete/is_active precedent, and max_redemptions (below) does the same
    thing automatically once a usage cap is reached. Uniqueness is per-event, not global, and
    is always compared case-insensitively (code is stored upper-cased — see admin_routes.py).
    """

    __tablename__ = "coupons"
    __table_args__ = (db.UniqueConstraint("event_id", "code", name="uq_coupons_event_code"),)

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    code = db.Column(db.String(50), nullable=False)
    # 1-100 — a 100% coupon makes the order free (see app/orders/routes.py's auto-issue path).
    discount_percent = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # Comma-separated TicketType ids this coupon is restricted to (same comma-separated-string
    # convention as SiteSettings.maintenance_allowed_event_slugs) — empty means unrestricted:
    # the coupon applies to any coupon_eligible ticket type on the event, matching the original
    # behavior before this field existed. Non-empty means it applies ONLY to those ticket types,
    # letting two coupons target different, possibly-overlapping subsets of an event's ticket
    # types (e.g. "member" allowed on Adult, "sanatan" not).
    allowed_ticket_type_ids = db.Column(db.String(500), nullable=False, default="")
    # Nullable = unlimited (the original, still-default behavior). Non-null caps the total number
    # of TICKETS (QR codes) issued under PAID orders that used this coupon — NOT a count of
    # orders. A single order can carry any quantity, so counting orders would let e.g. a
    # max_redemptions=1 coupon issue an unbounded number of tickets in one checkout — see
    # redemption_count_for_coupon()'s own docstring below and app/orders/routes.py's checkout-
    # time gate, which is what actually prevents an order from ever pushing the total past this
    # cap (deactivate_coupon_if_limit_reached(), in app/coupons/service.py, is a secondary/UI
    # signal only — it flips is_active for admin/public display once the cap is reached, called
    # right after an order becomes paid, but the checkout-time gate is the real enforcement).
    max_redemptions = db.Column(db.Integer, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def allowed_ticket_type_id_list(self) -> list[int]:
        return [int(x) for x in self.allowed_ticket_type_ids.split(",") if x]

    def applies_to_ticket_type(self, ticket_type_id: int) -> bool:
        """True if this coupon has no ticket-type restriction, or explicitly allows this one."""
        if not self.allowed_ticket_type_ids:
            return True
        return ticket_type_id in self.allowed_ticket_type_id_list()

    def __repr__(self) -> str:
        return f"<Coupon {self.code!r}>"


def redemption_count_for_coupon(coupon_id: int) -> int:
    """Total number of TICKETS (one row per QR code) the coupon actually DISCOUNTED, under PAID
    orders that used it. A ticket in the same order that the coupon does not apply to (a
    ticket type that is not coupon-eligible, or one outside the coupon's own allow-list) was
    paid in full and is not a use of the coupon. This is deliberately NOT a count of orders —
    one order can carry any quantity, so counting orders would let a single checkout blow
    straight through max_redemptions. The one place "how many times used" is computed, shared
    by deactivate_coupon_if_limit_reached(), the admin serializer, the checkout preview and
    checkout's own pre-order gate (which counts the same kind of ticket), so all of them always
    agree; the accounting coupon_usage lines list the same tickets. Local import avoids a
    circular import (app.orders.models does not import app.coupons.models at module scope
    either, but this keeps the direction consistent)."""
    from app.orders.models import Order, OrderItem
    from app.tickets.models import Ticket, TicketType

    coupon = db.session.get(Coupon, coupon_id)
    if coupon is None:
        return 0
    query = (
        Ticket.query.join(OrderItem, Ticket.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(TicketType, OrderItem.ticket_type_id == TicketType.id)
        .filter(
            Order.coupon_id == coupon_id,
            Order.payment_status == "paid",
            TicketType.coupon_eligible.is_(True),
        )
    )
    allowed = coupon.allowed_ticket_type_id_list()
    if allowed:
        query = query.filter(OrderItem.ticket_type_id.in_(allowed))
    return query.count()
