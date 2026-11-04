import re

from flask import Blueprint, g, jsonify, request

from app.audit.service import log_action
from app.auth.decorators import require_role
from app.extensions import db
from app.lookups.models import LookupValue
from app.lookups.registry import GROUP_ORDER, LOOKUP_LISTS
from app.lookups.service import is_fixed, is_protected, list_available, lookup_items, lookup_rows, missing_defaults, usage_count, value_available

admin_lookups_bp = Blueprint("admin_lookups", __name__, url_prefix="/api/admin/lookups")
admin_lookups_bp.before_request(require_role("admin"))

VALUE_PATTERN = re.compile(r"^[a-z0-9_]{1,60}$")


def _serialize(row: LookupValue) -> dict:
    return {
        "id": row.id,
        "list_key": row.list_key,
        "value": row.value,
        "label": row.label,
        "sort_order": row.sort_order,
        "is_active": row.is_active,
        "usage_count": usage_count(row.list_key, row.value),
        "protected": is_protected(row.list_key, row.value),
    }


def _ensure_seeded(list_key: str) -> list[LookupValue]:
    """Materialise registry defaults the first time a list is edited; a fixed list also gets any default it is missing."""
    rows = lookup_rows(list_key)
    if not rows:
        for order, (value, label) in enumerate(LOOKUP_LISTS[list_key]["defaults"], start=1):
            db.session.add(LookupValue(list_key=list_key, value=value, label=label, sort_order=order))
        db.session.commit()
        rows = lookup_rows(list_key)
    elif missing_defaults(list_key, rows):
        # a fixed list gets the values the code added since its rows were saved, at the end (W19-R19)
        last = max(r.sort_order for r in rows)
        for order, (value, label) in enumerate(missing_defaults(list_key, rows), start=last + 1):
            db.session.add(LookupValue(list_key=list_key, value=value, label=label, sort_order=order))
        db.session.commit()
        rows = lookup_rows(list_key)
    return rows


@admin_lookups_bp.get("")
def list_lookup_lists():
    return jsonify({"items": [
        {
            "key": k,
            "title": v["title"],
            "description": v["description"],
            "group": v["group"],
            "fixed": bool(v.get("fixed")),
            "value_count": len(lookup_items(k, include_inactive=True)),
        }
        for k, v in sorted(LOOKUP_LISTS.items(), key=lambda kv: GROUP_ORDER.index(kv[1]["group"]))
        if list_available(k)
    ]})


@admin_lookups_bp.get("/<list_key>")
def admin_get_lookup(list_key: str):
    if not list_available(list_key):
        return jsonify({"error": "Unknown list"}), 404
    return jsonify({"items": [_serialize(r) for r in _ensure_seeded(list_key) if value_available(list_key, r.value)]})


@admin_lookups_bp.post("/<list_key>")
def admin_create_lookup(list_key: str):
    if not list_available(list_key):
        return jsonify({"error": "Unknown list"}), 404
    if is_fixed(list_key):
        return jsonify({"error": "This list is fixed by the system; only wording and order can be changed."}), 400
    data = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}
    value = data.get("value")
    label = data.get("label")
    if not isinstance(label, str) or not label.strip():
        errors["label"] = "This field is required."
    elif len(label.strip()) > 120:
        errors["label"] = "Must be at most 120 characters."
    if not isinstance(value, str) or not VALUE_PATTERN.match(value):
        errors["value"] = "Use lowercase letters, digits and underscores only."
    rows = _ensure_seeded(list_key)
    if "value" not in errors and any(r.value == value for r in rows):
        errors["value"] = "This value already exists."
    if errors:
        return jsonify({"errors": errors}), 400
    row = LookupValue(
        list_key=list_key, value=value, label=label.strip(),
        sort_order=max((r.sort_order for r in rows), default=0) + 1,
    )
    db.session.add(row)
    db.session.commit()
    log_action(g.current_user, "lookup_value_changed", f"Added '{row.label}' to {list_key}", "lookup_value", row.id)
    return jsonify(_serialize(row)), 201


@admin_lookups_bp.patch("/<list_key>/<int:row_id>")
def admin_update_lookup(list_key: str, row_id: int):
    row = db.session.get(LookupValue, row_id)
    if row is None or row.list_key != list_key:
        return jsonify({"error": "Value not found"}), 404
    data = request.get_json(silent=True) or {}
    errors: dict[str, str] = {}
    if "label" in data:
        label = data["label"]
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 120:
            errors["label"] = "Must be 1-120 characters."
    if "sort_order" in data and (isinstance(data["sort_order"], bool) or not isinstance(data["sort_order"], int)):
        errors["sort_order"] = "Must be an integer."
    if "is_active" in data and not isinstance(data["is_active"], bool):
        errors["is_active"] = "Must be true or false."
    elif data.get("is_active") is False and is_protected(list_key, row.value):
        errors["is_active"] = "This value is required by the system and cannot be hidden."
    if errors:
        return jsonify({"errors": errors}), 400
    if "label" in data:
        row.label = data["label"].strip()
    if "sort_order" in data:
        row.sort_order = data["sort_order"]
    if "is_active" in data:
        row.is_active = data["is_active"]
    db.session.commit()
    log_action(g.current_user, "lookup_value_changed", f"Updated '{row.label}' in {list_key}", "lookup_value", row.id)
    return jsonify(_serialize(row))


@admin_lookups_bp.delete("/<list_key>/<int:row_id>")
def admin_delete_lookup(list_key: str, row_id: int):
    row = db.session.get(LookupValue, row_id)
    if row is None or row.list_key != list_key:
        return jsonify({"error": "Value not found"}), 404
    if is_protected(list_key, row.value):
        return jsonify({"error": "This value is required by the system and cannot be deleted."}), 409
    if usage_count(list_key, row.value) > 0:
        return jsonify({"error": "This value is used by existing records. Hide it instead."}), 409
    label = row.label
    db.session.delete(row)
    db.session.commit()
    log_action(g.current_user, "lookup_value_changed", f"Deleted '{label}' from {list_key}", "lookup_value", row_id)
    return "", 204


@admin_lookups_bp.put("/<list_key>/order")
def admin_reorder_lookup(list_key: str):
    """Save a new display order for a whole list in one go: `{"ids": [<row ids in the new order>]}`
    must name exactly the list's current rows (nothing missing, nothing extra)."""
    if not list_available(list_key):
        return jsonify({"error": "Unknown list"}), 404
    data = request.get_json(silent=True) or {}
    ids = data.get("ids")
    all_rows = _ensure_seeded(list_key)
    rows = [r for r in all_rows if value_available(list_key, r.value)]
    if (
        not isinstance(ids, list)
        or any(isinstance(i, bool) or not isinstance(i, int) for i in ids)
        or sorted(ids) != sorted(r.id for r in rows)
    ):
        return jsonify({"errors": {"ids": "Must list every value of this list exactly once."}}), 400
    by_id = {r.id: r for r in rows}
    for position, row_id in enumerate(ids, start=1):
        by_id[row_id].sort_order = position
    for offset, hidden in enumerate((r for r in all_rows if r not in rows), start=len(ids) + 1):
        hidden.sort_order = offset  # values of a module that is off keep their place after the shown ones
    db.session.commit()
    log_action(g.current_user, "lookup_value_changed", f"Reordered {list_key}", "lookup_list", None)
    return jsonify({"items": [_serialize(by_id[i]) for i in ids]})
