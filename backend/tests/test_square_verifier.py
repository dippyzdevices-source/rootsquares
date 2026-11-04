"""Square token verifier (auth item C): a square's token is checked against ITS OWN project, the admin is matched by auth user id only.
No network: providers and the admin lookup are injected, the platform database is a throwaway SQLite file."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from app.main import create_app
from app.platform.models import Organization, Square, SquareStatus
from app.platform.square_verifier import SquareAdmin, SquareAuthError, SquareAuthVerifier, default_provider_factory
from app.providers.auth import FakeAuthProvider, NeonAuthProvider, SupabaseAuthProvider
from app.shared.crypto import Encryptor
from app.shared.db import Base
from tests.conftest import make_settings

CONNECTION = "postgresql+psycopg://u:p@h:6543/postgres"
SECRETS = {"project_url": "https://abcdefghijklmnopqrst.supabase.co", "service_role": "k"}


def build(tmp_path: Path, **kwargs: Any) -> tuple[SquareAuthVerifier, uuid.UUID, Any, dict[str, Any]]:
    settings = make_settings(DATABASE_URL=f"sqlite:///{tmp_path / 'v.db'}")
    app = create_app(settings)
    Base.metadata.create_all(app.extensions["db_engine"]())
    enc = Encryptor(settings.fernet_key)
    with app.extensions["db_factory"]()() as db:
        org = Organization(name="Club")
        db.add(org)
        db.flush()
        sq = Square(
            org_id=org.id,
            name="First",
            slug="first-org",
            theme_id="paper-brick",
            status=SquareStatus.READY,
            db_connection=enc.encrypt(CONNECTION),
            provider_secrets=enc.encrypt(json.dumps(SECRETS)),
            provider_project_ref="abcdefghijklmnopqrst",
            provider="supabase",
        )
        db.add(sq)
        db.commit()
        sq_id = sq.id
    seen: dict[str, Any] = {"providers": [], "lookups": []}

    def provider_factory(provider: str, secrets: dict[str, str]) -> Any:
        seen["providers"].append((provider, secrets["project_url"]))
        return FakeAuthProvider()

    def admin_lookup(connection_url: str, auth_user_id: str) -> SquareAdmin | None:
        seen["lookups"].append((connection_url, auth_user_id))
        return SquareAdmin(id="a1", email="o@example.com", name="O", role="owner") if auth_user_id == "owner-1" else None

    verifier = SquareAuthVerifier(
        app.extensions["db_factory"],
        settings,
        provider_factory=kwargs.get("provider_factory", provider_factory),
        admin_lookup=admin_lookup,
        clock=kwargs.get("clock", lambda: 0.0),
    )
    return verifier, sq_id, app, seen


def test_a_token_of_the_square_gives_its_admin(tmp_path: Path) -> None:
    verifier, sq_id, _app, seen = build(tmp_path)
    who = verifier.authenticate(sq_id, "fake:owner-1:o@example.com")
    assert who is not None and who.admin is not None and who.admin.role == "owner" and who.email == "o@example.com"
    assert seen["providers"] == [("supabase", SECRETS["project_url"])]  # the provider was built from THIS square's project url
    assert seen["lookups"] == [(CONNECTION, "owner-1")]  # and the lookup used the decrypted connection of this square


def test_a_member_who_is_not_an_admin_has_no_admin_record(tmp_path: Path) -> None:
    verifier, sq_id, _app, _seen = build(tmp_path)
    who = verifier.authenticate(sq_id, "fake:visitor-9:v@example.com")
    assert who is not None and who.admin is None


def test_an_admin_email_in_the_token_is_not_enough(tmp_path: Path) -> None:
    """Same email as the owner, different auth user id: must not become admin."""
    verifier, sq_id, _app, _seen = build(tmp_path)
    who = verifier.authenticate(sq_id, "fake:somebody-else:o@example.com")
    assert who is not None and who.admin is None


def test_an_invalid_token_is_none(tmp_path: Path) -> None:
    verifier, sq_id, _app, seen = build(tmp_path)
    assert verifier.authenticate(sq_id, "garbage") is None and seen["lookups"] == []


def test_unknown_unready_and_authless_squares_are_refused(tmp_path: Path) -> None:
    verifier, sq_id, app, _seen = build(tmp_path)
    with pytest.raises(SquareAuthError) as e:
        verifier.authenticate(uuid.uuid4(), "fake:owner-1:o@example.com")
    assert e.value.code == "not_found"
    with app.extensions["db_factory"]()() as db:
        db.get(Square, sq_id).status = SquareStatus.FAILED  # type: ignore[union-attr]
        db.commit()
    verifier.forget(sq_id)
    with pytest.raises(SquareAuthError) as e2:
        verifier.authenticate(sq_id, "fake:owner-1:o@example.com")
    assert e2.value.code == "not_ready"

    with app.extensions["db_factory"]()() as db:
        sq = db.get(Square, sq_id)
        assert sq is not None
        sq.status, sq.provider, sq.provider_project_ref, sq.provider_secrets = SquareStatus.READY, "local", None, None
        db.commit()
    local_verifier = SquareAuthVerifier(app.extensions["db_factory"], make_settings(), provider_factory=default_provider_factory)
    with pytest.raises(SquareAuthError) as e3:
        local_verifier.authenticate(sq_id, "x")
    assert e3.value.code == "no_auth"


def test_the_square_is_read_once_per_ttl(tmp_path: Path) -> None:
    now = [0.0]
    verifier, sq_id, _app, seen = build(tmp_path, clock=lambda: now[0])
    verifier.authenticate(sq_id, "fake:owner-1:a@b.c")
    verifier.authenticate(sq_id, "fake:owner-1:a@b.c")
    assert len(seen["providers"]) == 1
    now[0] = 601.0  # past SQUARE_AUTH_CACHE_SECONDS: secrets and keys are re-read
    verifier.authenticate(sq_id, "fake:owner-1:a@b.c")
    assert len(seen["providers"]) == 2


def test_default_providers_use_the_squares_own_urls() -> None:
    sb = default_provider_factory("supabase", {"project_url": "https://abc.supabase.co"})
    assert isinstance(sb, SupabaseAuthProvider) and sb._jwks_url == "https://abc.supabase.co/auth/v1/.well-known/jwks.json"
    nn = default_provider_factory("neon", {"auth_url": "https://ep-1.aws.neon.tech/db/auth"})
    assert isinstance(nn, NeonAuthProvider) and nn._jwks_url == "https://ep-1.aws.neon.tech/db/auth/.well-known/jwks.json"
    for bad in (("local", {}), ("supabase", {}), ("", {"project_url": "x"})):
        with pytest.raises(SquareAuthError):
            default_provider_factory(*bad)


def test_check_square_token_command(tmp_path: Path) -> None:
    verifier, _sq_id, app, _seen = build(tmp_path)
    app.extensions["square_auth"] = verifier
    runner = app.test_cli_runner()
    ok = runner.invoke(args=["check-square-token", "first-org", "fake:owner-1:o@example.com"])
    assert ok.exit_code == 0 and "sub=owner-1" in ok.output and "admin of the square: owner" in ok.output
    assert "invalid_token" in runner.invoke(args=["check-square-token", "first-org", "nope"]).output
    assert "No such square" in runner.invoke(args=["check-square-token", "nope", "x"]).output
