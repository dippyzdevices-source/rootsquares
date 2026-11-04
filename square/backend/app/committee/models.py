from sqlalchemy import func

from app.extensions import db


class CommitteeMember(db.Model):
    """A public BCA Oslo committee profile shown on the /committee page.

    Distinct from `Member` (a paying association member) and `User` (a login account) —
    a committee profile is purely public-facing organizational content, not tied to either.
    `address`/`email`/`phone`/`member_since`/`quote` are here specifically because a committee
    profile is meant to publish them publicly (an organizational contact point, like a business
    card — matching the design system's PortraitCard "committee" variant); never reuse a
    Member's private contact details for this. `quote` replaces the old free-text `description`
    (biography) field — a short personal line, not a bio.
    """

    __tablename__ = "committee_members"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200), nullable=False)
    # Optional muted line under `name` (e.g. the Bengali rendering of the name).
    sub_name = db.Column(db.String(200))
    portrait_url = db.Column(db.String(500))
    address = db.Column(db.String(300))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    # A plain year (e.g. 1994), not a date — matches the design system's memberSince field.
    member_since = db.Column(db.Integer)
    quote = db.Column(db.Text)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<CommitteeMember {self.name!r} ({self.role!r})>"
