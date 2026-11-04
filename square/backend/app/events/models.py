from datetime import datetime, timezone

from sqlalchemy import func

from app.extensions import db


class EventSeries(db.Model):
    """The rule behind a recurring event (app/events/series.py, wave 14 item 6): every `interval_weeks` weeks ("weekly"), or the `nth` weekday of each month
    ("monthly_weekday"; nth 5 = the last one). The events of the series are ordinary events that carry `series_id`."""

    __tablename__ = "event_series"

    id = db.Column(db.Integer, primary_key=True)
    frequency = db.Column(db.String(20), nullable=False)
    interval_weeks = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    nth = db.Column(db.Integer, nullable=True)
    first_date = db.Column(db.Date, nullable=True)  # the first occurrence, kept when it is deleted, so "N times" still counts from it
    until_date = db.Column(db.Date, nullable=True)
    max_count = db.Column(db.Integer, nullable=True)
    horizon_days = db.Column(db.Integer, nullable=False, default=120, server_default="120")
    ended = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())


class Event(db.Model):
    """A single BCA Oslo event (festival, cultural, or community).

    Multi-day schedules (e.g. Durga Puja's Friday/Saturday programme) live in
    the separate EventSession table below (BCA-033).
    """

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    # Optional second line under the title, typically the Bengali rendering of the name.
    sub_name = db.Column(db.String(200))
    # Optional per-event override of the site-wide description typeface (SiteSettings.description_style);
    # null = use the site default. Values: DESCRIPTION_STYLES in app/settings/admin_routes.py.
    description_style = db.Column(db.String(20))
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    short_description = db.Column(db.String(500))
    description = db.Column(db.Text)
    # Conventional values: festival, cultural, community, other (PRD §13).
    # Not a DB enum on purpose — admins may need new types without a migration.
    event_type = db.Column(db.String(50), nullable=False, index=True)
    start_datetime = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    end_datetime = db.Column(db.DateTime(timezone=True))
    # Optional cut-off for buying tickets (e.g. the Friday before a Saturday event, to order food). The
    # event itself stays live and listed; after this moment every ticket type reads as "ended".
    sales_close_at = db.Column(db.DateTime(timezone=True))
    # Optional start of ticket sales; before this moment every ticket type reads as "upcoming".
    sales_open_at = db.Column(db.DateTime(timezone=True))
    venue = db.Column(db.String(200))
    address = db.Column(db.String(300))
    capacity = db.Column(db.Integer)
    banner_image = db.Column(db.String(500))
    # How buyers may pay for this event's tickets: a comma-separated list of "qr", "app", "cash" (the old "both" = "qr,app").
    # See app.orders.service.allowed_payment_methods() for what actually applies at checkout.
    # How a multi-day event's ticket types are shown on the buy page: all on one page under a heading
    # per day ("sections"), or one day at a time in tabs ("tabs"). Single-day events ignore it.
    ticket_layout = db.Column(db.String(10), nullable=False, default="sections", server_default="sections")
    ticket_payment_methods = db.Column(db.String(30), nullable=False, default="qr,app", server_default="qr,app")
    # Optional wording shown to Cash payers of this event ("your place is not confirmed until you pay …");
    # empty = the site-wide ticket note from Settings -> Payments.
    cash_note = db.Column(db.Text, nullable=True)
    # Per-event ticket limits, all optional (null = no limit): the most tickets of one ticket type
    # a single email address can reserve, and — on an order using a coupon — the most
    # coupon-eligible adult / child tickets. Enforced server-side at checkout.
    max_tickets_per_email = db.Column(db.Integer)
    coupon_max_adult = db.Column(db.Integer)
    coupon_max_child = db.Column(db.Integer)
    # Optional links to this event's own Facebook / Instagram event pages (http(s) only).
    facebook_url = db.Column(db.String(500))
    instagram_url = db.Column(db.String(500))
    # Lifecycle state (e.g. scheduled/cancelled/completed) — distinct from
    # `published`, which controls public-site visibility.
    status = db.Column(db.String(50), nullable=False, default="scheduled")
    published = db.Column(db.Boolean, nullable=False, default=False, index=True)
    # The series this event belongs to, if it repeats (null for a one-off event).
    series_id = db.Column(db.Integer, db.ForeignKey("event_series.id", ondelete="SET NULL"), nullable=True, index=True)
    # Nullable — pre-existing rows have no attribution. Set at admin create/update time
    # (see app/events/admin_routes.py).
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    sessions = db.relationship(
        "EventSession",
        backref="event",
        order_by="EventSession.sort_order",
        cascade="all, delete-orphan",
    )
    task_assignments = db.relationship(
        "EventTaskAssignment",
        backref="event",
        cascade="all, delete-orphan",
    )
    banners = db.relationship(
        "EventBanner",
        backref="event",
        order_by="EventBanner.sort_order",
        cascade="all, delete-orphan",
    )

    @property
    def sales_not_open(self) -> bool:
        """True while `sales_open_at` is still in the future."""
        if self.sales_open_at is None:
            return False
        at = self.sales_open_at
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < at

    @property
    def sales_closed(self) -> bool:
        """True once `sales_close_at` has passed (the event stays live; only ticket buying stops)."""
        if self.sales_close_at is None:
            return False
        at = self.sales_close_at
        if at.tzinfo is None:  # SQLite (tests) drops tzinfo; values are always written as UTC
            at = at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > at

    def __repr__(self) -> str:
        return f"<Event {self.slug!r}>"


class EventBanner(db.Model):
    """One image in an event's banner slider (admin-uploaded, ordered via sort_order).

    Additive alongside the older single `Event.banner_image` column — an event with rows
    here shows a slider on the public detail page; an event with none falls back to its own
    `banner_image` (if set) exactly as before, so no data migration was needed for existing
    events. Stores `storage_key` (not a URL) so a delete can also remove the object from
    storage — same pattern as `gallery.models.Media`.
    """

    __tablename__ = "event_banners"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    storage_key = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<EventBanner event_id={self.event_id} sort_order={self.sort_order}>"


class EventSession(db.Model):
    """One schedule row within an Event's multi-day programme.

    e.g. Durga Puja 2026 -> ("Friday", 18:00, "Cultural Programme"). Rows are
    a flat, admin-ordered list (`sort_order`) rather than a nested day/time
    structure — the frontend groups consecutive rows under a day_label
    header whenever it changes, so there's no separate "day" table to keep
    in sync.
    """

    __tablename__ = "event_sessions"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_label = db.Column(db.String(50), nullable=False)
    time = db.Column(db.Time, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    # Optional free text explaining what this schedule item covers — shown under its title
    # on the public event page. Same purpose/shape as TicketType.description.
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<EventSession {self.day_label} {self.time} {self.title!r}>"


class EventTaskAssignment(db.Model):
    """One member helping with one task category (Food/Cultural/Decoration/...) on an event.

    Deliberately modeled against `Member` (the roster), not `User`/the auth `volunteer`
    role — coordinating who's cooking or decorating has nothing to do with login permissions,
    and many people helping on the day never log into the site at all (see `Member.user_id`'s
    own nullable precedent). Distinct from `app.checkin.models.EventVolunteer`, which scopes
    check-in *scanning access* for the auth `volunteer` role — an entirely different concept.
    """

    __tablename__ = "event_task_assignments"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(
        db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Fixed admin-curated set (the admin-managed `task_category` lookup list) rather
    # than free text, matching this app's Membership.status-style fixed-value convention.
    category = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    member = db.relationship("Member")

    def __repr__(self) -> str:
        return f"<EventTaskAssignment event_id={self.event_id} member_id={self.member_id} category={self.category!r}>"
