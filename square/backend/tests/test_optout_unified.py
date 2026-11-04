"""One opt-out for everything we send (W14-R17): leaving the newsletter, the messages or the do-not-contact list is leaving all of them."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.messages import service as messages
from app.messages.models import MessageSuppression
from app.newsletter.models import Subscriber
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _admin():
    _, token = make_user_and_token(role="admin")
    return auth_header(token)


def _status(email):
    return Subscriber.query.filter_by(email=email).one().status


def test_leaving_the_newsletter_puts_the_address_on_the_do_not_contact_list_and_subscribing_again_takes_it_off():
    app = _new_app()
    with app.app_context():
        c = app.test_client()
        c.post("/api/newsletter/subscribe", json={"email": "Pia@X.org", "consent": True})
        c.post("/api/newsletter/confirm", json={"token": Subscriber.query.one().token})
        token = Subscriber.query.one().token
        assert c.post("/api/newsletter/unsubscribe", json={"token": token}).status_code == 200
        assert _status("pia@x.org") == "unsubscribed"
        assert MessageSuppression.query.filter_by(email="pia@x.org").count() == 1
        # explicit consent again ends the opt-out in both places
        c.post("/api/newsletter/subscribe", json={"email": "pia@x.org", "consent": True})
        assert _status("pia@x.org") == "pending" and MessageSuppression.query.count() == 1  # still opted out until the link is clicked
        c.post("/api/newsletter/confirm", json={"token": Subscriber.query.one().token})
        assert _status("pia@x.org") == "subscribed" and MessageSuppression.query.count() == 0
        db.drop_all()


def test_leaving_through_a_message_or_the_admin_list_unsubscribes_the_newsletter_subscriber_too():
    app = _new_app()
    with app.app_context():
        c = app.test_client()
        for e in ("a@x.org", "b@x.org"):
            db.session.add(Subscriber(email=e))
        db.session.commit()
        t = messages.unsubscribe_token("a@x.org")
        assert c.post(f"/api/messages/unsubscribe?e=a@x.org&t={t}").status_code == 200
        assert _status("a@x.org") == "unsubscribed"
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            assert c.post("/api/admin/messages/suppressions", json={"emails": "b@x.org"}, headers=_admin()).status_code == 201
        assert _status("b@x.org") == "unsubscribed"
        # an address on the list that is still marked subscribed (an older mismatch) is fixed the next time it is put there
        db.session.get(Subscriber, 1).status = "subscribed"
        db.session.commit()
        assert messages.suppress("a@x.org") is False and _status("a@x.org") == "unsubscribed"
        db.drop_all()


def test_a_newsletter_to_the_subscribers_skips_the_do_not_contact_list():
    app = _new_app()
    with app.app_context():
        for e in ("keep@x.org", "left@x.org"):
            db.session.add(Subscriber(email=e))
        db.session.add(MessageSuppression(email="left@x.org"))  # on the list, still marked subscribed
        db.session.commit()
        assert messages.preview({"type": "subscribers", "params": {}}, "update") == {"total": 2, "skipped": 1, "will_receive": 1}
        db.drop_all()
