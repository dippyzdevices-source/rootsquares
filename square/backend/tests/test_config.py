"""Tests for config (16 tests), e.g. testing config pins supabase auth with a fake url; development and production take the auth provider from the environment; validate auth config accepts each known provider with a url."""
import pytest

from app import create_app
from app.config import (
    Config,
    DevelopmentConfig,
    ProductionConfig,
    TestingConfig,
    _engine_options,
    default_frontend_origins,
    validate_auth_config,
    validate_production_config,
)


def test_testing_config_pins_supabase_auth_with_a_fake_url():
    # Deliberately NOT "neon" and NOT env-driven — the existing pytest suite fakes the
    # Supabase/ES256 path directly and must keep doing so whatever the developer's .env says.
    assert TestingConfig.AUTH_PROVIDER == "supabase"
    assert TestingConfig.AUTH_URL == "https://example.supabase.co"


def test_development_and_production_take_the_auth_provider_from_the_environment_only():
    # APP_ENV no longer picks the provider: neither config overrides what Config reads from
    # AUTH_PROVIDER/AUTH_URL, so prod can run either provider.
    assert DevelopmentConfig.AUTH_PROVIDER == Config.AUTH_PROVIDER
    assert ProductionConfig.AUTH_PROVIDER == Config.AUTH_PROVIDER
    assert DevelopmentConfig.AUTH_URL == Config.AUTH_URL
    assert ProductionConfig.AUTH_URL == Config.AUTH_URL


@pytest.mark.parametrize("provider", ["supabase", "neon"])
def test_validate_auth_config_accepts_each_known_provider_with_a_url(provider):
    validate_auth_config({"AUTH_PROVIDER": provider, "AUTH_URL": "https://auth.example.com"})


@pytest.mark.parametrize("provider", ["", None, "firebase", "Supabase "])
def test_validate_auth_config_rejects_a_missing_or_unknown_provider(provider):
    with pytest.raises(RuntimeError, match="AUTH_PROVIDER"):
        validate_auth_config({"AUTH_PROVIDER": provider, "AUTH_URL": "https://auth.example.com"})


@pytest.mark.parametrize("url", ["", None])
def test_validate_auth_config_rejects_an_empty_url(url):
    with pytest.raises(RuntimeError, match="AUTH_URL"):
        validate_auth_config({"AUTH_PROVIDER": "neon", "AUTH_URL": url})


@pytest.mark.parametrize("env_name, config_cls", [("development", DevelopmentConfig), ("production", ProductionConfig)])
def test_create_app_refuses_to_start_without_an_auth_provider(monkeypatch, env_name, config_cls):
    monkeypatch.setattr(config_cls, "AUTH_PROVIDER", "")
    monkeypatch.setattr(config_cls, "AUTH_URL", "https://auth.example.com")
    with pytest.raises(RuntimeError, match="AUTH_PROVIDER"):
        create_app(env_name)


@pytest.mark.parametrize("env_name, config_cls", [("development", DevelopmentConfig), ("production", ProductionConfig)])
def test_create_app_refuses_to_start_without_an_auth_url(monkeypatch, env_name, config_cls):
    monkeypatch.setattr(config_cls, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(config_cls, "AUTH_URL", "")
    with pytest.raises(RuntimeError, match="AUTH_URL"):
        create_app(env_name)


def test_create_app_in_testing_needs_no_auth_environment():
    assert create_app("testing").config["AUTH_PROVIDER"] == "supabase"


def test_engine_options_for_postgres_validate_connections_and_bound_cold_starts():
    # Neon suspends idle compute: pre-ping replaces a connection the pool kept open across a
    # suspend, and connect_timeout stops a stalled wake-up from hanging a worker forever.
    options = _engine_options("postgresql+psycopg://user:pw@host/db")
    assert options["pool_pre_ping"] is True
    assert options["connect_args"] == {"connect_timeout": 10}


def test_engine_options_are_empty_for_sqlite():
    # sqlite3.connect() rejects connect_timeout as a kwarg — the test suite runs on SQLite.
    assert _engine_options("sqlite:///:memory:") == {}
    assert _engine_options("") == {}


def test_testing_config_engine_options_are_empty_on_sqlite():
    assert TestingConfig.SQLALCHEMY_DATABASE_URI.startswith("sqlite")
    assert TestingConfig.SQLALCHEMY_ENGINE_OPTIONS == {}


# ---- safe defaults (rootsquares W6-R37) ------------------------------------------------------------------------------------------
def test_production_refuses_the_development_secret_key_or_a_short_one():
    for bad in ("dev-secret-key-change-me", "", "too-short"):
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            validate_production_config({"IS_PRODUCTION": True, "SECRET_KEY": bad})


def test_production_accepts_its_own_long_secret_key_and_other_environments_need_none():
    validate_production_config({"IS_PRODUCTION": True, "SECRET_KEY": "x" * 32})
    validate_production_config({"IS_PRODUCTION": False, "SECRET_KEY": "dev-secret-key-change-me"})
    assert ProductionConfig.IS_PRODUCTION is True and DevelopmentConfig.IS_PRODUCTION is False and TestingConfig.IS_PRODUCTION is False


def test_create_app_in_production_stops_without_a_real_secret_key(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "AUTH_PROVIDER", "supabase")
    monkeypatch.setattr(ProductionConfig, "AUTH_URL", "https://example.supabase.co")
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "dev-secret-key-change-me")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")


def test_default_browser_origins_are_local_in_development_and_none_in_production():
    assert default_frontend_origins("development") == "http://localhost:5274,http://127.0.0.1:5274"
    assert default_frontend_origins("production") == ""
    assert "bca-oslo" not in default_frontend_origins("development") + default_frontend_origins("production")


def test_default_bucket_names_are_the_ones_rootsquares_gives_every_square():
    assert (Config.STORAGE_PUBLIC_BUCKET, Config.STORAGE_PRIVATE_BUCKET) == ("public", "private")
