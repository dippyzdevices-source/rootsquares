"""Tests for admin imports routes (13 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin routes allow a cors preflight with no auth header."""
from datetime import date
from io import BytesIO
from unittest.mock import patch

from openpyxl import Workbook

from app import create_app
from app.extensions import db
from app.memberships.models import MembershipType
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

HEADER = [
    "name", "email", "phone", "address", "family_info",
    "membership_type", "membership_status", "start_date", "end_date",
]


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _seed_membership_types():
    db.session.add_all(
        [MembershipType(name="individual", price=0), MembershipType(name="family", price=0)]
    )
    db.session.commit()


def _workbook_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    sheet = wb.active
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post("/api/admin/imports/members/preview")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/imports/members/preview", headers=auth_header(token)
            )
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/imports/members/preview", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_preview_requires_a_file():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/imports/members/preview", headers=_admin_headers()
            )
        assert response.status_code == 400
        db.drop_all()


def test_preview_rejects_a_file_over_1mb():
    import io

    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/imports/members/preview",
                headers=_admin_headers(),
                data={"file": (io.BytesIO(b"0" * (1024 * 1024 + 1)), "big.xlsx")},
                content_type="multipart/form-data",
            )
        assert response.status_code == 400
        assert "1MB" in response.get_json()["error"]
        db.drop_all()


def test_preview_reports_valid_and_invalid_rows_without_writing_anything():
    from app.members.models import Member

    app = _new_app()
    with app.app_context():
        _seed_membership_types()
        file_bytes = _workbook_bytes([
            ["Priya Das", "priya@example.com", "+4712345678", "Oslo", None,
             "individual", "active", "2026-01-01", None],
            ["Bad Row", "not-an-email", None, None, None, "individual", "active",
             "2026-01-01", None],
        ])

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/imports/members/preview",
                data={"file": (BytesIO(file_bytes), "members.xlsx")},
                headers=_admin_headers(),
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["valid_count"] == 1
        assert data["invalid_count"] == 1
        assert data["rows"][1]["errors"]["email"]
        assert Member.query.count() == 0  # preview never writes
        db.drop_all()


def test_confirm_creates_a_new_member_and_membership():
    from app.members.models import Member
    from app.memberships.models import Membership

    app = _new_app()
    with app.app_context():
        _seed_membership_types()
        payload = {
            "filename": "members.xlsx",
            "rows": [
                {
                    "name": "Priya Das",
                    "email": "priya@example.com",
                    "phone": "+4712345678",
                    "address": "Oslo",
                    "family_info": None,
                    "membership_type": "individual",
                    "membership_status": "active",
                    "start_date": "2026-01-01",
                    "end_date": None,
                }
            ],
        }

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/imports/members/confirm", json=payload, headers=_admin_headers()
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["members_created"] == 1
        assert data["memberships_created"] == 1
        assert data["failed_rows"] == 0

        member = Member.query.filter_by(email="priya@example.com").one()
        assert Membership.query.filter_by(member_id=member.id).count() == 1
        db.drop_all()


def test_confirm_generates_billing_periods_for_an_active_membership():
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipPeriod

    app = _new_app()
    with app.app_context():
        _seed_membership_types()
        payload = {
            "filename": "members.xlsx",
            "rows": [
                {
                    "name": "Priya Das",
                    "email": "priya@example.com",
                    "phone": "+4712345678",
                    "address": "Oslo",
                    "family_info": None,
                    "membership_type": "individual",
                    "membership_status": "active",
                    "start_date": "2026-01-01",
                    "end_date": None,
                }
            ],
        }

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                "/api/admin/imports/members/confirm", json=payload, headers=_admin_headers()
            )

        member = Member.query.filter_by(email="priya@example.com").one()
        membership = Membership.query.filter_by(member_id=member.id).one()
        assert MembershipPeriod.query.filter_by(membership_id=membership.id).count() == 1
        db.drop_all()


def test_confirm_does_not_generate_periods_for_a_pending_membership():
    from app.members.models import Member
    from app.memberships.models import Membership, MembershipPeriod

    app = _new_app()
    with app.app_context():
        _seed_membership_types()
        payload = {
            "filename": "members.xlsx",
            "rows": [
                {
                    "name": "Priya Das",
                    "email": "priya@example.com",
                    "phone": "+4712345678",
                    "address": "Oslo",
                    "family_info": None,
                    "membership_type": "individual",
                    "membership_status": "pending",
                    "start_date": "2026-01-01",
                    "end_date": None,
                }
            ],
        }

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                "/api/admin/imports/members/confirm", json=payload, headers=_admin_headers()
            )

        member = Member.query.filter_by(email="priya@example.com").one()
        membership = Membership.query.filter_by(member_id=member.id).one()
        assert MembershipPeriod.query.filter_by(membership_id=membership.id).count() == 0
        db.drop_all()


def test_confirm_appends_a_new_membership_for_an_existing_member_without_touching_the_profile():
    from app.members.models import Member
    from app.memberships.models import Membership

    app = _new_app()
    with app.app_context():
        _seed_membership_types()
        member = Member(name="Priya Das", email="priya@example.com", address="Original Address")
        db.session.add(member)
        db.session.commit()

        payload = {
            "rows": [
                {
                    "name": "Priya D. Changed",
                    "email": "priya@example.com",
                    "address": "New Address",
                    "membership_type": "family",
                    "membership_status": "active",
                    "start_date": "2027-01-01",
                }
            ],
        }

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/imports/members/confirm", json=payload, headers=_admin_headers()
            )

        data = response.get_json()
        assert data["members_created"] == 0  # matched by email, not recreated
        assert data["memberships_created"] == 1

        db.session.refresh(member)
        assert member.name == "Priya Das"  # profile never overwritten by a re-import
        assert member.address == "Original Address"
        assert Membership.query.filter_by(member_id=member.id).count() == 1
        db.drop_all()


def test_confirm_skips_invalid_rows_and_counts_them_as_failed():
    app = _new_app()
    with app.app_context():
        payload = {"rows": [{"name": "Bad Row", "email": "not-an-email"}]}

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/imports/members/confirm", json=payload, headers=_admin_headers()
            )

        data = response.get_json()
        assert data["members_created"] == 0
        assert data["failed_rows"] == 1
        db.drop_all()


def test_confirm_creates_an_import_batch_log_entry():
    from app.imports.models import ImportBatch

    app = _new_app()
    with app.app_context():
        payload = {
            "filename": "members.xlsx",
            "rows": [
                {
                    "name": "Priya Das", "email": "priya@example.com",
                    "membership_type": "individual", "membership_status": "active",
                    "start_date": "2026-01-01",
                }
            ],
        }

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().post(
                "/api/admin/imports/members/confirm", json=payload, headers=_admin_headers()
            )

        batch = ImportBatch.query.one()
        assert batch.filename == "members.xlsx"
        assert batch.total_rows == 1
        db.drop_all()


def test_list_import_history():
    from app.imports.models import ImportBatch

    app = _new_app()
    with app.app_context():
        admin_user, _ = make_user_and_token(role="admin", email="admin@example.com")
        db.session.add(
            ImportBatch(admin_user_id=admin_user.id, filename="members.xlsx", total_rows=5,
                        members_created=3, memberships_created=5, failed_rows=0)
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/imports", headers=_admin_headers())

        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["filename"] == "members.xlsx"
        db.drop_all()
