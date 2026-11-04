"""The e-mails of the own sending domain (ADR 095, W25-R31): to staff when an owner asks, to the owner when staff act or when the domain is ready,
and the instructions
an owner sends to the person who looks after their domain. Each function answers (subject, plain text); `email_html.from_text` makes the HTML of the same text.
Only the square's name, a domain and plain sentences go in: no personal data of members."""

from __future__ import annotations

from app.platform.models import Square
from app.shared.config import Settings


def owner_link(settings: Settings, sq: Square) -> str:
    return f"{settings.PLATFORM_FRONTEND_URL.rstrip('/')}/squares/{sq.id}/settings"


def staff_link(settings: Settings, sq: Square) -> str:
    base = (settings.admin_origins or [settings.PLATFORM_FRONTEND_URL])[0].rstrip("/")
    return f"{base}/squares/{sq.id}?tab=actions"


def staff_request(settings: Settings, sq: Square) -> tuple[str, str]:
    domain, local = sq.mail_domain_request or "", sq.mail_domain_request_local or "hello"
    return f"Own sending domain requested: {sq.name}", (
        f"{sq.name} asks for its own sending domain.\n\nDomain: {domain}\nSender: {local}@{domain}\n\n"
        f"Open the square in the admin application (Actions, Own sending domain) to set it up or turn it down:\n{staff_link(settings, sq)}\n\n"
        "The owner is told by e-mail when you set it up.\n"
    )


def staff_auto(settings: Settings, sq: Square) -> tuple[str, str]:
    domain, local = sq.mail_domain or "", sq.mail_from_local or "hello"
    return f"Own sending domain set up: {sq.name}", (
        f"{sq.name} asked for its own sending domain and it was set up at once (automatic approval is on).\n\nDomain: {domain}\nSender: {local}@{domain}\n\n"
        f"The owner was told to add the records. Look at it in the admin application:\n{staff_link(settings, sq)}\n"
    )


def staff_help(settings: Settings, sq: Square, contact: str | None) -> tuple[str, str]:
    return f"IT help asked: {sq.name}", (
        f"{sq.name} asked for help with its own sending domain. The owner was told that a small one-time support fee applies.\n\n"
        f"Domain: {sq.mail_domain or sq.mail_domain_request or 'not chosen yet'}\nE-mail contact of the square: {contact or 'not set'}\n\n"
        f"Open the square in the admin application:\n{staff_link(settings, sq)}\n"
    )


def owner_approved(settings: Settings, sq: Square) -> tuple[str, str]:
    return f"Your own sending domain for {sq.name}: one step for you", (
        f"We have set up {sq.mail_domain} for {sq.name}.\n\n"
        "One step is left, for you or whoever looks after your domain: add the e-mail records shown on your square's Settings page at your domain provider. "
        "You can send them to your web person from that page. They do not change your website or your normal mailboxes.\n\n"
        "We check every hour and e-mail you when it is ready.\n\n"
        f"{owner_link(settings, sq)}\n"
    )


def owner_rejected(settings: Settings, sq: Square, domain: str, note: str) -> tuple[str, str]:
    why = f"\nWhat we say: {note.strip()}\n" if note.strip() else ""
    return f"We could not set up {domain} for {sq.name}", (
        f"We could not set up {domain} as the sending domain of {sq.name}.\n{why}\n"
        "Nothing has changed: your mail still goes out from the shared address. "
        "You can ask for another domain, or ask us for help, on your square's Settings page.\n\n"
        f"{owner_link(settings, sq)}\n"
    )


def owner_ready(settings: Settings, sq: Square) -> tuple[str, str]:
    address = f"{sq.mail_from_local or 'hello'}@{sq.mail_domain}"
    return f"Your own sending address for {sq.name} is ready", (
        f"{sq.mail_domain} is verified. From now on the mail of {sq.name} is sent from {address}, and a newsletter can be sent.\n\n"
        f"You can change the name before the @ or remove the domain any time:\n{owner_link(settings, sq)}\n"
    )


def owner_failed(settings: Settings, sq: Square) -> tuple[str, str]:
    return f"We could not verify {sq.mail_domain} for {sq.name}", (
        f"The e-mail records for {sq.mail_domain} were not found. Your mail still goes out from the shared address, and a newsletter cannot be sent.\n\n"
        "Check that every record on your square's Settings page was added exactly as shown at your domain provider. If you would like help, press "
        '"Ask us for help" there (a small one-time support fee applies).\n\n'
        f"{owner_link(settings, sq)}\n"
    )


def instructions(sq: Square, records: list[dict[str, object]]) -> tuple[str, str]:
    lines = [
        f"{sq.name} would like to send its e-mail from the domain {sq.mail_domain}.",
        "",
        "To allow that, please add the records below at the place where the domain is managed (the DNS settings of your domain provider). "
        "They do not change the website or the normal mailboxes of the domain. Copy each name and value exactly as shown. "
        "The names are relative to the main domain, which is how most DNS pages want them.",
        "",
    ]
    for r in records:
        lines.append(f"Type: {r.get('type', '')}")
        lines.append(f"Name: {r.get('name', '')}")
        lines.append(f"Value: {r.get('value', '')}")
        if r.get("priority") not in (None, ""):
            lines.append(f"Priority: {r.get('priority')}")
        lines.append("")
    lines.append("When the records are in, it can take from a few minutes to a few hours before they are seen. The owner of the square is told when it works.")
    return f"E-mail records to add for {sq.mail_domain}", "\n".join(lines) + "\n"
