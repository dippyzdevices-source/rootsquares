from app.lookups.models import LookupValue
from app.lookups.registry import LOOKUP_LISTS
from app.modules import module_enabled


def lookup_rows(list_key: str) -> list[LookupValue]:
    return (
        LookupValue.query.filter_by(list_key=list_key)
        .order_by(LookupValue.sort_order.asc(), LookupValue.id.asc())
        .all()
    )


def value_available(list_key: str, value: str) -> bool:
    """A value that belongs to a module (the list's `value_modules`) is offered only while that module is on (W8-R25)."""
    return module_enabled(LOOKUP_LISTS[list_key].get("value_modules", {}).get(value))


def missing_defaults(list_key: str, rows: list[LookupValue]) -> list[tuple[str, str]]:
    """The registry defaults of a FIXED list that a square's saved rows do not have yet: a value the code added after the rows were made (Bank transfer, Stripe).
    The code branches on every value of a fixed list, so each one must always be there; the admin can reword and reorder it, never add or remove one (W19-R19)."""
    if not rows or not LOOKUP_LISTS[list_key].get("fixed"):
        return []
    have = {r.value for r in rows}
    return [(v, label) for v, label in LOOKUP_LISTS[list_key]["defaults"] if v not in have]


def lookup_items(list_key: str, *, include_inactive: bool = False) -> list[dict]:
    """`[{value, label, is_active}]` in display order. Falls back to the registry defaults
    while the list has no rows at all. Values of a module that is off are left out."""
    rows = lookup_rows(list_key)
    if not rows:
        return [
            {"value": v, "label": label, "is_active": True}
            for v, label in LOOKUP_LISTS[list_key]["defaults"]
            if value_available(list_key, v)
        ]
    items = [
        {"value": r.value, "label": r.label, "is_active": r.is_active}
        for r in rows
        if (include_inactive or r.is_active) and value_available(list_key, r.value)
    ]
    # a fixed list always offers every value the code knows, even in a square whose rows were saved before it existed
    items += [{"value": v, "label": label, "is_active": True} for v, label in missing_defaults(list_key, rows) if value_available(list_key, v)]
    return items


def is_protected(list_key: str, value: str) -> bool:
    """Values the code itself relies on — these can be renamed but never hidden or deleted."""
    spec = LOOKUP_LISTS[list_key]
    return bool(spec.get("fixed")) or value in spec.get("protected", [])


def is_fixed(list_key: str) -> bool:
    """A fixed list holds values the code branches on: wording and order are editable, nothing else."""
    return bool(LOOKUP_LISTS[list_key].get("fixed"))


def usage_count(list_key: str, value: str) -> int:
    """How many records still store this value — a value in use can be hidden but not deleted.
    Register each converted list's consumer here."""
    if list_key == "expense_category":
        from app.accounting.models import Expense

        return Expense.query.filter_by(category=value).count()
    if list_key == "relationship_type":
        from app.members.models import FamilyMember

        return FamilyMember.query.filter_by(relationship_type=value).count()
    if list_key == "task_category":
        from app.events.models import EventTaskAssignment

        return EventTaskAssignment.query.filter_by(category=value).count()
    if list_key == "news_category":
        from app.news.models import News

        return News.query.filter_by(category=value).count()
    if list_key == "album_category":
        from app.gallery.models import Album

        return Album.query.filter_by(category=value).count()
    if list_key == "event_type":
        from app.events.models import Event

        return Event.query.filter_by(event_type=value).count()
    if list_key == "committee_role":
        # CommitteeMember.role stores the label text itself (free text), not the slug.
        from app.committee.models import CommitteeMember

        return CommitteeMember.query.filter_by(role=label_for(list_key, value)).count()
    return 0


def active_values(list_key: str) -> list[str]:
    return [i["value"] for i in lookup_items(list_key)]


def all_values(list_key: str) -> list[str]:
    """Every value including hidden ones — for filters that must still accept a retired value."""
    return [i["value"] for i in lookup_items(list_key, include_inactive=True)]


def label_for(list_key: str, value: str) -> str:
    for item in lookup_items(list_key, include_inactive=True):
        if item["value"] == value:
            return item["label"]
    return value.replace("_", " ").capitalize()


def list_available(list_key: str) -> bool:
    """A known list whose module (if it belongs to one) is on in this square (W8-R10)."""
    spec = LOOKUP_LISTS.get(list_key)
    return spec is not None and module_enabled(spec.get("module"))
