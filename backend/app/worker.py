"""Job runner entrypoint (skeleton). Later: poll the Postgres job table with SELECT ... FOR UPDATE SKIP LOCKED.
No daemon threads: run this as a separate process (`python -m app.worker`)."""

from __future__ import annotations

import structlog

from app.shared.config import Settings
from app.shared.logging import configure_logging


def main() -> int:
    settings = Settings()
    configure_logging(settings.LOG_LEVEL)
    structlog.get_logger("app.worker").info("worker_skeleton", detail="no job runner yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
