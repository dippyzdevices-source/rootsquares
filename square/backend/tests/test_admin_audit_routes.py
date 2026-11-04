"""Tests for admin audit routes (11 tests), e.g. admin routes reject requests with no token; admin routes reject a non admin role; admin routes allow a cors preflight with no auth header."""
from unittest.mock import patch

from app import create_app
from app.audit.models import AuditLog
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_headers():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _add_entry(actor, action="settings_updated", description="Updated site contact settings",
               target_type=None, target_id=None):
    entry = AuditLog(actor_user_id=actor.id, action=action, description=description,
                     target_type=target_type, target_id=target_id)
    db.session.add(entry)
    db.session.commit()
    return entry


def test_admin_routes_reject_requests_with_no_token():
    app = _new_app()
    with app.app_context():
        response = app.test_client().get("/api/admin/audit-log")
        assert response.status_code == 401
        db.drop_all()


def test_admin_routes_reject_a_non_admin_role():
    app = _new_app()
    with app.app_context():
        _, token = make_user_and_token(role="member")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/audit-log", headers=auth_header(token))
        assert response.status_code == 403
        db.drop_all()


def test_admin_routes_allow_a_cors_preflight_with_no_auth_header():
    app = _new_app()
    with app.app_context():
        response = app.test_client().options(
            "/api/admin/audit-log", headers={"Origin": "http://localhost:5173"}
        )
        assert response.status_code == 200
        db.drop_all()


def test_list_audit_log_returns_entries_newest_first_with_actor_email():
    app = _new_app()
    with app.app_context():
        admin_user, _ = make_user_and_token(role="admin", email="admin@example.com")
        _add_entry(admin_user, action="settings_updated", description="Updated site contact settings")
        _add_entry(admin_user, action="event_deleted", description='Deleted event "Durga Puja 2026"',
                   target_type="event", target_id=1)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get("/api/admin/audit-log", headers=_admin_headers())

        assert response.status_code == 200
        items = response.get_json()["items"]
        assert len(items) == 2
        assert items[0]["action"] == "event_deleted"  # newest first
        assert items[0]["actor_email"] == "admin@example.com"
        assert items[0]["target_type"] == "event"
        assert items[0]["target_id"] == 1
        db.drop_all()


def test_list_audit_log_filters_by_action():
    app = _new_app()
    with app.app_context():
        admin_user, _ = make_user_and_token(role="admin", email="admin@example.com")
        _add_entry(admin_user, action="settings_updated")
        _add_entry(admin_user, action="event_deleted", target_type="event", target_id=1)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/audit-log?action=event_deleted", headers=_admin_headers()
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["action"] == "event_deleted"
        db.drop_all()


def test_list_audit_log_rejects_an_invalid_action_filter():
    app = _new_app()
    with app.app_context():
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/audit-log?action=bogus", headers=_admin_headers()
            )
        assert response.status_code == 400
        db.drop_all()


def test_list_audit_log_searches_description():
    app = _new_app()
    with app.app_context():
        admin_user, _ = make_user_and_token(role="admin", email="admin@example.com")
        _add_entry(admin_user, description="Marked order BCA-2026-000001 as paid")
        _add_entry(admin_user, description="Updated site contact settings")

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            response = app.test_client().get(
                "/api/admin/audit-log?q=BCA-2026-000001", headers=_admin_headers()
            )

        items = response.get_json()["items"]
        assert len(items) == 1
        assert "BCA-2026-000001" in items[0]["description"]
        db.drop_all()


def test_valid_actions_includes_payment_refunded():
    from app.audit.admin_routes import VALID_ACTIONS

    assert "payment_refunded" in VALID_ACTIONS


def test_valid_actions_includes_order_rejected():
    from app.audit.admin_routes import VALID_ACTIONS

    assert "order_rejected" in VALID_ACTIONS


def test_export_audit_log_returns_an_xlsx_of_the_filtered_entries():
    from io import BytesIO

    from openpyxl import load_workbook

    app = _new_app()
    with app.app_context():
        admin_user, _ = make_user_and_token(role="admin", email="admin@example.com")
        _add_entry(admin_user, action="settings_updated", description="Updated site contact settings")
        _add_entry(admin_user, action="event_deleted", description='Deleted event "Durga Puja 2026"',
                   target_type="event", target_id=1)

        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            everything = app.test_client().get("/api/admin/audit-log/export", headers=_admin_headers())
            filtered = app.test_client().get(
                "/api/admin/audit-log/export?action=event_deleted", headers=_admin_headers()
            )

        assert everything.status_code == 200
        assert "spreadsheetml" in everything.content_type
        assert "audit-log.xlsx" in everything.headers["Content-Disposition"]
        rows = list(load_workbook(BytesIO(everything.data)).active.iter_rows(values_only=True))
        assert rows[0] == ("When", "Who", "Email", "Action", "Target", "Description")
        assert len(rows) == 3  # header + both entries, newest first
        assert rows[1][3] == "event_deleted"
        assert rows[1][4] == "event #1"
        assert rows[1][2] == "admin@example.com"

        filtered_rows = list(load_workbook(BytesIO(filtered.data)).active.iter_rows(values_only=True))
        assert len(filtered_rows) == 2  # header + the one event_deleted entry
        db.drop_all()


def test_export_audit_log_rejects_an_invalid_action_filter_and_non_admins():
    app = _new_app()
    with app.app_context():
        assert app.test_client().get("/api/admin/audit-log/export").status_code == 401
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            bad = app.test_client().get("/api/admin/audit-log/export?action=nope", headers=_admin_headers())
            _, member_token = make_user_and_token(role="member", email="m@example.com")
            denied = app.test_client().get("/api/admin/audit-log/export", headers=auth_header(member_token))
        assert bad.status_code == 400
        assert denied.status_code == 403
        db.drop_all()
