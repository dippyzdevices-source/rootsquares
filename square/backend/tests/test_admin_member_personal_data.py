"""Tests for admin member personal data (2 tests), e.g. export collects profile family newsletter and audits without personal; export 404 for unknown member and 403 for non admin."""
from unittest.mock import patch

from app import create_app
from app.audit.models import AuditLog
from app.extensions import db
from app.members.models import FamilyMember, Member
from app.messages.models import Message, MessageRecipient, MessageSuppression
from app.newsletter.models import Subscriber
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _get(app, member_id, token_role="admin"):
    _, token = make_user_and_token(role=token_role, email=f"{token_role}@example.com")
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().get(
            f"/api/admin/members/{member_id}/personal-data", headers=auth_header(token)
        )


def test_export_collects_profile_family_newsletter_and_audits_without_personal_data():
    app = _new_app()
    with app.app_context():
        member = Member(name="Priya Das", email="priya@example.com", phone="123")
        db.session.add(member)
        db.session.flush()
        db.session.add(FamilyMember(member_id=member.id, name="Raj", relationship_type="child", age=7))
        db.session.add(Subscriber(email="priya@example.com"))
        message = Message(subject="Spring news", kind="update", status="sent")
        db.session.add(message)
        db.session.flush()
        db.session.add(MessageRecipient(message_id=message.id, email="Priya@Example.com", name="Priya", status="sent"))
        db.session.add(MessageSuppression(email="priya@example.com"))
        db.session.commit()

        response = _get(app, member.id)

        assert response.status_code == 200
        assert "attachment" in response.headers["Content-Disposition"]
        body = response.get_json()
        assert body["profile"]["name"] == "Priya Das"
        assert body["family_members"][0]["name"] == "Raj"
        assert body["newsletter"][0]["status"] == "subscribed"
        assert body["messages"]["do_not_contact"] is True and body["messages"]["received"][0]["subject"] == "Spring news"
        entry = AuditLog.query.filter_by(action="member.personal_data_export").one()
        assert "Priya" not in entry.description and entry.target_id == member.id
        db.drop_all()


def test_export_404_for_unknown_member_and_403_for_non_admin():
    app = _new_app()
    with app.app_context():
        assert _get(app, 999).status_code == 404
        assert _get(app, 1, token_role="member").status_code == 403
        db.drop_all()
