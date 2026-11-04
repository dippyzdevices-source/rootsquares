"""Tests for newsletter (7 tests), e.g. subscribe validates email and consent; subscribe is idempotent case insensitive and sends one email; the address is on the list only after the link is clicked."""
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.newsletter.models import Subscriber
from tests.auth_helpers import FakeJWKClient, auth_header, make_user_and_token


def _new_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    return app


def _subscribe(client, **payload):
    body = {"email": "Anna@Example.no", "consent": True}
    body.update(payload)
    return client.post("/api/newsletter/subscribe", json=body)


def test_subscribe_validates_email_and_consent():
    app = _new_app()
    with app.app_context():
        c = app.test_client()
        assert _subscribe(c, email="nope").status_code == 400
        assert _subscribe(c, consent=False).status_code == 400
        assert Subscriber.query.count() == 0
        db.drop_all()


def _confirm(client, email="anna@example.no"):
    return client.post("/api/newsletter/confirm", json={"token": Subscriber.query.filter_by(email=email).one().token})


def test_subscribe_is_idempotent_case_insensitive_and_sends_one_email():
    app = _new_app()
    with app.app_context():
        c = app.test_client()
        assert _subscribe(c).status_code == 200
        assert _subscribe(c, email="anna@example.no").status_code == 200
        assert Subscriber.query.count() == 1
        sent = app.extensions["email_service"].sent_emails
        assert len(sent) == 1 and "newsletter/confirm?token=" in sent[0]["html"]  # asking twice sends the link once
        assert Subscriber.query.one().status == "pending"
        db.drop_all()


def test_the_address_is_on_the_list_only_after_the_link_is_clicked():
    app = _new_app()
    with app.app_context():
        c = app.test_client()
        assert _subscribe(c).get_json() == {"status": "pending"}
        assert c.post("/api/newsletter/confirm", json={"token": "bad"}).status_code == 404
        from app.messages import audiences

        assert audiences.resolve({"type": "subscribers", "params": {}}) == []
        assert _confirm(c).status_code == 200 and Subscriber.query.one().status == "subscribed"
        assert [r.email for r in audiences.resolve({"type": "subscribers", "params": {}})] == ["anna@example.no"]
        sent = app.extensions["email_service"].sent_emails
        assert len(sent) == 2 and "unsubscribe?token=" in sent[1]["html"]  # the welcome mail follows the click
        assert _confirm(c).status_code == 200 and len(app.extensions["email_service"].sent_emails) == 2  # clicking twice changes nothing
        assert _subscribe(c).get_json() == {"status": "pending"} and Subscriber.query.one().status == "subscribed"  # no answer reveals the list
        db.drop_all()


def test_asking_again_before_confirming_resends_the_link_only_after_an_hour():
    from datetime import datetime, timedelta, timezone

    app = _new_app()
    with app.app_context():
        c = app.test_client()
        _subscribe(c)
        row = Subscriber.query.one()
        row.consented_at = datetime.now(timezone.utc) - timedelta(minutes=61)
        db.session.commit()
        _subscribe(c)
        assert len(app.extensions["email_service"].sent_emails) == 2
        db.drop_all()


def test_unsubscribe_then_resubscribe():
    app = _new_app()
    with app.app_context():
        c = app.test_client()
        _subscribe(c)
        _confirm(c)
        token = Subscriber.query.one().token
        assert c.post("/api/newsletter/unsubscribe", json={"token": "bad"}).status_code == 404
        assert c.post("/api/newsletter/unsubscribe", json={"token": token}).status_code == 200
        assert Subscriber.query.one().status == "unsubscribed"
        _subscribe(c)
        assert Subscriber.query.one().status == "pending"  # coming back needs the link again
        _confirm(c)
        assert Subscriber.query.one().status == "subscribed"
        db.drop_all()


def test_admin_list_export_delete_require_admin():
    app = _new_app()
    with app.app_context():
        c = app.test_client()
        _subscribe(c)
        _subscribe(c, email="bo@example.no")
        _confirm(c)
        _confirm(c, "bo@example.no")
        sid = Subscriber.query.filter_by(email="bo@example.no").one().id
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            assert c.get("/api/admin/newsletter/subscribers").status_code == 401
            _, token = make_user_and_token(role="admin")
            h = auth_header(token)
            r = c.get("/api/admin/newsletter/subscribers?q=bo", headers=h)
            assert [i["email"] for i in r.get_json()["items"]] == ["bo@example.no"]
            assert r.get_json()["subscribed_count"] == 2
            assert c.get("/api/admin/newsletter/subscribers/export", headers=h).status_code == 200
            assert c.delete(f"/api/admin/newsletter/subscribers/{sid}", headers=h).status_code == 204
        assert Subscriber.query.count() == 1
        db.drop_all()


def test_subscribers_export_follows_the_search_and_status_filters():
    import io

    from openpyxl import load_workbook

    app = _new_app()
    with app.app_context():
        c = app.test_client()
        _subscribe(c)
        _subscribe(c, email="bo@example.no")
        _confirm(c)
        _confirm(c, "bo@example.no")
        with patch("app.auth.jwt_verification._get_jwks_client", return_value=FakeJWKClient()):
            _, token = make_user_and_token(role="admin")
            h = auth_header(token)
            everyone = c.get("/api/admin/newsletter/subscribers/export", headers=h)
            only_bo = c.get("/api/admin/newsletter/subscribers/export?q=bo", headers=h)
        emails = lambda r: [row[0] for row in list(load_workbook(io.BytesIO(r.data)).active.iter_rows(values_only=True))[1:]]
        assert len(emails(everyone)) == 2
        assert emails(only_bo) == ["bo@example.no"]
        db.drop_all()
