from sqlalchemy import func

from app.extensions import db


class Member(db.Model):
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)
    # Nullable — a member imported via Excel exists on the roster before they ever log in.
    # Auto-linked to a real User the first time someone logs in with a matching email (see
    # app/members/routes.py's _find_my_member).
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=True, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    # A child member points at their parent's Member row (set via the parent's email — see
    # app/memberships/service.py's child_membership_error); null for everyone else.
    parent_member_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Only meaningful while user_id is None (an imported, not-yet-linked profile) — once
    # linked, prefer the live User.email/.phone, which Supabase Auth actually owns.
    email = db.Column(db.String(255), index=True)
    phone = db.Column(db.String(50))
    address = db.Column(db.String(300))
    photo_url = db.Column(db.String(500), nullable=True)
    # Legacy free-text fallback — no longer shown/edited in the live UI (see FamilyMember
    # below), but kept as the one Excel import/export column for family info, since bulk
    # import has no reasonable way to author several structured rows per spreadsheet cell.
    family_info = db.Column(db.Text)
    # GDPR (W14-R3): an erase request starts a grace period; after it the personal fields are anonymised (rows are never deleted).
    erase_requested_at = db.Column(db.DateTime(timezone=True), nullable=True)
    erased_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Newest first, matching the self-service /api/memberships/me ordering — a member's
    # "current" status is always memberships[0] when any rows exist.
    memberships = db.relationship(
        "Membership", backref="member", order_by="Membership.start_date.desc(), Membership.id.desc()"
    )
    family_members = db.relationship(
        "FamilyMember",
        backref="member",
        order_by="FamilyMember.sort_order",
        cascade="all, delete-orphan",
    )
    # String target avoids importing app.auth.models here (no circular import).
    user = db.relationship("User")
    parent = db.relationship("Member", remote_side=[id], backref="children")

    def __repr__(self) -> str:
        return f"<Member {self.name!r}>"


class FamilyMember(db.Model):
    """One structured family-member entry, replacing the old single free-text field in the
    live UI (self-service dashboard + admin member detail) — see `Member.family_info` for
    the legacy column this superseded, kept only as an Excel import/export fallback.
    """

    __tablename__ = "family_members"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    # Fixed set (the admin-managed `relationship_type` lookup list) rather than free text,
    # matching this app's Membership.status-style convention.
    relationship_type = db.Column(db.String(20), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<FamilyMember {self.name!r} ({self.relationship_type})>"
