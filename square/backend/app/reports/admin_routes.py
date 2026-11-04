"""Admin reporting — read-only aggregate stats, distinct from the per-record list/export
pages (Members, Orders, Payments, Tickets) that already exist elsewhere. Nothing here writes
anything; every number is computed fresh from existing tables, no new state.
"""

from flask import Blueprint, jsonify
from sqlalchemy import func

from app.auth.decorators import require_role
from app.extensions import db
from app.memberships.models import Membership
from app.modules import module_enabled
from app.orders.models import Order
from app.tickets.models import Ticket

admin_reports_bp = Blueprint("admin_reports", __name__, url_prefix="/api/admin/reports")
admin_reports_bp.before_request(require_role("admin"))


@admin_reports_bp.get("/summary")
def admin_reports_summary():
    # Without the Tickets module (W8-R29) there are no orders or tickets to report
    tickets_on = module_enabled("tickets")
    revenue_total = (
        db.session.query(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(Order.payment_status == "paid")
        .scalar()
        if tickets_on
        else 0
    )

    # Ticket rows only ever exist for a paid order's items (created at mark-paid, never at
    # checkout) — so a plain count is already "tickets sold", no join/filter needed.
    tickets_total = Ticket.query.count() if tickets_on else 0

    # Without the Memberships module (W8-R19) there is nothing to count and nothing to show
    memberships_by_status: dict = {}
    memberships_by_type: dict = {}
    memberships_active_by_type: dict = {}
    if module_enabled("memberships"):
        memberships_by_status = dict(
            db.session.query(Membership.status, func.count(Membership.id))
            .group_by(Membership.status)
            .all()
        )
        memberships_by_type = dict(
            db.session.query(Membership.membership_type, func.count(Membership.id))
            .group_by(Membership.membership_type)
            .all()
        )
        # Active members only, by type (the dashboard's Membership card).
        memberships_active_by_type = dict(
            db.session.query(Membership.membership_type, func.count(Membership.id))
            .filter(Membership.status == "active")
            .group_by(Membership.membership_type)
            .all()
        )
    orders_by_status = (
        dict(
            db.session.query(Order.payment_status, func.count(Order.id))
            .group_by(Order.payment_status)
            .all()
        )
        if tickets_on
        else {}
    )

    return jsonify(
        {
            "revenue_total": revenue_total,
            "tickets_total": tickets_total,
            "memberships_by_status": memberships_by_status,
            "memberships_by_type": memberships_by_type,
            "memberships_active_by_type": memberships_active_by_type,
            "orders_by_status": orders_by_status,
        }
    )
