"""Email content builders. One function per email "type" — kept separate from EmailService
so future emails (ticket confirmations, membership confirmations, etc.) each get their own
small render function here without touching the service/provider layer at all.
"""

import base64
import html
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from string import Template
from types import SimpleNamespace
from urllib.parse import quote

from app.common.money import format_money
from app.common.site import order_prefix, site_currency, site_domain, site_logo_url, site_name, site_name_html, site_theme_id  # noqa: F401
from app.email import own_look
from app.email.theme_palette import THEME_EMAIL_COLORS

import bleach
import qrcode

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_ASSETS_DIR = _TEMPLATES_DIR / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts"

# Brand palette (W13-R29): the colours come from the served square's theme (app/email/theme_palette.py, generated from design/tenant-themes-v7/themes.json by
# square/frontend/scripts/build_layout_themes.py); paper-brick, and any unknown theme, gives the terracotta / paper / ink colours these emails always had. Values are
# plain hex (email clients do not support CSS variables) and are read when an email is rendered, because every square has its own.
def _pal() -> SimpleNamespace:
    # the owner's own three colours (Theme page, W18-R51) come first, else the theme's colours
    return SimpleNamespace(**(own_look.colours() or THEME_EMAIL_COLORS.get(site_theme_id(), THEME_EMAIL_COLORS["paper-brick"])))


def _btn_r(default: int) -> str:
    """The corner of a button in px: the owner's button shape (W18-R51), else the corner this e-mail always had."""
    return f"{own_look.button_radius(default)}px"


def _card_r(default: int) -> str:
    """The corner of a card or panel in px: the owner's card shape (W18-R51), else the corner this e-mail always had."""
    return f"{own_look.card_radius(default)}px"

_LOGO_CID = "site-logo"


@lru_cache(maxsize=None)
def _font_data_uri(filename: str) -> str:
    """Base64-encodes a WOFF2 font file (backend/app/email/templates/assets/fonts/) into a
    `data:` URI for inline @font-face embedding — the real Marcellus/Karla from the live design
    system, with NO network request. A remote @import (tried first, then reverted) let some real
    mail clients start rendering before the font arrived, then reflow — visibly "jumping" —
    once it did; an inline data URI is part of the same document load, so there is nothing to
    arrive late. Cached (the files never change at runtime) — base64 is otherwise recomputed on
    every render. Latin-subset-only builds (~24KB/~14KB raw) keep the added weight modest; a
    client that doesn't support @font-face at all just uses the declared fallback stack, same as
    before.
    """
    data = (_FONTS_DIR / filename).read_bytes()
    return f"data:font/woff2;base64,{base64.b64encode(data).decode()}"


def _format_price(amount_ore: int) -> str:
    return format_money(amount_ore, site_currency())


@lru_cache(maxsize=64)
def _logo_png(letter: str) -> bytes:
    """The site's mark for the email header: its first letter in a ring (rootsquares W6-R40; bca-oslo attached its own logo image here)."""
    from PIL import Image, ImageDraw, ImageFont

    size = 128
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((6, 6, size - 6, size - 6), outline=_pal().accent, width=6)
    font = ImageFont.load_default(size=64)
    draw.text((size / 2, size / 2), letter, fill=_pal().heading, font=font, anchor="mm")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


_LOGO_MAX_BYTES = 1_000_000
_logo_images: dict[str, bytes] = {}  # uploaded logos already fetched and shrunk, by address (a replaced logo has a new address)


def _uploaded_logo_png(url: str) -> bytes | None:
    """The square's uploaded logo as a small PNG for the email header (rootsquares W6-R59), or None when it cannot be fetched or read: the email is
    then sent with the letter mark instead of failing. Fetched once per address and kept; a failure is not kept, so the next email tries again."""
    if url in _logo_images:
        return _logo_images[url]
    try:
        import requests
        from PIL import Image

        response = requests.get(url, timeout=5, stream=True)
        response.raise_for_status()
        data = response.raw.read(_LOGO_MAX_BYTES + 1, decode_content=True)
        if not data or len(data) > _LOGO_MAX_BYTES:
            return None
        image = Image.open(BytesIO(data))
        image.thumbnail((128, 128))  # the header shows it at about 40px; this keeps the email small and sharp enough
        buffer = BytesIO()
        image.convert("RGBA").save(buffer, format="PNG")
    except Exception:  # a broken logo must never stop an email (network, bad image, anything)
        return None
    _logo_images[url] = buffer.getvalue()
    return _logo_images[url]


def _logo_attachment(content_id: str) -> dict:
    """The site's mark every email's header shows, as a CID-embedded attachment — same reasoning as _ticket_qr_attachment's docstring: a remote
    <img> would depend on FRONTEND_ORIGIN being a publicly reachable URL (never true in local/test, since email clients fetch images from their
    own servers, not the sender's machine) and a data-URI <img> is blocked by Gmail and others. A real file, attached once per email, works everywhere.
    """
    url = site_logo_url()
    uploaded = _uploaded_logo_png(url) if url else None
    letter = (site_name().strip()[:1] or "·").upper()
    return {
        "filename": "logo.png",
        "content": list(uploaded or _logo_png(letter)),
        "content_id": content_id,
        "content_type": "image/png",
    }


def _ticket_qr_attachment(ticket_code: str, content_id: str) -> dict:
    """Same QR data as app.tickets.qr.generate_qr_data_url, but as a CID attachment rather
    than a data-URI <img>, which Gmail and several other mail clients block.
    """
    buffer = BytesIO()
    qrcode.make(ticket_code).save(buffer, format="PNG")
    return {
        "filename": "ticket-qr.png",
        "content": list(buffer.getvalue()),
        "content_id": content_id,
        "content_type": "image/png",
    }


def _format_event_datetime(dt) -> str:
    return dt.strftime("%A %d %B %Y, %H:%M") if dt else ""


def _directions_url(event) -> str | None:
    """Mirrors frontend/src/pages/public/EventDetailView.vue's directionsUrl computed."""
    if event is None:
        return None
    parts = [p for p in (event.venue, event.address) if p]
    if not parts:
        return None
    return "https://www.google.com/maps/dir/?api=1&destination=" + quote(", ".join(parts))


def _escape_ics_text(text: str) -> str:
    """RFC 5545 TEXT escaping — mirrors frontend/src/utils/calendar.ts's escapeIcsText."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _format_ics_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _event_ics_attachment(event) -> dict | None:
    """A calendar invite for the event, as a real (non-inline) email attachment — most mail
    clients offer an "Add to calendar" affordance for a text/calendar attachment automatically,
    the email equivalent of EventDetailView.vue's "Add to calendar" button (which downloads the
    same RFC 5545 shape via frontend/src/utils/calendar.ts's buildEventIcs). No DESCRIPTION
    field: Event.description is rich HTML, not suited to a calendar app's description field, and
    only title/time/location were actually asked for.
    """
    if event is None or not event.start_datetime:
        return None
    start = event.start_datetime
    end = event.end_datetime or event.start_datetime
    location = ", ".join(p for p in (event.venue, event.address) if p)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{site_name()}//Events//EN",
        "BEGIN:VEVENT",
        f"UID:event-{event.id}@{site_domain()}",
        f"DTSTAMP:{_format_ics_datetime(datetime.now(timezone.utc))}",
        f"DTSTART:{_format_ics_datetime(start)}",
        f"DTEND:{_format_ics_datetime(end)}",
        f"SUMMARY:{_escape_ics_text(event.title)}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape_ics_text(location)}")
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    content = "\r\n".join(lines).encode("utf-8")
    return {
        "filename": f"{event.slug}.ics",
        "content": list(content),
        "content_type": "text/calendar",
    }


def _render_base(*, title: str, body_html: str) -> tuple[str, dict]:
    """Returns (html, logo_attachment) — every email shares one CID-embedded wordmark icon,
    so the caller only needs to fold logo_attachment into its own attachments list.
    """
    template = Template((_TEMPLATES_DIR / "base_layout.html").read_text(encoding="utf-8"))
    html_out = template.substitute(
        title=html.escape(title),
        body=body_html,
        logo_cid=_LOGO_CID,
        c_sunk=_pal().sunk, c_body=_pal().body, c_card=_pal().card, c_line=_pal().border, c_ink=_pal().heading, c_mute=_pal().muted,
        site_name=site_name_html(),
        font_karla_b64=_font_data_uri("karla-variable-latin.woff2"),
        font_marcellus_b64=_font_data_uri("marcellus-400-latin.woff2"),
    )
    return html_out, _logo_attachment(_LOGO_CID)


def render_buyer_message_email(*, subject: str, message: str, event_title: str) -> tuple[str, str, list[dict]]:
    """A message from the organiser to everyone who bought tickets (W11). Returns (html_body, text_body, attachments). The subject and the message are typed by the
    organiser and HTML-escaped; line breaks are kept."""
    body_html = f"""
<p style="margin:0 0 6px; font-size:13px; color:{_pal().muted};">About {html.escape(event_title)}</p>
<div style="font-size:15px; line-height:1.55; white-space:pre-line;">{html.escape(message).replace(chr(10), "<br>")}</div>
"""
    html_body_out, logo_attachment = _render_base(title=subject, body_html=body_html)
    text_body = f"{site_name()} — {event_title}\n\n{message}\n"
    return html_body_out, text_body, [logo_attachment]


def render_contact_submission_email(
    *, name: str, email: str, subject: str, message: str, submitted_at: str
) -> tuple[str, str, list[dict]]:
    """Returns (html_body, text_body, attachments). All visitor-supplied fields are HTML-escaped before
    being substituted — they are untrusted input rendered into an email client. Shares
    base_layout.html via _render_base() like every other email here (folded in from a
    once-separate, now-deleted contact_submission.html full-document template, which had
    quietly drifted able to skip any future base_layout-wide style change).
    """
    body_html = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
<tr><td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:13px; color:{_pal().muted}; width:120px; vertical-align:top;">Name</td>
<td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:14px; vertical-align:top;">{html.escape(name)}</td></tr>
<tr><td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:13px; color:{_pal().muted}; vertical-align:top;">Email</td>
<td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:14px; vertical-align:top;">{html.escape(email)}</td></tr>
<tr><td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:13px; color:{_pal().muted}; vertical-align:top;">Subject</td>
<td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:14px; vertical-align:top;">{html.escape(subject)}</td></tr>
<tr><td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:13px; color:{_pal().muted}; vertical-align:top;">Message</td>
<td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:14px; vertical-align:top; white-space:pre-line;">{html.escape(message).replace(chr(10), "<br>")}</td></tr>
<tr><td style="padding:8px 0; font-size:13px; color:{_pal().muted}; vertical-align:top;">Submitted</td>
<td style="padding:8px 0; font-size:14px; vertical-align:top;">{html.escape(submitted_at)}</td></tr>
</table>
<p style="margin:24px 0 0; font-size:12px; color:{_pal().muted};">Reply directly to this email to respond to {html.escape(name)}.</p>
"""
    html_body_out, logo_attachment = _render_base(title="Contact Form Submission", body_html=body_html)

    text_body = (
        f"{site_name()} — Contact Form Submission\n\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Subject: {subject}\n\n"
        f"Message:\n{message}\n\n"
        f"Submitted: {submitted_at}\n"
    )

    return html_body_out, text_body, [logo_attachment]


def render_order_received_email(*, order, event, order_url: str, vipps_number: str) -> tuple[str, str, list[dict]]:
    """Sent right after checkout — payment is manual (Vipps), so this is mainly payment
    instructions, not a confirmation that anything has been paid yet. Returns
    (html_body, text_body, attachments). vipps_number is the SQUARE's own Vipps number (rootsquares W6-R38; bca-oslo printed its own number and QR image here).
    order_url deep-links to OrderLookupView.vue, pre-filled with this order's number/email.
    """
    event_title = event.title if event else "your event"
    event_when = _format_event_datetime(event.start_datetime) if event else ""

    item_rows = "".join(
        f'<tr><td style="padding:6px 0; border-bottom:1px solid {_pal().border}; font-size:14px;">'
        f"{html.escape(item.ticket_type.name if item.ticket_type else 'Ticket')} × {item.quantity}</td>"
        f'<td style="padding:6px 0; border-bottom:1px solid {_pal().border}; font-size:14px; text-align:right;">'
        f"{_format_price(item.subtotal)}</td></tr>"
        for item in order.items
    )

    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(order.customer_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">Thanks for your order for <strong style="color:{_pal().heading};">{html.escape(event_title)}</strong>
({html.escape(event_when)}). Here's a summary:</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-bottom:16px;">
{item_rows}
<tr><td style="padding:10px 0 0; font-size:14px; font-weight:bold; color:{_pal().heading};">Total</td>
<td style="padding:10px 0 0; font-size:14px; font-weight:bold; text-align:right; color:{_pal().heading};">{_format_price(order.total_amount)}</td></tr>
</table>
<p style="margin:0 0 8px; font-size:14px;"><strong>Order number: {html.escape(order.order_number)}</strong></p>
<div style="background:{_pal().panel}; border:1px solid {_pal().border}; border-radius:{_card_r(8)}; padding:20px; margin:16px 0; text-align:center;">
<p style="margin:0 0 8px; font-size:14px; font-weight:600; color:{_pal().heading};">To complete your order, pay with Vipps</p>
<p style="margin:0; font-size:14px; text-align:left;">Vipps to <strong>{html.escape(vipps_number)}</strong> for {_format_price(order.total_amount)},
and mention the order number <strong>{html.escape(order.order_number)}</strong> in the payment message. Once you've
paid, click below and let us know so we can check for it.</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:12px auto 0;">
<tr><td align="center" style="border-radius:{_btn_r(8)}; background-color:{_pal().accent};">
<a href="{html.escape(order_url)}" style="display:inline-block; padding:14px 32px; font-family:'Karla','Helvetica Neue',Arial,sans-serif; font-size:15px; font-weight:600; color:{_pal().on_accent}; text-decoration:none; border-radius:{_btn_r(8)};">View my order &amp; report payment</a>
</td></tr>
</table>
</div>
<p style="margin:0; font-size:14px;">We'll confirm your payment and send your tickets as soon as possible.</p>
"""

    text_body = (
        f"Hi {order.customer_name},\n\n"
        f"Thanks for your order for {event_title} ({event_when}).\n\n"
        + "".join(
            f"{item.ticket_type.name if item.ticket_type else 'Ticket'} x {item.quantity}: {_format_price(item.subtotal)}\n"
            for item in order.items
        )
        + f"\nTotal: {_format_price(order.total_amount)}\n"
        f"Order number: {order.order_number}\n\n"
        f"To complete your order, Vipps to {vipps_number} for {_format_price(order.total_amount)}, and mention "
        f"the order number {order.order_number} in the payment message. Once paid, view your order and report "
        f"payment here: {order_url}\n\n"
        "We'll confirm your payment and send your tickets as soon as possible.\n"
    )

    html_out, logo_attachment = _render_base(title=f"Your {site_name()} order — payment instructions", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_cash_order_received_email(*, order, event, note: str, order_url: str) -> tuple[str, str, list[dict]]:
    """Sent right after a Cash checkout: the order summary and the admin-written cash wording
    (e.g. "your place is not confirmed until you pay"). Nothing is paid yet; an admin confirms."""
    event_title = event.title if event else "your event"
    event_when = _format_event_datetime(event.start_datetime) if event else ""
    item_rows = "".join(
        f'<tr><td style="padding:6px 0; border-bottom:1px solid {_pal().border}; font-size:14px;">'
        f"{html.escape(item.ticket_type.name if item.ticket_type else 'Ticket')} × {item.quantity}</td>"
        f'<td style="padding:6px 0; border-bottom:1px solid {_pal().border}; font-size:14px; text-align:right;">'
        f"{_format_price(item.subtotal)}</td></tr>"
        for item in order.items
    )
    note_html = (
        f'<p style="margin:0; font-size:14px; white-space:pre-line;">{html.escape(note)}</p>'
        if note
        else '<p style="margin:0; font-size:14px;">Pay in cash to the association; your order is confirmed once we have received it.</p>'
    )
    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(order.customer_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">Thanks for your order for <strong style="color:{_pal().heading};">{html.escape(event_title)}</strong>
({html.escape(event_when)}). Here's a summary:</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-bottom:16px;">
{item_rows}
<tr><td style="padding:10px 0 0; font-size:14px; font-weight:bold; color:{_pal().heading};">Total</td>
<td style="padding:10px 0 0; font-size:14px; font-weight:bold; text-align:right; color:{_pal().heading};">{_format_price(order.total_amount)}</td></tr>
</table>
<p style="margin:0 0 8px; font-size:14px;"><strong>Order number: {html.escape(order.order_number)}</strong></p>
<div style="background:{_pal().panel}; border:1px solid {_pal().border}; border-radius:{_card_r(8)}; padding:20px; margin:16px 0;">
<p style="margin:0 0 8px; font-size:14px; font-weight:600; color:{_pal().heading};">You chose to pay with cash</p>
{note_html}
</div>
<p style="margin:0; font-size:14px;">You can look up your order any time: <a href="{html.escape(order_url)}">{html.escape(order_url)}</a></p>
"""
    text_body = (
        f"Hi {order.customer_name},\n\n"
        f"Thanks for your order for {event_title} ({event_when}).\n\n"
        + "".join(
            f"{item.ticket_type.name if item.ticket_type else 'Ticket'} x {item.quantity}: {_format_price(item.subtotal)}\n"
            for item in order.items
        )
        + f"\nTotal: {_format_price(order.total_amount)}\nOrder number: {order.order_number}\n\n"
        "You chose to pay with cash.\n"
        + (note + "\n" if note else "Pay in cash to the association; your order is confirmed once we have received it.\n")
        + f"\nLook up your order: {order_url}\n"
    )
    html_out, logo_attachment = _render_base(title=f"Your {site_name()} order — pay with cash", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_donation_receipt_email(*, donation, thanks: str) -> tuple[str, str, list[dict]]:
    """Sent when a donation is paid: the amount, the reference and the square's own thank-you words (empty = none). No tax-deduction wording:
    that differs by country and belongs to the square (rule 11)."""
    thanks_html = (
        f'<p style="margin:16px 0 0; font-size:14px; white-space:pre-line;">{html.escape(thanks)}</p>' if thanks else ""
    )
    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(donation.donor_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">Thank you for your gift to <strong style="color:{_pal().heading};">{html.escape(site_name())}</strong>. We have received it.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-bottom:16px;">
<tr><td style="padding:10px 0; font-size:14px; font-weight:bold; color:{_pal().heading};">Amount</td>
<td style="padding:10px 0; font-size:14px; font-weight:bold; text-align:right; color:{_pal().heading};">{_format_price(donation.amount)}</td></tr>
</table>
<p style="margin:0; font-size:14px;">Reference: <strong>{html.escape(donation.reference)}</strong></p>
{thanks_html}
"""
    text_body = (
        f"Hi {donation.donor_name},\n\nThank you for your gift to {site_name()}. We have received it.\n\n"
        f"Amount: {_format_price(donation.amount)}\nReference: {donation.reference}\n" + (f"\n{thanks}\n" if thanks else "")
    )
    html_out, logo_attachment = _render_base(title=f"Thank you for your gift to {site_name()}", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def _bank_rows(bank: dict) -> list[tuple[str, str]]:
    labels = (("holder", "Account holder"), ("bank_name", "Bank"), ("account_number", "Account number"), ("iban", "IBAN"), ("bic", "BIC / SWIFT"))
    return [(label, bank[key]) for key, label in labels if bank.get(key)]


def render_bank_order_received_email(*, order, event, bank: dict, order_url: str) -> tuple[str, str, list[dict]]:
    """Sent right after a bank transfer checkout: the order summary, the square's account details and the order number to write as the reference.
    Nothing is paid yet; an admin confirms when the money arrives."""
    event_title = event.title if event else "your event"
    event_when = _format_event_datetime(event.start_datetime) if event else ""
    rows_html = "".join(
        f'<tr><td style="padding:4px 12px 4px 0; font-size:13px; color:{_pal().muted};">{html.escape(label)}</td>'
        f'<td style="padding:4px 0; font-size:14px;">{html.escape(value)}</td></tr>'
        for label, value in _bank_rows(bank)
    )
    note_html = f'<p style="margin:12px 0 0; font-size:14px; white-space:pre-line;">{html.escape(bank["note"])}</p>' if bank.get("note") else ""
    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(order.customer_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">Thanks for your order for <strong style="color:{_pal().heading};">{html.escape(event_title)}</strong>
({html.escape(event_when)}). Total to pay: <strong>{_format_price(order.total_amount)}</strong>.</p>
<div style="background:{_pal().panel}; border:1px solid {_pal().border}; border-radius:{_card_r(8)}; padding:20px; margin:16px 0;">
<p style="margin:0 0 8px; font-size:14px; font-weight:600; color:{_pal().heading};">Pay by bank transfer</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">{rows_html}</table>
<p style="margin:12px 0 0; font-size:14px;">Write <strong>{html.escape(order.order_number)}</strong> as the reference or message.</p>
{note_html}
</div>
<p style="margin:0; font-size:14px;">We confirm your tickets once the money has arrived. You can look up your order any time: <a href="{html.escape(order_url)}">{html.escape(order_url)}</a></p>
"""
    text_body = (
        f"Hi {order.customer_name},\n\nThanks for your order for {event_title} ({event_when}).\n"
        f"Total to pay: {_format_price(order.total_amount)}\n\nPay by bank transfer:\n"
        + "".join(f"{label}: {value}\n" for label, value in _bank_rows(bank))
        + f"Reference: {order.order_number}\n"
        + (f"\n{bank['note']}\n" if bank.get("note") else "")
        + f"\nLook up your order: {order_url}\n"
    )
    html_out, logo_attachment = _render_base(title=f"Your {site_name()} order — bank transfer", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_order_awaiting_verification_email(*, order, event, admin_url: str) -> tuple[str, str, list[dict]]:
    """Sent to CONTACT_EMAIL when a customer reports having paid — this is the actionable
    moment for an admin/volunteer to actually go verify and mark the order paid or reject it.
    """
    event_title = event.title if event else "an event"

    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">An order is awaiting payment verification.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-bottom:16px;">
<tr><td style="padding:6px 0; font-size:13px; color:{_pal().muted}; width:140px;">Order number</td>
<td style="padding:6px 0; font-size:14px;">{html.escape(order.order_number)}</td></tr>
<tr><td style="padding:6px 0; font-size:13px; color:{_pal().muted};">Event</td>
<td style="padding:6px 0; font-size:14px;">{html.escape(event_title)}</td></tr>
<tr><td style="padding:6px 0; font-size:13px; color:{_pal().muted};">Customer</td>
<td style="padding:6px 0; font-size:14px;">{html.escape(order.customer_name)} ({html.escape(order.customer_email)})</td></tr>
<tr><td style="padding:6px 0; font-size:13px; color:{_pal().muted};">Total</td>
<td style="padding:6px 0; font-size:14px;">{_format_price(order.total_amount)}</td></tr>
</table>
<p style="margin:0; font-size:14px;"><a href="{html.escape(admin_url)}" style="color:{_pal().accent};">Review this order in the admin console</a></p>
"""

    text_body = (
        "An order is awaiting payment verification.\n\n"
        f"Order number: {order.order_number}\n"
        f"Event: {event_title}\n"
        f"Customer: {order.customer_name} ({order.customer_email})\n"
        f"Total: {_format_price(order.total_amount)}\n\n"
        f"Review this order: {admin_url}\n"
    )

    html_out, logo_attachment = _render_base(
        title=f"Order {order.order_number} awaiting payment verification", body_html=body_html
    )
    return html_out, text_body, [logo_attachment]


def render_payment_notification_received_email(*, order, event) -> tuple[str, str, list[dict]]:
    """Sent to the customer right after they click "I've made this payment" — mirrors
    VippsPaymentPanel.vue's own pending_verification message ("Thanks — we've noted your
    payment and will confirm it shortly.") so the email matches what the web page already says.
    """
    event_title = event.title if event else "your event"

    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(order.customer_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">Thanks — we've noted your payment for order
<strong>{html.escape(order.order_number)}</strong> ({html.escape(event_title)}) and will confirm it shortly.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin-bottom:16px;">
<tr><td style="padding:6px 0; font-size:13px; color:{_pal().muted}; width:140px;">Order number</td>
<td style="padding:6px 0; font-size:14px;">{html.escape(order.order_number)}</td></tr>
<tr><td style="padding:6px 0; font-size:13px; color:{_pal().muted};">Total</td>
<td style="padding:6px 0; font-size:14px;">{_format_price(order.total_amount)}</td></tr>
</table>
<p style="margin:0; font-size:14px;">We'll review it and send your tickets as soon as it's confirmed.</p>
"""

    text_body = (
        f"Hi {order.customer_name},\n\n"
        f"Thanks — we've noted your payment for order {order.order_number} ({event_title}) and will confirm it "
        "shortly.\n\n"
        f"Order number: {order.order_number}\n"
        f"Total: {_format_price(order.total_amount)}\n\n"
        "We'll review it and send your tickets as soon as it's confirmed.\n"
    )

    html_out, logo_attachment = _render_base(
        title=f"We've received your payment notification for order {order.order_number}", body_html=body_html
    )
    return html_out, text_body, [logo_attachment]


def render_tickets_confirmed_email(*, order, event) -> tuple[str, str, list[dict]]:
    """The main ticket-booking email — sent once an admin marks the order paid and its
    Ticket rows (with QR codes) exist. Each QR code is a CID-embedded attachment rather than
    a data-URI <img> — Gmail and several other mail clients silently block data URIs, which
    is why an earlier version of this email showed a broken image instead of a QR code.
    Returns (html_body, text_body, attachments).
    """
    event_title = event.title if event else "your event"
    event_when = _format_event_datetime(event.start_datetime) if event else ""
    event_venue = event.venue if event and event.venue else ""
    event_address = event.address if event and event.address else ""
    event_location = ", ".join(p for p in (event_venue, event_address) if p)
    directions_url = _directions_url(event)
    ics_attachment = _event_ics_attachment(event)

    ticket_blocks = []
    ticket_lines = []
    attachments: list[dict] = []
    for item in order.items:
        type_name = item.ticket_type.name if item.ticket_type else "Ticket"
        for ticket in item.tickets:
            content_id = f"ticket-qr-{ticket.id}"
            attachments.append(_ticket_qr_attachment(ticket.ticket_code, content_id))
            ticket_blocks.append(
                f"""
<div style="border:1px solid {_pal().border}; border-radius:{_card_r(8)}; padding:16px; margin-bottom:12px; text-align:center;">
<p style="margin:0 0 8px; font-size:13px; color:{_pal().muted};">{html.escape(type_name)}</p>
<img src="cid:{content_id}" alt="Ticket QR code" width="160" height="160" style="display:block; margin:0 auto 8px;" />
<p style="margin:0; font-size:13px; font-family:monospace; color:{_pal().heading};">{html.escape(ticket.ticket_code)}</p>
</div>"""
            )
            ticket_lines.append(f"{type_name}: {ticket.ticket_code}")

    if ics_attachment:
        attachments.append(ics_attachment)

    location_html = ""
    if event_location:
        directions_link_html = (
            f' — <a href="{html.escape(directions_url)}" style="color:{_pal().accent};">Get directions</a>'
            if directions_url
            else ""
        )
        location_html = (
            f'<p style="margin:0 0 16px; font-size:14px;">Location: '
            f"<strong>{html.escape(event_location)}</strong>{directions_link_html}</p>"
        )

    calendar_html = (
        '<p style="margin:16px 0 0; font-size:14px;">A calendar invite is attached — open it to '
        "add this event to your calendar.</p>"
        if ics_attachment
        else ""
    )

    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(order.customer_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">Your payment for <strong>{html.escape(event_title)}</strong>
({html.escape(event_when)}{', ' + html.escape(event_location) if event_location else ''}) is confirmed. Here
{'are your tickets' if len(ticket_blocks) != 1 else 'is your ticket'}:</p>
{location_html}
{''.join(ticket_blocks)}
<p style="margin:16px 0 0; font-size:14px;">Present a QR code (or its code) at check-in. Order number
<strong>{html.escape(order.order_number)}</strong>, total paid {_format_price(order.total_amount)}.</p>
{calendar_html}
"""

    location_text = ""
    if event_location:
        location_text = f"Location: {event_location}"
        if directions_url:
            location_text += f" — Get directions: {directions_url}"
        location_text += "\n\n"

    text_body = (
        f"Hi {order.customer_name},\n\n"
        f"Your payment for {event_title} ({event_when}{', ' + event_location if event_location else ''}) is confirmed.\n\n"
        + location_text
        + "\n".join(ticket_lines)
        + f"\n\nOrder number: {order.order_number}\nTotal paid: {_format_price(order.total_amount)}\n\n"
        "Present a QR code (or its code) at check-in.\n"
        + ("\nA calendar invite (.ics) is attached — open it to add this event to your calendar.\n" if ics_attachment else "")
    )

    html_out, logo_attachment = _render_base(title=f"Your tickets for {event_title} are confirmed", body_html=body_html)
    attachments.append(logo_attachment)
    return html_out, text_body, attachments


def render_order_rejected_email(*, order, event, reason: str) -> tuple[str, str, list[dict]]:
    event_title = event.title if event else "your event"

    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(order.customer_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">We were unable to verify payment for your order
<strong>{html.escape(order.order_number)}</strong> for <strong>{html.escape(event_title)}</strong>.</p>
<div style="background:{_pal().panel}; border:1px solid {_pal().border}; border-radius:{_card_r(8)}; padding:16px; margin:16px 0;">
<p style="margin:0; font-size:14px;">{html.escape(reason)}</p>
</div>
<p style="margin:0; font-size:14px;">If you believe this is a mistake, or would like to try again, please
get in touch and we'll help sort it out.</p>
"""

    text_body = (
        f"Hi {order.customer_name},\n\n"
        f"We were unable to verify payment for your order {order.order_number} for {event_title}.\n\n"
        f"{reason}\n\n"
        "If you believe this is a mistake, or would like to try again, please get in touch and we'll help "
        "sort it out.\n"
    )

    html_out, logo_attachment = _render_base(title=f"Update on your order {order.order_number}", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_vipps_payment_failed_email(*, order, event, retry_url: str) -> tuple[str, str, list[dict]]:
    """Sent when a Vipps App payment did not go through and the order was cancelled for it. Nothing was charged;
    the buyer is invited to try again."""
    event_title = event.title if event else "your event"
    link_html = (
        f'<p style="margin:16px 0;"><a href="{html.escape(retry_url)}" style="display:inline-block; padding:10px 20px; '
        f'background:{_pal().accent}; color:{_pal().on_accent}; text-decoration:none; border-radius:{_btn_r(6)}; font-size:14px;">'
        "Try again</a></p>"
        if retry_url
        else ""
    )
    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(order.customer_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">Your Vipps payment for order <strong>{html.escape(order.order_number)}</strong>
for <strong>{html.escape(event_title)}</strong> did not go through, so the order has been cancelled and
<strong>you have not been charged</strong>.</p>
<p style="margin:0 0 16px; font-size:14px;">You are welcome to place the order again while tickets are still on sale.</p>
{link_html}
<p style="margin:0; font-size:14px;">If money has left your account, or you need help, please get in touch and we'll sort it out.</p>
"""
    text_body = (
        f"Hi {order.customer_name},\n\n"
        f"Your Vipps payment for order {order.order_number} for {event_title} did not go through, so the order has "
        "been cancelled and you have not been charged.\n\n"
        "You are welcome to place the order again while tickets are still on sale."
        + (f" {retry_url}" if retry_url else "")
        + "\n\nIf money has left your account, or you need help, please get in touch and we'll sort it out.\n"
    )
    html_out, logo_attachment = _render_base(title=f"Your payment for order {order.order_number} did not go through", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_order_cancelled_email(*, order, event, reason: str) -> tuple[str, str, list[dict]]:
    """Sent when an admin cancels an order that was already paid (tickets issued). Unlike the rejection
    email above, the buyer did pay, so it says their tickets no longer work and invites a refund question."""
    event_title = event.title if event else "your event"

    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(order.customer_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">Your order <strong>{html.escape(order.order_number)}</strong> for
<strong>{html.escape(event_title)}</strong> has been cancelled. The tickets from this order are no longer valid
and will not be accepted at the door.</p>
<div style="background:{_pal().panel}; border:1px solid {_pal().border}; border-radius:{_card_r(8)}; padding:16px; margin:16px 0;">
<p style="margin:0; font-size:14px;">{html.escape(reason)}</p>
</div>
<p style="margin:0; font-size:14px;">If you have paid for this order and have questions about a refund, or you think
this is a mistake, please get in touch and we'll help sort it out.</p>
"""

    text_body = (
        f"Hi {order.customer_name},\n\n"
        f"Your order {order.order_number} for {event_title} has been cancelled. The tickets from this order are "
        "no longer valid and will not be accepted at the door.\n\n"
        f"{reason}\n\n"
        "If you have paid for this order and have questions about a refund, or you think this is a mistake, "
        "please get in touch and we'll help sort it out.\n"
    )

    html_out, logo_attachment = _render_base(title=f"Your order {order.order_number} was cancelled", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_order_refunded_email(*, order, event, amount_ore: int, reason: str) -> tuple[str, str, list[dict]]:
    """Sent when an admin refunds the payment of a ticket order (which also cancels the order and voids its
    tickets). `reason` may be empty."""
    event_title = event.title if event else "your event"
    amount = _format_price(amount_ore)
    reason_html = (
        f'<div style="background:{_pal().panel}; border:1px solid {_pal().border}; border-radius:{_card_r(8)}; padding:16px; margin:16px 0;">'
        f'<p style="margin:0; font-size:14px;">{html.escape(reason)}</p></div>'
        if reason
        else ""
    )

    body_html = f"""
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(order.customer_name)},</p>
<p style="margin:0 0 16px; font-size:14px;">Your payment of <strong>{html.escape(amount)}</strong> for order
<strong>{html.escape(order.order_number)}</strong> ({html.escape(event_title)}) has been refunded. The tickets from
this order are no longer valid and will not be accepted at the door.</p>
{reason_html}<p style="margin:0; font-size:14px;">Depending on how you paid, the money can take a few days to show on your
account. If you have questions, or you think this is a mistake, please get in touch and we'll help sort it out.</p>
"""

    reason_text = f"{reason}\n\n" if reason else ""
    text_body = (
        f"Hi {order.customer_name},\n\n"
        f"Your payment of {amount} for order {order.order_number} ({event_title}) has been refunded. The tickets from "
        "this order are no longer valid and will not be accepted at the door.\n\n"
        f"{reason_text}"
        "Depending on how you paid, the money can take a few days to show on your account. If you have questions, "
        "or you think this is a mistake, please get in touch and we'll help sort it out.\n"
    )

    html_out, logo_attachment = _render_base(title=f"Your order {order.order_number} was refunded", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def _expiry_minutes(expires_at: str | None) -> int | None:
    """Whole minutes until an ISO-8601 `expires_at` (Neon sends one on every send.* event).
    None when it's missing or unparseable — callers then just omit the expiry sentence rather
    than hardcode a number Neon may change.
    """
    if not expires_at:
        return None
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return max(1, round((expiry - datetime.now(timezone.utc)).total_seconds() / 60))


def _expiry_note(subject: str, expires_at: str | None) -> str:
    minutes = _expiry_minutes(expires_at)
    if minutes is None:
        return ""
    return f"This {subject} expires in {minutes} minute{'' if minutes == 1 else 's'}."


def render_signup_code_email(*, code: str, expires_at: str | None) -> tuple[str, str, list[dict]]:
    """Sent by the Neon Auth webhook (app.auth.neon_webhooks) when someone registers with an
    email address — the 6-digit code they enter on the registration page. Returns
    (html_body, text_body, attachments).
    """
    note = _expiry_note("code", expires_at)
    note_html = f'<p style="margin:0 0 16px; font-size:13px; color:{_pal().muted};">{note}</p>' if note else ""

    body_html = f"""
<p style="margin:0 0 8px; font-size:12px; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:{_pal().accent};">Verify your email</p>
<p style="margin:0 0 16px; font-size:14px;">Thanks for registering with <strong style="color:{_pal().heading};">{site_name_html()}</strong>. Enter this code on the registration page to confirm your email address:</p>
<div style="background:{_pal().panel}; border:1px solid {_pal().border}; border-radius:{_card_r(8)}; padding:20px; margin:16px 0; text-align:center;">
<p style="margin:0 0 8px; font-size:13px; color:{_pal().muted};">Your verification code</p>
<p style="margin:0; padding-left:0.3em; font-family:'Marcellus',Georgia,serif; font-size:34px; letter-spacing:0.3em; color:{_pal().heading};">{html.escape(code)}</p>
</div>
{note_html}
<p style="margin:0; font-size:12px; color:{_pal().muted};">If you didn't create an account with {site_name_html()}, you can safely ignore this email.</p>
"""

    text_body = (
        f"{site_name()} — Confirm your email address\n\n"
        f"Thanks for registering with {site_name()}.\n"
        "Enter this code on the registration page to confirm your email address:\n\n"
        f"    {code}\n\n"
        + (f"{note}\n\n" if note else "")
        + f"If you didn't create an account with {site_name()}, you can safely ignore this email.\n"
    )

    html_out, logo_attachment = _render_base(title="Confirm your email address", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_password_reset_email(*, reset_url: str, expires_at: str | None) -> tuple[str, str, list[dict]]:
    """Sent by the Neon Auth webhook when someone asks to reset their password — the link opens
    ResetPasswordView.vue with the token. Returns (html_body, text_body, attachments).
    """
    note = _expiry_note("link", expires_at)
    note_html = f'<p style="margin:0 0 16px; font-size:13px; color:{_pal().muted};">{note}</p>' if note else ""
    safe_url = html.escape(reset_url)

    body_html = f"""
<p style="margin:0 0 8px; font-size:12px; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:{_pal().accent};">Password reset</p>
<p style="margin:0 0 20px; font-size:14px;">We received a request to reset the password for your {site_name_html()} account. Use the button below to choose a new one.</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 20px;">
<tr><td align="center" style="border-radius:{_btn_r(8)}; background-color:{_pal().accent};">
<a href="{safe_url}" style="display:inline-block; padding:14px 32px; font-family:'Karla','Helvetica Neue',Arial,sans-serif; font-size:15px; font-weight:600; color:{_pal().on_accent}; text-decoration:none; border-radius:{_btn_r(8)};">Reset my password</a>
</td></tr>
</table>
<p style="margin:0 0 16px; font-size:12px; line-height:1.6; color:{_pal().muted};">If the button doesn't work, copy and paste this link into your browser:<br />
<a href="{safe_url}" style="color:{_pal().accent}; word-break:break-all;">{safe_url}</a></p>
{note_html}
<p style="margin:0; font-size:12px; color:{_pal().muted};">If you didn't ask to reset your password, you can safely ignore this email — your password won't change.</p>
"""

    text_body = (
        f"{site_name()} — Reset your password\n\n"
        f"We received a request to reset the password for your {site_name()} account.\n"
        f"Choose a new password here: {reset_url}\n\n"
        + (f"{note}\n\n" if note else "")
        + "If you didn't ask to reset your password, you can safely ignore this email — your password won't change.\n"
    )

    html_out, logo_attachment = _render_base(title="Reset your password", body_html=body_html)
    return html_out, text_body, [logo_attachment]



def render_welcome_email(
    *, dashboard_url: str, events_url: str | None = None, gallery_url: str | None = None, dashboard_text: str | None = None
) -> tuple[str, str, list[dict]]:
    """Sent once, the first time the backend sees a new account (see app.auth.service /
    app.auth.emails) — for an email/password user that is their first login after verifying their
    address; for Google, their first sign-in. Returns (html_body, text_body, attachments).
    """
    # An address is None when the square does not have that module (W8-R17): the email then does not point at it.
    links = [("Your dashboard", dashboard_text or "Update your details, request a membership and find your tickets.", dashboard_url)]
    if events_url:
        links.append(("Events", "See what's coming up and book your tickets.", events_url))
    if gallery_url:
        links.append(("Gallery", "Browse photos from our festivals and events.", gallery_url))
    rows = "".join(
        f'<tr><td style="padding:12px 0; border-bottom:1px solid {_pal().border}; font-size:14px;">'
        f'<a href="{html.escape(url)}" style="color:{_pal().accent}; font-weight:600; text-decoration:none;">'
        f"{html.escape(title)} &rarr;</a>"
        f'<div style="margin-top:2px; font-size:13px; color:{_pal().muted};">{html.escape(description)}</div>'
        "</td></tr>"
        for title, description, url in links
    )

    body_html = f"""
<p style="margin:0 0 8px; font-size:12px; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:{_pal().accent};">Your account is ready</p>
<p style="margin:0 0 16px; font-size:14px;">Thanks for joining <strong style="color:{_pal().heading};">{site_name_html()}</strong>. Here are a few places to start:</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:0 0 20px;">
{rows}
</table>
<p style="margin:0; font-size:12px; color:{_pal().muted};">You're receiving this because you created an account at {site_name_html()}.</p>
"""

    text_body = (
        f"Welcome to {site_name()}\n\n"
        "Your account is ready. Here are a few places to start:\n\n"
        + "".join(f"{title}: {url}\n    {description}\n" for title, description, url in links)
        + f"\nYou're receiving this because you created an account at {site_name()}.\n"
    )

    html_out, logo_attachment = _render_base(title=f"Welcome to {site_name()}", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_membership_reminder_email(
    *,
    name: str,
    kind: str,
    membership_type: str,
    lines: list[tuple[str, str]],
    total_text: str,
    dashboard_url: str,
    child_name: str | None = None,
) -> tuple[str, str, list[dict]]:
    """Admin-triggered nudge about an unpaid membership. `kind` is "request" (they asked for a
    membership but never paid the first period) or "dues" (active, with unpaid periods).
    `lines` are (period label, amount text) pairs. Returns (html_body, text_body, attachments)."""
    type_label = membership_type.replace("_", " ").capitalize()
    if child_name:
        # Sent to the parent about their child's membership.
        eyebrow = "Membership" if kind == "request" else "Payment due"
        intro = (
            f"<strong style=\"color:{_pal().heading};\">{html.escape(child_name)}</strong>'s "
            f"{html.escape(type_label)} membership at {html.escape(site_name())} is waiting for payment."
        )
        intro_text = f"{child_name}'s {type_label} membership at {site_name()} is waiting for payment."
    elif kind == "request":
        eyebrow = "Membership"
        intro = (
            f"You asked to join {site_name_html()} as a <strong style=\"color:{_pal().heading};\">{html.escape(type_label)}</strong> "
            "member, but the payment hasn't come through yet. Your membership starts as soon as it does."
        )
        intro_text = (
            f"You asked to join {site_name()} as a {type_label} member, but the payment hasn't come through yet. "
            "Your membership starts as soon as it does."
        )
    else:
        eyebrow = "Payment due"
        intro = (
            f"Your <strong style=\"color:{_pal().heading};\">{html.escape(type_label)}</strong> membership has "
            "payments waiting. A quick payment keeps it in good standing."
        )
        intro_text = f"Your {type_label} membership has payments waiting. A quick payment keeps it in good standing."

    rows = "".join(
        f'<tr><td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:14px;">{html.escape(label)}</td>'
        f'<td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:14px; text-align:right;">{html.escape(amount)}</td></tr>'
        for label, amount in lines
    )
    body_html = f"""
<p style="margin:0 0 8px; font-size:12px; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:{_pal().accent};">{eyebrow}</p>
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(name)},</p>
<p style="margin:0 0 16px; font-size:14px;">{intro}</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:0 0 8px;">
{rows}
<tr><td style="padding:10px 0; font-size:14px; font-weight:600; color:{_pal().heading};">Total</td><td style="padding:10px 0; font-size:14px; font-weight:600; color:{_pal().heading}; text-align:right;">{html.escape(total_text)}</td></tr>
</table>
<p style="margin:16px 0 20px;"><a href="{html.escape(dashboard_url)}" style="display:inline-block; background:{_pal().accent}; color:{_pal().on_accent}; text-decoration:none; font-weight:600; font-size:14px; padding:10px 20px; border-radius:{_btn_r(6)};">Pay on your dashboard</a></p>
<p style="margin:0; font-size:12px; color:{_pal().muted};">You can pay from your member dashboard. If you've already paid, thank you — please ignore this message.</p>
"""
    text_body = (
        f"Hi {name},\n\n{intro_text}\n\n"
        + "".join(f"  {label}{'  ' + amount if amount else ''}\n" for label, amount in lines)
        + f"\nTotal: {total_text}\n\nPay on your dashboard: {dashboard_url}\n\n"
        "If you've already paid, thank you — please ignore this message.\n"
    )
    html_out, logo_attachment = _render_base(title=f"Your {site_name()} membership", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_newsletter_confirm_email(*, confirm_url: str) -> tuple[str, str, list[dict]]:
    """Double opt-in (W15-R9): one click confirms the newsletter subscription. Returns (html_body, text_body, attachments)."""
    body_html = f"""
<p style="margin:0 0 8px; font-size:12px; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:{_pal().accent};">Newsletter</p>
<p style="margin:0 0 16px; font-size:14px;">Please confirm that you want the <strong style="color:{_pal().heading};">{site_name_html()}</strong> newsletter.</p>
<p style="margin:0 0 16px; font-size:14px;"><a href="{html.escape(confirm_url)}" style="color:{_pal().accent}; font-weight:600;">Yes, subscribe me</a></p>
<p style="margin:0; font-size:12px; color:{_pal().muted};">If you did not ask for this, ignore this e-mail: you will not be subscribed.</p>
"""
    text_body = (
        f"Please confirm that you want the {site_name()} newsletter: {confirm_url}\n\n"
        "If you did not ask for this, ignore this e-mail: you will not be subscribed.\n"
    )
    html_out, logo_attachment = _render_base(title="Confirm your newsletter subscription", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_membership_active_email(
    *,
    name: str,
    membership_type: str,
    start_text: str,
    valid_until_text: str | None,
    dashboard_url: str,
    child_name: str | None = None,
) -> tuple[str, str, list[dict]]:
    """Sent once when a membership becomes active (admin approval, or the member's payment confirmed). For a
    child the email goes to the parent and names the child. Returns (html_body, text_body, attachments)."""
    type_label = membership_type.replace("_", " ").capitalize()
    whose = f"{child_name}'s" if child_name else "Your"
    details = [("Membership", type_label), ("Starts", start_text)]
    if valid_until_text:
        details.append(("Valid until", valid_until_text))
    rows = "".join(
        f'<tr><td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:14px; color:{_pal().muted};">{html.escape(label)}</td>'
        f'<td style="padding:8px 0; border-bottom:1px solid {_pal().border}; font-size:14px; text-align:right;">{html.escape(value)}</td></tr>'
        for label, value in details
    )
    body_html = f"""
<p style="margin:0 0 8px; font-size:12px; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:{_pal().accent};">Membership active</p>
<p style="margin:0 0 16px; font-size:14px;">Hi {html.escape(name)},</p>
<p style="margin:0 0 16px; font-size:14px;">{html.escape(whose)} membership of <strong style="color:{_pal().heading};">{html.escape(site_name())}</strong> is now active. Welcome!</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:0 0 16px;">
{rows}
</table>
<p style="margin:16px 0 20px;"><a href="{html.escape(dashboard_url)}" style="display:inline-block; background:{_pal().accent}; color:{_pal().on_accent}; text-decoration:none; font-weight:600; font-size:14px; padding:10px 20px; border-radius:{_btn_r(6)};">Open your dashboard</a></p>
<p style="margin:0; font-size:12px; color:{_pal().muted};">You can see your membership and payments on your member dashboard.</p>
"""
    text_body = (
        f"Hi {name},\n\n"
        f"{whose} membership of {site_name()} is now active. Welcome!\n\n"
        + "".join(f"  {label}: {value}\n" for label, value in details)
        + f"\nOpen your dashboard: {dashboard_url}\n"
    )
    html_out, logo_attachment = _render_base(title=f"Your {site_name()} membership is active", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_newsletter_subscribed_email(*, unsubscribe_url: str) -> tuple[str, str, list[dict]]:
    """Confirmation sent when someone subscribes (or re-subscribes) to the newsletter, with the
    one-click unsubscribe link. Returns (html_body, text_body, attachments)."""
    body_html = f"""
<p style="margin:0 0 8px; font-size:12px; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:{_pal().accent};">Newsletter</p>
<p style="margin:0 0 16px; font-size:14px;">You're subscribed to the <strong style="color:{_pal().heading};">{site_name_html()}</strong> newsletter — one email a month: what's on, what needs doing.</p>
<p style="margin:0; font-size:12px; color:{_pal().muted};">Changed your mind? <a href="{html.escape(unsubscribe_url)}" style="color:{_pal().accent};">Unsubscribe</a> at any time.</p>
"""
    text_body = (
        f"You're subscribed to the {site_name()} newsletter — one email a month: what's on, what needs doing.\n\n"
        f"Changed your mind? Unsubscribe at any time: {unsubscribe_url}\n"
    )
    html_out, logo_attachment = _render_base(title="Newsletter subscription", body_html=body_html)
    return html_out, text_body, [logo_attachment]


def render_message_email(*, subject: str, body_html: str, kind: str, unsubscribe_url: str | None, footer_text_override: str = "") -> tuple[str, str, list[dict]]:
    """One message of the Messages module for one person. `body_html` is admin-authored rich text, already sanitised on save, with the person's
    placeholders filled in. An "update" ends with the person's own unsubscribe link; a "service" message says what kind of message it is."""
    plain = html.unescape(bleach.clean(body_html, tags=[], strip=True)).strip()
    own = footer_text_override.strip()  # the square's own sentence (Messages page); the unsubscribe link is always added to a News message
    if kind == "update" and unsubscribe_url:
        standard = f"You receive this because you are in the {site_name()} contact list"
        footer_text = (html.escape(own) + " ") if own else f"{standard} (member, participant, donor or subscriber). "
        footer_link = f'<a href="{html.escape(unsubscribe_url)}" style="color:{_pal().accent};">Unsubscribe</a>.'
        text_footer = f"{own or standard + '.'}\nUnsubscribe: {unsubscribe_url}\n"
    else:
        standard = f"This is a service message from {site_name()} about something you booked, bought or joined."
        footer_text = html.escape(own) if own else standard
        footer_link = ""
        text_footer = f"{own or standard}\n"
    footer = (
        f'<p style="margin:24px 0 0; padding-top:12px; border-top:1px solid {_pal().border}; font-size:12px; color:{_pal().muted};">'
        f"{footer_text}{footer_link}</p>"
    )
    body_html = body_html.replace("<img ", '<img style="max-width:100%; height:auto; border-radius:6px;" ')
    body = f'<div style="font-size:14px; line-height:1.6;">{body_html}</div>{footer}'
    html_out, logo_attachment = _render_base(title=subject, body_html=body)
    return html_out, f"{plain}\n\n--\n{text_footer}", [logo_attachment]
