"""Tests for messages (15 tests), e.g. the square can write its own footer sentence and the unsubscribe link; audiences resolve dedupe and follow the modules; update message honours opt outs and unsubscribe link works."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.audit.models import AuditLog
from app.extensions import db
from app.members import erasure
from app.members.models import Member
from app.messages import audiences, rules, service
from app.messages.models import Message, MessageRecipient, MessageRule, MessageRuleRun, MessageSuppression
from app.newsletter.models import Subscriber
from app.orders.models import Order
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token
from tests.test_orders_checkout import _add_event


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin(app, method, path, **kw):
    _, token = make_user_and_token(role="admin", email="admin@example.com")
    with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
        return getattr(app.test_client(), method)(path, headers=auth_header(token), **kw)


def _member(name, email):
    member = Member(name=name, email=email)
    db.session.add(member)
    db.session.commit()
    return member


def _paid_order(event_id, name, email, n):
    order = Order(order_number=n, event_id=event_id, customer_name=name, customer_email=email, total_amount=100, payment_status="paid")
    db.session.add(order)
    db.session.commit()
    return order


class FakeChannel:
    def __init__(self):
        self.sent = []

    def send(self, *, to, subject, html, text, headers, attachments):
        self.sent.append({"to": to, "subject": subject, "html": html, "text": text, "headers": headers})


def _with_channel():
    fake = FakeChannel()
    return fake, patch.dict("app.messages.channels.CHANNELS", {"email": fake})


def test_the_square_can_write_its_own_footer_sentence_and_the_unsubscribe_link_stays():
    app = _new_app()
    with app.app_context():
        _member("Asha", "asha@example.com")
        saved = _admin(app, "patch", "/api/admin/settings", json={"message_footer_update": "Sent by the committee <b>of Hall</b>.", "message_footer_service": "A notice about your booking."})
        assert saved.status_code == 200 and saved.get_json()["message_footer_update"].startswith("Sent by")
        assert _admin(app, "patch", "/api/admin/settings", json={"message_footer_update": "x" * 401}).status_code == 400
        for kind, expect in (("update", "Sent by the committee &lt;b&gt;of Hall&lt;/b&gt;."), ("service", "A notice about your booking.")):
            created = _admin(app, "post", "/api/admin/messages", json={"kind": kind, "subject": "S", "body_html": "<p>Hi</p>", "audience": {"type": "members", "params": {}}})
            fake, ctx = _with_channel()
            with ctx:
                _admin(app, "post", f"/api/admin/messages/{created.get_json()['id']}/send")
            html_body = fake.sent[0]["html"]
            assert expect in html_body and "contact list" not in html_body and "service message from" not in html_body
            assert ("Unsubscribe" in html_body) == (kind == "update")
        db.drop_all()


def test_audiences_resolve_dedupe_and_follow_the_modules():
    app = _new_app()
    with app.app_context():
        _member("Asha", "Asha@Example.com")
        _member("Asha again", "asha@example.com")
        _member("No address", "")
        event = _add_event()
        _paid_order(event.id, "Buyer", "buyer@example.com", "T-1")
        db.session.add(Subscriber(email="sub@example.com"))
        db.session.commit()
        assert [r.email for r in audiences.resolve({"type": "members", "params": {}})] == ["asha@example.com"]
        assert [r.email for r in audiences.resolve({"type": "ticket_holders", "params": {"event_id": event.id}})] == ["buyer@example.com"]
        assert [r.email for r in audiences.resolve({"type": "subscribers", "params": {}})] == ["sub@example.com"]
        assert [r.email for r in audiences.resolve({"type": "custom", "params": {"emails": "a@x.org, B@x.org; a@x.org"}})] == ["a@x.org", "b@x.org"]
        clean, error = audiences.validate_audience({"type": "ticket_holders", "params": {}})
        assert error and not clean
        _, error = audiences.validate_audience({"type": "ticket_holders", "params": {"event_id": 999}})
        assert error == "That event does not exist."
        db.drop_all()


def test_update_message_honours_opt_outs_and_unsubscribe_link_works():
    app = _new_app()
    with app.app_context():
        _member("Asha", "asha@example.com")
        _member("Ben", "ben@example.com")
        db.session.add(MessageSuppression(email="ben@example.com"))
        db.session.commit()
        created = _admin(app, "post", "/api/admin/messages", json={"kind": "update", "subject": "News {{name}}", "body_html": "<p>Hello {{name}}</p>", "audience": {"type": "members", "params": {}}})
        assert created.status_code == 201
        message_id = created.get_json()["id"]
        info = _admin(app, "post", "/api/admin/messages/preview", json={"kind": "update", "audience": {"type": "members"}}).get_json()
        assert info == {"total": 2, "skipped": 1, "will_receive": 1}
        fake, ctx = _with_channel()
        with ctx:
            sent = _admin(app, "post", f"/api/admin/messages/{message_id}/send")
        assert sent.status_code == 202
        assert [m["to"] for m in fake.sent] == ["asha@example.com"]
        mail = fake.sent[0]
        assert mail["subject"] == "News Asha" and "Hello Asha" in mail["html"] and "Unsubscribe" in mail["html"]
        assert "List-Unsubscribe" in mail["headers"]
        message = db.session.get(Message, message_id)
        assert message.status == "sent" and (message.sent_count, message.skipped_count, message.recipients_total) == (1, 1, 2)
        assert all("asha@" not in a.description for a in AuditLog.query.all())

        token = service.unsubscribe_token("asha@example.com")
        client = app.test_client()
        assert client.post("/api/messages/unsubscribe?e=asha@example.com&t=wrong").status_code == 400
        assert client.get(f"/api/messages/unsubscribe?e=asha@example.com&t={token}").status_code == 200
        assert MessageSuppression.query.filter_by(email="asha@example.com").count() == 0  # a GET only checks
        assert client.post(f"/api/messages/unsubscribe?e=asha@example.com&t={token}").status_code == 200
        assert MessageSuppression.query.filter_by(email="asha@example.com").count() == 1
        db.drop_all()


def test_service_message_ignores_opt_outs_and_has_no_unsubscribe():
    app = _new_app()
    with app.app_context():
        _member("Ben", "ben@example.com")
        db.session.add(MessageSuppression(email="ben@example.com"))
        db.session.commit()
        message = Message(kind="service", subject="Your event", body_html="<p>Tomorrow</p>", audience={"type": "members", "params": {}})
        db.session.add(message)
        db.session.commit()
        fake, ctx = _with_channel()
        with ctx:
            assert service.begin(message, None) is True
        assert [m["to"] for m in fake.sent] == ["ben@example.com"]
        assert "Unsubscribe" not in fake.sent[0]["html"] and fake.sent[0]["headers"] is None
        db.drop_all()


def test_nobody_to_send_to_is_refused_and_draft_only_edits():
    app = _new_app()
    with app.app_context():
        created = _admin(app, "post", "/api/admin/messages", json={"kind": "update", "subject": "S", "body_html": "<p>x</p>", "audience": {"type": "custom", "params": {"emails": "a@x.org"}}}).get_json()
        db.session.add(MessageSuppression(email="a@x.org"))
        db.session.commit()
        refused = _admin(app, "post", f"/api/admin/messages/{created['id']}/send")
        assert refused.status_code == 400
        patched = _admin(app, "patch", f"/api/admin/messages/{created['id']}", json={"subject": "New subject"})
        assert patched.status_code == 200 and patched.get_json()["subject"] == "New subject"
        bad = _admin(app, "post", "/api/admin/messages", json={"kind": "nope", "subject": "", "audience": {}})
        assert bad.status_code == 400 and {"kind", "subject", "audience"} <= set(bad.get_json()["errors"])
        db.drop_all()


def test_scheduled_message_fires_when_due_and_can_be_unscheduled():
    app = _new_app()
    with app.app_context():
        created = _admin(app, "post", "/api/admin/messages", json={"kind": "update", "subject": "Later", "body_html": "<p>x</p>", "audience": {"type": "custom", "params": {"emails": "a@x.org"}}}).get_json()
        past = _admin(app, "post", f"/api/admin/messages/{created['id']}/send", json={"scheduled_for": "2000-01-01T00:00:00Z"})
        assert past.status_code == 400
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        ok = _admin(app, "post", f"/api/admin/messages/{created['id']}/send", json={"scheduled_for": future})
        assert ok.status_code == 200 and ok.get_json()["status"] == "scheduled"
        assert _admin(app, "post", f"/api/admin/messages/{created['id']}/unschedule").get_json()["status"] == "draft"
        _admin(app, "post", f"/api/admin/messages/{created['id']}/send", json={"scheduled_for": future})
        message = db.session.get(Message, created["id"])
        message.scheduled_for = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
        fake, ctx = _with_channel()
        with ctx:
            assert service.fire_due_messages() == 1
            assert service.fire_due_messages() == 0  # claimed once
        assert [m["to"] for m in fake.sent] == ["a@x.org"]
        db.drop_all()


def test_a_failed_address_is_counted_and_the_rest_still_go():
    app = _new_app()
    with app.app_context():
        message = Message(kind="service", subject="S", body_html="<p>x</p>", audience={"type": "custom", "params": {"emails": "bad@x.org good@x.org"}})
        db.session.add(message)
        db.session.commit()

        class Flaky(FakeChannel):
            def send(self, *, to, **kw):
                if to.startswith("bad"):
                    raise RuntimeError("boom")
                super().send(to=to, **kw)

        flaky = Flaky()
        with patch.dict("app.messages.channels.CHANNELS", {"email": flaky}):
            service.begin(message, None)
        assert [m["to"] for m in flaky.sent] == ["good@x.org"]
        db.session.refresh(message)
        assert (message.sent_count, message.failed_count, message.status) == (1, 1, "sent")
        db.drop_all()


def test_event_reminder_rule_sends_once_to_the_ticket_holders_with_placeholders():
    app = _new_app()
    with app.app_context():
        event = _add_event(title="Spring Gala", start_datetime=datetime.now(timezone.utc) + timedelta(days=2), published=True)
        _paid_order(event.id, "Buyer One", "one@example.com", "T-1")
        rule = MessageRule(name="Day before", trigger="event_before", offset_days=2, send_hour=0, subject="{{event_title}} is coming", body_html="<p>Hi {{name}}, see you on {{event_date}} at {{event_venue}}</p>")
        db.session.add(rule)
        db.session.commit()
        fake, ctx = _with_channel()
        with ctx:
            assert rules.run_rules() == 1
            assert rules.run_rules() == 0  # the same target is never reminded twice
        assert [m["to"] for m in fake.sent] == ["one@example.com"]
        assert fake.sent[0]["subject"] == "Spring Gala is coming" and "Hi Buyer One" in fake.sent[0]["html"]
        assert MessageRuleRun.query.count() == 1 and Message.query.one().source == f"rule:{rule.id}"
        db.drop_all()


def test_membership_reminders_find_the_right_members():
    from app.memberships.models import Membership, MembershipPeriod, MembershipType

    app = _new_app()
    with app.app_context():
        db.session.add(MembershipType(name="adult", price=200, billing_frequency="yearly"))
        member = _member("Asha", "asha@example.com")
        target = date.today() + timedelta(days=7)
        membership = Membership(member_id=member.id, membership_type="adult", status="active", start_date=date.today() - timedelta(days=300), end_date=target)
        db.session.add(membership)
        db.session.commit()
        db.session.add(MembershipPeriod(membership_id=membership.id, period_start=target, period_end=target + timedelta(days=364), label="2027", amount=20000, currency="NOK", status="unpaid"))
        db.session.add_all(
            [
                MessageRule(name="Ending", trigger="membership_ending", offset_days=7, send_hour=0, subject="Ends {{end_date}}", body_html="<p>{{name}}, your {{membership_type}} ends</p>"),
                MessageRule(name="Due", trigger="period_due", offset_days=7, send_hour=0, subject="Due {{period_label}}", body_html="<p>{{amount}} due {{due_date}}</p>"),
            ]
        )
        db.session.commit()
        fake, ctx = _with_channel()
        with ctx:
            assert rules.run_rules() == 2
        subjects = sorted(m["subject"] for m in fake.sent)
        assert subjects[0].startswith("Due 2027") and subjects[1].startswith("Ends ")
        assert any("20000" not in m["html"] and "200.00" in m["html"] for m in fake.sent if m["subject"].startswith("Due"))
        db.drop_all()


def test_rule_crud_and_options_follow_modules():
    app = _new_app()
    with app.app_context():
        options = _admin(app, "get", "/api/admin/messages/options").get_json()
        assert {"members", "ticket_holders", "custom"} <= {a["key"] for a in options["audiences"]}
        assert {"event_before", "event_before_members", "membership_ending", "period_due"} == {t["key"] for t in options["triggers"]}
        created = _admin(app, "post", "/api/admin/messages/rules", json={"name": "Day before", "trigger": "event_before", "offset_days": 1, "subject": "S", "body_html": "<p>Hi</p>"})
        assert created.status_code == 201
        rule_id = created.get_json()["id"]
        assert _admin(app, "patch", f"/api/admin/messages/rules/{rule_id}", json={"enabled": False, "send_hour": 18}).get_json()["send_hour"] == 18
        bad = _admin(app, "post", "/api/admin/messages/rules", json={"name": "", "trigger": "x", "offset_days": -1, "subject": "", "body_html": ""})
        assert bad.status_code == 400 and {"name", "trigger", "offset_days", "subject", "body_html"} <= set(bad.get_json()["errors"])
        assert _admin(app, "delete", f"/api/admin/messages/rules/{rule_id}").status_code == 204
        db.drop_all()


def test_opt_out_list_can_be_managed_and_erasure_anonymises_recipient_rows():
    app = _new_app()
    with app.app_context():
        added = _admin(app, "post", "/api/admin/messages/suppressions", json={"emails": "x@y.org, z@y.org"})
        assert added.get_json() == {"added": 2}
        rows = _admin(app, "get", "/api/admin/messages/suppressions").get_json()["items"]
        assert len(rows) == 2
        assert _admin(app, "delete", f"/api/admin/messages/suppressions/{rows[0]['id']}").status_code == 204

        member = _member("Asha", "asha@example.com")
        message = Message(kind="service", subject="S", body_html="<p>x</p>", audience={"type": "members", "params": {}})
        db.session.add(message)
        db.session.commit()
        fake, ctx = _with_channel()
        with ctx:
            service.begin(message, None)
        erasure.anonymise_member(member)
        row = MessageRecipient.query.one()
        assert row.email.endswith("@erased.invalid") and row.name == "" and row.status == "sent"
        db.drop_all()


def test_event_reminder_to_all_members_for_a_community_without_ticket_sales():
    app = _new_app()
    with app.app_context():
        _member("Asha", "asha@example.com")
        _member("Ben", "ben@example.com")
        db.session.add(MessageSuppression(email="ben@example.com"))  # a service message ignores the opt-out list
        event = _add_event(title="Sunday gathering", start_datetime=datetime.now(timezone.utc) + timedelta(days=1), published=True)
        db.session.add(MessageRule(name="Day before", trigger="event_before_members", offset_days=1, send_hour=0, subject="Tomorrow: {{event_title}}", body_html="<p>Hello {{name}}</p>"))
        db.session.commit()
        fake, ctx = _with_channel()
        with ctx:
            assert rules.run_rules() == 1
            assert rules.run_rules() == 0
        assert sorted(m["to"] for m in fake.sent) == ["asha@example.com", "ben@example.com"]
        assert fake.sent[0]["subject"] == "Tomorrow: Sunday gathering" and event.id
        db.drop_all()


def test_people_waiting_to_be_erased_and_cancelled_events_get_no_messages():
    app = _new_app()
    with app.app_context():
        staying = _member("Stays", "stays@example.com")
        leaving = _member("Leaves", "leaves@example.com")
        erasure.request_erase(leaving)
        assert [r.email for r in audiences.resolve({"type": "members", "params": {}})] == ["stays@example.com"]
        assert staying.erase_requested_at is None

        event = _add_event(title="Spring Gala", start_datetime=datetime.now(timezone.utc) + timedelta(days=2), published=True)
        _paid_order(event.id, "Buyer One", "one@example.com", "T-1")
        event.status = "cancelled"
        db.session.add(MessageRule(name="Day before", trigger="event_before", offset_days=2, send_hour=0, subject="s", body_html="<p>b</p>"))
        db.session.commit()
        fake, ctx = _with_channel()
        with ctx:
            assert rules.run_rules() == 0
        assert fake.sent == []
        db.drop_all()


def test_donors_and_ticket_holders_skip_a_person_waiting_to_be_erased():
    from app.donations.models import Donation

    app = _new_app()
    with app.app_context():
        leaving = _member("Leaves", "leaves@example.com")
        erasure.request_erase(leaving)
        event = _add_event(title="Spring Gala", start_datetime=datetime.now(timezone.utc) + timedelta(days=2), published=True)
        _paid_order(event.id, "Leaves", "Leaves@Example.com", "T-1")
        _paid_order(event.id, "Buyer", "buyer@example.com", "T-2")
        db.session.add(Donation(reference="DON-1", donor_name="Leaves", donor_email="leaves@example.com", amount=100, currency="NOK", status="paid"))
        db.session.add(Donation(reference="DON-2", donor_name="Giver", donor_email="giver@example.com", amount=100, currency="NOK", status="paid"))
        db.session.commit()
        assert [r.email for r in audiences.resolve({"type": "ticket_holders", "params": {"event_id": event.id}})] == ["buyer@example.com"]
        assert [r.email for r in audiences.resolve({"type": "donors", "params": {}})] == ["giver@example.com"]
        db.drop_all()


def test_message_list_can_be_narrowed_to_one_audience_for_the_newsletters_tab():
    app = _new_app()
    with app.app_context():
        for subject, kind in (("To subscribers", "subscribers"), ("To members", "members"), ("To subscribers again", "subscribers")):
            db.session.add(Message(kind="update", subject=subject, body_html="<p>x</p>", audience={"type": kind, "params": {}}))
        db.session.commit()
        body = _admin(app, "get", "/api/admin/messages?audience=subscribers").get_json()
        assert body["total"] == 2 and {m["subject"] for m in body["items"]} == {"To subscribers", "To subscribers again"}
        assert _admin(app, "get", "/api/admin/messages").get_json()["total"] == 3
        db.drop_all()


def test_a_newsletter_waits_for_the_squares_own_sending_domain_and_other_messages_do_not():
    app = _new_app()
    with app.app_context():
        db.session.add(Subscriber(email="sub@example.com"))
        db.session.commit()
        news = _admin(app, "post", "/api/admin/messages", json={"kind": "update", "subject": "News", "body_html": "<p>x</p>", "audience": {"type": "subscribers", "params": {}}}).get_json()
        other = _admin(app, "post", "/api/admin/messages", json={"kind": "update", "subject": "Hi", "body_html": "<p>x</p>", "audience": {"type": "custom", "params": {"emails": "a@x.org"}}}).get_json()
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        with patch("app.email.service.own_sending_domain_verified", return_value=False):
            refused = _admin(app, "post", f"/api/admin/messages/{news['id']}/send", json={"scheduled_for": future})
            assert refused.status_code == 409 and refused.get_json()["code"] == "own_domain_required"
            assert db.session.get(Message, news["id"]).status == "draft"
            assert _admin(app, "post", f"/api/admin/messages/{other['id']}/send", json={"scheduled_for": future}).status_code == 200  # not a newsletter
        with patch("app.email.service.own_sending_domain_verified", return_value=True):
            assert _admin(app, "post", f"/api/admin/messages/{news['id']}/send", json={"scheduled_for": future}).status_code == 200
        # scheduled, then the domain is lost: when it is due it goes back to draft and nothing is sent
        message = db.session.get(Message, news["id"])
        message.scheduled_for = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
        fake, patched = _with_channel()
        with patched, patch("app.email.service.own_sending_domain_verified", return_value=False):
            assert service.fire_due_messages() == 0
        assert db.session.get(Message, news["id"]).status == "draft" and fake.sent == []
        db.drop_all()
