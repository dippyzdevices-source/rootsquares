"""Platform e-mail (W12-R14): Resend over httpx, or nothing. Plain text plus an optional HTML body with inline images (W13-R5, app/platform/email_html.py).
Never logs the key, the address or the text; only the error type."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.shared.config import Settings
from app.shared.interfaces import EmailProvider

log = structlog.get_logger("app.email")
RESEND_URL = "https://api.resend.com/emails"


class EmailSendError(Exception):
    pass


class ResendEmailProvider:
    def __init__(self, api_key: str, from_address: str, client: httpx.Client | None = None, reply_to: str = "") -> None:
        self._key = api_key
        self._from = from_address
        self._client = client
        self._reply_to = reply_to

    def send(self, to: str, subject: str, body: str, html: str | None = None, inline_images: list[dict[str, Any]] | None = None) -> None:
        payload: dict[str, Any] = {"from": self._from, "to": [to], "subject": subject, "text": body}
        if self._reply_to:
            payload["reply_to"] = self._reply_to  # the From address only sends (no mailbox): replies go to a real one
        if html:
            payload["html"] = html
            if inline_images:
                payload["attachments"] = inline_images
        headers = {"Authorization": f"Bearer {self._key}"}
        try:
            if self._client is not None:
                resp = self._client.post(RESEND_URL, json=payload, headers=headers, timeout=15)
            else:
                resp = httpx.post(RESEND_URL, json=payload, headers=headers, timeout=15)
        except httpx.HTTPError as exc:
            log.warning("email_failed", error=type(exc).__name__)
            raise EmailSendError("The e-mail service could not be reached") from exc
        if resp.status_code >= 300:
            log.warning("email_refused", status=resp.status_code)
            raise EmailSendError(f"The e-mail service answered {resp.status_code}")


def build_email(settings: Settings) -> EmailProvider | None:
    if settings.EMAIL_PROVIDER == "resend":
        return ResendEmailProvider(settings.RESEND_API_KEY, settings.EMAIL_FROM, reply_to=settings.EMAIL_REPLY_TO)
    return None
