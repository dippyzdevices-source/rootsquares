"""Tests for admin memberships routes (21 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin create membership requires a known member id."""
from datetime import date
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership, MembershipType
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _make_member(email="priya@example.com"):
    user, _ = make_user_and_token(email=email)
    member = Member(user_id=user.id, name="Priya Das")
    db.session.add(member)
    db.session.commit()
    return member


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().post("/api/admin/memberships", json={})
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/memberships", json={}, headers=auth_header(token)
            )
        assert response.status_code == 403
        db.drop_all()


def test_admin_create_membership_requires_a_known_member_id():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/memberships",
                json={"member_id": 999, "membership_type": "individual", "start_date": "2026-01-01"},
                headers=_admin_headers(),
            )
        assert response.status_code == 400
        assert "member_id" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_membership_validates_type_and_required_fields():
    app = _new_app()
    with app.app_context():
        member = _make_member()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/memberships",
                json={"member_id": member.id, "membership_type": "bogus", "start_date": "2026-01-01"},
                headers=_admin_headers(),
            )

        assert response.status_code == 400
        assert "membership_type" in response.get_json()["errors"]
        db.drop_all()


def test_admin_create_membership_succeeds_and_defaults_status_to_pending():
    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="individual", price=0))
        db.session.commit()
        member = _make_member()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/memberships",
                json={
                    "member_id": member.id,
                    "membership_type": "individual",
                    "start_date": "2026-01-01",
                },
                headers=_admin_headers(),
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "pending"
        assert data["membership_type"] == "individual"
        assert Membership.query.filter_by(member_id=member.id).count() == 1
        db.drop_all()


def test_admin_create_membership_rejects_end_date_before_start_date():
    app = _new_app()
    with app.app_context():
        member = _make_member()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/memberships",
                json={
                    "member_id": member.id,
                    "membership_type": "individual",
                    "start_date": "2026-06-01",
                    "end_date": "2026-01-01",
                },
                headers=_admin_headers(),
            )

        assert response.status_code == 400
        assert "end_date" in response.get_json()["errors"]
        db.drop_all()


def test_admin_update_membership_marks_it_active():
    app = _new_app()
    with app.app_context():
        member = _make_member()
        membership = Membership(
            member_id=member.id,
            membership_type="individual",
            status="pending",
            start_date=date(2026, 1, 1),
        )
        db.session.add(membership)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/memberships/{membership.id}",
                json={"status": "active"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        assert response.get_json()["status"] == "active"
        db.drop_all()


def test_admin_update_membership_returns_404_for_unknown_id():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                "/api/admin/memberships/999", json={"status": "active"}, headers=_admin_headers()
            )
        assert response.status_code == 404
        db.drop_all()


def test_admin_update_membership_rejects_an_invalid_status():
    app = _new_app()
    with app.app_context():
        member = _make_member()
        membership = Membership(
            member_id=member.id,
            membership_type="individual",
            status="pending",
            start_date=date(2026, 1, 1),
        )
        db.session.add(membership)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/memberships/{membership.id}",
                json={"status": "bogus"},
                headers=_admin_headers(),
            )

        assert response.status_code == 400
        assert "status" in response.get_json()["errors"]
        db.drop_all()


def test_admin_list_memberships_includes_member_name_and_email():
    app = _new_app()
    with app.app_context():
        member = _make_member(email="priya@example.com")
        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="pending",
                start_date=date(2026, 1, 1),
            )
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/memberships", headers=_admin_headers())

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["member_name"] == "Priya Das"
        assert data["items"][0]["member_email"] == "priya@example.com"
        db.drop_all()


def test_admin_list_memberships_falls_back_to_the_member_own_email_when_unlinked():
    # A member imported via Excel (no linked User yet) has no member.user — the serializer
    # must fall back to member.email rather than crash on member.user.email.
    app = _new_app()
    with app.app_context():
        member = Member(name="Rina Sarkar", email="rina@example.com")
        db.session.add(member)
        db.session.commit()
        db.session.add(
            Membership(
                member_id=member.id,
                membership_type="individual",
                status="pending",
                start_date=date(2026, 1, 1),
            )
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/memberships", headers=_admin_headers())

        assert response.status_code == 200
        data = response.get_json()
        assert data["items"][0]["member_name"] == "Rina Sarkar"
        assert data["items"][0]["member_email"] == "rina@example.com"
        db.drop_all()


def test_admin_list_memberships_filters_by_status():
    app = _new_app()
    with app.app_context():
        member = _make_member()
        db.session.add(
            Membership(member_id=member.id, membership_type="individual", status="pending",
                       start_date=date(2026, 1, 1))
        )
        db.session.add(
            Membership(member_id=member.id, membership_type="individual", status="active",
                       start_date=date(2025, 1, 1))
        )
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/memberships?status=pending", headers=_admin_headers()
            )

        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["status"] == "pending"
        db.drop_all()


def test_admin_list_memberships_rejects_an_invalid_status_filter():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/memberships?status=bogus", headers=_admin_headers()
            )
        assert response.status_code == 400
        db.drop_all()


def test_admin_list_memberships_orders_newest_first():
    app = _new_app()
    with app.app_context():
        member = _make_member()
        older = Membership(member_id=member.id, membership_type="individual", status="pending",
                            start_date=date(2025, 1, 1))
        db.session.add(older)
        db.session.commit()
        newer = Membership(member_id=member.id, membership_type="family", status="pending",
                            start_date=date(2026, 1, 1))
        db.session.add(newer)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/memberships", headers=_admin_headers())

        items = response.get_json()["items"]
        assert items[0]["id"] == newer.id
        assert items[1]["id"] == older.id
        db.drop_all()


def test_admin_update_membership_status_logs_an_audit_entry():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        member = _make_member()
        membership = Membership(
            member_id=member.id,
            membership_type="individual",
            status="pending",
            start_date=date(2026, 1, 1),
        )
        db.session.add(membership)
        db.session.commit()
        admin_user, token = make_user_and_token(role="admin", email="admin@example.com")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().patch(
                f"/api/admin/memberships/{membership.id}",
                json={"status": "active"},
                headers=auth_header(token),
            )

        entry = AuditLog.query.one()
        assert entry.actor_user_id == admin_user.id
        assert entry.action == "membership_status_changed"
        assert entry.target_type == "membership"
        assert entry.target_id == membership.id
        assert "active" in entry.description
        db.drop_all()


def test_admin_update_membership_without_a_status_change_does_not_log():
    from app.audit.models import AuditLog

    app = _new_app()
    with app.app_context():
        member = _make_member()
        membership = Membership(
            member_id=member.id,
            membership_type="individual",
            status="pending",
            start_date=date(2026, 1, 1),
        )
        db.session.add(membership)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().patch(
                f"/api/admin/memberships/{membership.id}",
                json={"end_date": "2026-12-31"},
                headers=_admin_headers(),
            )

        assert AuditLog.query.count() == 0
        db.drop_all()


def test_admin_update_membership_to_active_generates_periods():
    from app.memberships.models import MembershipPeriod, MembershipType

    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="individual", price=200, billing_frequency="monthly"))
        member = _make_member()
        membership = Membership(
            member_id=member.id, membership_type="individual", status="pending",
            start_date=date(2027, 1, 1),
        )
        db.session.add(membership)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().patch(
                f"/api/admin/memberships/{membership.id}", json={"status": "active"},
                headers=_admin_headers(),
            )

        assert MembershipPeriod.query.filter_by(membership_id=membership.id).count() == 12
        db.drop_all()


def test_admin_update_membership_to_a_non_active_status_generates_no_periods():
    from app.memberships.models import MembershipPeriod, MembershipType

    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="individual", price=200, billing_frequency="monthly"))
        member = _make_member()
        membership = Membership(
            member_id=member.id, membership_type="individual", status="pending",
            start_date=date(2027, 1, 1),
        )
        db.session.add(membership)
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            app.test_client().patch(
                f"/api/admin/memberships/{membership.id}", json={"status": "expired"},
                headers=_admin_headers(),
            )

        assert MembershipPeriod.query.filter_by(membership_id=membership.id).count() == 0
        db.drop_all()


def test_admin_create_membership_directly_active_generates_periods():
    from app.memberships.models import MembershipPeriod, MembershipType

    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="individual", price=200, billing_frequency="monthly"))
        member = _make_member()
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/memberships",
                json={
                    "member_id": member.id, "membership_type": "individual",
                    "start_date": "2027-01-01", "status": "active",
                },
                headers=_admin_headers(),
            )

        membership_id = response.get_json()["id"]
        assert MembershipPeriod.query.filter_by(membership_id=membership_id).count() == 12
        db.drop_all()


def test_admin_create_membership_as_pending_generates_no_periods():
    from app.memberships.models import MembershipPeriod, MembershipType

    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="individual", price=200, billing_frequency="monthly"))
        member = _make_member()
        db.session.commit()

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().post(
                "/api/admin/memberships",
                json={
                    "member_id": member.id, "membership_type": "individual",
                    "start_date": "2027-01-01",
                },
                headers=_admin_headers(),
            )

        membership_id = response.get_json()["id"]
        assert MembershipPeriod.query.filter_by(membership_id=membership_id).count() == 0
        db.drop_all()


def test_type_change_drops_stale_unpaid_periods_keeps_paid_and_records_history():
    from app.memberships.models import MembershipPeriod, MembershipTypeChange
    from app.memberships.service import generate_periods_for_membership

    app = _new_app()
    with app.app_context():
        db.session.add_all([
            MembershipType(name="Individual", price=150, billing_frequency="yearly"),
            MembershipType(name="Family", price=250, billing_frequency="monthly"),
        ])
        member = _make_member()
        membership = Membership(
            member_id=member.id, membership_type="Individual", status="active",
            start_date=date(2026, 1, 1),
        )
        db.session.add(membership)
        db.session.commit()
        generate_periods_for_membership(membership)
        assert MembershipPeriod.query.count() == 1  # the yearly "2026" period

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().patch(
                f"/api/admin/memberships/{membership.id}",
                json={"membership_type": "Family"},
                headers=_admin_headers(),
            )

        assert response.status_code == 200
        labels = [p.label for p in MembershipPeriod.query.order_by(MembershipPeriod.period_start)]
        assert labels[0] == "January 2026" and len(labels) == 12
        change = MembershipTypeChange.query.one()
        assert (change.from_type, change.to_type) == ("Individual", "Family")
        db.drop_all()
