"""EmailService — the only way backend code sends email. Resend is the concrete provider
today, but nothing outside this module ever imports `resend` directly, so swapping providers
later (or adding a second one) never touches a route/service that just wants to send an email.

Usage: `get_email_service().send_email(to=..., subject=..., html=..., text=..., reply_to=...)`.
Never construct ResendEmailService/FakeEmailService directly outside this module/tests.
"""

import uuid
from abc import ABC, abstractmethod

import resend
from flask import current_app


class EmailServiceError(Exception):
    """Raised when an email genuinely failed to send (provider error, network failure)."""


class EmailServiceNotConfiguredError(EmailServiceError):
    """Raised only when send_email() is actually called without RESEND_API_KEY/EMAIL_FROM
    configured — never at app startup, matching this app's lazy-configuration convention for
    optional external integrations (see app.storage.service / app.payments.online_provider).
    """


class EmailService(ABC):
    @abstractmethod
    def send_email(
        self,
        *,
        to: str | list[str],
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
        attachments: list[dict] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Returns the provider's message id. `to` may be a single address or a list — Resend
        sends one message to every address in the list, all visible to each other in the To
        header (see app.email.service.parse_recipient_list for the CONTACT_EMAIL multi-address
        convention). Each attachment is {"filename": str, "content": list[int], "content_id":
        str | None} — content_id lets the html body reference it inline via
        <img src="cid:...">  (see app.email.templates). `headers` adds custom message headers
        (e.g. List-Unsubscribe on newsletter mail).
        """
        ...


class ResendEmailService(EmailService):
    """The only real implementation. `from_address` is the full "Name <email@domain>" sender
    string (EMAIL_FROM) — the visitor's own address must never be used as From, only Reply-To.
    """

    def __init__(self, *, api_key: str, from_address: str, default_reply_to: str = ""):
        self._from_address = from_address
        self._default_reply_to = default_reply_to  # the square's own contact address: a reply to a customer mail must reach someone (the From address has no mailbox)
        resend.api_key = api_key

    def send_email(
        self,
        *,
        to: str | list[str],
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
        attachments: list[dict] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        params: dict = {
            "from": self._from_address,
            "to": to if isinstance(to, list) else [to],
            "subject": subject,
            "html": html,
        }
        if text:
            params["text"] = text
        if reply_to or self._default_reply_to:
            params["reply_to"] = reply_to or self._default_reply_to
        if attachments:
            params["attachments"] = attachments
        if headers:
            params["headers"] = headers

        try:
            result = resend.Emails.send(params)
        except Exception as exc:
            # Never log the API key or the email body — only enough to diagnose a delivery
            # failure server-side (see app.contact.routes, which never surfaces this to the
            # visitor beyond a generic friendly message).
            current_app.logger.error("Email send failed provider=resend error=%s", exc)
            raise EmailServiceError("Failed to send email") from exc

        message_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        current_app.logger.info("Email sent successfully provider=resend message_id=%s", message_id)
        return message_id


class FakeEmailService(EmailService):
    """In-memory EmailService for tests — no network call, ever. Records every call in
    `sent_emails` so tests can assert on recipient/subject/reply_to/html/text.
    """

    def __init__(self):
        self.sent_emails: list[dict] = []

    def send_email(
        self,
        *,
        to: str | list[str],
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
        attachments: list[dict] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        message_id = f"fake-{uuid.uuid4()}"
        self.sent_emails.append(
            {
                "id": message_id,
                "to": to,
                "subject": subject,
                "html": html,
                "text": text,
                "reply_to": reply_to,
                "attachments": attachments or [],
                "headers": headers or {},
            }
        )
        return message_id


class NotConfiguredEmailService(EmailService):
    """Wired up whenever RESEND_API_KEY/EMAIL_FROM are missing outside TESTING — the app still
    starts normally (no crash on boot), but any real attempt to send raises a clear,
    developer-facing error instead of silently pretending to succeed.
    """

    def send_email(self, **_kwargs) -> str:
        raise EmailServiceNotConfiguredError(
            "Email is not configured — set RESEND_API_KEY and EMAIL_FROM to send email."
        )


def sender_for(site_name: str, configured_from: str) -> str:
    """`Name <address>` with the square's own name in front of the configured sending address (rootsquares W6-R43): the platform verifies one sending
    domain, and every square's mail shows that square's name. Without a name the configured sender is kept."""
    from email.utils import formataddr, parseaddr

    _, address = parseaddr(configured_from)
    if "@" not in address or not site_name.strip():
        return configured_from
    return formataddr((site_name.strip().replace("\n", " ").replace("\r", " "), address))


def get_email_service() -> EmailService:
    service = current_app.extensions["email_service"]
    from app.tenancy import current_tenant

    tenant = current_tenant()
    if tenant is not None and isinstance(service, ResendEmailService):
        own = square_contact_email()
        # a Grove square with a verified own domain sends from it (platform squares.mail_domain, ADR 091); everyone else from the shared sending address
        sender = getattr(tenant, "mail_from_address", "") or current_app.config["EMAIL_FROM"]
        return ResendEmailService(api_key=current_app.config["RESEND_API_KEY"], from_address=sender_for(tenant.name, sender), default_reply_to=own[0] if own else "")
    return service


def square_contact_email() -> list[str]:
    """Where the square's mail goes and where replies to it go, in this order (ADR 093, W25-R9): the address the owner set on the platform (squares
    `mail_contact_email`), else the square's public contact address (its site setting `contact_email`); empty when neither is set or no square is served."""
    from app.tenancy import current_tenant

    tenant = current_tenant()
    own = (getattr(tenant, "mail_contact_email", "") or "").strip()
    if own:
        return parse_recipient_list(own)
    try:
        from app.settings.models import get_site_settings

        return parse_recipient_list((get_site_settings().contact_email or "").strip())
    except Exception:  # noqa: BLE001 - mail must not fail because a setting could not be read (background job, no database open)
        return []


def own_sending_domain_verified() -> bool:
    """True when the square sends from its own verified domain. With no square served (single-site set-up, tests) nothing is enforced, so True."""
    from app.tenancy import current_tenant

    tenant = current_tenant()
    return tenant is None or bool(getattr(tenant, "mail_from_address", ""))


def contact_recipients() -> list[str]:
    """Who gets the notifications of the square's contact form and of payments to verify: the square's own contact address; `CONTACT_EMAIL` of the
    server only as a fallback for a single-site set-up (rootsquares W25-R8: it used to be one address for every square)."""
    return square_contact_email() or parse_recipient_list(current_app.config.get("CONTACT_EMAIL", ""))


def parse_recipient_list(raw: str) -> list[str]:
    """Splits a CONTACT_EMAIL-style config value into addresses — comma-separated, each
    trimmed, blanks dropped. A single address (no comma) still returns a one-item list."""
    return [addr.strip() for addr in raw.split(",") if addr.strip()]
