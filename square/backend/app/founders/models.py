from sqlalchemy import func

from app.extensions import db


class Founder(db.Model):
    """A founder / long-standing leader quote shown in the Heritage page's rotating founder
    section. Same shape as CommitteeMember minus the contact fields — purely public content.
    """

    __tablename__ = "founders"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    # Optional muted line under `name` (e.g. the Bengali rendering of the name).
    sub_name = db.Column(db.String(200))
    # Free text ("Founding member", "President", ...).
    role = db.Column(db.String(200), nullable=False)
    quote = db.Column(db.Text, nullable=False)
    portrait_url = db.Column(db.String(500))
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
        return f"<Founder {self.name!r}>"
