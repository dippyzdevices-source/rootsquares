"""Admin dropdown filters accept several comma-separated values (OR within a filter, AND across filters)."""

from datetime import date
from unittest.mock import patch

from app.extensions import db
from tests.auth_helpers import FakeJWKClient
from tests.test_admin_accounting_routes import _add_event, _add_order, _admin_headers, _new_app


def _get(app, path, headers):
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return app.test_client().get(path, headers=headers)


def test_orders_filter_takes_several_statuses_and_events():
    app = _new_app()
    with app.app_context():
        e1, e2 = _add_event(), _add_event(slug="second", title="Second")
        _add_order(e1, amount=100, payment_status="paid")
        _add_order(e1, amount=100, payment_status="pending")
        _add_order(e2, amount=100, payment_status="cancelled")
        h = _admin_headers()
        n = lambda q: len(_get(app, f"/api/admin/orders?{q}", h).get_json()["items"])
        assert n("") == 3
        assert n("payment_status=paid,pending") == 2
        assert n(f"event_id={e1.id},{e2.id}") == 3
        assert n(f"event_id={e2.id}&payment_status=paid,cancelled") == 1
        db.drop_all()


def test_tickets_filter_takes_several_statuses():
    from app.tickets.models import Ticket

    app = _new_app()
    with app.app_context():
        e1 = _add_event()
        for _ in range(3):
            _add_order(e1, amount=100, payment_status="paid")
        tickets = Ticket.query.order_by(Ticket.id).all()
        tickets[0].status, tickets[1].status = "used", "void"
        db.session.commit()
        h = _admin_headers()
        n = lambda q: len(_get(app, f"/api/admin/tickets?{q}", h).get_json()["items"])
        assert n("status=valid") == 1
        assert n("status=valid,used") == 2
        assert n("status=valid,used,void") == 3
        assert _get(app, "/api/admin/tickets?status=valid,bogus", h).status_code == 400
        db.drop_all()


def test_payments_filter_takes_several_providers_and_statuses():
    from app.payments.models import Payment

    app = _new_app()
    with app.app_context():
        e1 = _add_event()
        for provider, status in (("cash", "paid"), ("vipps_qr", "pending"), ("stripe", "paid")):
            order = _add_order(e1, amount=100, payment_status="paid")
            db.session.add(Payment(payment_type="event_ticket", order_id=order.id, provider=provider, amount=100, status=status))
        db.session.commit()
        h = _admin_headers()
        n = lambda q: len(_get(app, f"/api/admin/payments?{q}", h).get_json()["items"])
        assert n("provider=cash,stripe") == 2
        assert n("status=paid,pending") == 3
        assert n("provider=cash,vipps_qr&status=paid") == 1
        assert n("payment_type=event_ticket,membership") == 3
        assert _get(app, "/api/admin/payments?payment_type=event_ticket,nope", h).status_code == 400
        db.drop_all()


def test_members_filter_takes_several_statuses_and_types():
    from app.members.models import Member
    from app.memberships.models import Membership
    from tests.auth_helpers import make_user_and_token

    app = _new_app()
    with app.app_context():
        for i, (mtype, status) in enumerate((("adult", "active"), ("child", "expired"), ("adult", "cancelled"))):
            user, _ = make_user_and_token(email=f"m{i}@example.com")
            member = Member(user_id=user.id, name=f"M{i}")
            db.session.add(member)
            db.session.commit()
            db.session.add(Membership(member_id=member.id, membership_type=mtype, status=status, start_date=date(2026, 1, 1)))
        db.session.commit()
        h = _admin_headers()
        n = lambda q: len(_get(app, f"/api/admin/members?{q}", h).get_json()["items"])
        assert n("status=active,expired") == 2
        assert n("membership_type=adult,child") == 3
        assert n("membership_type=adult&status=active,expired") == 1
        db.drop_all()


def test_newsletter_filter_takes_several_statuses():
    from app.newsletter.models import Subscriber

    app = _new_app()
    with app.app_context():
        db.session.add_all([Subscriber(email="a@x.no", status="subscribed"), Subscriber(email="b@x.no", status="unsubscribed")])
        db.session.commit()
        h = _admin_headers()
        n = lambda q: len(_get(app, f"/api/admin/newsletter/subscribers?{q}", h).get_json()["items"])
        assert n("status=subscribed") == 1
        assert n("status=subscribed,unsubscribed") == 2
        assert _get(app, "/api/admin/newsletter/subscribers?status=subscribed,bogus", h).status_code == 400
        db.drop_all()


def test_audit_log_filter_takes_several_actions():
    from app.audit.models import AuditLog

    from tests.auth_helpers import auth_header, make_user_and_token

    app = _new_app()
    with app.app_context():
        admin, token = make_user_and_token(role="admin")
        db.session.add_all([
            AuditLog(actor_user_id=admin.id, action="order_marked_paid", description="a"),
            AuditLog(actor_user_id=admin.id, action="settings_updated", description="b"),
            AuditLog(actor_user_id=admin.id, action="event_created", description="c"),
        ])
        db.session.commit()
        h = auth_header(token)
        n = lambda q: len(_get(app, f"/api/admin/audit-log?{q}", h).get_json()["items"])
        assert n("action=order_marked_paid") == 1
        assert n("action=order_marked_paid,settings_updated") == 2
        assert _get(app, "/api/admin/audit-log?action=order_marked_paid,bogus", h).status_code == 400
        db.drop_all()
