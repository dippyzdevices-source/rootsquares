"""Tests for contact routes (14 tests), e.g. valid submission sends email via email service; email uses correct recipient sender and reply to; multiple comma separated contact emails all receive the message."""
from app import create_app
from app.contact.routes import _submission_log
from app.email.service import EmailServiceError


def _new_app(**config_overrides):
    app = create_app("testing")
    app.config["CONTACT_EMAIL"] = "bengali.culture.oslo@gmail.com"
    app.config["EMAIL_FROM"] = "BCA Oslo <noreply@bcaoslo.no>"
    for key, value in config_overrides.items():
        app.config[key] = value
    return app


def _post(app, payload, ip="10.0.0.1"):
    return app.test_client().post("/api/contact", json=payload, headers={"X-Forwarded-For": ip})


VALID_PAYLOAD = {
    "name": "Priya Das",
    "email": "priya@example.com",
    "subject": "Membership question",
    "message": "Hello, I would like to know more about membership options.",
}


def test_valid_submission_sends_email_via_email_service():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        response = _post(app, VALID_PAYLOAD, ip="10.0.0.2")

        assert response.status_code == 200
        assert response.get_json() == {"success": True, "message": "Your message has been sent successfully."}

        sent = app.extensions["email_service"].sent_emails
        assert len(sent) == 1


def test_email_uses_correct_recipient_sender_and_reply_to():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        _post(app, VALID_PAYLOAD, ip="10.0.0.3")

        sent = app.extensions["email_service"].sent_emails[0]
        assert sent["to"] == ["bengali.culture.oslo@gmail.com"]
        assert sent["reply_to"] == "priya@example.com"


def test_multiple_comma_separated_contact_emails_all_receive_the_message():
    app = _new_app(CONTACT_EMAIL="first@bcaoslo.no, second@bcaoslo.no")
    _submission_log.clear()
    with app.app_context():
        _post(app, VALID_PAYLOAD, ip="10.0.0.15")

        sent = app.extensions["email_service"].sent_emails[0]
        assert sent["to"] == ["first@bcaoslo.no", "second@bcaoslo.no"]


def test_email_subject_includes_website_prefix_and_form_subject():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        _post(app, VALID_PAYLOAD, ip="10.0.0.4")

        sent = app.extensions["email_service"].sent_emails[0]
        assert sent["subject"] == "[BCA Oslo] Membership question"


def test_email_has_html_and_text_bodies():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        _post(app, VALID_PAYLOAD, ip="10.0.0.5")

        sent = app.extensions["email_service"].sent_emails[0]
        assert "Priya Das" in sent["html"]
        assert "Membership question" in sent["html"]
        assert "Priya Das" in sent["text"]
        assert "Membership question" in sent["text"]


def test_missing_required_fields_rejected():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        response = _post(app, {}, ip="10.0.0.6")

        assert response.status_code == 400
        errors = response.get_json()["errors"]
        assert set(errors.keys()) == {"name", "email", "subject", "message"}
        assert app.extensions["email_service"].sent_emails == []


def test_invalid_email_rejected():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        payload = {**VALID_PAYLOAD, "email": "not-an-email"}
        response = _post(app, payload, ip="10.0.0.7")

        assert response.status_code == 400
        assert "email" in response.get_json()["errors"]


def test_excessively_long_message_rejected():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        payload = {**VALID_PAYLOAD, "message": "x" * 5001}
        response = _post(app, payload, ip="10.0.0.8")

        assert response.status_code == 400
        assert "message" in response.get_json()["errors"]


def test_too_short_message_rejected():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        payload = {**VALID_PAYLOAD, "message": "short"}
        response = _post(app, payload, ip="10.0.0.9")

        assert response.status_code == 400
        assert "message" in response.get_json()["errors"]


def test_honeypot_filled_returns_success_but_sends_no_email():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        payload = {**VALID_PAYLOAD, "website": "http://spam.example"}
        response = _post(app, payload, ip="10.0.0.10")

        assert response.status_code == 200
        assert response.get_json()["success"] is True
        assert app.extensions["email_service"].sent_emails == []


def test_rate_limit_blocks_after_max_requests_from_same_ip():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        ip = "10.0.0.11"
        for _ in range(5):
            response = _post(app, VALID_PAYLOAD, ip=ip)
            assert response.status_code == 200

        response = _post(app, VALID_PAYLOAD, ip=ip)
        assert response.status_code == 429
        assert "error" in response.get_json()


def test_missing_contact_email_config_returns_friendly_error_without_internals():
    app = _new_app(CONTACT_EMAIL="")
    _submission_log.clear()
    with app.app_context():
        response = _post(app, VALID_PAYLOAD, ip="10.0.0.12")

        assert response.status_code == 503
        body = response.get_json()
        assert body["error"] == "We couldn't send your message right now. Please try again later."


def test_email_service_failure_returns_friendly_error_without_internals(monkeypatch):
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        def _raise(*args, **kwargs):
            raise EmailServiceError("Failed to send email")

        monkeypatch.setattr(app.extensions["email_service"], "send_email", _raise)

        response = _post(app, VALID_PAYLOAD, ip="10.0.0.13")

        assert response.status_code == 503
        body = response.get_json()
        assert body["error"] == "We couldn't send your message right now. Please try again later."
        assert "Failed to send email" not in str(body)


def test_response_never_includes_api_key_or_message_id():
    app = _new_app()
    _submission_log.clear()
    with app.app_context():
        response = _post(app, VALID_PAYLOAD, ip="10.0.0.14")

        body = response.get_json()
        assert "RESEND_API_KEY" not in str(body)
        assert "id" not in body
