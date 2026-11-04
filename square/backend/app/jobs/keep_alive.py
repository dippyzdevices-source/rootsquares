"""Pings this app's own public URL every 14 minutes so Render's free tier never sees the
~15-minute idle window that would otherwise spin the service down. Ported from a Node.js
`cron` snippet (backend/jobs/serverAlive.job.py, invalid as Python — removed) to a plain
Python daemon thread, since a repeating self-ping doesn't need a new dependency.
"""

import logging
import threading
import time
import urllib.request

import click

from app.jobs import heartbeat

logger = logging.getLogger(__name__)

PING_INTERVAL_SECONDS = 14 * 60


def _ping_loop(url: str) -> None:
    while True:
        time.sleep(PING_INTERVAL_SECONDS)
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                logger.info("Keep-alive ping to %s succeeded (%s)", url, response.status)
            heartbeat.record("keep_alive", True)
        except Exception as exc:  # noqa: BLE001 - a failed ping must never crash this thread
            heartbeat.record("keep_alive", False)
            logger.warning("Keep-alive ping to %s failed: %s", url, exc)


def start_keep_alive_job(app) -> None:
    """No-op unless KEEP_ALIVE_URL is set (e.g. local dev/tests never ping anything), and
    no-op for any `flask <command>` invocation (`flask users promote`, `flask db upgrade`,
    etc.) — those run inside a Click context, which a real gunicorn-served `wsgi:app` import
    never does, so checking for one distinguishes "someone ran a one-off CLI command" from
    "this is the actual long-running web process" without needing a separate env var. A CLI
    command has no business starting a background ping loop meant to keep the live web
    service warm.
    """
    if app.config["TESTING"] or not app.config.get("KEEP_ALIVE_URL"):
        return
    if click.get_current_context(silent=True) is not None:
        return

    url = app.config["KEEP_ALIVE_URL"]
    threading.Thread(target=_ping_loop, args=(url,), daemon=True).start()
