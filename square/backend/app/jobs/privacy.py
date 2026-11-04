"""Once a day: anonymise people whose 30-day erase grace has ended and orders past the retention period
(app/members/erasure.py). Same thread pattern and guards as vipps_sweep.py; idempotent, so several workers are harmless."""

import logging
import threading
import time

import click

from app.jobs import heartbeat

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 24 * 60 * 60


def run_privacy(app) -> int:
    from app.jobs.squares import run_everywhere
    from app.members.erasure import run_privacy_jobs

    return run_everywhere(app, run_privacy_jobs) + run_everywhere(app, _purge_analytics)


def _purge_analytics() -> int:
    """The visitors of earlier days are deleted and the totals older than 24 months go (ADR 090); the counter also does this on the first hit of a new day."""
    from sqlalchemy.exc import OperationalError, ProgrammingError

    from app.analytics import service
    from app.extensions import db

    try:
        service.purge(service.today())  # also when the owner has switched counting off: whatever was kept is still removed on schedule
    except (OperationalError, ProgrammingError):
        db.session.rollback()  # a square whose database has not been upgraded to the analytics tables yet: nothing to remove
    return 0


def _loop(app) -> None:
    time.sleep(10 * 60)  # not at boot; then once a day
    while True:
        try:
            count = run_privacy(app)
            heartbeat.record("privacy", True)
            if count:
                logger.info("Privacy job anonymised %s record group(s)", count)
        except Exception:  # noqa: BLE001 - a failed run must never kill this thread
            heartbeat.record("privacy", False)
            logger.exception("Privacy job failed")
        time.sleep(INTERVAL_SECONDS)


def start_privacy_job(app) -> None:
    if app.config["TESTING"]:
        return
    if click.get_current_context(silent=True) is not None:
        return
    threading.Thread(target=_loop, args=(app,), daemon=True).start()
