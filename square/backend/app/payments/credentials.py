"""The square's own payment provider keys, entered by its admin and stored encrypted (rootsquares W16-R4, docs/plans/payment-credentials-plan.md).

No environment variables and no shared default: a square that has not connected a provider simply cannot take payments with it.
The keys live in the square's own database (`payment_credentials`), encrypted with the server's FERNET_KEY, and are write-only: nothing
here returns them to a browser, a log or an audit entry. `status()` is the only view meant for screens and carries no secret.
"""

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, g, has_app_context, has_request_context

from app.extensions import db
from app.payments.models import PaymentCredential

PROVIDERS = ("vipps", "stripe")
MODES = ("test", "production")
VERSION = "v1:"  # prefix of every stored token, so the key or the format can change later
_DEV_FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"dev-only-fernet-key").digest()).decode()  # same development default as app/tenancy.py


class CredentialsError(Exception):
    """The keys could not be stored (the server has no encryption key in production)."""


@dataclass(frozen=True)
class VippsCredentials:
    client_id: str
    client_secret: str
    subscription_key: str
    msn: str
    mode: str  # "test" | "production"
    webhook_secret: str = ""


@dataclass(frozen=True)
class StripeCredentials:
    secret_key: str  # a restricted key (rk_...) is recommended; sk_... works too
    webhook_secret: str = ""
    tax_code: str = ""  # set = Managed Payments; optional Stripe product tax code (txcd_...) for accounts that use Managed Payments

    @property
    def mode(self) -> str:
        return "test" if "_test_" in self.secret_key else "production"


def _fernet() -> Fernet:
    key = current_app.config.get("FERNET_KEY") or ""
    if not key:
        if current_app.config.get("IS_PRODUCTION"):
            raise CredentialsError("The server has no FERNET_KEY, so payment keys cannot be stored safely.")
        key = _DEV_FERNET_KEY
    return Fernet(key.encode())


def encrypt(data: dict) -> str:
    return VERSION + _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt(token: str) -> dict | None:
    if not token.startswith(VERSION):
        return None
    try:
        return json.loads(_fernet().decrypt(token[len(VERSION):].encode()).decode())
    except (InvalidToken, ValueError):
        current_app.logger.error("payment credentials: a stored token cannot be decrypted (was FERNET_KEY changed?)")
        return None


def _row(provider: str) -> PaymentCredential | None:
    return PaymentCredential.query.filter_by(provider=provider).first()


def get_secret(provider: str) -> tuple[dict, PaymentCredential] | None:
    """The decrypted fields and the row, or None when the provider is not connected. Never pass the dict to a response or a log."""
    row = _row(provider)
    if row is None:
        return None
    fields = decrypt(row.ciphertext)
    return (fields, row) if fields else None


def get_vipps() -> VippsCredentials | None:
    cache = g.setdefault("_vipps_credentials", {}) if has_request_context() else {}
    if "v" in cache:
        return cache["v"]
    found = get_secret("vipps")
    value = None
    if found is not None:
        f, row = found
        if all(f.get(k) for k in ("client_id", "client_secret", "subscription_key", "msn")):
            value = VippsCredentials(f["client_id"], f["client_secret"], f["subscription_key"], f["msn"], row.mode, f.get("webhook_secret", ""))
    cache["v"] = value
    return value


def get_stripe() -> StripeCredentials | None:
    cache = g.setdefault("_stripe_credentials", {}) if has_request_context() else {}
    if "v" in cache:
        return cache["v"]
    found = get_secret("stripe")
    value = StripeCredentials(found[0]["secret_key"], found[0].get("webhook_secret", ""), found[0].get("tax_code", "")) if found and found[0].get("secret_key") else None
    cache["v"] = value
    return value


def save(provider: str, fields: dict, *, mode: str, hint: dict, webhook_registered: bool = False, user_id: int | None = None) -> PaymentCredential:
    if provider not in PROVIDERS or mode not in MODES:
        raise CredentialsError("Unknown provider or mode.")
    token = encrypt(fields)
    row = _row(provider) or PaymentCredential(provider=provider)
    row.ciphertext = token
    row.mode = mode
    row.hint = hint
    row.verified_at = datetime.now(timezone.utc)
    row.webhook_registered = webhook_registered
    row.updated_by = user_id
    db.session.add(row)
    db.session.commit()
    _forget()
    return row


def delete(provider: str) -> bool:
    row = _row(provider)
    if row is None:
        return False
    db.session.delete(row)
    db.session.commit()
    _forget()
    return True


def _forget() -> None:
    if has_request_context():
        g.pop("_vipps_credentials", None)
        g.pop("_stripe_credentials", None)


def status(provider: str) -> dict:
    """What a screen may know: whether the provider is connected, in which mode, and non-secret hints."""
    row = _row(provider) if has_app_context() else None
    if row is None:
        return {"provider": provider, "connected": False}
    return {
        "provider": provider,
        "connected": True,
        "mode": row.mode,
        "hint": row.hint or {},
        "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "webhook_registered": bool(row.webhook_registered),
    }


def last4(value: str) -> str:
    value = (value or "").strip()
    return value[-4:] if len(value) >= 8 else ""
