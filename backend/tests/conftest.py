"""Pytest fixtures shared by the tests in this folder."""
from __future__ import annotations

import os
from pathlib import Path

# W26-R58: the tests never read the developer's real settings file (backend/.env.local): it holds real addresses and keys, and one typo in it (a stray slash in
# EMAIL_PROVIDER) failed every test that builds Settings() directly. Set before app.shared.config is imported (the file name is read once, at import).
os.environ["ENV_FILE"] = str(Path(__file__).parent / "no-settings-file-in-tests")

import pytest  # noqa: E402
from flask import Flask  # noqa: E402
from flask.testing import FlaskClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.shared.config import Settings  # noqa: E402


def make_settings(**overrides: object) -> Settings:
    """Settings that ignore the real environment and .env file."""
    values: dict[str, object] = {"ENV": "test"}
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.fixture
def app() -> Flask:
    return create_app(make_settings())


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
