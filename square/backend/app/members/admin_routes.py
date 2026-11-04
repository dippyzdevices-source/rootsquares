"""Admin member directory: search/list members, view full detail, edit a profile.

Protected by role-based auth — every route in this blueprint requires the "admin" role via
the before_request hook below. See app/auth/decorators.py for require_role.
"""

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy import or_, select

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.auth.emails import send_welcome_email_to
from app.auth.models import User
from app.common.query_params import csv_arg
from app.extensions import db
from app.imports.excel import write_xlsx
from app.members.merge import find_duplicate_groups, merge_error, merge_members
from app.members.erasure import cancel_erase, request_erase
from app.members.models import FamilyMember, Member
from app.members.privacy import build_person_export
from app.members.routes import _serialize_family_member, _validate_family_member_payload
from app.modules import module_enabled
from app.memberships.models import Membership
from app.memberships.routes import _serialize_membership
from app.memberships.service import (
    awaiting_payment_clause,
    ensure_family_entry_for_child,
    find_member_by_email,
    is_awaiting_payment,
)

admin_members_bp = Blueprint("admin_members", __name__, url_prefix="/api/admin/members")
admin_members_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 100


def _member_email(member: Member) -> str | None:
    return member.user.email if member.user else member.email


def _member_phone(member: Member) -> str | None:
    return member.user.phone if member.user else member.phone


def _serialize_member_summary(member: Member) -> dict:
    # Memberships off: the roster shows people only; their membership rows are kept in the database but shown nowhere (ADR 044).
    latest = member.memberships[0] if member.memberships and module_enabled("memberships") else None
    return {
        "id": member.id,
        "name": member.name,
        "email": _member_email(member),
        "phone": _member_phone(member),
        "linked": member.user_id is not None,
        "erase_requested_at": member.erase_requested_at.isoformat() if member.erase_requested_at else None,
        "erased_at": member.erased_at.isoformat() if member.erased_at else None,
        "latest_membership": (
            {
                "id": latest.id,
                "membership_type": latest.membership_type,
                "status": latest.status,
                # A self-service request still waiting for its first payment: nothing for an
                # admin to approve — it activates itself once the payment is confirmed.
                "awaiting_payment": is_awaiting_payment(latest),
            }
            if latest
            else None
        ),
    }


def _serialize_member_detail(member: Member) -> dict:
    return {
        "id": member.id,
        "name": member.name,
        "address": member.address,
        "photo_url": member.photo_url,
        "family_info": member.family_info,
        "family_members": [_serialize_family_member(f) for f in member.family_members],
        "email": _member_email(member),
        "phone": _member_phone(member),
        "linked": member.user_id is not None,
        "parent": (
            {"id": member.parent.id, "name": member.parent.name, "email": _member_email(member.parent)}
            if member.parent
            else None
        ),
        "children": [{"id": c.id, "name": c.name} for c in member.children],
        "memberships": [_serialize_membership(m) for m in member.memberships] if module_enabled("memberships") else [],
    }


def _filtered_members_stmt():
    """The members query for the current search / role / membership type / status filters, ordered by name.
    Shared by the list and the Excel export so the download always matches what the page shows."""
    # Outer join — an imported member with no linked User yet must still be listed.
    stmt = select(Member).outerjoin(User, User.id == Member.user_id)

    q = request.args.get("q", "").strip()
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(Member.name.ilike(pattern), User.email.ilike(pattern), Member.email.ilike(pattern))
        )

    # Optional linked-user role filter (e.g. "volunteer", for the event task-assignment
    # picker) — a member with no linked user has no role at all, so this naturally excludes
    # them rather than needing a separate inner join.
    role = request.args.get("role", "").strip()
    if role:
        stmt = stmt.where(User.role == role)
    else:
        # The Members list is for people who hold (or held) a membership. Someone who only signed in and
        # saved a profile, with no membership of any status, is not a member yet: they appear under
        # Members -> Users, and their member page stays reachable from there. (A role-filtered lookup,
        # e.g. the task-assignment picker, is about login accounts, so it keeps every linked member.)
        stmt = stmt.where(select(Membership.id).where(Membership.member_id == Member.id).correlate(Member).exists())

    # Filter by the status and/or type of each member's *latest* membership (what the list displays).
    statuses = csv_arg("status")
    membership_types = csv_arg("membership_type")
    if (statuses or membership_types) and module_enabled("memberships"):
        latest_id = (
            select(Membership.id)
            .where(Membership.member_id == Member.id)
            .order_by(Membership.start_date.desc(), Membership.id.desc())
            .limit(1)
            .correlate(Member)
            .scalar_subquery()
        )
        stmt = stmt.join(Membership, Membership.id == latest_id)
        if statuses:
            # "pending" means a request somebody has paid for; an unpaid one is shown as "Awaiting payment".
            stmt = stmt.where(
                db.or_(
                    *[
                        db.and_(Membership.status == "pending", ~awaiting_payment_clause())
                        if s == "pending"
                        else Membership.status == s
                        for s in statuses
                    ]
                )
            )
        if membership_types:
            stmt = stmt.where(Membership.membership_type.in_(membership_types))

    stmt = stmt.order_by(Member.name.asc())
    return stmt


@admin_members_bp.get("")
def admin_list_members():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    stmt = _filtered_members_stmt()
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [_serialize_member_summary(member) for member in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


@admin_members_bp.post("")
def admin_create_member():
    """Add a person to the roster by hand (a volunteer, a helper). Not a membership: it creates no Membership row. A person with an email that is
    already on the roster is not added twice: the answer is 409 with the existing person's id (W11-R24, ADR 044)."""
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    errors: dict[str, str] = {}
    if not isinstance(name, str) or not name.strip():
        errors["name"] = "This field is required."
    if email not in (None, "") and (not isinstance(email, str) or "@" not in email or len(email) > 255):
        errors["email"] = "Must be an email address."
    if phone not in (None, "") and (not isinstance(phone, str) or len(phone) > 50):
        errors["phone"] = "Must be at most 50 characters."
    if errors:
        return jsonify({"errors": errors}), 400
    email = email.strip() if isinstance(email, str) and email.strip() else None
    if email:
        existing = find_member_by_email(email)
        if existing is not None:
            return jsonify({"error": "A person with this email is already on the list.", "member_id": existing.id}), 409
    member = Member(name=name.strip(), email=email, phone=phone.strip() if isinstance(phone, str) and phone.strip() else None)
    db.session.add(member)
    db.session.commit()
    log_action(g.current_user, "member_added", f"Added person #{member.id} ({member.name})", target_type="member", target_id=member.id)
    return jsonify(_serialize_member_detail(member)), 201


@admin_members_bp.get("/duplicates")
def admin_list_duplicate_members():
    return jsonify(
        {
            "groups": [
                {
                    "reason": group["reason"],
                    "members": [_serialize_member_summary(m) for m in group["members"]],
                }
                for group in find_duplicate_groups()
            ]
        }
    )


@admin_members_bp.post("/<int:member_id>/merge")
def admin_merge_member(member_id: int):
    """Fold `merge_id` into this member (the one kept), then delete the other record."""
    keep = db.session.get(Member, member_id)
    if keep is None:
        return jsonify({"error": "Member not found"}), 404
    data = request.get_json(silent=True) or {}
    merge_id = data.get("merge_id")
    merge = db.session.get(Member, merge_id) if isinstance(merge_id, int) else None
    if merge is None:
        return jsonify({"errors": {"merge_id": "Must reference an existing member."}}), 400
    error = merge_error(keep, merge)
    if error:
        return jsonify({"errors": {"merge_id": error}}), 400

    description = f"Merged member #{merge.id} ({merge.name}) into #{keep.id} ({keep.name})"
    merge_members(keep, merge)
    db.session.commit()
    log_action(g.current_user, "members_merged", description, target_type="member", target_id=keep.id)
    return jsonify(_serialize_member_detail(keep))


@admin_members_bp.get("/export")
def admin_export_members():
    members = db.session.scalars(_filtered_members_stmt()).all()
    with_memberships = module_enabled("memberships")
    headers = ["Name", "Email", "Phone", "Address", "Family info", "Signed up"]
    if with_memberships:
        headers += ["Latest membership type", "Latest membership status"]
    headers.append("Parent email")
    rows = []
    for member in members:
        latest = member.memberships[0] if member.memberships else None
        row = [
            member.name,
            _member_email(member),
            _member_phone(member),
            member.address,
            member.family_info,
            "Yes" if member.user_id is not None else "No",
        ]
        if with_memberships:
            row += [latest.membership_type if latest else None, latest.status if latest else None]
        row.append(_member_email(member.parent) if member.parent else None)
        rows.append(row)

    data = write_xlsx(headers, rows)
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=members.xlsx"},
    )


@admin_members_bp.post("/<int:member_id>/welcome-email")
def admin_resend_member_welcome_email(member_id: int):
    """Sends the welcome email to this member's address again - the login's email when linked, else the
    roster email (an imported member who has never signed in). Not audit-logged: a new audit action
    needs a migration."""
    member = db.session.get(Member, member_id)
    if member is None:
        return jsonify({"error": "Member not found"}), 404
    address = _member_email(member)
    if not address:
        return jsonify({"error": "This member has no email address."}), 400
    if not send_welcome_email_to(address):
        return jsonify({"error": "The email could not be sent. Please try again shortly."}), 502
    return jsonify({"sent_to": address})


@admin_members_bp.get("/<int:member_id>")
def admin_get_member(member_id: int):
    member = db.session.get(Member, member_id)
    if member is None:
        return jsonify({"error": "Member not found"}), 404
    return jsonify(_serialize_member_detail(member))


@admin_members_bp.get("/<int:member_id>/personal-data")
def admin_export_personal_data(member_id: int):
    """Everything held about one person, as a JSON download (GDPR access / portability)."""
    member = db.session.get(Member, member_id)
    if member is None:
        return jsonify({"error": "Member not found"}), 404
    payload = build_person_export(member)
    # No personal data in the audit line: the id only.
    log_action(
        g.current_user,
        "member.personal_data_export",
        f"Exported the personal data of member #{member.id}",
        target_type="member",
        target_id=member.id,
    )
    response = jsonify(payload)
    response.headers["Content-Disposition"] = f"attachment; filename=personal-data-{member.id}.json"
    return response


@admin_members_bp.post("/<int:member_id>/erase-request")
def admin_request_erase(member_id: int):
    """Record a person's request to be forgotten: sign-in stops now, anonymised after the grace period (30 days)."""
    member = db.session.get(Member, member_id)
    if member is None:
        return jsonify({"error": "Member not found"}), 404
    if member.erased_at is not None:
        return jsonify({"error": "This person is already erased"}), 409
    request_erase(member)
    log_action(g.current_user, "member.erase_requested", f"Erase requested for member #{member.id}", target_type="member", target_id=member.id)
    return jsonify(_serialize_member_detail(member))


@admin_members_bp.post("/<int:member_id>/erase-cancel")
def admin_cancel_erase(member_id: int):
    member = db.session.get(Member, member_id)
    if member is None:
        return jsonify({"error": "Member not found"}), 404
    if not cancel_erase(member):
        return jsonify({"error": "No pending erase request"}), 409
    log_action(g.current_user, "member.erase_cancelled", f"Erase request cancelled for member #{member.id}", target_type="member", target_id=member.id)
    return jsonify(_serialize_member_detail(member))


@admin_members_bp.patch("/<int:member_id>")
def admin_update_member(member_id: int):
    member = db.session.get(Member, member_id)
    if member is None:
        return jsonify({"error": "Member not found"}), 404

    data = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}

    if "name" in data:
        name = data["name"]
        if not name or not isinstance(name, str) or not name.strip():
            errors["name"] = "This field is required."
        else:
            member.name = name.strip()

    if "address" in data:
        member.address = data["address"]

    if "family_info" in data:
        member.family_info = data["family_info"]

    if "parent_email" in data:
        parent_email = data["parent_email"]
        if not parent_email:
            member.parent_member_id = None
        elif not isinstance(parent_email, str):
            errors["parent_email"] = "Must be an email address."
        else:
            parent = find_member_by_email(parent_email)
            if parent is None:
                errors["parent_email"] = "No member found with this email."
            elif parent.id == member.id:
                errors["parent_email"] = "A member cannot be their own parent."
            else:
                member.parent_member_id = parent.id
                db.session.flush()
                ensure_family_entry_for_child(member)

    if errors:
        db.session.rollback()
        return jsonify({"errors": errors}), 400

    db.session.commit()
    return jsonify(_serialize_member_detail(member))


@admin_members_bp.post("/<int:member_id>/family")
def admin_create_family_member(member_id: int):
    member = db.session.get(Member, member_id)
    if member is None:
        return jsonify({"error": "Member not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_family_member_payload(data, existing=None)
    if errors:
        return jsonify({"errors": errors}), 400

    family_member = FamilyMember(
        member_id=member.id,
        name=cleaned["name"],
        relationship_type=cleaned["relationship_type"],
        age=cleaned.get("age"),
        sort_order=cleaned.get("sort_order", len(member.family_members)),
    )
    db.session.add(family_member)
    db.session.commit()

    return jsonify(_serialize_family_member(family_member)), 201


@admin_members_bp.patch("/<int:member_id>/family/<int:family_member_id>")
def admin_update_family_member(member_id: int, family_member_id: int):
    family_member = db.session.get(FamilyMember, family_member_id)
    if family_member is None or family_member.member_id != member_id:
        return jsonify({"error": "Family member not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_family_member_payload(data, existing=family_member)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(family_member, field, value)

    db.session.commit()
    return jsonify(_serialize_family_member(family_member))


@admin_members_bp.delete("/<int:member_id>/family/<int:family_member_id>")
def admin_delete_family_member(member_id: int, family_member_id: int):
    family_member = db.session.get(FamilyMember, family_member_id)
    if family_member is None or family_member.member_id != member_id:
        return jsonify({"error": "Family member not found"}), 404

    db.session.delete(family_member)
    db.session.commit()
    return "", 204
