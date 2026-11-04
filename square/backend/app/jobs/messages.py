"""Once a minute: start the scheduled messages whose time has come, resume stalled sends and make the reminders that are due
(app/messages/service.py, app/messages/rules.py). Same thread pattern and CLI/TESTING guards as vipps_sweep.py; every step is idempotent
and claims its work atomically, so several workers are harmless."""

import logging
import threading
import time

import click

from app.jobs import heartbeat

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60


def _tick() -> int:
    from app.messages.rules import run_rules
    from app.messages.service import fire_due_messages

    return fire_due_messages() + run_rules()


def run_tick(app) -> int:
    from app.jobs.squares import run_everywhere

    return run_everywhere(app, _tick, module="messages")


def _loop(app) -> None:
    while True:
        time.sleep(CHECK_INTERVAL_SECONDS)
        try:
            started = run_tick(app)
            heartbeat.record("messages", True)
            if started:
                logger.info("Messages job started %s message(s)", started)
        except Exception:  # noqa: BLE001 - a failed tick must never kill this thread
            heartbeat.record("messages", False)
            logger.exception("Messages job failed")


def start_messages_job(app) -> None:
    if app.config["TESTING"]:
        return
    if click.get_current_context(silent=True) is not None:
        return
    threading.Thread(target=_loop, args=(app,), daemon=True).start()
