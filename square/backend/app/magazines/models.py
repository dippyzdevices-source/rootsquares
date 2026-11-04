from sqlalchemy import func

from app.extensions import db


class Magazine(db.Model):
    """A PDF magazine / newsletter issue, listed under the public News section and read in the
    in-page PDF reader. The PDF and cover live in object storage; only their URLs are stored."""

    __tablename__ = "magazines"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    # Free-text issue name, e.g. "Puja 2026" or "Issue 12".
    issue_label = db.Column(db.String(100))
    issue_date = db.Column(db.Date, index=True)
    description = db.Column(db.String(1000))
    # Optional per-item override of the site-wide description typeface; null = site default.
    description_style = db.Column(db.String(20))
    pdf_url = db.Column(db.String(500))
    cover_url = db.Column(db.String(500))
    published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Magazine {self.title!r}>"
