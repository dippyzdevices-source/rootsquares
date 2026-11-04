"""Excel import of children: a `parent_email` column marks a child row; the child may have no
email of their own and is linked to their parent at confirm time."""

from io import BytesIO
from unittest.mock import patch

from openpyxl import Workbook, load_workbook

from app import create_app
from app.extensions import db
from app.imports.excel import validate_row
from app.members.models import Member
from app.memberships.models import Membership, MembershipPeriod, MembershipType
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

HEADER = [
    "name", "email", "phone", "address", "family_info",
    "membership_type", "membership_status", "start_date", "end_date", "parent_email",
]
TYPES = {"adult", "child"}


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                MembershipType(name="adult", price=300, billing_frequency="yearly"),
                MembershipType(name="child", price=100, billing_frequency="yearly"),
            ]
        )
        db.session.commit()
    return app


def _headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _adult(name="Anita Das", email="anita@x.no", status="active"):
    return [name, email, None, None, None, "adult", status, "2026-01-01", None, None]


def _child(name="Rohan Das", parent="anita@x.no", email=None, mtype="child"):
    return [name, email, None, None, None, mtype, "active", "2026-01-01", None, parent]


def _xlsx(rows):
    wb = Workbook()
    sheet = wb.active
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _preview(client, rows):
    return client.post(
        "/api/admin/imports/members/preview",
        headers=_headers(),
        data={"file": (BytesIO(_xlsx(rows)), "m.xlsx")},
        content_type="multipart/form-data",
    ).get_json()


def _confirm(client, preview, only_valid=True):
    payload = [
        {k: v for k, v in r.items() if k != "errors"}
        for r in preview["rows"]
        if not (only_valid and r["errors"])
    ]
    return client.post(
        "/api/admin/imports/members/confirm", headers=_headers(), json={"filename": "m.xlsx", "rows": payload}
    )


def test_validate_row_child_rules():
    def row(**over):
        base = {"name": "Rohan", "membership_type": "child", "membership_status": "active", "start_date": "2026-01-01"}
        base.update(over)
        return base

    cleaned, errors = validate_row(row(parent_email="Anita@X.no"), TYPES)
    assert errors == {} and cleaned["email"] is None and cleaned["parent_email"] == "anita@x.no"
    assert "parent_email" in validate_row(row(), TYPES)[1]  # child with no parent
    assert "membership_type" in validate_row(row(membership_type="adult", parent_email="a@x.no"), TYPES)[1]
    assert "parent_email" in validate_row(row(parent_email="nope"), TYPES)[1]
    # An adult row still needs an email.
    assert "email" in validate_row(row(membership_type="adult"), TYPES)[1]


def test_preview_checks_parent_in_file_or_database():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        client = app.test_client()
        # A child listed BEFORE its parent in the same file is fine; unknown / inactive parents are not.
        data = _preview(
            client,
            [
                _child("Rohan Das", "anita@x.no"),
                _adult(),
                _child("Lost Kid", "nobody@x.no"),
                _adult("Pending Pat", "pat@x.no", status="pending"),
                _child("Pat Kid", "pat@x.no"),
            ],
        )
        errors = [r["errors"] for r in data["rows"]]
        assert errors[0] == {} and errors[1] == {} and errors[3] == {}
        assert "parent_email" in errors[2] and "parent_email" in errors[4]
        assert (data["valid_count"], data["invalid_count"]) == (3, 2)
        assert Member.query.count() == 0
        db.drop_all()


def test_confirm_links_children_to_a_parent_created_in_the_same_file():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        client = app.test_client()
        preview = _preview(client, [_child("Rohan Das", "anita@x.no"), _adult()])
        resp = _confirm(client, preview)
        assert resp.status_code == 201
        body = resp.get_json()
        assert (body["members_created"], body["memberships_created"], body["failed_rows"], body["failures"]) == (2, 2, 0, [])
        parent = Member.query.filter_by(email="anita@x.no").one()
        child = Member.query.filter_by(name="Rohan Das").one()
        assert child.parent_member_id == parent.id and child.email is None
        assert {(f.name, f.relationship_type) for f in parent.family_members} == {("Rohan Das", "child")}
        assert Membership.query.filter_by(member_id=child.id, membership_type="child", status="active").count() == 1
        assert MembershipPeriod.query.count() == 2  # one yearly period each
        db.drop_all()


def test_confirm_reports_failed_children_with_a_reason_and_skips_them():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        client = app.test_client()
        preview = _preview(client, [_adult("Pending Pat", "pat@x.no", status="pending"), _child("Pat Kid", "pat@x.no")])
        # The preview already flags it; send it to confirm anyway (the backend never trusts the frontend).
        body = _confirm(client, preview, only_valid=False).get_json()
        assert body["failed_rows"] == 1 and body["failures"][0]["name"] == "Pat Kid"
        assert body["failures"][0]["row_number"] == 2 and "no active" in body["failures"][0]["reason"]
        assert Member.query.filter_by(name="Pat Kid").count() == 0
        db.drop_all()


def test_reimporting_the_same_child_does_not_create_a_second_one():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        client = app.test_client()
        _confirm(client, _preview(client, [_adult(), _child("Rohan Das", "anita@x.no")]))
        second = _confirm(client, _preview(client, [_child("rohan das", "anita@x.no")])).get_json()
        assert second["members_created"] == 0 and second["memberships_created"] == 0
        assert Member.query.filter(Member.parent_member_id.isnot(None)).count() == 1
        child = Member.query.filter(Member.parent_member_id.isnot(None)).one()
        assert Membership.query.filter_by(member_id=child.id).count() == 1
        db.drop_all()


def test_child_email_already_used_by_another_member_is_rejected():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        client = app.test_client()
        preview = _preview(client, [_adult(), _child("Rohan Das", "anita@x.no", email="anita@x.no")])
        body = _confirm(client, preview).get_json()
        assert body["failed_rows"] == 1 and "already belongs" in body["failures"][0]["reason"]
        db.drop_all()


def test_members_export_includes_the_parent_email():
    app = _new_app()
    with app.app_context(), patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        client = app.test_client()
        _confirm(client, _preview(client, [_adult(), _child()]))
        data = client.get("/api/admin/members/export", headers=_headers()).data
        sheet = load_workbook(BytesIO(data)).active
        header = [c.value for c in sheet[1]]
        by_name = {r[0]: dict(zip(header, r)) for r in sheet.iter_rows(min_row=2, values_only=True)}
        assert by_name["Rohan Das"]["Parent email"] == "anita@x.no"
        assert by_name["Anita Das"]["Parent email"] is None
        db.drop_all()
