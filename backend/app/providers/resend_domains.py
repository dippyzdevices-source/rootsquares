"""Resend's Domains API (W25-R24, ADR 091): add, verify, read and remove a square's own sending domain. Plain httpx, like app/providers/email.py.

Calls, read from Resend's own reference on 2026-10-30:
  POST /domains {name, region} -> {id, status, records: [{record, name, type, value, priority, ttl, status}]};
  POST /domains/{id}/verify (asks Resend to look at the DNS again, answers only {object, id});
  GET /domains/{id} (the status and the records);  DELETE /domains/{id}.
Status values: not_started, pending, verified, partially_verified, partially_failed, failed, temporary_failure.

Needs a **full access** key of the Resend account (a sending-only key cannot manage domains): `RESEND_DOMAINS_API_KEY`, a different key from the
sending one and held only by the customer service. Never logs the key; a refused call is logged by status only. The text Resend answers with
(its own `message`) holds no secret and is shown to the owner, so a wrong domain name is explained."""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from app.shared.config import Settings

log = structlog.get_logger("app.mail_domains")
BASE = "https://api.resend.com"
_ID_RE = re.compile(r"^[0-9a-fA-F-]{20,64}$")


class DomainApiError(Exception):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class ResendDomains:
    def __init__(self, api_key: str, region: str = "eu-west-1", client: httpx.Client | None = None) -> None:
        self._key = api_key
        self._region = region
        self._client = client

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._key}"}
        try:
            client = self._client
            resp = (client.request if client is not None else httpx.request)(method, BASE + path, json=body, headers=headers, timeout=20)
        except httpx.HTTPError as exc:
            log.warning("mail_domain_unreachable", error=type(exc).__name__)
            raise DomainApiError("The e-mail service could not be reached") from exc
        if resp.status_code >= 300:
            log.warning("mail_domain_refused", status=resp.status_code, path=path.split("/")[1] if "/" in path else path)
            try:
                text = str(resp.json().get("message") or "")
            except ValueError:
                text = ""
            raise DomainApiError(text or f"The e-mail service answered {resp.status_code}", resp.status_code)
        try:
            data = resp.json()
        except ValueError as exc:
            raise DomainApiError("The e-mail service sent an answer that could not be read", resp.status_code) from exc
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _id(domain_id: str) -> str:
        if not _ID_RE.match(domain_id or ""):
            raise DomainApiError("The stored domain id is not valid")
        return domain_id

    def create(self, name: str) -> dict[str, Any]:
        return self._call("POST", "/domains", {"name": name, "region": self._region})

    def verify(self, domain_id: str) -> dict[str, Any]:
        return self._call("POST", f"/domains/{self._id(domain_id)}/verify")

    def get(self, domain_id: str) -> dict[str, Any]:
        return self._call("GET", f"/domains/{self._id(domain_id)}")

    def delete(self, domain_id: str) -> dict[str, Any]:
        return self._call("DELETE", f"/domains/{self._id(domain_id)}")


def build_resend_domains(settings: Settings) -> ResendDomains | None:
    """None when no full-access key is set: the owner's card then says the feature is not switched on yet."""
    if settings.RESEND_DOMAINS_API_KEY:
        return ResendDomains(settings.RESEND_DOMAINS_API_KEY, settings.RESEND_DOMAINS_REGION)
    return None
