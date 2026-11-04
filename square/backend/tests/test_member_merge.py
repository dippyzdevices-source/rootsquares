"""Tests for member merge (3 tests), e.g. duplicates report groups by email; merge moves data deletes other and keeps one active; merge rejects same member and parent child."""
from datetime import date
from unittest.mock import patch

from app.audit.models import AuditLog
from app.extensions import db
from app.members.models import FamilyMember, Member
from app.memberships.models import Membership
from tests.auth_helpers import FakeJWKClient
from tests.test_membership_drive import _add_type, _admin_headers, _new_app


def _two_dupes():
    _add_type(name="adult", price=300)
    a = Member(name="Priya Das", email="priya@example.com", phone="41234567")
    b = Member(name="Priya Das", email="PRIYA@example.com", address="Oslo")
    db.session.add_all([a, b])
    db.session.commit()
    db.session.add_all(
        [
            Membership(member_id=a.id, membership_type="adult", status="active", start_date=date(2026, 1, 1)),
            Membership(member_id=b.id, membership_type="adult", status="active", start_date=date(2026, 6, 1)),
            FamilyMember(member_id=b.id, name="Kid", relationship_type="child"),
        ]
    )
    db.session.commit()
    return a, b


def test_duplicates_report_groups_by_email():
    app = _new_app()
    with app.app_context():
        a, b = _two_dupes()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            r = app.test_client().get("/api/admin/members/duplicates", headers=_admin_headers())
        groups = r.get_json()["groups"]
        assert len(groups) == 1 and groups[0]["reason"] == "email"
        assert {m["id"] for m in groups[0]["members"]} == {a.id, b.id}
        db.drop_all()


def test_merge_moves_data_deletes_other_and_keeps_one_active():
    app = _new_app()
    with app.app_context():
        a, b = _two_dupes()
        a_id, b_id = a.id, b.id
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            r = app.test_client().post(
                f"/api/admin/members/{a_id}/merge", json={"merge_id": b_id}, headers=_admin_headers()
            )
        assert r.status_code == 200
        assert db.session.get(Member, b_id) is None
        keep = db.session.get(Member, a_id)
        assert keep.address == "Oslo"  # blank field filled from the merged record
        assert [f.name for f in keep.family_members] == ["Kid"]
        assert sorted(m.status for m in keep.memberships) == ["active", "expired"]
        assert AuditLog.query.filter_by(action="members_merged").count() == 1
        db.drop_all()


def test_merge_rejects_same_member_and_parent_child():
    app = _new_app()
    with app.app_context():
        a, b = _two_dupes()
        b.parent_member_id = a.id
        db.session.commit()
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            c = app.test_client()
            h = _admin_headers()
            assert c.post(f"/api/admin/members/{a.id}/merge", json={"merge_id": a.id}, headers=h).status_code == 400
            assert c.post(f"/api/admin/members/{a.id}/merge", json={"merge_id": b.id}, headers=h).status_code == 400
        db.drop_all()
