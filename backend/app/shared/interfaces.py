"""Provider and cross-package interfaces (docs/reference/architecture.md section 13; ADR 026).

Only signatures that Stage 1 can already fix. They grow stage by stage; concrete providers live in app/providers
and every interface gets an in-memory fake there for tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class AuthProvider(Protocol):
    name: str

    def verify(self, token: str) -> dict[str, str]:
        """Return {"sub": ..., "email": ..., "name": ...} or raise jwt.PyJWTError on an invalid token."""


class StorageProvider(Protocol):
    def upload(self, key: str, data: bytes, content_type: str) -> None: ...

    def delete(self, key: str) -> None: ...

    def url_for(self, key: str) -> str:
        """Stable public URL (public bucket) or a presigned, time-limited URL (private bucket)."""

    def key_from_url(self, url: str) -> str | None:
        """Inverse of url_for for a URL this provider produced, else None."""


class EmailProvider(Protocol):
    def send(self, to: str, subject: str, body: str, html: str | None = None, inline_images: list[dict[str, Any]] | None = None) -> None: ...


class PaymentProvider(Protocol):
    name: str


class DomainProvider(Protocol):
    def add_domain(self, hostname: str) -> str: ...


class BillingProvider(Protocol):
    name: str


class JobQueue(Protocol):
    def enqueue(self, kind: str, payload: dict[str, object], square: str | None = None) -> None: ...


class RateLimiter(Protocol):
    def allow(self, key: str, limit: int, window_seconds: int) -> bool: ...


@dataclass
class Providers:
    """Container wired in create_app and kept in app.extensions["providers"]. Empty until the stages that need them."""

    auth: AuthProvider | None = None
    storage: StorageProvider | None = None  # public bucket
    private_storage: StorageProvider | None = None
    email: EmailProvider | None = None
    payment: PaymentProvider | None = None
    domain: DomainProvider | None = None
    billing: BillingProvider | None = None
    jobs: JobQueue | None = None
    rate_limiter: RateLimiter | None = None
