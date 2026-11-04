from sqlalchemy import func

from app.extensions import db


class Expense(db.Model):
    """A manually-recorded expense: against one Event's accounting (event_id set), or in the
    square's general book (event_id empty, W14-R15: the book of a square that has no Events
    module, or costs that belong to no event). Collections and income are never duplicated
    here — they are derived live from Order/Payment/Donation (the sources of truth), never stored.
    """

    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True
    )
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(300), nullable=False)
    category = db.Column(db.String(30), nullable=False)
    # Minor units (øre) — same universal money convention as Order/Payment/TicketType.
    amount = db.Column(db.Integer, nullable=False)
    vendor = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    # Storage key of an uploaded receipt scan/photo in the private Supabase Storage bucket
    # (never the public one — receipts carry real vendor/financial detail). Null until a
    # receipt is uploaded via POST .../expenses/<id>/receipt.
    receipt_key = db.Column(db.String(500), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Expense event_id={self.event_id} {self.category} {self.amount}>"


class GeneralIncome(db.Model):
    """Money that came in without an event, a gift or a membership payment, typed in by an admin (W15-R16): a grant, a hall hire, cash at a stall.
    Only in the general book; amounts in minor units like every money column."""

    __tablename__ = "general_income"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(300), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    source_name = db.Column(db.String(200), nullable=True)  # who it came from
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<GeneralIncome {self.id} {self.amount}>"


class GeneralBudget(db.Model):
    """What the square plans to spend on one expense category in one year, in the general book (W15-R18). Minor units; no row = no budget."""

    __tablename__ = "general_budget"
    __table_args__ = (db.UniqueConstraint("year", "category", name="uq_general_budget_year_category"),)

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<GeneralBudget {self.year} {self.category} {self.amount}>"


class GeneralIncomeTarget(db.Model):
    """What the square aims to raise from one income source (donation, membership, manual) in one year, in the general book (W17-R6). Minor units; no row = no target."""

    __tablename__ = "general_income_target"
    __table_args__ = (db.UniqueConstraint("year", "source", name="uq_general_income_target_year_source"),)

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<GeneralIncomeTarget {self.year} {self.source} {self.amount}>"
class EventContribution(db.Model):
    """A donation or sponsorship received for a single Event — recorded by an admin (like an
    Expense) or, later, made through the public donate form. Counts towards the event's Collection
    only while `status == "paid"`. Minor units (øre), same convention as every other money column.
    """

    __tablename__ = "event_contributions"

    KINDS = ("donation", "sponsorship")

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind = db.Column(db.String(20), nullable=False)
    # Donor / sponsor name (a company for a sponsorship); may be "Anonymous".
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    # Null only for a sponsorship enquiry that named no amount yet; an admin sets it before marking it received.
    amount = db.Column(db.Integer, nullable=True)
    date = db.Column(db.Date, nullable=False)
    # Sponsorship enquiry details (public form): who to contact and what the sponsor wants.
    contact_name = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    website = db.Column(db.String(300), nullable=True)
    requirements = db.Column(db.Text, nullable=True)
    # How it was received (cash, vipps_qr, vipps_app, bank ...); free-form for admin entries.
    payment_method = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    # paid = received (counts in the Collection); pending = awaiting payment/confirmation;
    # failed / refunded = never counted.
    status = db.Column(db.String(20), nullable=False, default="paid", server_default="paid")
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<EventContribution event_id={self.event_id} {self.kind} {self.amount}>"
