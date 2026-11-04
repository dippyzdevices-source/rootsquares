"""Every hour: top up the recurring events so a weekly service always has its next weeks made (app/events/series.py). Same thread pattern and CLI/TESTING
guards as messages.py; idempotent (an existing date is never made twice), so several workers are harmless."""

import logging
import threading
import time

import click

from app.jobs import heartbeat

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60 * 60


def run_tick(app) -> int:
    from app.events.series import extend_all
    from app.jobs.squares import run_everywhere

    return run_everywhere(app, extend_all, module="events")


def _loop(app) -> None:
    time.sleep(5 * 60)  # not at boot
    while True:
        try:
            made = run_tick(app)
            heartbeat.record("event_series", True)
            if made:
                logger.info("Event series job made %s event(s)", made)
        except Exception:  # noqa: BLE001 - a failed run must never kill this thread
            heartbeat.record("event_series", False)
            logger.exception("Event series job failed")
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_event_series_job(app) -> None:
    if app.config["TESTING"]:
        return
    if click.get_current_context(silent=True) is not None:
        return
    threading.Thread(target=_loop, args=(app,), daemon=True).start()
