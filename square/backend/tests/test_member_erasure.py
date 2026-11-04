"""Tests for member erasure (4 tests), e.g. request blocks sign in and cancel restores it with audit; job anonymises only after grace and keeps rows and amounts; retention anonymises old orders only."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.audit.models import AuditLog
from app.auth.models import User
from app.extensions import db
from app.members import erasure
from app.members.models import FamilyMember, Member
from app.newsletter.models import Subscriber
from app.orders.models import Order
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _post(app, path):
    _, token = make_user_and_token(role="admin", email="admin@example.com")
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().post(path, headers=auth_header(token))


def _person():
    user, token = make_user_and_token(email="priya@example.com")
    member = Member(user_id=user.id, name="Priya Das", email="priya@example.com", phone="1", address="Street 1")
    db.session.add(member)
    db.session.flush()
    db.session.add(FamilyMember(member_id=member.id, name="Raj", relationship_type="child", age=7))
    db.session.add(Subscriber(email="priya@example.com"))
    db.session.commit()
    return user, token, member


def _order(event_id=1, **kw):
    order = Order(order_number=kw.pop("n", "T-1"), event_id=event_id, customer_name="Priya Das",
                  customer_email="priya@example.com", customer_phone="1", total_amount=1000, **kw)
    db.session.add(order)
    db.session.commit()
    return order


def test_request_blocks_sign_in_and_cancel_restores_it_with_audit():
    app = _new_app()
    with app.app_context():
        user, token, member = _person()
        assert _post(app, f"/api/admin/members/{member.id}/erase-request").status_code == 200
        db.session.refresh(user)
        assert user.disabled_at is not None
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            r = app.test_client().get("/api/auth/me", headers=auth_header(token))
        assert r.status_code == 401
        assert _post(app, f"/api/admin/members/{member.id}/erase-cancel").status_code == 200
        db.session.refresh(user)
        assert user.disabled_at is None
        actions = {a.action for a in AuditLog.query.all()}
        assert {"member.erase_requested", "member.erase_cancelled"} <= actions
        assert all("Priya" not in a.description for a in AuditLog.query.all())
        db.drop_all()


def test_job_anonymises_only_after_grace_and_keeps_rows_and_amounts():
    app = _new_app()
    with app.app_context():
        user, _, member = _person()
        order = _order()
        erasure.request_erase(member)
        assert erasure.process_erase_requests() == 0  # still inside the grace period
        member.erase_requested_at = datetime.now(timezone.utc) - timedelta(days=31)
        db.session.commit()
        assert erasure.process_erase_requests() == 1
        db.session.refresh(member); db.session.refresh(order); db.session.refresh(user)
        assert member.name == "Erased person" and member.email is None and member.erased_at
        assert member.family_members[0].name == "Erased person"
        assert order.customer_name == "Erased person" and order.total_amount == 1000
        assert order.customer_email.endswith("@erased.invalid") and order.customer_phone is None
        assert user.email.endswith("@erased.invalid")
        assert Subscriber.query.one().email.endswith("@erased.invalid")
        assert Member.query.count() == 1 and Order.query.count() == 1 and User.query.filter_by(id=user.id).count() == 1
        db.drop_all()


def test_retention_anonymises_old_orders_only():
    app = _new_app()
    with app.app_context():
        old = _order(n="T-OLD")
        new = _order(n="T-NEW")
        old.created_at = datetime(datetime.now().year - 6, 6, 1, tzinfo=timezone.utc)
        db.session.commit()
        assert erasure.anonymise_old_orders() == 1
        db.session.refresh(old); db.session.refresh(new)
        assert old.customer_name == "Erased person" and new.customer_name == "Priya Das"
        assert erasure.anonymise_old_orders() == 0  # idempotent
        db.drop_all()


def test_erase_removes_the_account_at_the_squares_supabase_project_and_never_fails_the_job():
    from types import SimpleNamespace

    import requests
    from flask import g

    app = _new_app()
    with app.test_request_context():
        g.tenant = SimpleNamespace(auth_url="https://abc.supabase.co", storage_key="SERVICE-KEY")
        with patch("app.members.erasure.requests.delete") as delete:
            delete.return_value = SimpleNamespace(status_code=204)
            assert erasure.delete_provider_account("uid-1", "supabase") is True
            url = delete.call_args.args[0]
            assert url == "https://abc.supabase.co/auth/v1/admin/users/uid-1"
            assert delete.call_args.kwargs["headers"]["Authorization"] == "Bearer SERVICE-KEY"
            delete.return_value = SimpleNamespace(status_code=404)
            assert erasure.delete_provider_account("uid-1", "supabase") is True  # already gone
            delete.return_value = SimpleNamespace(status_code=500)
            assert erasure.delete_provider_account("uid-1", "supabase") is False
            delete.side_effect = requests.ConnectionError("down")
            assert erasure.delete_provider_account("uid-1", "supabase") is False
        with patch("app.members.erasure.requests.delete") as delete:
            assert erasure.delete_provider_account("uid-1", "neon") is False  # no Neon call yet
            with patch.dict("os.environ", {"ERASE_DELETE_PROVIDER_ACCOUNT": "false"}):
                assert erasure.delete_provider_account("uid-1", "supabase") is False
            delete.assert_not_called()
