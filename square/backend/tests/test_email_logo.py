"""The square's uploaded logo in the email header, with the letter mark as the fallback (rootsquares W6-R59)."""

from dataclasses import replace
from io import BytesIO

from flask import g
from PIL import Image

from app import create_app
from app.email import templates
from tests.test_site_identity import SQUARE

LOGO_URL = "https://files.example/square-logos/a.png"


def _png(size=(400, 200), colour=(200, 30, 30, 255)) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeRaw(BytesIO):
    def read(self, size=-1, decode_content=False):  # like urllib3's response: read() takes decode_content
        return super().read(size)


class FakeResponse:
    def __init__(self, data: bytes, status: int = 200):
        self.raw = FakeRaw(data)
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError("http error")


def _attachment(monkeypatch, response, logo_url=LOGO_URL):
    import requests

    calls = []
    monkeypatch.setattr(requests, "get", lambda url, **kw: calls.append(url) or response)
    templates._logo_images.clear()
    app = create_app("testing")
    with app.test_request_context():
        g.tenant = replace(SQUARE, logo_url=logo_url)
        return templates._logo_attachment("site-logo"), calls


def test_the_uploaded_logo_is_shrunk_and_attached(monkeypatch):
    attachment, calls = _attachment(monkeypatch, FakeResponse(_png()))
    image = Image.open(BytesIO(bytes(attachment["content"])))
    assert calls == [LOGO_URL] and image.size == (128, 64)  # kept in proportion, at most 128 wide
    assert attachment["content_id"] == "site-logo" and attachment["content_type"] == "image/png"


def test_it_is_fetched_once_per_address(monkeypatch):
    _, first = _attachment(monkeypatch, FakeResponse(_png()))
    app = create_app("testing")
    with app.test_request_context():
        g.tenant = replace(SQUARE, logo_url=LOGO_URL)
        templates._logo_attachment("site-logo")
    assert first == [LOGO_URL]  # the second email did not fetch again (the cache holds it)


def test_a_broken_logo_falls_back_to_the_letter_mark_and_is_not_remembered(monkeypatch):
    for response in (FakeResponse(b"not an image"), FakeResponse(b"", 200), FakeResponse(_png(), 500), FakeResponse(b"x" * 1_000_001)):
        attachment, _ = _attachment(monkeypatch, response)
        assert Image.open(BytesIO(bytes(attachment["content"]))).size == (128, 128)  # the letter mark
    assert LOGO_URL not in templates._logo_images


def test_a_square_without_a_logo_uses_the_letter_mark_and_fetches_nothing(monkeypatch):
    attachment, calls = _attachment(monkeypatch, FakeResponse(_png()), logo_url="")
    assert calls == [] and Image.open(BytesIO(bytes(attachment["content"]))).size == (128, 128)
