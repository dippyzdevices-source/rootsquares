"""Structured JSON logs. request_id comes from contextvars and appears on every line.

Rule: no personal data in logs (no emails, names, member data, message text, query strings, request bodies)."""

from __future__ import annotations

import logging
import sys
from typing import TextIO

import structlog


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    out = stream or sys.stdout
    logging.basicConfig(level=level, stream=out, format="%(message)s", force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=out),
        cache_logger_on_first_use=False,
    )
