"""Tests for config (3 tests), e.g. defaults are valid; cors origins must be explicit; cors origins parsed."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.conftest import make_settings


def test_defaults_are_valid() -> None:
    s = make_settings()
    assert s.ENV == "test" and s.cors_origins == []


@pytest.mark.parametrize("origins", ["*", "http://ok.test,*", "localhost:5273", "ftp://x.test"])
def test_cors_origins_must_be_explicit(origins: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(CORS_ORIGINS=origins)


def test_cors_origins_parsed() -> None:
    assert make_settings(CORS_ORIGINS="http://a.test, https://b.test").cors_origins == ["http://a.test", "https://b.test"]
