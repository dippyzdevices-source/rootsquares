"""Admin follow-up on unpaid memberships (awaiting-payment requests + active members with dues),
reminder emails with a 3-day cooldown, removing a stale request, and a member cancelling their own
request before paying."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.audit.models import AuditLog
from app.extensions import db
from app.members.models import Member
from app.memberships.models import Membership, MembershipPeriod, MembershipType
from app.memberships.service import current_period_for_date, generate_periods_for_membership
from app.payments.models import Payment, PaymentAllocation
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token

BASE = "/api/admin/membership-follow-up"


def _app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                MembershipType(name="adult", price=300, billing_frequency="monthly"),
                MembershipType(name="family", price=500, billing_frequency="yearly"),
            ]
        )
        db.session.commit()
    return app


def _jwks():
    return patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient())


def _admin():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _member(email="priya@example.com", name="Priya Das", with_user=True):
    if with_user:
        user, token = make_user_and_token(email=email)
        member = Member(user_id=user.id, name=name)
        headers = auth_header(token)
    else:
        member = Member(name=name, email=email)
        headers = None
    db.session.add(member)
    db.session.commit()
    return member, headers


def _request(client, headers, membership_type="adult"):
    assert client.post("/api/memberships/me", json={"membership_type": membership_type}, headers=headers).status_code == 201


def _active(member, start, membership_type="adult"):
    membership = Membership(member_id=member.id, membership_type=membership_type, status="active", start_date=start)
    db.session.add(membership)
    db.session.commit()
    generate_periods_for_membership(membership)
    return membership


def _sent(app):
    return app.extensions["email_service"].sent_emails


def test_follow_up_lists_unpaid_requests_and_active_members_with_dues():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        asker, h = _member("asker@example.com", "Asker One")
        _request(client, h)
        payer, _ = _member("late@example.com", "Late Payer", with_user=False)
        today = date.today()
        _active(payer, date(today.year, 1, 1))

        data = client.get(BASE, headers=_admin()).get_json()
        assert [r["name"] for r in data["requests"]] == ["Asker One"]
        request_row = data["requests"][0]
        assert request_row["amount"] == 30000 and request_row["membership_type"] == "adult"
        assert request_row["can_remind"] is True and request_row["last_reminded_at"] is None
        assert request_row["days_waiting"] == 0

        assert [d["name"] for d in data["dues"]] == ["Late Payer"]
        due = data["dues"][0]
        assert due["due_count"] == today.month and due["due_total"] == today.month * 30000
        assert due["email"] == "late@example.com"
        db.drop_all()


def test_periods_before_the_membership_started_or_already_reported_are_not_dues():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        today = date.today()
        joined, _ = _member("joined@example.com", "Joined Recently", with_user=False)
        membership = _active(joined, today.replace(day=1))  # months before this one are not "overdue"
        data = client.get(BASE, headers=_admin()).get_json()
        assert data["dues"][0]["due_count"] == 1

        # A reported (pending) manual payment takes it off the list: nothing left to chase.
        period = current_period_for_date(membership, today)
        payment = Payment(payment_type="membership", provider="vipps", amount=30000, status="pending")
        db.session.add(payment)
        db.session.commit()
        db.session.add(PaymentAllocation(payment_id=payment.id, membership_period_id=period.id, amount=30000))
        db.session.commit()
        assert client.get(BASE, headers=_admin()).get_json()["dues"] == []
        db.drop_all()


def test_reminder_for_an_unpaid_request_emails_the_member_and_is_audited():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        member, h = _member()
        _request(client, h)
        membership = Membership.query.filter_by(member_id=member.id).one()

        r = client.post(f"{BASE}/{membership.id}/reminder", headers=_admin())
        assert r.status_code == 200 and r.get_json()["status"] == "sent"

        mail = _sent(app)[-1]
        assert mail["to"] == "priya@example.com" and "waiting for payment" in mail["subject"]
        assert "300 kr" in mail["html"] and "/member" in mail["html"] and "Priya Das" in mail["html"]
        assert "300 kr" in mail["text"]
        assert AuditLog.query.filter_by(action="membership_reminder_sent", target_id=membership.id).count() == 1

        listed = client.get(BASE, headers=_admin()).get_json()["requests"][0]
        assert listed["can_remind"] is False and listed["last_reminded_at"]
        db.drop_all()


def test_a_second_reminder_within_three_days_is_refused_then_allowed_after():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        member, h = _member()
        _request(client, h)
        membership = Membership.query.filter_by(member_id=member.id).one()

        assert client.post(f"{BASE}/{membership.id}/reminder", headers=_admin()).status_code == 200
        again = client.post(f"{BASE}/{membership.id}/reminder", headers=_admin())
        assert again.status_code == 409 and "3 days" in again.get_json()["error"]
        assert len(_sent(app)) == 1

        AuditLog.query.filter_by(action="membership_reminder_sent").update(
            {"created_at": datetime.now(timezone.utc) - timedelta(days=4)}
        )
        db.session.commit()
        assert client.post(f"{BASE}/{membership.id}/reminder", headers=_admin()).status_code == 200
        assert len(_sent(app)) == 2
        db.drop_all()


def test_reminder_for_dues_lists_the_unpaid_periods_and_a_total():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        member, _ = _member("late@example.com", "Late Payer", with_user=False)
        today = date.today()
        membership = _active(member, date(today.year, 1, 1))

        assert client.post(f"{BASE}/{membership.id}/reminder", headers=_admin()).status_code == 200
        mail = _sent(app)[-1]
        assert "payment is due" in mail["subject"]
        assert f"{today.month * 300:,}".replace(",", " ") + " kr" in mail["html"]  # e.g. "3 000 kr"
        assert "January" in mail["html"]
        db.drop_all()


def test_reminder_needs_something_unpaid_and_an_email_address():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        today = date.today()
        paid_up, _ = _member("ok@example.com", "Paid Up", with_user=False)
        membership = _active(paid_up, date(today.year, 1, 1))
        MembershipPeriod.query.filter_by(membership_id=membership.id).update({"status": "paid"})
        db.session.commit()
        assert client.post(f"{BASE}/{membership.id}/reminder", headers=_admin()).status_code == 409

        nobody, _ = _member(email=None, name="No Email", with_user=False)
        owing = _active(nobody, date(today.year, 1, 1))
        no_email = client.post(f"{BASE}/{owing.id}/reminder", headers=_admin())
        assert no_email.status_code == 400 and "email" in no_email.get_json()["error"]
        assert client.post(f"{BASE}/9999/reminder", headers=_admin()).status_code == 404
        assert _sent(app) == []
        db.drop_all()


def test_admin_can_remove_a_stale_unpaid_request_but_not_one_with_a_payment():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        stale, h1 = _member("stale@example.com", "Stale One")
        _request(client, h1)
        paying, h2 = _member("paying@example.com", "Paying One")
        _request(client, h2)
        stale_m = Membership.query.filter_by(member_id=stale.id).one()
        paying_m = Membership.query.filter_by(member_id=paying.id).one()
        period = current_period_for_date(paying_m, date.today())
        client.post(
            "/api/memberships/me/payments",
            json={"membership_period_ids": [period.id], "provider": "vipps"},
            headers=h2,
        )

        assert client.delete(f"{BASE}/{stale_m.id}", headers=_admin()).status_code == 204
        assert db.session.get(Membership, stale_m.id) is None
        assert MembershipPeriod.query.filter_by(membership_id=stale_m.id).count() == 0
        assert AuditLog.query.filter_by(action="membership_request_removed").count() == 1

        # A reported payment makes it a normal request an admin handles, not "stale".
        assert client.delete(f"{BASE}/{paying_m.id}", headers=_admin()).status_code == 409
        assert db.session.get(Membership, paying_m.id) is not None
        db.drop_all()


def test_follow_up_routes_need_an_admin():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        assert client.get(BASE).status_code == 401
        _, token = make_user_and_token(role="member")
        assert client.get(BASE, headers=auth_header(token)).status_code == 403
        assert client.post(f"{BASE}/1/reminder", headers=auth_header(token)).status_code == 403
        assert client.delete(f"{BASE}/1", headers=auth_header(token)).status_code == 403
        db.drop_all()


def test_member_can_cancel_their_own_unpaid_request_but_not_after_reporting_a_payment():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        member, h = _member()
        assert client.delete("/api/memberships/me/request", headers=h).status_code == 404  # nothing to cancel

        _request(client, h)
        assert client.delete("/api/memberships/me/request", headers=h).status_code == 204
        assert Membership.query.filter_by(member_id=member.id).count() == 0
        assert MembershipPeriod.query.count() == 0
        _request(client, h)  # and they can start over

        membership = Membership.query.filter_by(member_id=member.id).one()
        period = current_period_for_date(membership, date.today())
        client.post(
            "/api/memberships/me/payments", json={"membership_period_ids": [period.id], "provider": "vipps"}, headers=h
        )
        locked = client.delete("/api/memberships/me/request", headers=h)
        assert locked.status_code == 409 and "contact us" in locked.get_json()["error"]
        assert db.session.get(Membership, membership.id) is not None
        db.drop_all()


def test_member_cannot_cancel_an_active_membership_through_this_route():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        _active(member, date(date.today().year, 1, 1))
        assert app.test_client().delete("/api/memberships/me/request", headers=h).status_code == 404
        assert Membership.query.filter_by(member_id=member.id, status="active").count() == 1
        db.drop_all()


def test_reminder_for_a_childs_request_goes_to_the_parent_and_names_the_child():
    app = _app()
    with app.app_context(), _jwks():
        client = app.test_client()
        parent, _ = _member(email="anil@example.com", name="Anil Das", with_user=False)
        db.session.add(MembershipType(name="child", price=100, billing_frequency="yearly"))
        child = Member(name="Mini Das", parent_member_id=parent.id)
        db.session.add(child)
        db.session.commit()
        membership = Membership(member_id=child.id, membership_type="child", status="pending", start_date=date.today())
        db.session.add(membership)
        db.session.commit()
        generate_periods_for_membership(membership)

        listed = client.get(BASE, headers=_admin()).get_json()["requests"][0]
        assert listed["name"] == "Mini Das" and listed["email"] == "anil@example.com"

        r = client.post(f"{BASE}/{membership.id}/reminder", headers=_admin())
        assert r.status_code == 200
        mail = _sent(app)[-1]
        assert mail["to"] == "anil@example.com"
        assert "Hi Anil Das" in mail["html"] and "Mini Das" in mail["html"]
        db.drop_all()
