"""Order/ticket transactional emails — send_* functions are the only integration point
between the orders/admin_orders routes and EmailService. Each is best-effort: a failed send
is logged server-side and never blocks the underlying order action (checkout, payment claim,
mark-paid, and reject all succeed regardless of email delivery).
"""

from urllib.parse import urlencode

from flask import current_app

from app.common.site import site_name
from app.common.urls import frontend_base_url
from app.email.service import contact_recipients, get_email_service
from app.email.templates import (
    render_order_awaiting_verification_email,
    render_bank_order_received_email,
    render_cash_order_received_email,
    render_order_cancelled_email,
    render_order_refunded_email,
    render_order_received_email,
    render_order_rejected_email,
    render_vipps_payment_failed_email,
    render_payment_notification_received_email,
    render_tickets_confirmed_email,
)
from app.events.models import Event
from app.extensions import db
from app.orders.models import Order
from app.orders.service import cash_note_for_event


def _get_event(order: Order) -> Event | None:
    return db.session.get(Event, order.event_id)


def _order_lookup_url(order: Order) -> str:
    """Deep link to OrderLookupView.vue that pre-fills and auto-submits the lookup form —
    see that component's own query-param handling."""
    query = urlencode({"order_number": order.order_number, "email": order.customer_email})
    return f"{frontend_base_url()}/orders/lookup?{query}"


def _send(
    *,
    to: str | list[str],
    subject: str,
    html: str,
    text: str,
    reply_to: str | None = None,
    attachments: list[dict] | None = None,
) -> bool:
    # Returns whether the send worked (callers that only fire-and-forget ignore it).
    # Deliberately broad except — unlike app.contact.routes (where a failed send is the whole
    # point of the request and a 503 is the right response), an order/ticket action must never
    # fail because of an email hiccup: money has already changed hands or a real admin action
    # already happened. Any exception here is logged and swallowed, never re-raised.
    try:
        get_email_service().send_email(
            to=to, subject=subject, html=html, text=text, reply_to=reply_to, attachments=attachments
        )
        return True
    except Exception as exc:  # noqa: BLE001 - see comment above
        current_app.logger.error("Order email failed to send: %s", exc)
        return False


def send_order_received_email(order: Order) -> None:
    event = _get_event(order)
    from app.settings.models import get_site_settings

    html_body, text_body, attachments = render_order_received_email(
        order=order, event=event, order_url=_order_lookup_url(order), vipps_number=(get_site_settings().vipps_number or "").strip()
    )
    _send(
        to=order.customer_email,
        subject=f"Your {site_name()} order {order.order_number} — payment instructions",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )


def send_cash_order_received_email(order: Order) -> None:
    event = _get_event(order)
    html_body, text_body, attachments = render_cash_order_received_email(
        order=order, event=event, note=cash_note_for_event(event), order_url=_order_lookup_url(order)
    )
    _send(
        to=order.customer_email,
        subject=f"Your {site_name()} order {order.order_number} — pay with cash",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )


def send_bank_order_received_email(order: Order) -> None:
    from app.payments.bank import bank_details
    from app.settings.models import get_site_settings

    event = _get_event(order)
    html_body, text_body, attachments = render_bank_order_received_email(
        order=order, event=event, bank=bank_details(get_site_settings()), order_url=_order_lookup_url(order)
    )
    _send(
        to=order.customer_email,
        subject=f"Your {site_name()} order {order.order_number} — bank transfer details",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )


def send_order_awaiting_verification_email(order: Order) -> None:
    recipients = contact_recipients()
    if not recipients:
        current_app.logger.error("Order awaiting-verification email skipped — the square has no contact e-mail and CONTACT_EMAIL is not configured.")
        return

    event = _get_event(order)
    admin_url = f"{frontend_base_url()}/admin/orders/{order.id}"
    html_body, text_body, attachments = render_order_awaiting_verification_email(
        order=order, event=event, admin_url=admin_url
    )
    _send(
        to=recipients,
        subject=f"[{site_name()}] Order {order.order_number} awaiting payment verification",
        html=html_body,
        text=text_body,
        reply_to=order.customer_email,
        attachments=attachments,
    )


def send_payment_notification_received_email(order: Order) -> None:
    """To the customer, right after they click "I've made this payment" — separate from
    send_order_awaiting_verification_email, which goes to CONTACT_EMAIL instead."""
    event = _get_event(order)
    html_body, text_body, attachments = render_payment_notification_received_email(order=order, event=event)
    _send(
        to=order.customer_email,
        subject=f"We've received your payment notification for order {order.order_number}",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )


def send_tickets_confirmed_email(order: Order) -> None:
    event = _get_event(order)
    html_body, text_body, attachments = render_tickets_confirmed_email(order=order, event=event)
    _send(
        to=order.customer_email,
        subject=f"Your {site_name()} tickets for {event.title if event else 'your event'} are confirmed",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )


def resend_tickets_confirmed_email(order: Order) -> bool:
    """The same tickets-confirmed email, sent again by an admin (a buyer says it never arrived).
    Unlike the automatic send, the caller learns whether it went out."""
    event = _get_event(order)
    html_body, text_body, attachments = render_tickets_confirmed_email(order=order, event=event)
    return _send(
        to=order.customer_email,
        subject=f"Your {site_name()} tickets for {event.title if event else 'your event'} are confirmed",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )


def send_order_rejected_email(order: Order, reason: str) -> None:
    event = _get_event(order)
    html_body, text_body, attachments = render_order_rejected_email(order=order, event=event, reason=reason)
    _send(
        to=order.customer_email,
        subject=f"Update on your {site_name()} order {order.order_number}",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )


def send_vipps_payment_failed_email(order: Order) -> None:
    event = _get_event(order)
    retry_url = f"{frontend_base_url()}/events/{event.slug}" if event else ""
    html_body, text_body, attachments = render_vipps_payment_failed_email(order=order, event=event, retry_url=retry_url)
    _send(
        to=order.customer_email,
        subject=f"Your payment for {site_name()} order {order.order_number} did not go through",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )


def send_order_refunded_email(order: Order, amount_ore: int, reason: str) -> None:
    event = _get_event(order)
    html_body, text_body, attachments = render_order_refunded_email(
        order=order, event=event, amount_ore=amount_ore, reason=reason
    )
    _send(
        to=order.customer_email,
        subject=f"Your {site_name()} order {order.order_number} has been refunded",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )


def send_order_cancelled_email(order: Order, reason: str) -> None:
    event = _get_event(order)
    html_body, text_body, attachments = render_order_cancelled_email(order=order, event=event, reason=reason)
    _send(
        to=order.customer_email,
        subject=f"Your {site_name()} order {order.order_number} has been cancelled",
        html=html_body,
        text=text_body,
        attachments=attachments,
    )
