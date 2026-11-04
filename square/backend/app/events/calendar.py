"""The calendar feed (wave 14 item 6): events as an iCalendar (.ics) file that a phone or computer calendar can subscribe to or import.

Written by hand to RFC 5545 (no dependency): CRLF lines folded at 75 octets, text escaped, times in UTC. Only what the public site shows is in it
(published, not cancelled); it carries no personal data. A subscribed calendar re-reads the feed on its own, so a new Sunday gathering simply appears.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.common.site import site_domain, site_name
from app.common.urls import frontend_base_url
from app.events.models import Event

PRODID = "-//rootsquares//events//EN"
DEFAULT_LENGTH = timedelta(hours=2)  # an event without an end time is shown as two hours


def escape_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")


def fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after one space (never splitting a multi-byte character)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts: list[str] = []
    current = b""
    limit = 75
    for ch in line:
        encoded = ch.encode("utf-8")
        if len(current) + len(encoded) > limit:
            parts.append(current.decode("utf-8"))
            current, limit = b"", 74  # the leading space of a continuation line counts
        current += encoded
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def _utc(value: datetime) -> datetime:
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return _utc(value).strftime("%Y%m%dT%H%M%SZ")


def _plain(html: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html or "")).strip()


def vevent(event: Event, base_url: str, domain: str) -> list[str]:
    start = _utc(event.start_datetime)
    end = _utc(event.end_datetime) if event.end_datetime else start + DEFAULT_LENGTH
    where = ", ".join(p for p in (event.venue, event.address) if p)
    description = event.short_description or _plain(event.description)[:500]
    updated = event.updated_at or event.created_at or start
    lines = [
        "BEGIN:VEVENT",
        f"UID:event-{event.id}@{domain}",
        f"DTSTAMP:{_stamp(updated)}",
        f"LAST-MODIFIED:{_stamp(updated)}",
        f"DTSTART:{_stamp(start)}",
        f"DTEND:{_stamp(end)}",
        f"SUMMARY:{escape_text(event.title)}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{escape_text(description)}")
    if where:
        lines.append(f"LOCATION:{escape_text(where)}")
    if base_url:
        lines.append(f"URL:{base_url}/events/{event.slug}")
    lines.append("END:VEVENT")
    return lines


def build_calendar(events: list[Event], *, name: str | None = None) -> str:
    base_url = frontend_base_url()
    domain = site_domain() or "rootsquares"
    title = name or site_name()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_text(title)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for event in events:
        lines.extend(vevent(event, base_url, domain))
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"
