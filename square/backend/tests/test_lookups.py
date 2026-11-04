"""Tests for lookups (16 tests), e.g. public list falls back to defaults and unknown is 404; admin crud and inactive hidden from public; admin only."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _headers(role="admin"):
    _, token = make_user_and_token(role=role)
    return auth_header(token)


def test_public_list_falls_back_to_defaults_and_unknown_is_404():
    app = _new_app()
    client = app.test_client()
    with app.app_context():
        r = client.get("/api/lookups/expense_category")
        assert r.status_code == 200
        values = [i["value"] for i in r.get_json()["items"]]
        assert values[0] == "venue" and "other" in values
        assert client.get("/api/lookups/nope").status_code == 404


def test_admin_crud_and_inactive_hidden_from_public():
    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        h = _headers()
        rows = client.get("/api/admin/lookups/expense_category", headers=h).get_json()["items"]
        assert len(rows) == 11
        created = client.post("/api/admin/lookups/expense_category", headers=h,
                              json={"value": "insurance", "label": "Insurance"})
        assert created.status_code == 201
        assert client.post("/api/admin/lookups/expense_category", headers=h,
                           json={"value": "insurance", "label": "X"}).status_code == 400
        assert client.post("/api/admin/lookups/expense_category", headers=h,
                           json={"value": "Bad Value", "label": "X"}).status_code == 400
        rid = created.get_json()["id"]
        assert client.patch(f"/api/admin/lookups/expense_category/{rid}", headers=h,
                            json={"is_active": False}).status_code == 200
        public = [i["value"] for i in client.get("/api/lookups/expense_category").get_json()["items"]]
        assert "insurance" not in public and "venue" in public


def test_admin_only():
    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        assert client.get("/api/admin/lookups/expense_category", headers=_headers("member")).status_code == 403


def test_delete_only_when_unused():
    from datetime import date

    from app.accounting.models import Expense
    from app.events.models import Event
    from datetime import datetime, timezone

    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        h = _headers()
        rows = client.get("/api/admin/lookups/expense_category", headers=h).get_json()["items"]
        by_value = {r["value"]: r for r in rows}
        event = Event(title="E", slug="e", event_type="festival", start_datetime=datetime.now(timezone.utc), published=True)
        db.session.add(event)
        db.session.commit()
        db.session.add(Expense(event_id=event.id, date=date(2026, 1, 1), description="x", category="venue", amount=1))
        db.session.commit()
        used = client.delete(f"/api/admin/lookups/expense_category/{by_value['venue']['id']}", headers=h)
        assert used.status_code == 409
        free = client.delete(f"/api/admin/lookups/expense_category/{by_value['gifts']['id']}", headers=h)
        assert free.status_code == 204


def test_committee_role_defaults_and_usage():
    from app.committee.models import CommitteeMember
    from app.lookups.service import usage_count

    app = _new_app()
    client = app.test_client()
    with app.app_context():
        items = client.get("/api/lookups/committee_role").get_json()["items"]
        assert items[0] == {"value": "president", "label": "President"} and len(items) == 14
        db.session.add(CommitteeMember(name="A", role="Treasurer"))
        db.session.commit()
        assert usage_count("committee_role", "treasurer") == 1
        assert usage_count("committee_role", "advisor") == 0



def test_event_type_list_filter_and_hidden_type_rules():
    from datetime import datetime, timezone

    from app.events.models import Event

    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        h = _headers()
        items = client.get("/api/lookups/event_type").get_json()["items"]
        assert [i["value"] for i in items] == ["festival", "cultural", "community", "other"]
        rows = {r["value"]: r for r in client.get("/api/admin/lookups/event_type", headers=h).get_json()["items"]}
        db.session.add(Event(title="E", slug="e", event_type="community", start_datetime=datetime.now(timezone.utc), published=True))
        db.session.commit()
        assert client.delete(f"/api/admin/lookups/event_type/{rows['community']['id']}", headers=h).status_code == 409
        client.patch(f"/api/admin/lookups/event_type/{rows['community']['id']}", headers=h, json={"is_active": False})
        # hidden type: still filterable publicly, refused for a brand-new event
        assert client.get("/api/events?type=community").status_code == 200
        body = {"title": "N", "slug": "n", "event_type": "community", "start_datetime": "2027-01-01T10:00:00Z"}
        assert client.post("/api/admin/events", headers=h, json=body).status_code == 400


def test_album_category_defaults_filter_and_usage():
    from app.gallery.models import Album
    from app.lookups.service import usage_count

    app = _new_app()
    client = app.test_client()
    with app.app_context():
        values = [i["value"] for i in client.get("/api/lookups/album_category").get_json()["items"]]
        assert values == ["festivals", "cultural", "community", "archive"]
        db.session.add(Album(title="A", year=2020, category="archive", published=True))
        db.session.commit()
        assert usage_count("album_category", "archive") == 1
        assert client.get("/api/gallery/albums?category=archive").status_code == 200
        assert client.get("/api/gallery/albums?category=nope").status_code == 400


def test_news_category_defaults_filter_and_usage():
    from app.lookups.service import usage_count
    from app.news.models import News

    app = _new_app()
    client = app.test_client()
    with app.app_context():
        values = [i["value"] for i in client.get("/api/lookups/news_category").get_json()["items"]]
        assert values == ["announcement", "story", "blog"]
        db.session.add(News(title="N", slug="n", content="<p>x</p>", status="published", category="story"))
        db.session.commit()
        assert usage_count("news_category", "story") == 1
        assert client.get("/api/news?category=story").status_code == 200
        assert client.get("/api/news?category=nope").status_code == 400


def test_task_category_defaults_and_usage():
    from datetime import datetime, timezone

    from app.events.models import Event, EventTaskAssignment
    from app.lookups.service import usage_count
    from app.members.models import Member

    app = _new_app()
    client = app.test_client()
    with app.app_context():
        values = [i["value"] for i in client.get("/api/lookups/task_category").get_json()["items"]]
        assert values == ["food", "cultural", "decoration", "logistics", "registration", "other"]
        event = Event(title="E", slug="e", event_type="festival", start_datetime=datetime.now(timezone.utc), published=True)
        member = Member(name="M")
        db.session.add_all([event, member])
        db.session.commit()
        db.session.add(EventTaskAssignment(event_id=event.id, member_id=member.id, category="food"))
        db.session.commit()
        assert usage_count("task_category", "food") == 1
        assert usage_count("task_category", "other") == 0


def test_relationship_type_protected_child_and_usage():
    from app.lookups.service import usage_count
    from app.members.models import FamilyMember, Member

    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        h = _headers()
        values = [i["value"] for i in client.get("/api/lookups/relationship_type").get_json()["items"]]
        assert values == ["spouse", "child", "parent", "other"]
        rows = {r["value"]: r for r in client.get("/api/admin/lookups/relationship_type", headers=h).get_json()["items"]}
        assert rows["child"]["protected"] is True and rows["spouse"]["protected"] is False
        child_id = rows["child"]["id"]
        assert client.patch(f"/api/admin/lookups/relationship_type/{child_id}", headers=h, json={"is_active": False}).status_code == 400
        assert client.patch(f"/api/admin/lookups/relationship_type/{child_id}", headers=h, json={"label": "Son/Daughter"}).status_code == 200
        assert client.delete(f"/api/admin/lookups/relationship_type/{child_id}", headers=h).status_code == 409
        member = Member(name="M")
        db.session.add(member)
        db.session.commit()
        db.session.add(FamilyMember(member_id=member.id, name="X", relationship_type="spouse"))
        db.session.commit()
        assert usage_count("relationship_type", "spouse") == 1


def test_fixed_list_allows_rewording_but_not_add_hide_or_delete():
    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        h = _headers()
        lists = {l["key"]: l for l in client.get("/api/admin/lookups", headers=h).get_json()["items"]}
        assert lists["payment_status"]["fixed"] is True and lists["event_type"]["fixed"] is False
        rows = {r["value"]: r for r in client.get("/api/admin/lookups/payment_status", headers=h).get_json()["items"]}
        assert [r for r in rows if r == "paid"] and rows["paid"]["protected"] is True
        paid_id = rows["paid"]["id"]
        assert client.patch(f"/api/admin/lookups/payment_status/{paid_id}", headers=h, json={"label": "Settled"}).status_code == 200
        assert client.get("/api/lookups/payment_status").get_json()["items"][3] == {"value": "paid", "label": "Settled"}
        assert client.patch(f"/api/admin/lookups/payment_status/{paid_id}", headers=h, json={"is_active": False}).status_code == 400
        assert client.delete(f"/api/admin/lookups/payment_status/{paid_id}", headers=h).status_code == 409
        assert client.post("/api/admin/lookups/payment_status", headers=h, json={"value": "new", "label": "New"}).status_code == 400


def test_fixed_list_defaults_cover_every_status_the_code_uses():
    from app.lookups.registry import LOOKUP_LISTS
    from app.audit.admin_routes import VALID_ACTIONS  # noqa: F401  (imported only to prove no cycle)
    from app.tickets.admin_routes import VALID_TICKET_STATUSES, VALID_AGE_CATEGORIES

    def values(key):
        return {v for v, _ in LOOKUP_LISTS[key]["defaults"]}

    assert VALID_TICKET_STATUSES <= values("ticket_status")
    assert VALID_AGE_CATEGORIES <= values("ticket_age_category")


def test_audit_action_list_matches_the_actions_the_code_logs():
    from app.audit.admin_routes import VALID_ACTIONS
    from app.lookups.registry import LOOKUP_LISTS

    assert {v for v, _ in LOOKUP_LISTS["audit_action"]["defaults"]} == VALID_ACTIONS


def test_frontend_test_fixture_matches_the_backend_registry():
    """frontend/src/test-utils/lookupDefaults.ts feeds every Vitest spec; it must mirror the registry."""
    import re
    from pathlib import Path

    from app.lookups.registry import LOOKUP_LISTS

    text = Path(__file__).resolve().parents[2].joinpath("frontend/src/test-utils/lookupDefaults.ts").read_text(encoding="utf-8")
    parsed: dict[str, list[tuple[str, str]]] = {}
    for key, body in re.findall(r"^  (\w+): \[\n(.*?)^  \],", text, re.S | re.M):
        parsed[key] = re.findall(r'value: "([^"]*)", label: "([^"]*)"', body)
    assert parsed == {k: [tuple(d) for d in v["defaults"]] for k, v in LOOKUP_LISTS.items()}


def test_lists_index_has_group_and_value_count_for_every_list():
    from app.lookups.registry import LOOKUP_LISTS

    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        items = client.get("/api/admin/lookups", headers=_headers()).get_json()["items"]
        assert len(items) == len(LOOKUP_LISTS) and all(i["group"] for i in items)
        expense = next(i for i in items if i["key"] == "expense_category")
        assert expense["group"] == "Finance" and expense["value_count"] == 11


def test_reorder_saves_the_whole_order_and_rejects_a_partial_one():
    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        h = _headers()
        rows = client.get("/api/admin/lookups/event_type", headers=h).get_json()["items"]
        ids = [r["id"] for r in rows]
        reversed_ids = list(reversed(ids))
        ok = client.put("/api/admin/lookups/event_type/order", headers=h, json={"ids": reversed_ids})
        assert ok.status_code == 200 and [r["id"] for r in ok.get_json()["items"]] == reversed_ids
        public = [i["value"] for i in client.get("/api/lookups/event_type").get_json()["items"]]
        assert public == ["other", "community", "cultural", "festival"]
        assert client.put("/api/admin/lookups/event_type/order", headers=h, json={"ids": ids[:-1]}).status_code == 400
        assert client.put("/api/admin/lookups/event_type/order", headers=h, json={"ids": ids + [999]}).status_code == 400
        assert client.put("/api/admin/lookups/nope/order", headers=h, json={"ids": []}).status_code == 404


def test_a_fixed_list_saved_before_a_value_existed_still_shows_it():
    """Rows saved when payment methods had four values (before Stripe): the list shows all five, the admin page saves the missing one (W19-R19)."""
    from app.lookups.models import LookupValue

    app = _new_app()
    client = app.test_client()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        for order, (value, label) in enumerate([("cash", "Cash"), ("vipps_qr", "Vipps-QR"), ("bank_transfer", "Bank transfer"), ("vipps_app", "Vipps-App")], start=1):
            db.session.add(LookupValue(list_key="payment_provider", value=value, label=label, sort_order=order))
        db.session.commit()
        assert [i["value"] for i in client.get("/api/lookups/payment_provider").get_json()["items"]] == ["cash", "vipps_qr", "bank_transfer", "vipps_app", "stripe"]
        h = _headers()
        rows = client.get("/api/admin/lookups/payment_provider", headers=h).get_json()["items"]
        assert [r["value"] for r in rows] == ["cash", "vipps_qr", "bank_transfer", "vipps_app", "stripe"] and rows[-1]["id"]
        assert len(client.get("/api/admin/lookups/payment_provider", headers=h).get_json()["items"]) == 5  # saved once, not added again
