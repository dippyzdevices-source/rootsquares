"""When each background job last ran and whether that run worked (rootsquares W10-R19, ADR 038).

Kept in memory per server process: one flag and one time per job, no content. The owner's Health tab reads it through app/health_report.py. A job that has
not ticked yet since the server started says so; it is not called failing.
"""

from __future__ import annotations

import threading
import time
from typing import TypedDict


class Beat(TypedDict):
    at: float
    ok: bool


_beats: dict[str, Beat] = {}
_lock = threading.Lock()


def record(job: str, ok: bool) -> None:
    with _lock:
        _beats[job] = {"at": time.time(), "ok": ok}


def last(job: str) -> Beat | None:
    with _lock:
        b = _beats.get(job)
        return dict(b) if b else None  # type: ignore[return-value]
