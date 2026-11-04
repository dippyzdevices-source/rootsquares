import uuid

from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

from app.auth.decorators import require_auth
from app.extensions import db
from app.lookups.service import active_values
from app.gallery.media_processing import MediaValidationError, process_upload
from app.members.models import FamilyMember, Member
from app.storage.service import get_public_storage

members_bp = Blueprint("members", __name__, url_prefix="/api/members")



def _serialize_family_member(family_member: FamilyMember) -> dict:
    return {
        "id": family_member.id,
        "name": family_member.name,
        "relationship_type": family_member.relationship_type,
        "age": family_member.age,
        "sort_order": family_member.sort_order,
    }


def _serialize_member(member: Member) -> dict:
    return {
        "id": member.id,
        "name": member.name,
        "phone": member.phone,
        "address": member.address,
        "photo_url": member.photo_url,
        "family_info": member.family_info,
        "family_members": [_serialize_family_member(f) for f in member.family_members],
    }


def _validate_family_member_payload(data: dict, existing: FamilyMember | None) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    cleaned: dict = {}

    if existing is None:
        for field in ("name", "relationship_type"):
            if not data.get(field):
                errors[field] = "This field is required."

    if "name" in data:
        value = data["name"]
        if not isinstance(value, str) or not value.strip():
            errors["name"] = "Must be a non-empty string."
        elif len(value) > 200:
            errors["name"] = "Must be at most 200 characters."
        else:
            cleaned["name"] = value.strip()

    if "relationship_type" in data:
        value = data["relationship_type"]
        # A hidden type is refused for new choices, but an entry may keep its current one.
        if value not in active_values("relationship_type") and not (existing and existing.relationship_type == value):
            errors["relationship_type"] = f"Must be one of {sorted(active_values('relationship_type'))}."
        else:
            cleaned["relationship_type"] = value

    if "age" in data:
        value = data["age"]
        if value is None:
            cleaned["age"] = None
        elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors["age"] = "Must be a non-negative integer or null."
        else:
            cleaned["age"] = value

    if "sort_order" in data:
        value = data["sort_order"]
        if isinstance(value, bool) or not isinstance(value, int):
            errors["sort_order"] = "Must be an integer."
        else:
            cleaned["sort_order"] = value

    return cleaned, errors


def find_my_member(user) -> Member | None:
    """Resolve "the current user's Member row", auto-linking an Excel-imported profile the
    first time its email matches a real login — this is the only place that link happens,
    so every self-service route (members, memberships) must call this rather than querying
    Member.user_id directly.
    """
    member = Member.query.filter_by(user_id=user.id).first()
    if member is not None:
        return member

    unlinked = Member.query.filter(Member.user_id.is_(None), Member.email == user.email).first()
    if unlinked is not None:
        unlinked.user_id = user.id
        db.session.commit()
    return unlinked


@members_bp.get("/me")
@require_auth
def get_my_member():
    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"error": "Member profile not created yet"}), 404
    return jsonify(_serialize_member(member))


@members_bp.put("/me")
@require_auth
def upsert_my_member():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        return jsonify({"errors": {"name": "This field is required."}}), 400

    member = find_my_member(g.current_user)
    if member is None:
        member = Member(user_id=g.current_user.id, name=name.strip())
        db.session.add(member)
    else:
        member.name = name.strip()

    if "phone" in data:
        member.phone = data["phone"]
    if "address" in data:
        member.address = data["address"]
    if "family_info" in data:
        member.family_info = data["family_info"]

    db.session.commit()
    return jsonify(_serialize_member(member))


@members_bp.post("/me/photo")
@require_auth
def upload_my_photo():
    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"error": "Complete your member profile before uploading a photo."}), 400

    file = request.files.get("file")
    if file is None:
        return jsonify({"errors": {"file": "A file is required."}}), 400

    try:
        processed = process_upload(file)
    except MediaValidationError as exc:
        return jsonify({"errors": {"file": str(exc)}}), 400

    storage = get_public_storage()
    old_key = storage.key_from_url(member.photo_url) if member.photo_url else None

    unique_id = uuid.uuid4().hex
    safe_name = secure_filename(file.filename) or "photo"
    storage_key = f"members/{member.id}/photo-{unique_id}-{safe_name}"
    storage.upload(storage_key, processed.original_bytes, processed.original_content_type)
    if old_key:
        storage.delete(old_key)

    member.photo_url = storage.url_for(storage_key)
    db.session.commit()

    return jsonify(_serialize_member(member))


@members_bp.post("/me/family")
@require_auth
def create_my_family_member():
    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"error": "Complete your member profile before adding family info."}), 400

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


@members_bp.patch("/me/family/<int:family_member_id>")
@require_auth
def update_my_family_member(family_member_id: int):
    member = find_my_member(g.current_user)
    family_member = db.session.get(FamilyMember, family_member_id)
    if member is None or family_member is None or family_member.member_id != member.id:
        return jsonify({"error": "Family member not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, errors = _validate_family_member_payload(data, existing=family_member)
    if errors:
        return jsonify({"errors": errors}), 400

    for field, value in cleaned.items():
        setattr(family_member, field, value)

    db.session.commit()
    return jsonify(_serialize_family_member(family_member))


@members_bp.delete("/me/family/<int:family_member_id>")
@require_auth
def delete_my_family_member(family_member_id: int):
    member = find_my_member(g.current_user)
    family_member = db.session.get(FamilyMember, family_member_id)
    if member is None or family_member is None or family_member.member_id != member.id:
        return jsonify({"error": "Family member not found"}), 404

    db.session.delete(family_member)
    db.session.commit()
    return "", 204


def _serialize_my_task_assignment(assignment: "EventTaskAssignment") -> dict:
    event = assignment.event
    return {
        "id": assignment.id,
        "category": assignment.category,
        "event_id": event.id,
        "event_title": event.title,
        "event_slug": event.slug,
        "event_start_datetime": event.start_datetime.isoformat(),
        "event_end_datetime": event.end_datetime.isoformat() if event.end_datetime else None,
    }


@members_bp.get("/me/task-assignments")
@require_auth
def get_my_task_assignments():
    """Every event this member has ever been assigned to help with — past and future — for
    the self-service "Volunteering" portal page. Ordered soonest-first by the event's own
    start time; the frontend splits into upcoming/past using the same "has it started yet"
    comparison the rest of the app already uses for events.
    """
    from app.events.models import Event, EventTaskAssignment

    member = find_my_member(g.current_user)
    if member is None:
        return jsonify({"items": []})

    assignments = (
        EventTaskAssignment.query.join(Event)
        .filter(EventTaskAssignment.member_id == member.id)
        .order_by(Event.start_datetime.asc())
        .all()
    )
    return jsonify({"items": [_serialize_my_task_assignment(a) for a in assignments]})


@members_bp.get("/me/export")
@require_auth
def export_my_data():
    """GDPR personal-data export — everything BCA Oslo holds about the current user, in one
    JSON document: account, profile, membership history, and order/ticket history. Every
    query below is scoped to g.current_user, never accepting an id from the request.
    """
    from app.memberships.routes import _serialize_membership
    from app.orders.routes import _serialize_order, orders_for_user

    member = find_my_member(g.current_user)
    memberships = member.memberships if member else []
    orders = orders_for_user(g.current_user)

    return jsonify(
        {
            "account": {"email": g.current_user.email, "phone": g.current_user.phone},
            "profile": _serialize_member(member) if member else None,
            "memberships": [_serialize_membership(m) for m in memberships],
            "orders": [_serialize_order(o) for o in orders],
        }
    )
