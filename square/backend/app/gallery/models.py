from datetime import datetime, timezone

from sqlalchemy import func

from app.extensions import db


class Album(db.Model):
    __tablename__ = "albums"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    # Optional per-item override of the site-wide description typeface; null = site default.
    description_style = db.Column(db.String(20))
    # Optional — an album may relate to an event ("Durga Puja 2026") or stand alone
    # (a retrospective, a non-event album). Never required.
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True, index=True)
    # Optional, admin-picked (the admin-managed `album_category` lookup list) — separate
    # from event tagging: an album can belong to a category, an event, both, or neither.
    category = db.Column(db.String(20), nullable=True, index=True)
    # The year the album's photos are from — drives the public "Missing photographs?" archive
    # coverage (GET /api/gallery/coverage). Required via the admin API; the Python-side default
    # only keeps direct model construction (tests, scripts) working.
    year = db.Column(db.Integer, nullable=False, default=lambda: datetime.now(timezone.utc).year, index=True)
    published = db.Column(db.Boolean, nullable=False, default=False)
    # Nullable — pre-existing rows have no attribution. Set at admin create/update time
    # (see app/gallery/admin_routes.py).
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # No separate cover-image field — the cover is always media[0].
    media = db.relationship(
        "Media", backref="album", order_by="Media.created_at", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Album {self.title!r}>"


class Media(db.Model):
    __tablename__ = "media"

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(
        db.Integer, db.ForeignKey("albums.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename = db.Column(db.String(255), nullable=False)
    storage_key = db.Column(db.String(500), nullable=False)
    thumbnail_storage_key = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    caption = db.Column(db.String(300))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Media {self.filename!r}>"
