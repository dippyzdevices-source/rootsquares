from flask import Blueprint, jsonify

from app.lookups.service import list_available, lookup_items

lookups_bp = Blueprint("lookups", __name__, url_prefix="/api/lookups")


@lookups_bp.get("/<list_key>")
def get_lookup(list_key: str):
    if not list_available(list_key):
        return jsonify({"error": "Unknown list"}), 404
    items = [{"value": i["value"], "label": i["label"]} for i in lookup_items(list_key)]
    return jsonify({"items": items})
