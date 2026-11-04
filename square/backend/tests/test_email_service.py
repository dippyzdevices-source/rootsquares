"""Tests for email service (11 tests), e.g. get email service returns fake under testing; fake email service records sent email without network call; not configured email service raises on send."""
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.email.service import (
    EmailServiceError,
    EmailServiceNotConfiguredError,
    FakeEmailService,
    NotConfiguredEmailService,
    ResendEmailService,
    get_email_service,
    parse_recipient_list,
)


def _new_app():
    return create_app("testing")


def test_get_email_service_returns_fake_under_testing():
    app = _new_app()
    with app.app_context():
        assert isinstance(get_email_service(), FakeEmailService)


def test_fake_email_service_records_sent_email_without_network_call():
    service = FakeEmailService()
    message_id = service.send_email(
        to="bengali.culture.oslo@gmail.com",
        subject="Hello",
        html="<p>Hi</p>",
        text="Hi",
        reply_to="visitor@example.com",
    )

    assert message_id
    assert len(service.sent_emails) == 1
    sent = service.sent_emails[0]
    assert sent["to"] == "bengali.culture.oslo@gmail.com"
    assert sent["subject"] == "Hello"
    assert sent["html"] == "<p>Hi</p>"
    assert sent["text"] == "Hi"
    assert sent["reply_to"] == "visitor@example.com"


def test_not_configured_email_service_raises_on_send():
    service = NotConfiguredEmailService()
    with pytest.raises(EmailServiceNotConfiguredError):
        service.send_email(to="a@b.com", subject="s", html="<p>x</p>")


def test_resend_email_service_sends_via_resend_sdk():
    app = _new_app()
    with app.app_context():
        with patch("app.email.service.resend.Emails.send", return_value={"id": "abc123"}) as mock_send:
            service = ResendEmailService(api_key="re_fake", from_address="BCA Oslo <noreply@bcaoslo.no>")
            message_id = service.send_email(
                to="bengali.culture.oslo@gmail.com",
                subject="Hello",
                html="<p>Hi</p>",
                text="Hi",
                reply_to="visitor@example.com",
            )

        assert message_id == "abc123"
        mock_send.assert_called_once()
        params = mock_send.call_args[0][0]
        assert params["from"] == "BCA Oslo <noreply@bcaoslo.no>"
        assert params["to"] == ["bengali.culture.oslo@gmail.com"]
        assert params["subject"] == "Hello"
        assert params["html"] == "<p>Hi</p>"
        assert params["text"] == "Hi"
        assert params["reply_to"] == "visitor@example.com"


def test_resend_email_service_sends_to_multiple_recipients_when_given_a_list():
    app = _new_app()
    with app.app_context():
        with patch("app.email.service.resend.Emails.send", return_value={"id": "abc123"}) as mock_send:
            service = ResendEmailService(api_key="re_fake", from_address="BCA Oslo <noreply@bcaoslo.no>")
            service.send_email(
                to=["bengali.culture.oslo@gmail.com", "second@bcaoslo.no"],
                subject="Hello",
                html="<p>Hi</p>",
            )

        params = mock_send.call_args[0][0]
        assert params["to"] == ["bengali.culture.oslo@gmail.com", "second@bcaoslo.no"]


def test_fake_email_service_records_a_list_of_recipients():
    service = FakeEmailService()
    service.send_email(
        to=["bengali.culture.oslo@gmail.com", "second@bcaoslo.no"],
        subject="Hello",
        html="<p>Hi</p>",
    )

    assert service.sent_emails[0]["to"] == ["bengali.culture.oslo@gmail.com", "second@bcaoslo.no"]


def test_resend_email_service_wraps_provider_failure():
    app = _new_app()
    with app.app_context():
        with patch("app.email.service.resend.Emails.send", side_effect=RuntimeError("boom")):
            service = ResendEmailService(api_key="re_fake", from_address="BCA Oslo <noreply@bcaoslo.no>")
            with pytest.raises(EmailServiceError):
                service.send_email(to="bengali.culture.oslo@gmail.com", subject="Hello", html="<p>Hi</p>")


def test_parse_recipient_list_splits_trims_and_drops_blanks():
    assert parse_recipient_list("a@b.com, c@d.com ,, e@f.com") == ["a@b.com", "c@d.com", "e@f.com"]


def test_parse_recipient_list_returns_single_item_list_for_one_address():
    assert parse_recipient_list("a@b.com") == ["a@b.com"]


def test_parse_recipient_list_returns_empty_list_for_blank_config():
    assert parse_recipient_list("") == []


def test_resend_api_key_never_appears_in_log_output(caplog):
    app = _new_app()
    with app.app_context():
        with patch("app.email.service.resend.Emails.send", return_value={"id": "abc123"}):
            service = ResendEmailService(api_key="re_super_secret_key", from_address="noreply@bcaoslo.no")
            service.send_email(to="a@b.com", subject="s", html="<p>x</p>")

        assert "re_super_secret_key" not in caplog.text


def test_resend_email_service_falls_back_to_the_squares_reply_to_but_never_overrides_one():
    app = _new_app()
    with app.app_context():
        with patch("app.email.service.resend.Emails.send", return_value={"id": "x"}) as mock_send:
            service = ResendEmailService(api_key="re_fake", from_address="Club <hello@mail.example.com>", default_reply_to="club@example.org")
            service.send_email(to="buyer@example.com", subject="Your order", html="<p>Hi</p>")
            service.send_email(to="owner@example.org", subject="Contact", html="<p>Hi</p>", reply_to="visitor@example.com")
        assert mock_send.call_args_list[0][0][0]["reply_to"] == "club@example.org"
        assert mock_send.call_args_list[1][0][0]["reply_to"] == "visitor@example.com"


def test_contact_recipients_prefer_the_squares_own_address_and_fall_back_to_the_server_setting():
    from app.email.service import contact_recipients
    from app.extensions import db
    from app.settings.models import SiteSettings

    app = _new_app()
    app.config["CONTACT_EMAIL"] = "server@example.com"
    with app.app_context():
        db.create_all()
        assert contact_recipients() == ["server@example.com"]
        db.session.get(SiteSettings, 1).contact_email = "club@example.org, second@example.org"  # the first call made the row
        db.session.commit()
        assert contact_recipients() == ["club@example.org", "second@example.org"]
        db.drop_all()


def test_the_address_the_owner_set_on_the_platform_comes_first_then_the_public_contact_address():
    from types import SimpleNamespace

    from flask import g

    from app.email.service import contact_recipients, square_contact_email
    from app.extensions import db
    from app.settings.models import SiteSettings

    app = _new_app()
    app.config["CONTACT_EMAIL"] = "server@example.com"
    with app.test_request_context():
        db.create_all()
        db.session.add(SiteSettings(id=1, contact_email="public@example.org"))
        db.session.commit()
        g.tenant = SimpleNamespace(name="Club", mail_contact_email="")
        assert square_contact_email() == ["public@example.org"]  # nothing set on the platform
        g.tenant = SimpleNamespace(name="Club", mail_contact_email="private@example.org")
        assert square_contact_email() == ["private@example.org"] and contact_recipients() == ["private@example.org"]
        db.drop_all()


def test_customer_mail_replies_go_to_the_address_the_owner_set_on_the_platform():
    from types import SimpleNamespace

    from flask import g

    app = _new_app()
    app.extensions["email_service"] = ResendEmailService(api_key="re_fake", from_address="rootsquares <hello@mail.example.com>")
    app.config["RESEND_API_KEY"] = "re_fake"
    app.config["EMAIL_FROM"] = "rootsquares <hello@mail.example.com>"
    with app.test_request_context():
        g.tenant = SimpleNamespace(name="Club", mail_contact_email="private@example.org")
        with patch("app.email.service.resend.Emails.send", return_value={"id": "x"}) as mock_send:
            get_email_service().send_email(to="buyer@example.com", subject="Your order", html="<p>Hi</p>")
        params = mock_send.call_args[0][0]
        assert params["reply_to"] == "private@example.org" and params["from"].startswith("Club <")


def test_a_square_with_a_verified_own_domain_sends_from_it_with_its_own_name():
    from types import SimpleNamespace

    from flask import g

    app = _new_app()
    app.extensions["email_service"] = ResendEmailService(api_key="re_fake", from_address="rootsquares <hello@mail.example.com>")
    app.config["RESEND_API_KEY"] = "re_fake"
    app.config["EMAIL_FROM"] = "rootsquares <hello@mail.example.com>"
    with app.test_request_context():
        g.tenant = SimpleNamespace(name="Club", mail_contact_email="", mail_from_address="tickets@mail.club.no")
        with patch("app.email.service.resend.Emails.send", return_value={"id": "x"}) as mock_send:
            get_email_service().send_email(to="buyer@example.com", subject="Your order", html="<p>Hi</p>")
        assert mock_send.call_args[0][0]["from"] == "Club <tickets@mail.club.no>"
        g.tenant = SimpleNamespace(name="Club", mail_contact_email="", mail_from_address="")  # no own domain: the shared sender
        with patch("app.email.service.resend.Emails.send", return_value={"id": "x"}) as mock_send:
            get_email_service().send_email(to="buyer@example.com", subject="Your order", html="<p>Hi</p>")
        assert mock_send.call_args[0][0]["from"] == "Club <hello@mail.example.com>"


def test_the_own_domain_is_used_only_when_verified_and_the_package_has_it():
    from app.tenancy import _own_from_address

    def row(**kw):
        base = {"mail_domain": "mail.club.no", "mail_domain_status": "verified", "mail_from_local": "tickets", "launch_package": "grove", "custom_modules": None}
        return {**base, **kw}

    assert _own_from_address(row()) == "tickets@mail.club.no"
    assert _own_from_address(row(launch_package="")) == "tickets@mail.club.no"  # a square made before packages counts as Grove
    assert _own_from_address(row(mail_from_local=None)) == "hello@mail.club.no"
    assert _own_from_address(row(mail_domain_status="pending")) == "" and _own_from_address(row(mail_domain_status="failed")) == ""
    assert _own_from_address(row(launch_package="square")) == "" and _own_from_address(row(launch_package="roots")) == "" and _own_from_address(row(launch_package="event")) == ""
    assert _own_from_address(row(launch_package="custom", custom_modules='["events"]')) == ""
    assert _own_from_address(row(launch_package="custom", custom_modules='["events","messages"]')) == "tickets@mail.club.no"
    assert _own_from_address(row(mail_domain=None)) == ""


def test_nothing_is_enforced_when_no_square_is_served():
    from app.email.service import own_sending_domain_verified

    app = _new_app()
    with app.test_request_context():
        assert own_sending_domain_verified() is True
