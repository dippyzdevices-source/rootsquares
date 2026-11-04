"""Every few minutes, re-check Vipps app payments that are still "initiated" — the safety net
for customers who paid and never returned to the site, and for any missed webhook. A plain
daemon thread (same pattern and same CLI/TESTING guards as keep_alive.py); the work itself is
app.payments.vipps.sweep_initiated_payments(), which is idempotent and row-locked, so several
gunicorn workers each running this loop is harmless.
"""

import logging
import threading
import time

import click

from app.jobs import heartbeat

logger = logging.getLogger(__name__)

SWEEP_INTERVAL_SECONDS = 5 * 60


def run_sweep(app) -> int:
    """One sweep of the pending Vipps payments, in every square (many-squares mode) or in the single database."""
    from app.jobs.squares import run_everywhere
    from app.payments.vipps import sweep_initiated_payments

    return run_everywhere(app, sweep_initiated_payments, module="payments")


def _sweep_loop(app) -> None:
    while True:
        time.sleep(SWEEP_INTERVAL_SECONDS)
        try:
            checked = run_sweep(app)
            heartbeat.record("vipps_sweep", True)
            if checked:
                logger.info("Vipps sweep checked %s pending payment(s)", checked)
        except Exception:  # noqa: BLE001 - a failed sweep must never kill this thread
            heartbeat.record("vipps_sweep", False)
            logger.exception("Vipps sweep failed")


def start_vipps_sweep_job(app) -> None:
    if app.config["TESTING"]:
        return
    if click.get_current_context(silent=True) is not None:
        return
    if app.extensions.get("tenancy") is None:  # one database: no Vipps set up, no loop
        from app.payments.vipps import is_enabled

        with app.app_context():
            if not is_enabled():
                return
    # Many-squares mode has no database of its own to ask at start-up (it would read the server's default database, which is not a square and may not exist): the loop asks every
    # square, and run_everywhere skips a square whose Payments module is off (W27-R8).
    threading.Thread(target=_sweep_loop, args=(app,), daemon=True).start()
