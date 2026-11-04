from sqlalchemy import func

from app.extensions import db


class News(db.Model):
    """A news/content article (PRD §27).

    Visibility is `status == "published" AND published_at <= now()` — a future
    `published_at` gives "schedule" for free without a separate status value.
    `status` also supports "draft" and "archived", same non-enum reasoning as
    Event.status: admins may need new lifecycle states without a migration.
    """

    __tablename__ = "news"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    summary = db.Column(db.String(500))
    # Optional per-item override of the site-wide description typeface; null = site default.
    description_style = db.Column(db.String(20))
    content = db.Column(db.Text, nullable=False)
    banner_image = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    # Optional — an article with no category is neither an Announcement nor a Story, just
    # unclassified. Fixed small set (the admin-managed `news_category` lookup list) rather than
    # free text, same reasoning as Membership.status.
    category = db.Column(db.String(20), index=True)
    # Free-text byline, deliberately NOT a User foreign key — the credited author of a piece
    # (e.g. a committee member without a login, or a name the admin wants shown) is a distinct
    # concern from created_by/updated_by (who touched the CMS record). Nullable: older/imported
    # articles have no byline.
    author = db.Column(db.String(120))
    # Nullable — pre-existing rows and any future non-admin-form creation path have no
    # attribution. Set at admin create/update time (see app/news/admin_routes.py).
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    published_at = db.Column(db.DateTime(timezone=True), index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    images = db.relationship(
        "NewsImage",
        backref="news",
        order_by="NewsImage.sort_order",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<News {self.slug!r}>"


class NewsImage(db.Model):
    """One additional image for a news article (admin-uploaded, ordered via sort_order).

    Additive alongside the single `News.banner_image` — the banner stays the lead/hero image
    shown at the top of the article; rows here are extra images shown in a gallery further
    down the page. Stores `storage_key` (not a URL) so a delete can also remove the object
    from storage — same pattern as `events.models.EventBanner`/`gallery.models.Media`.
    """

    __tablename__ = "news_images"

    id = db.Column(db.Integer, primary_key=True)
    news_id = db.Column(db.Integer, db.ForeignKey("news.id"), nullable=False, index=True)
    storage_key = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<NewsImage news_id={self.news_id} sort_order={self.sort_order}>"
