"""Tests for welcome email (7 tests), e.g. first sight of a new user sends one welcome email with the three links; a returning user does not get another welcome email; a user who already exists gets no welcome email."""
from unittest.mock import MagicMock, patch

from app import create_app
from app.auth.models import User
from app.auth.service import resolve_user_from_token
from app.email.service import EmailServiceError
from app.email.templates import render_welcome_email
from app.extensions import db
from tests.auth_helpers import FakeJWKClient, make_token

PATCH_JWKS = "app.auth.jwt_verification._get_jwks_client"


def _new_app():
    app = create_app("testing")
    # Several origins on purpose: links must use only the first (see app.common.urls).
    app.config["FRONTEND_ORIGIN"] = "https://bca-oslo.org,http://localhost:5173"
    with app.app_context():
        db.create_all()
    return app


def _resolve(token):
    with patch(PATCH_JWKS, return_value=FakeJWKClient()):
        return resolve_user_from_token(token)


def _sent(app):
    return app.extensions["email_service"].sent_emails


def test_first_sight_of_a_new_user_sends_one_welcome_email_with_the_three_links():
    app = _new_app()
    with app.app_context():
        _resolve(make_token(sub="new-sub", email="priya@example.com"))

        assert len(_sent(app)) == 1
        email = _sent(app)[0]
        assert email["to"] == "priya@example.com"
        assert email["subject"] == "Welcome to BCA Oslo"
        for path in ("/member", "/events", "/gallery"):
            assert f'href="https://bca-oslo.org{path}"' in email["html"]
            assert f"https://bca-oslo.org{path}" in email["text"]
        assert "bca-oslo.org,http" not in email["html"]
        assert [a["content_id"] for a in email["attachments"]] == ["site-logo"]
        db.drop_all()


def test_a_returning_user_does_not_get_another_welcome_email():
    app = _new_app()
    with app.app_context():
        token = make_token(sub="returning-sub", email="returning@example.com")
        _resolve(token)
        _resolve(token)
        _resolve(token)

        assert len(_sent(app)) == 1
        db.drop_all()


def test_a_user_who_already_exists_gets_no_welcome_email():
    app = _new_app()
    with app.app_context():
        db.session.add(User(auth_user_id="old-sub", email="old@example.com", role="member", auth_provider="supabase"))
        db.session.commit()

        _resolve(make_token(sub="old-sub", email="old@example.com"))

        assert _sent(app) == []
        db.drop_all()


def test_a_failed_welcome_email_never_blocks_signing_in():
    app = _new_app()
    with app.app_context():
        with patch.object(app.extensions["email_service"], "send_email", side_effect=EmailServiceError("boom")):
            user = _resolve(make_token(sub="fail-sub", email="fail@example.com"))

        assert user is not None
        assert User.query.filter_by(auth_user_id="fail-sub").count() == 1
        db.drop_all()


def test_a_user_with_no_email_claim_is_created_but_nothing_is_sent():
    app = _new_app()
    with app.app_context():
        user = _resolve(make_token(sub="no-email-sub", email=""))

        assert user is not None
        assert _sent(app) == []
        db.drop_all()


def test_when_two_first_requests_race_only_the_winner_sends_and_the_loser_does_not_crash():
    # The frontend fires several /api/auth/me calls at once on first login; auth_user_id is unique,
    # so the loser's insert raises IntegrityError. It must return the winner's row and stay quiet.
    app = _new_app()
    with app.app_context():
        existing = User(auth_user_id="race-sub", email="race@example.com", role="member", auth_provider="supabase")
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id

        lookup = MagicMock()
        # First lookup (before inserting) still sees nothing; the second (after the failed insert) finds the winner.
        lookup.filter_by.return_value.first.side_effect = [None, existing]
        with patch.object(User, "query", lookup):
            user = _resolve(make_token(sub="race-sub", email="race@example.com"))

        assert user is not None and user.id == existing_id
        assert _sent(app) == []
        assert User.query.filter_by(auth_user_id="race-sub").count() == 1
        db.drop_all()


def test_welcome_email_template_escapes_urls_and_carries_the_brand():
    html_body, text_body, attachments = render_welcome_email(
        dashboard_url='https://x.test/member?a=1&b="2"',
        events_url="https://x.test/events",
        gallery_url="https://x.test/gallery",
    )

    assert "Welcome to BCA Oslo" in html_body
    assert 'href="https://x.test/member?a=1&amp;b=&quot;2&quot;"' in html_body
    assert 'b="2"' in text_body
    assert "cid:site-logo" in html_body
    assert [a["content_id"] for a in attachments] == ["site-logo"]
