"""What anybody may see about a ready square: a hello-world page for it (no sign-in). The page proves the square is wired to its OWN database by
reading one fact from it. Nothing secret and no personal data leave here (no emails, keys or connection strings)."""

from __future__ import annotations

import json

import psycopg
import structlog

from app.platform.models import Square
from app.platform.provisioning import to_libpq
from app.shared.config import Settings
from app.shared.crypto import Encryptor

log = structlog.get_logger("app.public")


def public_auth_config(settings: Settings, sq: Square) -> tuple[str | None, str | None]:
    """(project url, publishable key) of the square's own auth project: both are public by design (every browser that signs in to the square
    needs them). The service key never leaves the platform."""
    if not sq.provider_secrets:
        return None, None
    try:
        secrets = json.loads(Encryptor(settings.fernet_key).decrypt(sq.provider_secrets))
    except ValueError:
        return None, None
    return secrets.get("project_url"), secrets.get("publishable") or secrets.get("anon")


def square_database_check(settings: Settings, sq: Square) -> dict[str, object]:
    """Ask the square's own database how many admins it has. {"ok": False} when it cannot be reached (the reason goes to the log, not the page)."""
    if not sq.db_connection:
        return {"ok": False}
    try:
        url = Encryptor(settings.fernet_key).decrypt(sq.db_connection)
        with psycopg.connect(to_libpq(url), connect_timeout=5, prepare_threshold=None) as conn:
            row = conn.execute("select count(*) from admins").fetchone()
        return {"ok": True, "admins": int(row[0]) if row else 0}
    except Exception as exc:  # noqa: BLE001 (any failure means: not reachable right now)
        log.warning("square_database_check_failed", square_id=str(sq.id), error_type=type(exc).__name__)
        return {"ok": False}
