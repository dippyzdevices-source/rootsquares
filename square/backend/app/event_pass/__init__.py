"""The Event pass on the square server (rootsquares W11, ADR 044).

An Event pass is a square for a single event: 45 days live, then 45 days of archive (owner only, read-only), then the platform deletes it. The archive guard
itself lives in `app/tenancy.py` (it needs no database). This package holds the parts that read the square's data:
- `GET /api/admin/event-pass`          what the owner sees on the wrap-up page: the phase, the dates, the events and what the export contains;
- `GET /api/admin/event-pass/export`   ONE zip with everything worth keeping: the accounting report of each event (PDF), its buyers and expenses (Excel), the
                                       orders, tickets (the attendee list) and the people list (Excel) and the expense receipts (the files);
- `one_event_refusal()`                the rule that a pass holds one event (an event may be one day or consecutive days; a second event is a second pass).
Both routes answer 404 for any square that is not an Event pass.
"""

from __future__ import annotations

import io
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone

from flask import Blueprint, Response, g, jsonify

from app.accounting.admin_routes import (
    admin_accounting_event_report,
    admin_accounting_export_event_buyers,
    admin_accounting_export_event_expenses,
)
from app.accounting.models import Expense
from app.audit.service import log_action
from app.auth.decorators import require_role
from app.events.models import Event
from app.extensions import db
from app.members.admin_routes import admin_export_members
from app.modules import module_enabled
from app.orders.admin_routes import admin_export_orders
from app.storage.service import get_private_storage
from app.tenancy import EVENT_PASS, current_tenant
from app.tickets.admin_routes import admin_export_tickets

MAX_RECEIPT_BYTES = 15 * 1024 * 1024

admin_event_pass_bp = Blueprint("admin_event_pass", __name__, url_prefix="/api/admin/event-pass")
admin_event_pass_bp.before_request(require_role("admin"))


@admin_event_pass_bp.before_request
def _only_for_a_pass():
    if not is_event_pass():
        return jsonify({"error": "Not found"}), 404
    return None


def is_event_pass() -> bool:
    tenant = current_tenant()
    return tenant is not None and tenant.package == EVENT_PASS


def one_event_refusal():
    """409 when this square is an Event pass that already holds its event; None otherwise (every other square, or the first event)."""
    if is_event_pass() and Event.query.count() >= 1:
        return (
            jsonify(
                {
                    "error": "An Event pass holds one event (one day or consecutive days). Edit the event you have, or start a second pass for a second event.",
                    "code": "event_pass_limit",
                }
            ),
            409,
        )
    return None


def _events() -> list[Event]:
    return Event.query.order_by(Event.start_datetime.asc(), Event.id.asc()).all()


@admin_event_pass_bp.get("")
def event_pass_summary():
    tenant = current_tenant()
    assert tenant is not None
    return jsonify(
        {
            "phase": tenant.event_phase,
            "live_until": tenant.event_live_until,
            "archive_until": tenant.event_archive_until,
            "events": [{"id": e.id, "title": e.title, "slug": e.slug} for e in _events()],
            "export": [
                "Accounting report of each event (PDF)",
                "Buyers and expenses of each event (Excel)",
                "All orders (Excel)",
                "All tickets, the attendee list (Excel)",
                *(["The people list (Excel)"] if module_enabled("members") else []),
                "The expense receipts (the uploaded files)",
            ],
        }
    )


def _bytes(result) -> bytes | None:
    """The body of a view function's answer when it is a normal 200 response; None for an error answer (a (json, status) tuple or a non-200)."""
    return result.get_data() if isinstance(result, Response) and result.status_code == 200 else None


def _receipt(key: str) -> bytes | None:
    """The file of a receipt: from the in-memory storage in tests, else through a signed, time-limited address. None when it cannot be fetched."""
    storage = get_private_storage()
    objects = getattr(storage, "objects", None)
    if isinstance(objects, dict):
        return objects.get(key)
    try:
        with urllib.request.urlopen(storage.url_for(key), timeout=20) as answer:  # a signed address from our own storage (no new dependency)
            data = answer.read(MAX_RECEIPT_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return data if len(data) <= MAX_RECEIPT_BYTES else None


@admin_event_pass_bp.get("/export")
def event_pass_export():
    buffer = io.BytesIO()
    missing: list[str] = []
    events = _events()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:

        def add(name: str, result) -> None:
            data = _bytes(result)
            if data is None:
                missing.append(name)
            else:
                bundle.writestr(name, data)

        for event in events:
            add(f"{event.slug}/accounting-report.pdf", admin_accounting_event_report(event.id))
            add(f"{event.slug}/buyers.xlsx", admin_accounting_export_event_buyers(event.id))
            add(f"{event.slug}/expenses.xlsx", admin_accounting_export_event_expenses(event.id))
        add("orders.xlsx", admin_export_orders())
        add("tickets.xlsx", admin_export_tickets())
        if module_enabled("members"):
            add("people.xlsx", admin_export_members())
        for expense in Expense.query.filter(Expense.receipt_key.is_not(None)).order_by(Expense.id.asc()).all():
            data = _receipt(expense.receipt_key)
            name = f"receipts/expense-{expense.id}-{expense.receipt_key.rsplit('/', 1)[-1]}"
            if data is None:
                missing.append(name)
            else:
                bundle.writestr(name, data)
        bundle.writestr("README.txt", _readme(missing))
    log_action(g.current_user, "event_pass_exported", f"Exported the Event pass ({len(events)} event(s), {len(missing)} item(s) missing)")
    slug = events[0].slug if events else "event"
    return Response(
        buffer.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={slug}-event-export.zip"},
    )


def _readme(missing: list[str]) -> str:
    tenant = current_tenant()
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"Event pass export of {tenant.name if tenant else 'the site'}, made {when}.",
        "",
        "Keep this file. The site and all its data are deleted when the archive ends"
        + (f" (about {tenant.event_archive_until[:10]})" if tenant and tenant.event_archive_until else "")
        + ". rootsquares keeps no copy.",
        "The accounting report is a record and an export, not bookkeeping software: you, the organiser, are responsible for keeping your accounting records",
        "for as long as the law of your country requires.",
        "",
        "Inside: the accounting report of each event (PDF), buyers and expenses of each event, all orders, all tickets (the attendee list), the people list and",
        "the expense receipts (the files), as Excel sheets and files.",
    ]
    if missing:
        lines += ["", "These items could not be included (try the export again, or download them one by one in the admin area):", *[f"- {name}" for name in missing]]
    return "\n".join(lines) + "\n"
