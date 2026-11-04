"""Read-only viewer for the audit log — admin-only. No POST/PATCH/DELETE routes exist here on
purpose: the log is written only by app.audit.service.log_action(), never through this API,
and is never edited or removed once written.
"""

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import select

from app.audit.models import AuditLog
from app.auth.decorators import require_role
from app.auth.models import User
from app.common.query_params import csv_arg
from app.extensions import db
from app.imports.excel import write_xlsx
from app.members.service import member_name_for_user

admin_audit_bp = Blueprint("admin_audit", __name__, url_prefix="/api/admin/audit-log")
admin_audit_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 50

VALID_ACTIONS = {
    "user_role_changed",
    "membership_status_changed",
    "order_marked_paid",
    "order_rejected",
    "order_cancelled",
    "settings_updated",
    "event_created",
    "event_updated",
    "event_deleted",
    "coupon_created",
    "coupon_updated",
    "gallery_album_deleted",
    "gallery_media_deleted",
    "news_deleted",
    "ticket_type_deleted",
    "payment_refunded",
    "payment_confirmed",
    "payment_rejected",
    "committee_member_deleted",
    "founder_deleted",
    "sponsor_deleted",
    "magazine_deleted",
    "expense_deleted",
    "income_deleted",
    "lookup_value_changed",
    "membership_drive_signup",
    "members_merged",
    "newsletter_sent",
    "newsletter_scheduled",
    "membership_reminder_sent",
    "membership_request_removed",
}


def _serialize_audit_log_entry(entry: AuditLog) -> dict:
    actor = db.session.get(User, entry.actor_user_id)
    return {
        "id": entry.id,
        "actor_email": actor.email if actor else None,
        "actor_name": member_name_for_user(entry.actor_user_id),
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "description": entry.description,
        "created_at": entry.created_at.isoformat(),
    }


def _filtered_stmt():
    """The audit-log query narrowed by the shared ?action= / ?q= filters (newest first). Returns
    (statement, None) or (None, error response) — used by both the list and the Excel export so
    the download always matches what the admin is looking at."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())

    actions = csv_arg("action")
    if actions:
        if any(a not in VALID_ACTIONS for a in actions):
            return None, (jsonify({"error": f"action must be one of {sorted(VALID_ACTIONS)}"}), 400)
        stmt = stmt.where(AuditLog.action.in_(actions))

    q = request.args.get("q")
    if q:
        stmt = stmt.where(AuditLog.description.ilike(f"%{q}%"))
    return stmt, None


@admin_audit_bp.get("")
def admin_list_audit_log():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    stmt, error = _filtered_stmt()
    if error:
        return error

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [_serialize_audit_log_entry(e) for e in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_audit_bp.get("/export")
def admin_export_audit_log():
    """Excel download of every audit entry matching the current filters (read-only, like the rest
    of this blueprint)."""
    stmt, error = _filtered_stmt()
    if error:
        return error

    headers = ["When", "Who", "Email", "Action", "Target", "Description"]
    rows = []
    for entry in db.session.scalars(stmt):
        item = _serialize_audit_log_entry(entry)
        target = f'{item["target_type"]} #{item["target_id"]}' if item["target_type"] else None
        rows.append(
            [item["created_at"], item["actor_name"], item["actor_email"], item["action"], target, item["description"]]
        )

    return Response(
        write_xlsx(headers, rows),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=audit-log.xlsx"},
    )
