"""Render's Custom Domains API (W26-R8, ADR 098): add, verify, read and remove a square's own website domain on the square site service. Plain httpx,
like app/providers/resend_domains.py.

Calls, read from Render's own API reference (api-docs.render.com, 2026-11-02):
  base https://api.render.com/v1, header `Authorization: Bearer <key>`;
  POST   /services/{serviceId}/custom-domains {name} -> 201 and an ARRAY of {id, name, domainType, publicSuffix, redirectForName, verificationStatus,
         createdAt, server?}; 409 when the domain exists; 402 when payment is required;
  POST   /services/{serviceId}/custom-domains/{idOrName}/verify -> 202 (asks Render to look at the DNS again, no body);
  GET    /services/{serviceId}/custom-domains/{idOrName} -> 200 and one of those objects (`verificationStatus`: verified | unverified);
  DELETE /services/{serviceId}/custom-domains/{idOrName} -> 204.
Errors are `{"id", "message", "code"?}`.

The key is an account key (it reaches every workspace of the account), so it is held ONLY by the admin service (staff activate and remove
domains); the customer service never gets it. Never logs the key; a refused call is logged by status only. Render's own `message` holds no
secret and is shown to staff."""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from app.shared.config import Settings

log = structlog.get_logger("app.render_domains")
BASE = "https://api.render.com/v1"
_NAME_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
_SERVICE_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


class RenderApiError(Exception):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class RenderDomains:
    def __init__(self, api_key: str, service_id: str, client: httpx.Client | None = None) -> None:
        if not _SERVICE_RE.match(service_id or ""):
            raise RenderApiError("RENDER_SITE_SERVICE_ID is not a service id")
        self._key = api_key
        self._service = service_id
        self._client = client

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        headers = {"Authorization": f"Bearer {self._key}", "Accept": "application/json"}
        url = f"{BASE}/services/{self._service}/custom-domains{path}"
        try:
            client = self._client
            resp = (client.request if client is not None else httpx.request)(method, url, json=body, headers=headers, timeout=20)
        except httpx.HTTPError as exc:
            log.warning("render_domain_unreachable", error=type(exc).__name__)
            raise RenderApiError("The host (Render) could not be reached") from exc
        if resp.status_code >= 300:
            log.warning("render_domain_refused", status=resp.status_code, method=method)
            try:
                text = str(resp.json().get("message") or "")
            except (ValueError, AttributeError):
                text = ""
            raise RenderApiError(text or f"The host (Render) answered {resp.status_code}", resp.status_code)
        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise RenderApiError("The host (Render) sent an answer that could not be read", resp.status_code) from exc

    @staticmethod
    def _name(name: str) -> str:
        value = (name or "").strip().lower()
        if not _NAME_RE.match(value):
            raise RenderApiError("The domain name is not valid")
        return value

    def create(self, name: str) -> list[dict[str, Any]]:
        """Add the domain. Render may add its twin too (the www or the bare name); the answer lists every domain it made."""
        data = self._call("POST", "", {"name": self._name(name)})
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []

    def verify(self, name: str) -> None:
        self._call("POST", f"/{self._name(name)}/verify")

    def get(self, name: str) -> dict[str, Any]:
        data = self._call("GET", f"/{self._name(name)}")
        return data if isinstance(data, dict) else {}

    def delete(self, name: str) -> None:
        self._call("DELETE", f"/{self._name(name)}")


def build_render_domains(settings: Settings) -> RenderDomains | None:
    """None without the key and the service id: staff then add the domain on Render by hand (guide 40)."""
    if settings.RENDER_API_KEY and settings.RENDER_SITE_SERVICE_ID:
        return RenderDomains(settings.RENDER_API_KEY, settings.RENDER_SITE_SERVICE_ID)
    return None
