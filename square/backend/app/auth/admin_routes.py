"""Admin management of user roles — deliberately narrow.

This can only toggle a user between "member" and "volunteer" (BCA-011's old
/admin/volunteers placeholder). Promoting someone to "admin" stays CLI-only
(`flask users promote`) on purpose — a web form is not where privilege escalation should live.
"""

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func, or_, select

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.auth.emails import send_welcome_email
from app.common.query_params import csv_arg
from app.auth.models import User
from app.checkin.models import EventVolunteer
from app.events.models import Event
from app.extensions import db
from app.members.models import Member

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/api/admin/users")
admin_users_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 50
ASSIGNABLE_ROLES = {"member", "volunteer"}


def _serialize_user(user: User, member_name: str | None) -> dict:
    return {"id": user.id, "email": user.email, "role": user.role, "member_name": member_name}


@admin_users_bp.get("")
def admin_list_users():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    # Outer join only to filter — a User need not have a linked Member (e.g. an admin, or a
    # member who signed up before ever being imported/linked), so search still works via email
    # alone in that case. db.paginate() only supports a single selected entity, so the actual
    # member name is fetched separately below rather than selected alongside User here.
    stmt = (
        select(User)
        .outerjoin(Member, Member.user_id == User.id)
        .where(User.role.in_(ASSIGNABLE_ROLES), User.auth_provider != "support")
        .order_by(User.email)
    )
    q = request.args.get("q")
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), Member.name.ilike(f"%{q}%")))

    # Optional role filter (e.g. "volunteer", used by AdminLayout.vue's sidebar count badge
    # to get just the volunteer total without fetching every member too).
    role = request.args.get("role")
    if role:
        if role not in ASSIGNABLE_ROLES:
            return jsonify({"error": f"role must be one of {sorted(ASSIGNABLE_ROLES)}"}), 400
        stmt = stmt.where(User.role == role)

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    member_names = {
        m.user_id: m.name
        for m in Member.query.filter(Member.user_id.in_([u.id for u in pagination.items])).all()
    }
    return jsonify(
        {
            "items": [_serialize_user(u, member_names.get(u.id)) for u in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_users_bp.get("/all")
def admin_list_all_users():
    """Everyone who has ever signed in, newest first - kept apart from the member roster: a User row is
    created the first time someone logs in (whatever their role), a Member row is the roster entry, and
    the two are only linked when the emails match. `created_at` is therefore the first sign-in."""
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    stmt = select(User).outerjoin(Member, Member.user_id == User.id).where(User.auth_provider != "support")  # never the rootsquares support user (ADR 089)
    q = request.args.get("q")
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), Member.name.ilike(f"%{q}%")))
    roles = csv_arg("role")
    if roles:
        stmt = stmt.where(User.role.in_(roles))
    stmt = stmt.order_by(User.created_at.desc(), User.id.desc())

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    members = {
        m.user_id: m
        for m in Member.query.filter(Member.user_id.in_([u.id for u in pagination.items])).all()
    }
    # A profile that matches the login's email but has not been tied to it yet (e.g. signed up at the
    # Membership Drive after the person had already logged in - the tie is only made the next time they
    # open their member pages) still counts: match it by email so the link shows straight away.
    unlinked_emails = {u.email.lower() for u in pagination.items if u.id not in members}
    by_email = {}
    if unlinked_emails:
        for m in Member.query.filter(Member.user_id.is_(None), func.lower(Member.email).in_(unlinked_emails)).order_by(Member.id).all():
            by_email.setdefault(m.email.lower(), m)

    def profile_of(u: User):
        return members.get(u.id) or by_email.get(u.email.lower())

    return jsonify(
        {
            "items": [
                {
                    "id": u.id,
                    "email": u.email,
                    "role": u.role,
                    "auth_provider": u.auth_provider,
                    "member_id": profile_of(u).id if profile_of(u) else None,
                    "member_name": profile_of(u).name if profile_of(u) else None,
                    "first_sign_in": u.created_at.isoformat() if u.created_at else None,
                }
                for u in pagination.items
            ],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_users_bp.post("/<int:user_id>/welcome-email")
def admin_resend_welcome_email(user_id: int):
    """Sends the welcome email to this login again (the automatic one goes out once, at first sign-in, and
    is lost if the mail service failed at that moment). Answers 502 when it could not be sent. Not
    audit-logged: a new audit action needs a migration."""
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    if not send_welcome_email(user):
        return jsonify({"error": "The email could not be sent. Please try again shortly."}), 502
    return jsonify({"sent_to": user.email})


@admin_users_bp.patch("/<int:user_id>")
def admin_update_user_role(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404

    if user.role not in ASSIGNABLE_ROLES:
        # Covers "admin" today — a role this endpoint doesn't manage stays untouched by it.
        return jsonify({"errors": {"role": "This user's role can't be changed here."}}), 400

    data = request.get_json(silent=True) or {}
    role = data.get("role")
    if role not in ASSIGNABLE_ROLES:
        return jsonify({"errors": {"role": f"Must be one of {sorted(ASSIGNABLE_ROLES)}."}}), 400

    old_role = user.role
    user.role = role
    db.session.commit()

    log_action(
        g.current_user,
        "user_role_changed",
        f"Changed {user.email}'s role from {old_role} to {role}",
        target_type="user",
        target_id=user.id,
    )

    member = Member.query.filter_by(user_id=user.id).first()
    return jsonify(_serialize_user(user, member.name if member else None))


@admin_users_bp.get("/<int:user_id>/events")
def admin_list_user_events(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    if user.role != "volunteer":
        return jsonify({"errors": {"role": "Only volunteers can be assigned to events."}}), 400

    events = db.session.execute(select(Event).order_by(Event.start_datetime.desc())).scalars().all()
    assigned_ids = {
        ev.event_id for ev in EventVolunteer.query.filter_by(user_id=user_id).all()
    }
    return jsonify(
        {
            "events": [
                {"id": e.id, "title": e.title, "start_datetime": e.start_datetime.isoformat()}
                for e in events
            ],
            "assigned_event_ids": sorted(assigned_ids),
        }
    )


@admin_users_bp.put("/<int:user_id>/events")
def admin_set_user_events(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    if user.role != "volunteer":
        return jsonify({"errors": {"role": "Only volunteers can be assigned to events."}}), 400

    data = request.get_json(silent=True) or {}
    event_ids = data.get("event_ids")
    if not isinstance(event_ids, list) or not all(isinstance(i, int) for i in event_ids):
        return jsonify({"errors": {"event_ids": "Must be a list of event ids."}}), 400

    valid_ids = (
        {e.id for e in Event.query.filter(Event.id.in_(event_ids)).all()} if event_ids else set()
    )
    unknown = set(event_ids) - valid_ids
    if unknown:
        return jsonify({"errors": {"event_ids": f"Unknown event ids: {sorted(unknown)}"}}), 400

    EventVolunteer.query.filter_by(user_id=user_id).delete()
    for event_id in valid_ids:
        db.session.add(EventVolunteer(event_id=event_id, user_id=user_id))
    db.session.commit()

    return jsonify({"assigned_event_ids": sorted(valid_ids)})
