"""Tests for qr (1 tests), e.g. generate qr data url returns a png data uri."""
import base64

from app.tickets.qr import generate_qr_data_url


def test_generate_qr_data_url_returns_a_png_data_uri():
    result = generate_qr_data_url("abc123")

    assert result.startswith("data:image/png;base64,")
    encoded = result.removeprefix("data:image/png;base64,")
    decoded = base64.b64decode(encoded)
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"  # PNG file signature
