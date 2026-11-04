"""Excel import for the Member roster — admin-only.

Follows CLAUDE.md's non-negotiable Excel rule: upload -> parse -> validate -> preview ->
confirm -> import, and nothing touches production data before confirmation. Preview parses
and validates an uploaded .xlsx file and returns the result — it never writes anything.
Confirm takes back the (already-validated, but re-validated here too — never trust the
frontend) row data as JSON, not the file again, and is the only place that writes: it never
updates an existing Member's profile or an existing Membership row, only ever creates a new
Member (if the email is unseen) and always appends a new Membership — matching how this
project already treats Membership as historical, never overwritten in place.
"""

from datetime import date

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func, select

from app.auth.decorators import require_role
from app.extensions import db
from app.imports.excel import parse_member_rows, validate_row
from app.imports.models import ImportBatch
from app.members.models import Member
from app.memberships.models import Membership, MembershipType
from app.memberships.service import (
    ensure_family_entry_for_child,
    find_member_by_email,
    generate_periods_for_membership,
    is_child_type,
    parent_adult_error,
)

admin_imports_bp = Blueprint("admin_imports", __name__, url_prefix="/api/admin/imports")
admin_imports_bp.before_request(require_role("admin"))

MAX_PER_PAGE = 50


def _all_membership_type_names() -> set[str]:
    # A bulk historical import may legitimately reference a since-deactivated type, so this
    # checks against every known name, not just the active ones offered to a self-service renewal.
    return {name for (name,) in db.session.query(MembershipType.name).all()}


def _serialize_batch(batch: ImportBatch) -> dict:
    return {
        "id": batch.id,
        "filename": batch.filename,
        "admin_email": batch.admin_user.email if batch.admin_user else None,
        "total_rows": batch.total_rows,
        "members_created": batch.members_created,
        "memberships_created": batch.memberships_created,
        "failed_rows": batch.failed_rows,
        "created_at": batch.created_at.isoformat(),
    }


@admin_imports_bp.get("")
def admin_list_import_history():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400
    if page < 1 or per_page < 1:
        return jsonify({"error": "page and per_page must be positive"}), 400
    per_page = min(per_page, MAX_PER_PAGE)

    pagination = db.paginate(
        select(ImportBatch).order_by(ImportBatch.id.desc()),
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return jsonify(
        {
            "items": [_serialize_batch(b) for b in pagination.items],
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "total_pages": pagination.pages,
        }
    )


MAX_IMPORT_FILE_SIZE = 1024 * 1024


def _check_child_parents(rows: list[dict]) -> None:
    """Preview-time parent check, adding an error to each child row whose parent can't qualify.
    A parent qualifies if it is already an active adult in the database, or is a valid, active,
    non-child row elsewhere in this same file (it will exist by the time children are written —
    confirm handles adults first). The active-parent rule is re-checked for real at confirm."""
    file_adults = {
        row["email"]
        for row in rows
        if not row["errors"]
        and row.get("email")
        and not row.get("parent_email")
        and row.get("membership_status") == "active"
        and not is_child_type(row.get("membership_type"))
    }
    for row in rows:
        parent_email = row.get("parent_email")
        if row["errors"] or not parent_email or parent_email in file_adults:
            continue
        error = parent_adult_error(find_member_by_email(parent_email))
        if error:
            row["errors"]["parent_email"] = error


@admin_imports_bp.post("/members/preview")
def admin_preview_members_import():
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "file is required"}), 400

    data = file.read()
    if len(data) > MAX_IMPORT_FILE_SIZE:
        return jsonify({"error": "File exceeds the 1MB size limit."}), 400

    try:
        raw_rows = parse_member_rows(data)
    except Exception:
        return jsonify({"error": "Could not read this file. Make sure it's a valid .xlsx file."}), 400

    valid_types = _all_membership_type_names()
    rows = []
    for index, raw_row in enumerate(raw_rows, start=1):
        cleaned, errors = validate_row(raw_row, valid_types)
        rows.append({"row_number": index, **cleaned, "errors": errors})

    _check_child_parents(rows)
    valid_count = sum(1 for row in rows if not row["errors"])
    invalid_count = len(rows) - valid_count

    return jsonify({"rows": rows, "valid_count": valid_count, "invalid_count": invalid_count})


@admin_imports_bp.post("/members/confirm")
def admin_confirm_members_import():
    data = request.get_json(silent=True) or {}
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        return jsonify({"error": "rows must be a non-empty list"}), 400
    filename = data.get("filename") or "import.xlsx"

    valid_types = _all_membership_type_names()
    members_created = 0
    memberships_created = 0
    failures: list[dict] = []
    memberships_needing_periods = []
    adult_rows: list[tuple[dict, dict]] = []
    child_rows: list[tuple[dict, dict]] = []

    def fail(raw_row, reason: str) -> None:
        row = raw_row if isinstance(raw_row, dict) else {}
        failures.append({"row_number": row.get("row_number"), "name": row.get("name"), "reason": reason})

    for raw_row in rows:
        if not isinstance(raw_row, dict):
            fail(raw_row, "Not a valid row.")
            continue
        cleaned, errors = validate_row(raw_row, valid_types)
        if errors:
            fail(raw_row, " ".join(errors.values()))
            continue
        (child_rows if cleaned["parent_email"] else adult_rows).append((raw_row, cleaned))

    def add_membership(member: Member, cleaned: dict) -> None:
        nonlocal memberships_created
        membership = Membership(
            member_id=member.id,
            membership_type=cleaned["membership_type"],
            status=cleaned["membership_status"],
            start_date=date.fromisoformat(cleaned["start_date"]),
            end_date=date.fromisoformat(cleaned["end_date"]) if cleaned["end_date"] else None,
        )
        db.session.add(membership)
        memberships_created += 1
        if membership.status == "active":
            memberships_needing_periods.append(membership)

    # Adults first, so a parent created earlier in the same file exists by the time its children
    # are written (a parent can't be fully validated at preview — see _check_child_parents).
    for _, cleaned in adult_rows:
        member = Member.query.filter_by(email=cleaned["email"]).first()
        if member is None:
            member = Member(
                name=cleaned["name"],
                email=cleaned["email"],
                phone=cleaned["phone"],
                address=cleaned["address"],
                family_info=cleaned["family_info"],
            )
            db.session.add(member)
            db.session.flush()
            members_created += 1
        add_membership(member, cleaned)

    for raw_row, cleaned in child_rows:
        parent = find_member_by_email(cleaned["parent_email"])
        parent_error = parent_adult_error(parent)
        if parent_error:
            fail(raw_row, f"Parent {cleaned['parent_email']}: {parent_error}")
            continue
        # A child usually has no email, so re-imports match on parent + name instead.
        child = Member.query.filter(
            Member.parent_member_id == parent.id,
            func.lower(Member.name) == cleaned["name"].lower(),
        ).first()
        if child is None:
            if cleaned["email"] and find_member_by_email(cleaned["email"]) is not None:
                fail(raw_row, "This email already belongs to another member.")
                continue
            child = Member(
                name=cleaned["name"],
                email=cleaned["email"],
                phone=cleaned["phone"],
                address=cleaned["address"],
                family_info=cleaned["family_info"],
                parent_member_id=parent.id,
            )
            db.session.add(child)
            db.session.flush()
            members_created += 1
            ensure_family_entry_for_child(child)
        already_has = Membership.query.filter_by(
            member_id=child.id,
            membership_type=cleaned["membership_type"],
            start_date=date.fromisoformat(cleaned["start_date"]),
        ).first()
        if already_has is None:
            add_membership(child, cleaned)

    batch = ImportBatch(
        admin_user_id=g.current_user.id,
        filename=filename,
        total_rows=len(rows),
        members_created=members_created,
        memberships_created=memberships_created,
        failed_rows=len(failures),
    )
    db.session.add(batch)
    db.session.commit()

    # Deferred until after the commit above so every membership has a real id — the third
    # activation path this generator needs (see admin_create_membership/admin_update_membership
    # in app/memberships/admin_routes.py for the other two).
    for membership in memberships_needing_periods:
        generate_periods_for_membership(membership)

    return jsonify({**_serialize_batch(batch), "failures": failures}), 201
