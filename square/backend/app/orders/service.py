import secrets

from app.extensions import db
from app.orders.models import Order
from app.tickets.models import Ticket


def issue_tickets_for_order(order: Order) -> None:
    """Create one Ticket row per purchased unit. Shared by the admin mark-paid action
    (app/orders/admin_routes.py) and checkout's own zero-amount auto-issue path
    (app/orders/routes.py) — the only two places a paid order ever gets tickets.
    """
    for item in order.items:
        for _ in range(item.quantity):
            db.session.add(Ticket(order_item_id=item.id, ticket_code=secrets.token_urlsafe(16)))


# The ticket payment methods an event can offer. Stored on the event as a comma-separated list
# ("qr,app,bank,cash,card"); the old value "both" (before Cash existed) means "qr,app". "card" is Stripe.
TICKET_METHODS = ("qr", "app", "bank", "cash", "card")


def parse_event_methods(setting) -> list[str]:
    """The event's stored setting as an ordered list of TICKET_METHODS (unknown names dropped)."""
    if not setting or setting == "both":
        return ["qr", "app"]
    wanted = {part.strip() for part in str(setting).split(",")}
    return [m for m in TICKET_METHODS if m in wanted]


def canonical_event_methods(setting) -> str | None:
    """Validates and normalises an incoming setting; None when it is empty/invalid."""
    if setting == "both":
        return "qr,app"
    parts = [part.strip() for part in str(setting or "").split(",") if part.strip()]
    if not parts or any(p not in TICKET_METHODS for p in parts):
        return None
    return ",".join(m for m in TICKET_METHODS if m in parts)


def allowed_payment_methods(event) -> set[str]:
    """What a buyer may use for this event right now, a subset of {"qr", "app", "bank", "cash", "card"}.

    The event's own list, narrowed by reality: "app" only exists while Vipps-App is switched on
    for customers (app.payments.vipps.is_public()), "qr" only while Vipps-QR is switched on and the
    square has its own Vipps number, and "cash" only while Cash is switched on (Settings -> Payments).
    If nothing is left, cash is offered anyway — tickets must always stay buyable.
    """
    from app.payments import stripe_gateway, vipps
    from app.settings.models import bank_transfer_available, get_site_settings, vipps_qr_available

    settings = get_site_settings()
    methods = set(parse_event_methods(getattr(event, "ticket_payment_methods", None)))
    if not vipps.is_public():
        methods.discard("app")
    if not stripe_gateway.is_public():
        methods.discard("card")
    if not vipps_qr_available(settings):
        methods.discard("qr")
    if not bank_transfer_available(settings):
        methods.discard("bank")
    if not settings.cash_enabled:
        methods.discard("cash")
    return methods or {"cash"}  # rootsquares W6-R38: never the Vipps QR as a fallback (a square may have no Vipps number); an admin confirms cash by hand


def cash_note_for_event(event) -> str:
    """What a cash buyer is told: the event's own note, else the site-wide ticket note."""
    from app.settings.models import get_site_settings

    own = (getattr(event, "cash_note", None) or "").strip()
    return own or (get_site_settings().cash_ticket_note or "").strip()
