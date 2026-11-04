"""Tests for common urls (1 tests), e.g. frontend base url returns first origin without trailing slash."""
import pytest
from flask import Flask

from app.common.urls import frontend_base_url


@pytest.mark.parametrize(
    "configured, expected",
    [
        ("http://localhost:5173", "http://localhost:5173"),
        ("https://bca-oslo.org,https://www.bca-oslo.org,http://localhost:5173", "https://bca-oslo.org"),
        (" https://bca-oslo.org/ , https://www.bca-oslo.org", "https://bca-oslo.org"),
        (",https://bca-oslo.org", "https://bca-oslo.org"),
        ("", ""),
    ],
)
def test_frontend_base_url_returns_first_origin_without_trailing_slash(configured, expected):
    app = Flask(__name__)
    app.config["FRONTEND_ORIGIN"] = configured
    with app.app_context():
        assert frontend_base_url() == expected
