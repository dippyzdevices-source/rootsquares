"""Tests for auth email templates (6 tests), e.g. signup code email shows the code and brand in html and text; signup code email states the expiry computed from expires at; signup code email omits the expiry sentence when expires at is missing."""
from datetime import datetime, timedelta, timezone

from app.email.templates import render_password_reset_email, render_signup_code_email


def _in(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def test_signup_code_email_shows_the_code_and_brand_in_html_and_text():
    html_body, text_body, attachments = render_signup_code_email(code="483920", expires_at=_in(15))

    assert "483920" in html_body
    assert "483920" in text_body
    assert "Confirm your email address" in html_body
    assert "BCA Oslo" in html_body
    assert "cid:site-logo" in html_body
    assert [a["content_id"] for a in attachments] == ["site-logo"]


def test_signup_code_email_states_the_expiry_computed_from_expires_at():
    html_body, text_body, _ = render_signup_code_email(code="483920", expires_at=_in(15))

    assert "expires in 15 minutes" in html_body
    assert "expires in 15 minutes" in text_body


def test_signup_code_email_omits_the_expiry_sentence_when_expires_at_is_missing_or_garbled():
    # Review Focus #2: an unusable expires_at must never break sending the code.
    for bad in (None, "", "not-a-date"):
        html_body, text_body, _ = render_signup_code_email(code="483920", expires_at=bad)
        assert "483920" in html_body
        assert "expires in" not in html_body
        assert "expires in" not in text_body


def test_signup_code_email_escapes_html_in_the_code():
    html_body, _, _ = render_signup_code_email(code="<b>1</b>", expires_at=None)

    assert "<b>1</b>" not in html_body
    assert "&lt;b&gt;1&lt;/b&gt;" in html_body


def test_password_reset_email_has_a_button_and_fallback_link_to_the_reset_url():
    url = "https://ep-x.neon.tech/neondb/auth/reset-password/tok?callbackURL=http://localhost:5173/reset-password&x=1"
    html_body, text_body, attachments = render_password_reset_email(reset_url=url, expires_at=_in(60))

    assert "Reset your password" in html_body
    assert 'href="' + url.replace("&", "&amp;") + '"' in html_body
    assert url in text_body
    assert "expires in 60 minutes" in html_body
    assert [a["content_id"] for a in attachments] == ["site-logo"]


def test_password_reset_email_omits_expiry_when_expires_at_is_missing():
    html_body, text_body, _ = render_password_reset_email(reset_url="https://example.com/r", expires_at=None)

    assert "expires in" not in html_body
    assert "expires in" not in text_body
