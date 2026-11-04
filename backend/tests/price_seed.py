"""The prices the billing tests run with. They are TEST DATA written into the test database, exactly as a platform admin would on the Prices page:
the application itself holds no price (W14-R29)."""

from __future__ import annotations

from flask import Flask

from app.platform.models import PlanPrice

TEST_PRICES: dict[str, tuple[int, str]] = {
    "launch.roots": (14_900, "one_off"),
    "launch.square": (29_900, "one_off"),
    "launch.grove": (39_900, "one_off"),
    "launch.event": (2_500, "one_off"),
    "running.keep.month": (500, "month"),
    "running.keep.year": (5_000, "year"),
    "running.live.month": (2_500, "month"),
    "running.live.year": (25_000, "year"),
}


def seed_prices(app: Flask) -> None:
    db = app.extensions["db_factory"]()()
    try:
        for key, (amount, interval) in TEST_PRICES.items():
            db.add(PlanPrice(key=key, amount_minor=amount, currency="USD", interval=interval))
        db.commit()
    finally:
        db.close()
