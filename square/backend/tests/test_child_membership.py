"""Tests for child membership (5 tests), e.g. drive child creates own member linked to parent; drive child rejects parent without active adult or unknown parent; admin child membership requires parent link and parent email sets it."""
from datetime import date
from unittest.mock import patch

from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership
from tests.test_membership_drive import _add_type, _admin_headers, _new_app


def _setup_parent(active=True):
    _add_type(name="adult", price=300)
    _add_type(name="child", price=100)
    parent = Member(name="Parent", email="parent@example.com", phone="41234567")
    db.session.add(parent)
    db.session.commit()
    db.session.add(
        Membership(
            member_id=parent.id,
            membership_type="adult",
            status="active" if active else "pending",
            start_date=date.today(),
        )
    )
    db.session.commit()
    return parent


def _drive(app, **overrides):
    payload = {"name": "Kid", "membership_type": "child", "parent_email": "parent@example.com"}
    payload.update(overrides)
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=__import__("tests.auth_helpers", fromlist=["x"]).FakeJWKClient()):
        return app.test_client().post(
            "/api/admin/membership-drive/signup", json=payload, headers=_admin_headers()
        )


def test_drive_child_creates_own_member_linked_to_parent():
    app = _new_app()
    with app.app_context():
        parent = _setup_parent()
        response = _drive(app)
        assert response.status_code == 201
        child = Member.query.filter_by(name="Kid").one()
        assert child.parent_member_id == parent.id
        assert child.email is None
        assert [(f.name, f.relationship_type) for f in parent.family_members] == [("Kid", "child")]
        assert [(f.name, f.relationship_type) for f in child.family_members] == [("Parent", "parent")]
        assert Membership.query.filter_by(member_id=child.id, status="active").count() == 1
        db.drop_all()


def test_drive_child_rejects_parent_without_active_adult_or_unknown_parent():
    app = _new_app()
    with app.app_context():
        _setup_parent(active=False)
        assert "parent_email" in _drive(app).get_json()["errors"]
        assert "parent_email" in _drive(app, parent_email="nobody@example.com").get_json()["errors"]
        assert Member.query.filter_by(name="Kid").count() == 0
        db.drop_all()


def test_admin_child_membership_requires_parent_link_and_parent_email_sets_it():
    app = _new_app()
    with app.app_context():
        parent = _setup_parent()
        kid = Member(name="Kid2")
        db.session.add(kid)
        db.session.commit()
        client = app.test_client()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=__import__("tests.auth_helpers", fromlist=["x"]).FakeJWKClient()):
            headers = _admin_headers()
            body = {"member_id": kid.id, "membership_type": "child", "start_date": "2026-10-01"}
            assert client.post("/api/admin/memberships", json=body, headers=headers).status_code == 400
            r = client.patch(
                f"/api/admin/members/{kid.id}", json={"parent_email": "parent@example.com"}, headers=headers
            )
            assert r.status_code == 200 and r.get_json()["parent"]["id"] == parent.id
            assert client.post("/api/admin/memberships", json=body, headers=headers).status_code == 201
        db.drop_all()


def test_activating_a_membership_expires_the_members_other_active_one():
    app = _new_app()
    with app.app_context():
        parent = _setup_parent()
        old = Membership.query.filter_by(member_id=parent.id).one()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=__import__("tests.auth_helpers", fromlist=["x"]).FakeJWKClient()):
            body = {"member_id": parent.id, "membership_type": "adult", "status": "active", "start_date": "2027-01-01"}
            assert app.test_client().post("/api/admin/memberships", json=body, headers=_admin_headers()).status_code == 201
        db.session.refresh(old)
        assert old.status == "expired" and old.end_date == date(2027, 1, 1)
        assert Membership.query.filter_by(member_id=parent.id, status="active").count() == 1
        db.drop_all()


def test_admin_members_list_filters_by_latest_membership_status():
    app = _new_app()
    with app.app_context():
        _setup_parent()  # parent: latest membership "adult" active
        pending = Member(name="Pending Pat", email="pat@example.com")
        db.session.add(pending)
        db.session.commit()
        db.session.add(Membership(member_id=pending.id, membership_type="adult", status="pending", start_date=date.today()))
        db.session.commit()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=__import__("tests.auth_helpers", fromlist=["x"]).FakeJWKClient()):
            r = app.test_client().get("/api/admin/members?status=pending", headers=_admin_headers())
        items = r.get_json()["items"]
        assert [i["name"] for i in items] == ["Pending Pat"]
        assert items[0]["latest_membership"]["id"]
        db.drop_all()
