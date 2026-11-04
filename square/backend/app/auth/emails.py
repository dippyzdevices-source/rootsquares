"""Emails sent to a person about their own account (as opposed to the admin/ops emails in
app.orders.emails). Each is best-effort: a failure is logged and swallowed, never raised, because
none of them may get in the way of what the person is actually doing (signing in).
"""

from app.common.site import site_name
from flask import current_app

from app.auth.models import User
from app.common.urls import frontend_base_url
from app.email.service import get_email_service
from app.modules import module_enabled
from app.email.templates import render_welcome_email



def _dashboard_text() -> str:
    """What the member area is for in this square (W8-R19): only the parts of it that the square has."""
    todo = ["update your details"]
    if module_enabled("memberships"):
        todo.append("request a membership")
    if module_enabled("tickets"):
        todo.append("find your tickets")
    text = todo[0] if len(todo) == 1 else ", ".join(todo[:-1]) + " and " + todo[-1]
    return text[0].upper() + text[1:] + "."


def send_welcome_email(user: User) -> bool:
    """Returns True when the mail service accepted it (first sign-in ignores the result; an admin
    resending it needs to know)."""
    return send_welcome_email_to(user.email)


def send_welcome_email_to(address: str | None) -> bool:
    """The same welcome email to any address - e.g. a roster member who has no login yet."""
    if not address:
        return False
    base_url = frontend_base_url()
    try:
        html_body, text_body, attachments = render_welcome_email(
            dashboard_url=f"{base_url}/member",
            dashboard_text=_dashboard_text(),
            events_url=f"{base_url}/events" if module_enabled("events") else None,
            gallery_url=f"{base_url}/gallery" if module_enabled("gallery") else None,
        )
        get_email_service().send_email(
            to=address,
            subject=f"Welcome to {site_name()}",
            html=html_body,
            text=text_body,
            attachments=attachments,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - best effort, see module docstring
        # Never log the address — only that it failed and why.
        current_app.logger.error("Welcome email failed to send: %s", exc)
        return False
