"""Platform e-mail (W12-R14): Resend over httpx, nothing sent without it; errors never carry the key."""

import httpx
import pytest

from app.providers.email import EmailSendError, ResendEmailProvider, build_email
from app.shared.config import Settings


def _client(status: int, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json={"id": "x"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sends_plain_text_with_the_key_in_the_header_only():
    seen: list = []
    ResendEmailProvider("re_secret", "rootsquares <hello@example.com>", _client(200, seen)).send("a@b.c", "Subject", "Body")
    req = seen[0]
    assert req.headers["authorization"] == "Bearer re_secret" and b"re_secret" not in req.content
    assert b'"text":"Body"' in req.content.replace(b" ", b"") and b"a@b.c" in req.content


def test_reply_to_is_sent_only_when_set():
    seen: list = []
    ResendEmailProvider("re_secret", "x@y.z", _client(200, seen), reply_to="hello@example.com").send("a@b.c", "S", "B")
    ResendEmailProvider("re_secret", "x@y.z", _client(200, seen)).send("a@b.c", "S", "B")
    assert b'"reply_to":"hello@example.com"' in seen[0].content.replace(b" ", b"")
    assert b"reply_to" not in seen[1].content


def test_a_refusal_is_an_error_without_the_key():
    with pytest.raises(EmailSendError) as err:
        ResendEmailProvider("re_secret", "x@y.z", _client(403, [])).send("a@b.c", "S", "B")
    assert "re_secret" not in str(err.value)


def test_no_provider_means_no_e_mail_and_resend_needs_its_settings():
    assert build_email(Settings(EMAIL_PROVIDER="none")) is None
    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        Settings(EMAIL_PROVIDER="resend", RESEND_API_KEY="", EMAIL_FROM="")
    assert build_email(Settings(EMAIL_PROVIDER="resend", RESEND_API_KEY="re_x", EMAIL_FROM="a@b.c")) is not None


def test_branded_mail_carries_html_logo_and_footer_gradient_and_escapes():
    from app.platform import email_html

    text = "Your free trial of <b>Club</b> ends soon.\n\nPay on your Billing page:\nhttps://x.test/squares/1/billing\n\nNothing is deleted.\n"
    mail = email_html.from_text(text, site_url="https://x.test/", eyebrow="Your trial", heading="Ends soon", button_label="Go to Billing")
    html = mail["html"]
    assert "&lt;b&gt;Club" in html and "<b>Club" not in html
    assert 'href="https://x.test/squares/1/billing"' in html and "Go to Billing" in html
    assert "https://x.test/squares/1/billing</td>" not in html  # the link is the button, not text
    assert "linear-gradient(180deg,#140b07,#1b100a,#22150e)" in html and "cid:rs-logo-ink" in html and "cid:rs-logo-cream" in html
    assert "https://x.test/pricing" in html
    assert {i["content_id"] for i in mail["inline_images"]} == {"rs-logo-ink", "rs-logo-cream"}


def test_resend_gets_text_html_and_inline_images():
    from app.platform import email_html

    seen: list = []
    mail = email_html.from_text("Hello.\n", site_url="https://x.test", eyebrow="Test", heading="Hi")
    ResendEmailProvider("re_secret", "x@y.z", _client(200, seen)).send("a@b.c", "S", "Hello.\n", **mail)
    body = seen[0].content
    assert b'"html"' in body and b'"attachments"' in body and b'"content_id"' in body and b'"text"' in body
