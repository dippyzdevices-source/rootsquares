"""The member roster as a people list that works without Memberships (rootsquares W11-R24, ADR 044): add a person by hand, and no membership data
shows anywhere while the Memberships module is off."""

from datetime import date
from io import BytesIO
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _call(app, method, path, headers, **kw):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return getattr(app.test_client(), method)(path, headers=headers, **kw)


def _member_with_membership(name="Priya Das", email="priya@example.com"):
    member = Member(name=name, email=email)
    db.session.add(member)
    db.session.flush()
    db.session.add(Membership(member_id=member.id, membership_type="Individual", status="active", start_date=date(2026, 1, 1)))
    db.session.commit()
    return member


def _memberships_off():
    return patch("app.members.admin_routes.module_enabled", side_effect=lambda key: key != "memberships")


def test_add_a_person_creates_no_membership():
    app = _new_app()
    with app.app_context():
        h = _admin()
        r = _call(app, "post", "/api/admin/members", h, json={"name": "  Sam Volunteer ", "email": "sam@example.com", "phone": "555"})
        assert r.status_code == 201
        body = r.get_json()
        assert body["name"] == "Sam Volunteer" and body["email"] == "sam@example.com" and body["linked"] is False
        assert Membership.query.count() == 0 and Member.query.count() == 1
        db.drop_all()


def test_add_a_person_checks_the_input_and_refuses_a_second_person_with_the_same_email():
    app = _new_app()
    with app.app_context():
        h = _admin()
        assert _call(app, "post", "/api/admin/members", h, json={"name": ""}).status_code == 400
        bad = _call(app, "post", "/api/admin/members", h, json={"name": "A", "email": "not-an-email"})
        assert bad.status_code == 400 and "email" in bad.get_json()["errors"]
        first = _call(app, "post", "/api/admin/members", h, json={"name": "Sam", "email": "Sam@Example.com"})
        assert first.status_code == 201
        again = _call(app, "post", "/api/admin/members", h, json={"name": "Sam Again", "email": "sam@example.com"})
        assert again.status_code == 409 and again.get_json()["member_id"] == first.get_json()["id"]
        assert Member.query.count() == 1
        db.drop_all()


def test_a_person_needs_no_email():
    app = _new_app()
    with app.app_context():
        r = _call(app, "post", "/api/admin/members", _admin(), json={"name": "Helper"})
        assert r.status_code == 201 and r.get_json()["email"] is None
        db.drop_all()


def test_memberships_off_hides_membership_data_in_list_detail_and_export():
    app = _new_app()
    with app.app_context():
        member = _member_with_membership()
        h = _admin()
        listed = _call(app, "get", "/api/admin/members", h).get_json()["items"][0]
        assert listed["latest_membership"] is not None  # on: shown
        with _memberships_off():
            listed = _call(app, "get", "/api/admin/members", h).get_json()["items"][0]
            assert listed["latest_membership"] is None
            assert _call(app, "get", f"/api/admin/members/{member.id}", h).get_json()["memberships"] == []
            # the membership filters are ignored: the person is still listed
            assert _call(app, "get", "/api/admin/members?status=expired", h).get_json()["total"] == 1
            sheet = _call(app, "get", "/api/admin/members/export", h).data
        assert b"Latest membership" not in _headers_of(sheet)
        assert Membership.query.count() == 1  # kept, never deleted
        on_sheet = _call(app, "get", "/api/admin/members/export", h).data
        assert b"Latest membership type" in _headers_of(on_sheet)
        db.drop_all()


def _headers_of(xlsx: bytes) -> bytes:
    """The text of the sheet's first row (shared strings of the workbook are enough for these checks)."""
    import zipfile

    with zipfile.ZipFile(BytesIO(xlsx)) as z:
        names = z.namelist()
        parts = [z.read(n) for n in names if n.startswith("xl/") and n.endswith(".xml") and "sheet" in n or "sharedStrings" in n]
    return b"".join(parts)
