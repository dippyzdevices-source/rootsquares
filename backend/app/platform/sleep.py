"""True sleep of a square (rootsquares W10-R44, ADR 042 addition, docs/plans/pricing-strategy.md section 3, docs/setup/22-stripe-billing.md).

Keep means the square's project at the provider is paused, so we stop paying for its compute while the project and its data are kept:
- Supabase: the Management API pause call (`POST /v1/projects/{ref}/pause`) and restore (`POST /v1/projects/{ref}/restore`), then wait until healthy.
- Neon: the compute endpoints are suspended (`POST /projects/{id}/endpoints/{endpoint}/suspend`) and started again (`.../start`).
  Neon also suspends idle computes by itself.
- Local (development): nothing at a provider; the square server still shows the back-soon page.
The real calls only run when `PROVIDER_SLEEP=true` (off by default: nothing at a provider is paused until the user switches it on). They are written from
the providers' published API documents and NOT run against a real project yet; the first real test is the user's (the guide lists it).

While a square sleeps nobody can sign in to it (its database is not there): the square server answers every request but its config and health with 503, and the
public site is the back-soon page. The public contact details are copied to the platform when the square goes to sleep (ADR 038 addition) and deleted on wake.
"""

from __future__ import annotations

import datetime as dt
import json
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx
import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.platform.models import AuditLog, Square
from app.platform.provisioning import NeonProvisioner, SupabaseProvisioner
from app.shared.config import Settings

log = structlog.get_logger("app.sleep")

AWAKE, SLEEPING, WAKING, FAILED = "awake", "sleeping", "waking", "failed"
CONTACT_KEYS = ("contact_email", "contact_phone", "contact_address")


def mark_asleep(sq: Square) -> None:
    """Remember when the square fell asleep (the 12-month archive counts from here, archive.py). Idempotent."""
    if sq.asleep_since is None:
        sq.asleep_since = dt.datetime.now(dt.UTC)


def mark_awake(sq: Square) -> None:
    sq.asleep_since = None


def fetch_contact(settings: Settings, sq: Square) -> dict[str, str] | None:
    """The square's PUBLIC contact details (the same ones its Contact page shows), asked while its database is still awake. None = could not ask."""
    if not settings.SQUARE_SERVER_URL or not settings.SQUARE_INTERNAL_KEY:
        return None
    try:
        r = httpx.get(
            settings.SQUARE_SERVER_URL.rstrip("/") + "/api/internal/sleep-snapshot",
            headers={"X-Internal-Key": settings.SQUARE_INTERNAL_KEY, "Host": sq.domain},
            timeout=5.0,
        )
        r.raise_for_status()
        body = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("sleep_snapshot_unavailable", slug=sq.slug, error=type(exc).__name__)
        return None
    return {k: str(body.get(k) or "")[:300] for k in CONTACT_KEYS} if isinstance(body, dict) else None


def contact_of(sq: Square) -> dict[str, str]:
    try:
        data = json.loads(sq.sleep_contact or "{}")
    except ValueError:
        return {}
    return {k: str(data.get(k) or "") for k in CONTACT_KEYS} if isinstance(data, dict) else {}


def pause_resources(settings: Settings, sq: Square, client: httpx.Client | None = None) -> bool:
    """Pause the square's project at its provider. False = nothing to pause (switch off, local, or no project)."""
    if not settings.PROVIDER_SLEEP:
        return False
    if sq.provider_project_ref:
        prov = SupabaseProvisioner(settings.SUPABASE_ACCESS_TOKEN, settings.SUPABASE_ORG_SLUG, settings.SUPABASE_REGION, client=client)
        prov.pause_project(sq.provider_project_ref)
        return True
    if sq.neon_project_id:
        NeonProvisioner(settings.NEON_API_KEY, settings.NEON_REGION, client=client).suspend_project(sq.neon_project_id)
        return True
    return False


def resume_resources(settings: Settings, sq: Square, client: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep) -> bool:
    """Start the square's project again and wait until it answers. False = nothing to resume."""
    if not settings.PROVIDER_SLEEP:
        return False
    if sq.provider_project_ref:
        prov = SupabaseProvisioner(settings.SUPABASE_ACCESS_TOKEN, settings.SUPABASE_ORG_SLUG, settings.SUPABASE_REGION, client=client, sleep=sleep)
        prov.resume_project(sq.provider_project_ref)
        return True
    if sq.neon_project_id:
        NeonProvisioner(settings.NEON_API_KEY, settings.NEON_REGION, client=client).start_project(sq.neon_project_id)
        return True
    return False


def _audit(db: Session, sq: Square, action: str, **data: Any) -> None:
    db.add(AuditLog(action=action, entity="square", entity_id=str(sq.id), org_id=sq.org_id, data=data))


def run_pause(app_factory: sessionmaker[Session], settings: Settings, square_id: uuid.UUID, client: httpx.Client | None = None) -> None:
    """Background job after the owner puts a square to sleep: pause the project at the provider. The square already shows the back-soon page; a failure
    is logged and audited and the square stays asleep (the project simply keeps running until it is paused again)."""
    with app_factory() as db:
        sq = db.get(Square, square_id)
        if sq is None:
            return
        try:
            paused = pause_resources(settings, sq, client)
            _audit(db, sq, "square.paused", provider_paused=paused)
        except Exception as exc:  # noqa: BLE001 - never leaks keys: only the error type is kept
            log.warning("pause_failed", square_id=str(square_id), error_type=type(exc).__name__)
            _audit(db, sq, "square.pause_failed", error_type=type(exc).__name__)
        db.commit()


def run_wake(
    app_factory: sessionmaker[Session],
    settings: Settings,
    square_id: uuid.UUID,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Background job after the owner wakes a square: start the project, wait until healthy, then the square is awake (contact copy deleted). A failure
    leaves it `failed`; pressing Wake up again retries."""
    with app_factory() as db:
        sq = db.get(Square, square_id)
        if sq is None:
            return
        try:
            woke = resume_resources(settings, sq, client, sleep)
            sq.sleep_state = AWAKE
            sq.sleep_contact = None
            mark_awake(sq)
            _audit(db, sq, "square.woke", provider_resumed=woke)
        except Exception as exc:  # noqa: BLE001
            log.warning("wake_failed", square_id=str(square_id), error_type=type(exc).__name__)
            sq.sleep_state = FAILED
            _audit(db, sq, "square.wake_failed", error_type=type(exc).__name__)
        db.commit()
