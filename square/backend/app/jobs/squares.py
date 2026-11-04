"""Background jobs for many squares (rootsquares W6-R44; bca-oslo had one database, so its jobs just ran).

`for_each_square(app, work)` runs `work()` once for every ready square, with that square's database, sign-in project and storage in place (as
for a request), and returns the results. One square failing is logged and never stops the others. A `flask`-style app context carries the square,
so links built outside a request use the square's own domain (app/common/urls.py). A job that belongs to an optional module names it
(`module="newsletter"`) and skips the squares that do not have that module.
"""

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from flask import Flask, g

logger = logging.getLogger(__name__)

T = TypeVar("T")


def for_each_square(app: Flask, work: Callable[[], T], module: str | None = None) -> list[T]:
    directory = app.extensions.get("tenancy")
    if directory is None:
        raise RuntimeError("for_each_square needs many-squares mode (PLATFORM_DATABASE_URL)")
    results: list[T] = []
    for tenant in directory.all_tenants():
        if module is not None and tenant.modules is not None and module not in tenant.modules:
            continue  # the owner turned this module off for the square (W8-R15): its job does not run there
        if getattr(tenant, "sleeping", False):
            continue  # the running plan is Keep (W10-R41): nothing runs for a resting square
        try:
            with app.app_context():
                g.tenant = tenant
                results.append(work())
        except Exception:  # noqa: BLE001 - one square's failure must not stop the others
            logger.exception("Job failed for square %s", tenant.slug)
    return results


def run_everywhere(app: Flask, work: Callable[[], Any], module: str | None = None) -> int:
    """Run `work()` (which returns a count) for every square in many-squares mode, else once for the single database; returns the total."""
    if app.extensions.get("tenancy") is not None:
        return sum(int(n or 0) for n in for_each_square(app, work, module))
    with app.app_context():
        return int(work() or 0)
