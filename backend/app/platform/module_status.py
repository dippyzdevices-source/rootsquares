"""Ask the shared square server what a square's modules hold and have pending (rootsquares W8-R27, docs/reference/optional-modules.md section 9c).

The square app knows its own tables; the platform only asks, with a shared key, naming the square by its host name. Any failure (not configured, server
down, wrong key) returns None: the owner's screen then shows no stored data and no warnings, and switching still works.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.platform.models import Square
from app.shared.config import Settings

log = structlog.get_logger("app.module_status")


def fetch_module_status(settings: Settings, sq: Square) -> list[dict[str, Any]] | None:
    if not settings.SQUARE_SERVER_URL or not settings.SQUARE_INTERNAL_KEY:
        return None
    try:
        response = httpx.get(
            settings.SQUARE_SERVER_URL.rstrip("/") + "/api/internal/modules/status",
            headers={"X-Internal-Key": settings.SQUARE_INTERNAL_KEY, "Host": sq.domain},
            timeout=5.0,
        )
        response.raise_for_status()
        items = response.json().get("items")
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("module_status_unavailable", slug=sq.slug, error=type(exc).__name__)
        return None
    return items if isinstance(items, list) else None


def fetch_square_analytics(settings: Settings, sq: Square, days: int) -> dict[str, Any] | None:
    """The square's visit numbers for its owner (ADR 090, the one exception to ADR 038): aggregates the square server already reduced (figures under 5
    hidden). The caller passes them on and keeps nothing. None = the square server could not be reached."""
    if not settings.SQUARE_SERVER_URL or not settings.SQUARE_INTERNAL_KEY:
        return None
    try:
        response = httpx.get(
            settings.SQUARE_SERVER_URL.rstrip("/") + "/api/internal/analytics",
            params={"days": days},
            headers={"X-Internal-Key": settings.SQUARE_INTERNAL_KEY, "Host": sq.domain},
            timeout=8.0,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("square_analytics_unavailable", slug=sq.slug, error=type(exc).__name__)
        return None
    return body if isinstance(body, dict) else None


def fetch_square_health(settings: Settings, sq: Square) -> dict[str, Any] | None:
    """The square's own health report (W10-R19, ADR 038): states and sentences. None = the square server could not be reached."""
    if not settings.SQUARE_SERVER_URL or not settings.SQUARE_INTERNAL_KEY:
        return None
    try:
        response = httpx.get(
            settings.SQUARE_SERVER_URL.rstrip("/") + "/api/internal/health",
            headers={"X-Internal-Key": settings.SQUARE_INTERNAL_KEY, "Host": sq.domain},
            timeout=5.0,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("square_health_unavailable", slug=sq.slug, error=type(exc).__name__)
        return None
    return body if isinstance(body, dict) and isinstance(body.get("checks"), list) else None
