"""Self-service membership requests are pay-first: the request creates a pending membership with
its periods, the member pays the CURRENT period, and the membership activates by itself once that
payment is confirmed. Unpaid requests stay out of the admin's approval lists."""

from datetime import date
from unittest.mock import patch

from app import create_app
from app.extensions import db
from tests.vipps_helpers import connect_vipps
from app.members.models import Member
from app.memberships.models import Membership, MembershipPeriod, MembershipType
from app.memberships.service import current_period_for_date
from app.payments import vipps
from app.payments.models import Payment, PaymentAllocation
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                MembershipType(name="adult", price=300, billing_frequency="monthly"),
                MembershipType(name="family", price=500, billing_frequency="yearly"),
                MembershipType(name="lifetime", price=5000, billing_frequency="yearly", contact_for_price=True),
            ]
        )
        db.session.commit()
    return app


def _member():
    user, token = make_user_and_token(email="priya@example.com")
    member = Member(user_id=user.id, name="Priya Das")
    db.session.add(member)
    db.session.commit()
    return member, auth_header(token)


def _admin():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _jwks():
    return patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient())


def _request(client, headers, membership_type="adult"):
    return client.post("/api/memberships/me", json={"membership_type": membership_type}, headers=headers)


def _pay(client, headers, period_ids, provider="vipps"):
    return client.post(
        "/api/memberships/me/payments",
        json={"membership_period_ids": period_ids, "provider": provider},
        headers=headers,
    )


def test_request_creates_a_pending_membership_with_periods_and_offers_only_the_current_one():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        client = app.test_client()
        assert _request(client, h).status_code == 201

        membership = Membership.query.filter_by(member_id=member.id).one()
        assert membership.status == "pending"
        assert MembershipPeriod.query.filter_by(membership_id=membership.id).count() == 12

        data = client.get("/api/memberships/me/periods", headers=h).get_json()
        assert data["membership"]["status"] == "pending"
        current = current_period_for_date(membership, date.today())
        assert [p["id"] for p in data["items"]] == [current.id]
        assert data["items"][0]["amount"] == 30000
        db.drop_all()


def test_while_pending_only_the_current_period_can_be_paid():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        client = app.test_client()
        _request(client, h)
        membership = Membership.query.filter_by(member_id=member.id).one()
        current = current_period_for_date(membership, date.today())
        other = MembershipPeriod.query.filter(
            MembershipPeriod.membership_id == membership.id, MembershipPeriod.id != current.id
        ).first()

        refused = _pay(client, h, [other.id])
        assert refused.status_code == 400 and "current period" in refused.get_json()["error"]
        assert _pay(client, h, [current.id]).status_code == 200
        db.drop_all()


def test_unpaid_requests_are_hidden_from_admin_review_until_a_payment_is_reported():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        client = app.test_client()
        _request(client, h)
        # An older-style pending request (no periods) still needs an admin.
        legacy_user, _ = make_user_and_token(email="old@example.com")
        legacy = Member(user_id=legacy_user.id, name="Old Request")
        db.session.add(legacy)
        db.session.commit()
        db.session.add(Membership(member_id=legacy.id, membership_type="adult", status="pending", start_date=date.today()))
        db.session.commit()

        def pending_names():
            members = client.get("/api/admin/members?status=pending", headers=_admin()).get_json()["items"]
            memberships = client.get("/api/admin/memberships?status=pending", headers=_admin()).get_json()
            return {m["name"] for m in members}, memberships["total"]

        names, total = pending_names()
        assert names == {"Old Request"} and total == 1

        row = next(m for m in client.get("/api/admin/members", headers=_admin()).get_json()["items"] if m["name"] == "Priya Das")
        assert row["latest_membership"]["awaiting_payment"] is True

        membership = Membership.query.filter_by(member_id=member.id).one()
        current = current_period_for_date(membership, date.today())
        _pay(client, h, [current.id])  # manual Vipps: reported, waiting for an admin

        names, total = pending_names()
        assert names == {"Old Request", "Priya Das"} and total == 2
        db.drop_all()


def test_admin_confirming_the_payment_activates_the_membership():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        # An older active membership expires when the new one activates.
        db.session.add(Membership(member_id=member.id, membership_type="family", status="expired", start_date=date(2024, 1, 1)))
        db.session.commit()
        client = app.test_client()
        _request(client, h)
        membership = Membership.query.filter_by(member_id=member.id, status="pending").one()
        current = current_period_for_date(membership, date.today())
        payment_id = _pay(client, h, [current.id]).get_json()["payment"]["id"]
        assert db.session.get(Membership, membership.id).status == "pending"  # reporting is not enough

        assert client.post(f"/api/admin/payments/{payment_id}/confirm", headers=_admin()).status_code == 200
        db.session.expire_all()
        assert db.session.get(Membership, membership.id).status == "active"
        assert db.session.get(MembershipPeriod, current.id).status == "paid"
        data = client.get("/api/memberships/me/periods", headers=h).get_json()
        assert data["membership"]["status"] == "active" and len(data["items"]) == 12  # whole year is visible now
        db.drop_all()


def test_rejecting_the_payment_leaves_the_request_pending_and_payable_again():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        client = app.test_client()
        _request(client, h)
        membership = Membership.query.filter_by(member_id=member.id).one()
        current = current_period_for_date(membership, date.today())
        payment_id = _pay(client, h, [current.id]).get_json()["payment"]["id"]
        client.post(f"/api/admin/payments/{payment_id}/reject", headers=_admin())

        assert db.session.get(Membership, membership.id).status == "pending"
        assert _pay(client, h, [current.id]).status_code == 200
        db.drop_all()


def test_vipps_app_payment_activates_the_membership_when_vipps_confirms():
    app = _app()
    with app.app_context(), _jwks():
        from app.settings.models import get_site_settings

        get_site_settings().vipps_app_public = True
        connect_vipps("whsec")
        db.session.commit()
        member, h = _member()
        client = app.test_client()
        _request(client, h)
        membership = Membership.query.filter_by(member_id=member.id).one()
        current = current_period_for_date(membership, date.today())

        with (
            patch.object(vipps.VippsClient, "create_payment", return_value={"redirectUrl": "https://vipps.test/pay"}),
            patch.object(vipps.VippsClient, "get_payment", return_value={"state": "AUTHORIZED"}),
            patch.object(vipps.VippsClient, "capture", return_value={}),
            patch.object(vipps.VippsClient, "cancel", return_value={}),
        ):
            payment_id = _pay(client, h, [current.id], provider="vipps_app").get_json()["payment"]["id"]
            assert db.session.get(Membership, membership.id).status == "pending"
            refreshed = client.post(f"/api/memberships/me/payments/{payment_id}/refresh", headers=h)

        assert refreshed.get_json()["payment"]["status"] == "paid"
        db.session.expire_all()
        assert db.session.get(Membership, membership.id).status == "active"
        db.drop_all()


def test_a_request_can_be_swapped_until_a_payment_is_started():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        client = app.test_client()
        _request(client, h, "adult")
        swapped = _request(client, h, "family")
        assert swapped.status_code == 201
        memberships = Membership.query.filter_by(member_id=member.id).all()
        assert [m.membership_type for m in memberships] == ["family"]
        assert MembershipPeriod.query.count() == 1  # the yearly one; the monthly set is gone

        family = memberships[0]
        current = current_period_for_date(family, date.today())
        _pay(client, h, [current.id])
        locked = _request(client, h, "adult")
        assert locked.status_code == 409
        assert Membership.query.filter_by(member_id=member.id).one().membership_type == "family"
        db.drop_all()


def test_a_cancelled_payment_attempt_does_not_lock_the_request():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        client = app.test_client()
        _request(client, h, "adult")
        membership = Membership.query.filter_by(member_id=member.id).one()
        current = current_period_for_date(membership, date.today())
        payment_id = _pay(client, h, [current.id]).get_json()["payment"]["id"]
        client.post(f"/api/admin/payments/{payment_id}/reject", headers=_admin())

        assert _request(client, h, "family").status_code == 201
        assert PaymentAllocation.query.count() == 0
        assert db.session.get(Payment, payment_id).status == "cancelled"  # kept as history
        db.drop_all()


def test_a_type_with_no_price_has_no_periods_and_stays_visible_for_admin_approval():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        client = app.test_client()
        assert _request(client, h, "lifetime").status_code == 201
        membership = Membership.query.filter_by(member_id=member.id).one()
        assert MembershipPeriod.query.filter_by(membership_id=membership.id).count() == 0
        assert client.get("/api/memberships/me/periods", headers=h).get_json()["membership"] is None
        listed = client.get("/api/admin/members?status=pending", headers=_admin()).get_json()["items"]
        assert [m["name"] for m in listed] == ["Priya Das"]
        db.drop_all()


def test_an_active_membership_still_blocks_a_new_request():
    app = _app()
    with app.app_context(), _jwks():
        member, h = _member()
        db.session.add(Membership(member_id=member.id, membership_type="adult", status="active", start_date=date(2026, 1, 1)))
        db.session.commit()
        assert _request(app.test_client(), h).status_code == 409
        db.drop_all()
