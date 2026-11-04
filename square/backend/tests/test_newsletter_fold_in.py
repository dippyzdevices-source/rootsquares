"""Tests for newsletter fold in (3 tests), e.g. every issue becomes a message once and nothing old is changed or delet; it waits while an issue is being sent; a scheduled newsletter goes out once from messages."""
from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.extensions import db
from app.messages import service as messages
from app.messages.models import Message
from app.newsletter import fold_in
from app.newsletter.models import NewsletterIssue, Subscriber
from app.newsletter.fold_in import SKIP_SUBSCRIBERS_CURSOR

NOW = datetime.now(timezone.utc)


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _issue(**kw):
    issue = NewsletterIssue(subject=kw.pop("subject", "News"), body_html="<p>Hi</p>", **kw)
    db.session.add(issue)
    db.session.commit()
    return issue


def test_every_issue_becomes_a_message_once_and_nothing_old_is_changed_or_deleted():
    app = _new_app()
    with app.app_context():
        sent = _issue(subject="Sent", status="sent", recipients_total=10, sent_count=9, failed_count=1, sent_at=NOW - timedelta(days=3))
        draft = _issue(subject="Draft", status="draft")
        both = _issue(subject="Both", status="draft", extra_recipients="x@y.org")
        later = _issue(subject="Later", status="scheduled", scheduled_for=NOW + timedelta(days=1))
        pasted = _issue(subject="Pasted", status="sent", extra_recipients="a@b.org c@d.org", last_subscriber_id=SKIP_SUBSCRIBERS_CURSOR, sent_count=2, recipients_total=2)

        result = fold_in.copy_issues_to_messages()
        assert result == {"copied": 5, "already": 0, "extras_dropped": [both.id]}
        by_subject = {m.subject: m for m in Message.query.all()}
        assert (by_subject["Sent"].status, by_subject["Sent"].sent_count, by_subject["Sent"].failed_count, by_subject["Sent"].recipients_total) == ("sent", 9, 1, 10)
        assert by_subject["Sent"].kind == "update" and by_subject["Sent"].audience == {"type": "subscribers", "params": {}}
        assert by_subject["Draft"].status == "draft" and by_subject["Later"].status == "scheduled" and by_subject["Later"].scheduled_for is not None
        assert by_subject["Pasted"].audience == {"type": "custom", "params": {"emails": "a@b.org c@d.org"}}
        assert by_subject["Sent"].source == f"newsletter:{sent.id}"
        assert db.session.get(NewsletterIssue, draft.id).moved_to_message_id == by_subject["Draft"].id
        assert NewsletterIssue.query.count() == 5 and db.session.get(NewsletterIssue, later.id).status == "scheduled"

        again = fold_in.copy_issues_to_messages()  # running it twice changes nothing
        assert again == {"copied": 0, "already": 5, "extras_dropped": []} and Message.query.count() == 5
        db.drop_all()


def test_it_waits_while_an_issue_is_being_sent():
    app = _new_app()
    with app.app_context():
        _issue(status="sending")
        with pytest.raises(fold_in.IssueSendingError):
            fold_in.copy_issues_to_messages()
        assert Message.query.count() == 0
        db.drop_all()


def test_a_scheduled_newsletter_goes_out_once_from_messages():
    from unittest.mock import patch

    app = _new_app()
    with app.app_context():
        db.session.add(Subscriber(email="pia@x.org"))
        _issue(status="scheduled", scheduled_for=NOW - timedelta(minutes=1))
        fold_in.copy_issues_to_messages()
        sent = []

        class Fake:
            def send(self, **kw):
                sent.append(kw["to"])

        with patch.dict("app.messages.channels.CHANNELS", {"email": Fake()}):
            assert messages.fire_due_messages() == 1
        assert sent == ["pia@x.org"]
        assert Message.query.one().status == "sent"
        db.drop_all()
