"""Tests that need Vipps connect it the way a square's owner does: keys stored in the square's own database (no environment variables)."""


def connect_vipps(webhook_secret: str = "x", mode: str = "test") -> None:
    from app.payments import credentials

    credentials.save(
        "vipps",
        {"client_id": "id", "client_secret": "s", "subscription_key": "k", "msn": "123", "webhook_secret": webhook_secret},
        mode=mode,
        hint={"client_id_last4": "", "msn": "123"},
    )
