"""Visit counts of a square's public site (rootsquares ADR 090, W23-R76): aggregates only.

No table here has a column that could hold an address, a browser string, a name or a person's id. `analytics_seen` holds one pseudonymous hash per visitor
for TODAY only (it decides "seen today" and is emptied; see service.py); the three other tables hold totals per day.
"""

from sqlalchemy import func

from app.extensions import db


class AnalyticsDaily(db.Model):
    """One row per day (in the square's own time zone): visits, page views and visitors of that day."""

    __tablename__ = "analytics_daily"

    day = db.Column(db.Date, primary_key=True)
    visits = db.Column(db.Integer, nullable=False, default=0)
    views = db.Column(db.Integer, nullable=False, default=0)
    visitors = db.Column(db.Integer, nullable=False, default=0)  # different visitors that day; not linkable from one day to the next


class AnalyticsPage(db.Model):
    """Page views per day and page path (no query, no fragment). At most MAX_PATHS different paths a day; the rest are counted as 'other'."""

    __tablename__ = "analytics_pages"

    day = db.Column(db.Date, primary_key=True)
    path = db.Column(db.String(200), primary_key=True)
    views = db.Column(db.Integer, nullable=False, default=0)


class AnalyticsSource(db.Model):
    """Visits per day and the referring site's host name ('direct' when there is none). At most MAX_SOURCES different a day; the rest are 'other'."""

    __tablename__ = "analytics_sources"

    day = db.Column(db.Date, primary_key=True)
    source = db.Column(db.String(100), primary_key=True)
    visits = db.Column(db.Integer, nullable=False, default=0)


class AnalyticsSeen(db.Model):
    """The visitors of today: a hash that changes every day (so nobody can be followed from one day to the next), the number of hits (a cap against inflation)
    and the time of the last one (a visit ends after 30 minutes of quiet). Rows of an earlier day are deleted by service.purge()."""

    __tablename__ = "analytics_seen"

    day = db.Column(db.Date, primary_key=True)
    visitor = db.Column(db.String(64), primary_key=True)
    hits = db.Column(db.Integer, nullable=False, default=1)
    last_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
