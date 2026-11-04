"""Membership transactional emails. Best-effort like the order emails: a failed send is logged and never
blocks the approval or payment that triggered it."""

from flask import current_app

from app.common.site import site_name
from app.common.urls import frontend_base_url
from app.email.service import get_email_service
from app.email.templates import render_membership_active_email


def _day(value) -> str:
    return f"{value.day} {value.strftime('%b %Y')}"


def send_membership_active_email(membership) -> bool:
    """Tell the member (for a child, their parent) that the membership is now active. Call once, at the moment
    the status actually changes to active - not on every re-save. Returns whether it was sent."""
    # Imported here: followup_routes is a route module that imports from this package.
    from app.memberships.followup_routes import _person

    member = membership.member
    person = _person(member)
    if not person["email"]:
        return False
    try:
        html_body, text_body, attachments = render_membership_active_email(
            name=person["parent_name"] or member.name,
            child_name=member.name if person["parent_name"] else None,
            membership_type=membership.membership_type,
            start_text=_day(membership.start_date),
            valid_until_text=_day(membership.end_date) if membership.end_date else None,
            dashboard_url=f"{frontend_base_url()}/member",
        )
        get_email_service().send_email(
            to=person["email"],
            subject=f"Your {site_name()} membership is active",
            html=html_body,
            text=text_body,
            attachments=attachments,
        )
        return True
    except Exception as exc:  # noqa: BLE001 - best effort; never log the address
        current_app.logger.error("Membership active email failed to send: %s", exc)
        return False
