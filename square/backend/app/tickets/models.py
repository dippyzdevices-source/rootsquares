from sqlalchemy import func

from app.extensions import db


class TicketType(db.Model):
    __tablename__ = "ticket_types"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    # Explains what this ticket type includes/covers — shown to buyers on the public
    # purchase page and to admins on the ticket-type form. Optional free text.
    description = db.Column(db.Text, nullable=True)
    # Minor units (øre) — avoids float rounding on money. Admin's price form accepts
    # kroner-with-decimals and converts before sending.
    price = db.Column(db.Integer, nullable=False)
    capacity = db.Column(db.Integer, nullable=True)
    sale_start = db.Column(db.DateTime(timezone=True), nullable=True)
    sale_end = db.Column(db.DateTime(timezone=True), nullable=True)
    # The day this ticket is for (optional) — only used to section ticket types by date; not
    # enforced at check-in. Null = not tied to one day (shown under "All days").
    valid_on = db.Column(db.Date, nullable=True)
    # Label only for now — not enforced at checkout. See spec Non-goals.
    members_only = db.Column(db.Boolean, nullable=False, default=False)
    # "adult" | "child" | "other" — lets a coupon (app/coupons/) enforce its own per-order
    # quantity cap (at most 2 adult + 2 child tickets) without guessing from the type's name.
    age_category = db.Column(db.String(20), nullable=False, default="other")
    # Whether a coupon may ever discount this ticket type — default True so existing behavior
    # is unchanged for every pre-existing row. When an order mixes an eligible and an
    # ineligible type, the coupon discounts only the eligible items (app/orders/routes.py);
    # the ineligible ones are still charged in full — never all-or-nothing.
    coupon_eligible = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    # Nullable — pre-existing rows have no attribution. Set at admin create/update time
    # (see app/tickets/admin_routes.py).
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<TicketType {self.name!r}>"


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(
        db.Integer, db.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Opaque, random — never derived from order/customer data (PRD §21).
    ticket_code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # "valid" | "used" | "void" — EPIC 9 (check-in) sets "used" via app/checkin/admin_routes.py's
    # scan endpoint. "void" is set only by admin_orders.admin_cancel_order, for a still-"valid"
    # ticket on an order the admin cancelled after tickets were issued — an already-"used"
    # ticket is left untouched (can't un-admit someone; see that function's own comment).
    status = db.Column(db.String(20), nullable=False, default="valid")
    # EPIC 9 (check-in) — both null until a scan sets them. checked_in_by_user_id has no FK
    # relationship declared (app.checkin.admin_routes looks the User up directly when needed,
    # the same way app.orders.admin_routes looks Event up by id rather than declaring a
    # relationship on Order) — keeps this model free of a cross-module import.
    checked_in_at = db.Column(db.DateTime(timezone=True), nullable=True)
    checked_in_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Ticket {self.ticket_code!r}>"
