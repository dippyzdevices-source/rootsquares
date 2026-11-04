"""Tests for membership active email (3 tests), e.g. approving a membership emails the member once; other status changes send nothing and a failed send never blocks the a; a childs active email goes to the parent and names the child."""
from datetime import date
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

SEND = "app.memberships.emails.get_email_service"


def _app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin_patch(app, membership_id, payload):
    _, token = make_user_and_token(role="admin")
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().patch(f"/api/admin/memberships/{membership_id}", json=payload, headers=auth_header(token))


def _pending(email="priya@example.com"):
    user, _ = make_user_and_token(email=email)
    member = Member(user_id=user.id, name="Priya Das")
    db.session.add(member)
    db.session.commit()
    membership = Membership(member_id=member.id, membership_type="individual", status="pending", start_date=date(2026, 10, 1))
    db.session.add(membership)
    db.session.commit()
    return membership


def test_approving_a_membership_emails_the_member_once():
    app = _app()
    with app.app_context():
        membership = _pending()
        with patch(SEND) as svc:
            assert _admin_patch(app, membership.id, {"status": "active"}).status_code == 200
            assert _admin_patch(app, membership.id, {"status": "active"}).status_code == 200  # re-save: no second mail
        assert svc.return_value.send_email.call_count == 1
        sent = svc.return_value.send_email.call_args.kwargs
        assert sent["to"] == "priya@example.com"
        assert sent["subject"] == "Your BCA Oslo membership is active"
        assert "Individual" in sent["text"] and "1 Oct 2026" in sent["text"]
        db.drop_all()


def test_other_status_changes_send_nothing_and_a_failed_send_never_blocks_the_approval():
    app = _app()
    with app.app_context():
        membership = _pending()
        with patch(SEND) as svc:
            _admin_patch(app, membership.id, {"status": "cancelled"})
        svc.return_value.send_email.assert_not_called()
        with patch(SEND) as svc:
            svc.return_value.send_email.side_effect = RuntimeError("mail down")
            response = _admin_patch(app, membership.id, {"status": "active"})
        assert response.status_code == 200 and response.get_json()["status"] == "active"
        db.drop_all()


def test_a_childs_active_email_goes_to_the_parent_and_names_the_child():
    from app.memberships.emails import send_membership_active_email

    app = _app()
    with app.app_context():
        parent_user, _ = make_user_and_token(email="parent@example.com")
        parent = Member(user_id=parent_user.id, name="Anita Das")
        db.session.add(parent)
        db.session.commit()
        child = Member(name="Riya Das", parent_member_id=parent.id)
        db.session.add(child)
        db.session.commit()
        membership = Membership(member_id=child.id, membership_type="child", status="active", start_date=date(2026, 10, 1))
        db.session.add(membership)
        db.session.commit()
        with patch(SEND) as svc:
            assert send_membership_active_email(membership) is True
        sent = svc.return_value.send_email.call_args.kwargs
        assert sent["to"] == "parent@example.com"
        assert "Hi Anita Das" in sent["text"] and "Riya Das's membership" in sent["text"]
        db.drop_all()
