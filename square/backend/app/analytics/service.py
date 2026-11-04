"""Counting the visits of a square's public site without knowing the visitor (rootsquares ADR 090, W23-R76).

The rules, all of them on purpose (docs/plans/analytics-plan.md section 5):
- no cookie, nothing stored in the browser: a visit is one beacon with the page path and the referring site;
- a visitor is told apart for ONE day only, by a hash of (address, browser string) made with a key that changes every day (derived from ANALYTICS_SALT_SECRET and the
  date); the table that holds the hashes is emptied of every earlier day, so nothing links one day to the next and nothing in the totals holds a hash;
- Do Not Track and Global Privacy Control are honoured (nothing is counted); bots, the admin area and anything over MAX_HITS a day from one hash are not counted;
- paths and sources are capped (MAX_PATHS, MAX_SOURCES a day, the rest is "other") so nobody can fill the database with made-up addresses;
- a day is a day in the square's own time zone.
Only aggregates are kept (24 months); a figure under FEW in a breakdown is reported as "fewer than FEW" (see report()).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
from typing import Any
from urllib.parse import urlparse

from flask import current_app, g
from sqlalchemy import and_, desc, func
from sqlalchemy.exc import IntegrityError

from app.analytics.models import AnalyticsDaily, AnalyticsPage, AnalyticsSeen, AnalyticsSource
from app.common.site import site_timezone
from app.extensions import db

MAX_PATHS = 200  # different paths counted a day; more are counted as "other"
MAX_SOURCES = 50  # different referring sites a day; more are counted as "other"
MAX_HITS = 600  # hits one visitor can add in a day
VISIT_GAP = dt.timedelta(minutes=30)  # quiet for this long and the next hit starts a new visit
FEW = 5  # a figure of a breakdown under this is not shown (0 is shown)
RETENTION_DAYS = 730  # 24 months of totals
TOP = 10
RANGES = (7, 30, 90)

BOT_WORDS = (
    "bot", "crawl", "spider", "slurp", "facebookexternalhit", "preview", "headless", "lighthouse", "pingdom", "uptime", "monitor", "curl/", "wget", "python-requests",
    "httpclient", "go-http", "java/", "libwww", "scrapy", "phantom", "selenium",
)  # fmt: skip
EXCLUDED_PREFIXES = ("/admin", "/api", "/login", "/register", "/auth", "/support", "/theme-review")
_PATH_OK = re.compile(r"^/[A-Za-z0-9\-._~%@+:,=/]*$")
_PURGED: dict[str, dt.date] = {}  # per square (this process): the day the old rows were last removed


def enabled() -> bool:
    """Counting needs the key (a long random value, set per server) and the owner's switch (the platform's flag for the square; a single-tenant server: ANALYTICS_ENABLED)."""
    if not current_app.config.get("ANALYTICS_SALT_SECRET"):
        return False
    tenant = g.get("tenant")
    if tenant is not None:
        return bool(getattr(tenant, "analytics", False))
    return bool(current_app.config.get("ANALYTICS_ENABLED"))


def today(now: dt.datetime | None = None) -> dt.date:
    return (now or dt.datetime.now(dt.timezone.utc)).astimezone(site_timezone()).date()


def is_bot(user_agent: str) -> bool:
    ua = user_agent.lower()
    return not ua or any(w in ua for w in BOT_WORDS)


def normalise_path(raw: object) -> str | None:
    """The page path without query or fragment, or None when it is not a public page of this site."""
    if not isinstance(raw, str):
        return None
    path = raw.strip().split("?", 1)[0].split("#", 1)[0]
    if len(path) > 200 or not _PATH_OK.match(path):
        return None
    if len(path) > 1:
        path = path.rstrip("/")
    low = path.lower()
    if any(low == p or low.startswith(p + "/") for p in EXCLUDED_PREFIXES):
        return None
    return path or "/"


def source_of(referrer: object, own_host: str) -> str | None:
    """'direct' when there is no referrer, the referring site's host name otherwise, None when the referrer is this very site (a click inside the site)."""
    if not isinstance(referrer, str) or not referrer.strip():
        return "direct"
    try:
        parsed = urlparse(referrer.strip())
    except ValueError:
        return "direct"
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "direct"
    host = parsed.hostname.lower().removeprefix("www.")[:100]
    own = own_host.lower().split(":")[0].removeprefix("www.")
    return None if host == own else host


def visitor_hash(ip: str, user_agent: str, day: dt.date) -> str:
    """A pseudonym for one visitor on one day. The key changes every day, so the same person has a different hash tomorrow and the two cannot be matched."""
    secret = str(current_app.config.get("ANALYTICS_SALT_SECRET", "")).encode()
    day_key = hmac.new(secret, day.isoformat().encode(), hashlib.sha256).digest()
    return hmac.new(day_key, f"{ip}|{user_agent}".encode(), hashlib.sha256).hexdigest()[:32]


def _row(model: Any, **keys: Any) -> Any:
    row = db.session.get(model, tuple(keys.values()))
    if row is None:
        row = model(**keys)
        db.session.add(row)
    return row


def _capped(model: Any, column: Any, day: dt.date, value: str, cap: int) -> str:
    """The key to count under: the value itself, or 'other' once the day already has `cap` different ones."""
    if db.session.get(model, (day, value)) is not None:
        return value
    seen = db.session.query(func.count()).select_from(model).filter(model.day == day).scalar() or 0
    return value if seen < cap else "other"


def record_hit(raw_path: object, referrer: object, user_agent: str, ip: str, host: str, *, now: dt.datetime | None = None) -> bool:
    """Count one page view. Returns whether it was counted (the caller answers the same either way, so nothing is learned from the answer)."""
    path = normalise_path(raw_path)
    if path is None or is_bot(user_agent):
        return False
    now = now or dt.datetime.now(dt.timezone.utc)
    day = today(now)
    purge_if_new_day(day)
    vh = visitor_hash(ip, user_agent, day)
    for attempt in (1, 2):  # two requests of a new visitor at once can both insert: the second tries again
        try:
            counted = _count(day, path, source_of(referrer, host), vh, now)
            db.session.commit()
            return counted
        except IntegrityError:
            db.session.rollback()
            if attempt == 2:
                return False
    return False


def _count(day: dt.date, path: str, source: str | None, vh: str, now: dt.datetime) -> bool:
    daily = _row(AnalyticsDaily, day=day)
    for field in ("visits", "views", "visitors"):
        if getattr(daily, field) is None:
            setattr(daily, field, 0)
    seen = db.session.get(AnalyticsSeen, (day, vh))
    if seen is None:
        db.session.add(AnalyticsSeen(day=day, visitor=vh, hits=1, last_at=now))
        daily.visitors += 1
        new_visit = True
    else:
        if seen.hits >= MAX_HITS:
            return False  # one visitor cannot inflate the day
        last = seen.last_at if seen.last_at.tzinfo else seen.last_at.replace(tzinfo=dt.timezone.utc)
        new_visit = now - last > VISIT_GAP
        seen.hits += 1
        seen.last_at = now
    if new_visit:
        daily.visits += 1
        if source is not None:  # a visit starts where the visitor came from; a click inside the site starts nothing
            key = _capped(AnalyticsSource, AnalyticsSource.source, day, source, MAX_SOURCES)
            src = _row(AnalyticsSource, day=day, source=key)
            src.visits = (src.visits or 0) + 1
    daily.views += 1
    page = _row(AnalyticsPage, day=day, path=_capped(AnalyticsPage, AnalyticsPage.path, day, path, MAX_PATHS))
    page.views = (page.views or 0) + 1
    return True


def purge(day: dt.date) -> None:
    """The visitors of an earlier day are deleted (this is what keeps the hashes from adding up to a trail); totals older than 24 months go too."""
    db.session.query(AnalyticsSeen).filter(AnalyticsSeen.day < day).delete(synchronize_session=False)
    cutoff = day - dt.timedelta(days=RETENTION_DAYS)
    for model in (AnalyticsDaily, AnalyticsPage, AnalyticsSource):
        db.session.query(model).filter(model.day < cutoff).delete(synchronize_session=False)
    db.session.commit()


def purge_if_new_day(day: dt.date) -> None:
    tenant = g.get("tenant")
    key = getattr(tenant, "slug", "single")
    if _PURGED.get(key) != day:
        purge(day)
        _PURGED[key] = day


def _few(value: int) -> tuple[int | None, bool]:
    return (None, True) if 0 < value < FEW else (value, False)


def _totals(rows: list[Any]) -> dict[str, int]:
    return {"visits": sum(r.visits for r in rows), "views": sum(r.views for r in rows), "visitors": sum(r.visitors for r in rows)}


def report(days: int, *, now: dt.datetime | None = None) -> dict[str, Any]:
    """The numbers for the owner: totals and a figure per day (exact), the period before for comparison, the top pages and sources, and per event the views against tickets
    bought. A figure of a breakdown under FEW is not sent: its value is null and `few` is true. `visitors` of a total is the sum of each day's different visitors (nobody is
    followed from one day to the next, so a count of different people over several days does not exist)."""
    days = days if days in RANGES else 30
    end = today(now)
    start = end - dt.timedelta(days=days - 1)
    prev_start = start - dt.timedelta(days=days)
    rows = {r.day: r for r in db.session.query(AnalyticsDaily).filter(AnalyticsDaily.day >= prev_start, AnalyticsDaily.day <= end)}
    current = [rows[d] for d in sorted(rows) if d >= start]
    before = [rows[d] for d in sorted(rows) if d < start]
    daily = []
    for i in range(days):
        d = start + dt.timedelta(days=i)
        r = rows.get(d)
        daily.append({"day": d.isoformat(), "visits": r.visits if r else 0, "views": r.views if r else 0, "visitors": r.visitors if r else 0})

    def top(model: Any, column: Any, field: Any) -> list[tuple[str, int]]:
        total = func.sum(field)
        q = db.session.query(column, total).filter(and_(model.day >= start, model.day <= end)).group_by(column).order_by(desc(total))
        return [(k, int(v)) for k, v in q.limit(TOP)]

    pages = [{"path": p, **dict(zip(("views", "few"), _few(v)))} for p, v in top(AnalyticsPage, AnalyticsPage.path, AnalyticsPage.views)]
    sources = [{"source": s, **dict(zip(("visits", "few"), _few(v)))} for s, v in top(AnalyticsSource, AnalyticsSource.source, AnalyticsSource.visits)]
    return {
        "enabled": enabled(),
        "days": days,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "daily": daily,
        "totals": _totals(current),
        "previous": _totals(before),
        "pages": pages,
        "sources": sources,
        "events": _events(start, end),
    }


def _events(start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    """Per event: page views of its page against tickets bought (paid orders made in the period). Titles are public; no buyer is named; a figure under FEW is hidden."""
    from app.events.models import Event
    from app.orders.models import Order, OrderItem

    tz = site_timezone()
    lo = dt.datetime.combine(start, dt.time.min, tzinfo=tz)
    hi = dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min, tzinfo=tz)
    views: dict[str, int] = {}
    for path, total in (
        db.session.query(AnalyticsPage.path, func.sum(AnalyticsPage.views))
        .filter(AnalyticsPage.day >= start, AnalyticsPage.day <= end, AnalyticsPage.path.like("/events/%"))
        .group_by(AnalyticsPage.path)
    ):
        parts = path.split("/")
        if len(parts) == 3 and parts[2]:  # /events/<slug>: the event's own page, not a sub page
            views[parts[2]] = int(total)
    sold = {
        event_id: int(qty or 0)
        for event_id, qty in db.session.query(Order.event_id, func.sum(OrderItem.quantity))
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(Order.payment_status == "paid", Order.created_at >= lo, Order.created_at < hi)
        .group_by(Order.event_id)
    }
    out: list[dict[str, Any]] = []
    for ev in db.session.query(Event).filter(Event.slug.in_(list(views)) if views else False):
        v, vf = _few(views.get(ev.slug, 0))
        t, tf = _few(sold.get(ev.id, 0))
        out.append({"slug": ev.slug, "title": ev.title, "views": v, "views_few": vf, "tickets": t, "tickets_few": tf, "_sort": views.get(ev.slug, 0)})
    for ev in db.session.query(Event).filter(Event.id.in_(list(sold))) if sold else []:  # an event with tickets bought but no counted views
        if ev.slug not in views:
            t, tf = _few(sold[ev.id])
            out.append({"slug": ev.slug, "title": ev.title, "views": 0, "views_few": False, "tickets": t, "tickets_few": tf, "_sort": 0})
    out.sort(key=lambda e: e["_sort"], reverse=True)
    for e in out:
        e.pop("_sort")
    return out[:TOP]
