from sqlalchemy import func

from app.extensions import db


class Testimonial(db.Model):
    """A member/attendee quote shown on the homepage (PRD-adjacent, 2026-09-14 backlog item).

    `photo_url` is optional by design — many testimonials won't have a photo on file,
    and requiring one would block otherwise-good content from being added.

    `status` (2026-09-16 — public submission) distinguishes admin-authored content from
    visitor-submitted content: admin-created rows default to `"approved"` (unchanged
    behavior — an admin typing a testimonial directly needs no separate review step), while
    the public submission endpoint (`POST /api/testimonials`) always creates rows as
    `"pending"`. `is_active` alone was never enough once submissions aren't admin-authored:
    it only controls "show/hide," not "has anyone actually reviewed this yet." The public
    listing requires BOTH `status="approved"` AND `is_active=True` — an admin can still take
    an approved testimonial down without un-approving it (e.g. seasonally), and rejecting one
    is a distinct, auditable action from just hiding it.
    """

    __tablename__ = "testimonials"

    VALID_STATUSES = ("pending", "approved", "rejected")

    id = db.Column(db.Integer, primary_key=True)
    quote = db.Column(db.Text, nullable=False)
    author_name = db.Column(db.String(200), nullable=False)
    author_context = db.Column(db.String(200))
    photo_url = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="approved", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Testimonial {self.author_name!r}>"
