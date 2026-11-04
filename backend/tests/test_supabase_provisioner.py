"""SupabaseProvisioner (ADR 028, W5-R12): the Management API is replaced by httpx.MockTransport, so nothing leaves the machine and nothing is created.
Also: provision_square storing the project reference and encrypted secrets, a provider-only owner (no password), the local-provisioner guard and
the additive column sync."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

import app.platform.provisioning as provisioning
from app.platform import square_auth
from app.platform.models import Organization, Square, SquareStatus
from app.platform.provisioning import LocalProvisioner, Owner, ProvisionResult, SupabaseApiError, SupabaseProvisioner, provision_square
from app.shared.crypto import Encryptor
from app.shared.db import Base, add_missing_columns
from tests.conftest import make_settings

REF = "abcdefghijklmnopqrst"
POOLER = [
    {"database_type": "READ_REPLICA", "db_user": "x", "db_host": "replica.example", "db_port": 6543, "db_name": "postgres"},
    {"database_type": "PRIMARY", "db_user": f"postgres.{REF}", "db_host": "aws-0-eu-west-1.pooler.supabase.com", "db_port": 6543, "db_name": "postgres"},
]
KEYS = [
    {"name": "anon", "type": "legacy", "api_key": "anon.jwt"},
    {"name": "service_role", "type": "legacy", "api_key": "service.jwt"},
    {"name": "default", "type": "publishable", "api_key": "sb_publishable_x"},
    {"name": "default", "type": "secret", "api_key": "sb_secret_x"},
    {"name": "empty", "type": "secret", "api_key": None},
]


class FakeManagementApi:
    def __init__(self, statuses: list[str] | None = None, fail_buckets: bool = False) -> None:
        self.statuses = list(statuses or ["COMING_UP", "COMING_UP", "ACTIVE_HEALTHY"])
        self.fail_buckets = fail_buckets
        self.calls: list[tuple[str, str]] = []
        self.bodies: dict[str, Any] = {}
        self.headers: dict[str, httpx.Headers] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        self.headers[f"{request.method} {path}"] = request.headers
        if request.content:
            self.bodies[f"{request.method} {path}"] = json.loads(request.content)
        if (request.method, path) == ("POST", "/v1/projects"):
            return httpx.Response(201, json={"ref": REF, "status": "COMING_UP"})
        if (request.method, path) == ("GET", f"/v1/projects/{REF}"):
            return httpx.Response(200, json={"ref": REF, "status": self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]})
        if path == f"/v1/projects/{REF}/config/database/pooler":
            return httpx.Response(200, json=POOLER)
        if path == f"/v1/projects/{REF}/api-keys":
            return httpx.Response(200, json=KEYS)
        if path == "/storage/v1/bucket":
            return httpx.Response(500 if self.fail_buckets else 200, json={})
        if request.method == "PATCH" and path == f"/v1/projects/{REF}/config/auth":
            return httpx.Response(200, json={})
        if request.method == "DELETE" and path == f"/v1/projects/{REF}":
            return httpx.Response(200, json={"ref": REF})
        return httpx.Response(404, json={})


def make(api: FakeManagementApi, **kwargs: Any) -> tuple[SupabaseProvisioner, list[float]]:
    slept: list[float] = []
    client = httpx.Client(base_url="https://api.supabase.com", transport=httpx.MockTransport(api))
    prov = SupabaseProvisioner("pat-token", "my-org", "eu-west-1", "rootsquares.com", client=client, sleep=slept.append, db_ready=lambda _url: None, **kwargs)
    return prov, slept


def test_creates_a_project_and_collects_everything_the_platform_must_store() -> None:
    api = FakeManagementApi()
    prov, slept = make(api)
    result = prov.create_database("firstorg")

    body = api.bodies["POST /v1/projects"]
    assert body["name"] == "rootsquares-firstorg" and body["organization_slug"] == "my-org"
    assert body["region_selection"] == {"type": "specific", "code": "eu-west-1"} and len(body["db_pass"]) >= 32
    assert api.headers["POST /v1/projects"]["authorization"] == "Bearer pat-token"
    assert slept == [5.0, 5.0]  # two COMING_UP answers before ACTIVE_HEALTHY

    password = body["db_pass"]
    assert result.connection_url == f"postgresql+psycopg://postgres.{REF}:{password}@aws-0-eu-west-1.pooler.supabase.com:6543/postgres"
    assert result.project_ref == REF
    assert result.secrets == {
        "project_url": f"https://{REF}.supabase.co",
        "anon": "anon.jwt",
        "service_role": "service.jwt",
        "publishable": "sb_publishable_x",
        "secret": "sb_secret_x",
    }
    assert api.bodies["PATCH /v1/projects/" + REF + "/config/auth"] == {
        "site_url": "https://firstorg.rootsquares.com",
        "uri_allow_list": "https://firstorg.rootsquares.com/**",
    }
    assert ("DELETE", f"/v1/projects/{REF}") not in api.calls


def test_buckets_are_created_with_the_service_key() -> None:
    api = FakeManagementApi()
    make(api)[0].create_database("a-b")
    buckets = [c for c in api.calls if c[1] == "/storage/v1/bucket"]
    assert len(buckets) == 2 and api.headers["POST /storage/v1/bucket"]["apikey"] == "service.jwt"
    assert api.headers["POST /storage/v1/bucket"]["authorization"] == "Bearer service.jwt"


def test_a_failed_step_removes_the_new_project_again() -> None:
    api = FakeManagementApi(fail_buckets=True)
    with pytest.raises(SupabaseApiError, match="500 to POST /storage/v1/bucket"):
        make(api)[0].create_database("firstorg")
    assert ("DELETE", f"/v1/projects/{REF}") in api.calls


def test_a_project_that_fails_to_start_is_removed_and_reported() -> None:
    api = FakeManagementApi(statuses=["COMING_UP", "INIT_FAILED"])
    with pytest.raises(RuntimeError, match="failed to start"):
        make(api)[0].create_database("firstorg")
    assert ("DELETE", f"/v1/projects/{REF}") in api.calls


def test_waiting_gives_up_after_the_limit() -> None:
    api = FakeManagementApi(statuses=["COMING_UP"])
    with pytest.raises(TimeoutError):
        make(api, wait_seconds=10.0)[0].create_database("firstorg")
    assert ("DELETE", f"/v1/projects/{REF}") in api.calls


# ---- provision_square ---------------------------------------------------------------------------------------------------------------
class StubProvisioner:
    def create_database(self, slug: str) -> ProvisionResult:
        secrets = {"project_url": "https://x.supabase.co", "service_role": "k"}
        return ProvisionResult(connection_url="postgresql+psycopg://u:p@h/db", project_ref=REF, secrets=secrets)


def test_provision_square_stores_the_reference_and_encrypted_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(provisioning, "seed_square", lambda url, slug, owner, cmd: seen.update(url=url, owner=owner))
    monkeypatch.setattr(provisioning, "create_square_auth_user", lambda secrets, owner: "auth-user-1")
    monkeypatch.setattr(provisioning, "link_owner", lambda url, email, auth_id: seen.update(linked=(email, auth_id)))
    settings = make_settings()
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        org = Organization(name="Club")
        db.add(org)
        db.flush()
        sq = Square(org_id=org.id, name="First", slug="firstorg", theme_id="paper-brick", status=SquareStatus.PROVISIONING)
        db.add(sq)
        db.commit()
        sq_id = sq.id

    provision_square(factory, settings, sq_id, Owner(email="o@example.com", name="O", password_hash=None), StubProvisioner())

    with factory() as db:
        sq = db.get(Square, sq_id)
        assert sq is not None and sq.status == SquareStatus.READY and sq.provider_project_ref == REF
        enc = Encryptor(settings.fernet_key)
        assert "service_role" not in (sq.provider_secrets or "") and json.loads(enc.decrypt(sq.provider_secrets or ""))["service_role"] == "k"
        assert enc.decrypt(sq.db_connection or "") == "postgresql+psycopg://u:p@h/db"
    assert seen["owner"].password_hash is None and seen["linked"] == ("o@example.com", "auth-user-1")


def test_the_built_in_bootstrap_accepts_an_owner_without_a_password() -> None:
    assert "password_hash text," in provisioning.BOOTSTRAP_SQL and "password_hash text not null" not in provisioning.BOOTSTRAP_SQL


def test_local_provisioner_refuses_a_hosted_platform_database() -> None:
    LocalProvisioner("postgresql+psycopg://u:p@127.0.0.1:5432/x")
    with pytest.raises(RuntimeError, match="on this machine"):
        LocalProvisioner("postgresql+psycopg://u:p@aws-0-eu-west-1.pooler.supabase.com:6543/postgres")


# ---- settings and column sync ---------------------------------------------------------------------------------------------------------
def test_supabase_provisioner_needs_a_token_and_an_organisation() -> None:
    with pytest.raises(ValueError, match="SUPABASE_ACCESS_TOKEN"):
        make_settings(PROVISIONER="supabase")
    s = make_settings(PROVISIONER="supabase", SUPABASE_ACCESS_TOKEN="t", SUPABASE_ORG_SLUG="o")
    assert isinstance(provisioning.make_provisioner(s), SupabaseProvisioner)


def test_add_missing_columns_adds_only_nullable_new_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE squares DROP COLUMN provider_project_ref"))
        conn.execute(text("ALTER TABLE squares DROP COLUMN provider_secrets"))
    assert sorted(add_missing_columns(engine)) == ["squares.provider_project_ref", "squares.provider_secrets"]
    assert "provider_secrets" in {c["name"] for c in inspect(engine).get_columns("squares")}
    assert add_missing_columns(engine) == []  # idempotent


def test_a_refused_call_shows_the_api_message_on_the_square(tmp_path: Path) -> None:
    class Refusing:
        def create_database(self, slug: str) -> ProvisionResult:
            refuse = httpx.MockTransport(lambda r: httpx.Response(403, json={"message": "Forbidden"}))
            client = httpx.Client(base_url="https://api.supabase.com", transport=refuse)
            return SupabaseProvisioner("t", "o", "eu-west-1", client=client).create_database(slug)

    settings = make_settings()
    engine = create_engine(f"sqlite:///{tmp_path / 'e.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        org = Organization(name="Club")
        db.add(org)
        db.flush()
        sq = Square(org_id=org.id, name="First", slug="first-org", theme_id="paper-brick", status=SquareStatus.PROVISIONING)
        db.add(sq)
        db.commit()
        sq_id = sq.id
    provision_square(factory, settings, sq_id, Owner(email="o@example.com", name="O", password_hash=None), Refusing())
    with factory() as db:
        sq = db.get(Square, sq_id)
        assert sq is not None and sq.status == SquareStatus.FAILED
        assert sq.error == "SupabaseApiError: Supabase answered 403 to POST /v1/projects: Forbidden"


# ---- the owner as a real user of the square's own auth ------------------------------------------------------------------------------
def test_owner_is_created_as_a_confirmed_auth_user_with_the_service_key() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), headers=request.headers, body=json.loads(request.content))
        return httpx.Response(200, json={"id": "11111111-2222-3333-4444-555555555555"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    secrets = {"project_url": f"https://{REF}.supabase.co", "service_role": "service.jwt"}
    auth_id = provisioning.create_square_auth_user(secrets, Owner(email="o@example.com", name="Asha", password_hash=None), client)
    assert auth_id == "11111111-2222-3333-4444-555555555555"
    assert seen["url"] == f"https://{REF}.supabase.co/auth/v1/admin/users" and seen["headers"]["apikey"] == "service.jwt"
    assert seen["headers"]["authorization"] == "Bearer service.jwt"
    assert seen["body"] == {"email": "o@example.com", "email_confirm": True, "user_metadata": {"full_name": "Asha"}}


def test_new_secret_keys_go_in_the_apikey_header_only() -> None:
    assert provisioning.service_headers({"secret": "sb_secret_x"}) == {"apikey": "sb_secret_x", "Content-Type": "application/json"}


def test_a_failure_after_the_project_exists_removes_the_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    discarded: list[str | None] = []

    class Prov(StubProvisioner):
        def discard(self, result: ProvisionResult) -> None:
            discarded.append(result.project_ref)

    monkeypatch.setattr(provisioning, "seed_square", lambda *a: None)

    def refuse(secrets: dict[str, str], owner: Owner) -> str:
        raise SupabaseApiError("Supabase answered 422 to POST /auth/v1/admin/users: nope")

    monkeypatch.setattr(provisioning, "create_square_auth_user", refuse)
    engine = create_engine(f"sqlite:///{tmp_path / 'd.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        org = Organization(name="Club")
        db.add(org)
        db.flush()
        sq = Square(org_id=org.id, name="First", slug="first-org", theme_id="paper-brick", status=SquareStatus.PROVISIONING)
        db.add(sq)
        db.commit()
        sq_id = sq.id
    provision_square(factory, make_settings(), sq_id, Owner(email="o@example.com", name="O", password_hash=None), Prov())
    with factory() as db:
        sq = db.get(Square, sq_id)
        assert sq is not None and sq.status == SquareStatus.FAILED and "422" in (sq.error or "")
    assert discarded == [REF]


# ---- Google sign-in on a square's project (flask enable-google) -------------------------------------------------------------------
def test_google_is_set_on_the_square_project_with_the_platform_client() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(method=request.method, url=str(request.url), auth=request.headers["authorization"], body=json.loads(request.content))
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    square_auth.set_google_login("pat", REF, "client-id", "client-secret", True, client)
    assert seen["method"] == "PATCH" and seen["url"] == f"https://api.supabase.com/v1/projects/{REF}/config/auth" and seen["auth"] == "Bearer pat"
    assert seen["body"] == {"external_google_enabled": True, "external_google_client_id": "client-id", "external_google_secret": "client-secret"}
    square_auth.set_google_login("pat", REF, "client-id", "client-secret", False, client)
    assert seen["body"] == {"external_google_enabled": False}  # switching off sends no secret
    assert square_auth.callback_url(REF) == f"https://{REF}.supabase.co/auth/v1/callback"


def test_enable_google_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import create_app

    settings = make_settings(
        DATABASE_URL=f"sqlite:///{tmp_path / 'g.db'}",
        PROVISIONER="supabase",
        SUPABASE_ACCESS_TOKEN="pat",
        SUPABASE_ORG_SLUG="o",
        GOOGLE_OAUTH_CLIENT_ID="cid",
        GOOGLE_OAUTH_CLIENT_SECRET="csecret",
    )
    app = create_app(settings)
    Base.metadata.create_all(app.extensions["db_engine"]())
    with app.extensions["db_factory"]()() as db:
        org = Organization(name="Club")
        db.add(org)
        db.flush()
        db.add(Square(org_id=org.id, name="First", slug="first-org", theme_id="paper-brick", status=SquareStatus.READY, provider_project_ref=REF))
        db.add(Square(org_id=org.id, name="Local", slug="local-sq", theme_id="paper-brick", status=SquareStatus.READY))
        db.commit()
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(square_auth, "set_google_login", lambda *args: calls.append(args))
    runner = app.test_cli_runner()

    declined = runner.invoke(args=["enable-google", "first-org"], input="n\n")
    assert declined.exit_code != 0 and f"https://{REF}.supabase.co/auth/v1/callback" in declined.output and calls == []

    done = runner.invoke(args=["enable-google", "first-org", "--yes"])
    assert done.exit_code == 0 and "switched on" in done.output and calls == [("pat", REF, "cid", "csecret", True)]
    with app.extensions["db_factory"]()() as db:
        assert db.scalar(select(Square.google_login).where(Square.slug == "first-org")) == "enabled"

    off = runner.invoke(args=["enable-google", "first-org", "--disable"])
    assert off.exit_code == 0 and calls[-1][-1] is False
    with app.extensions["db_factory"]()() as db:
        assert db.scalar(select(Square.google_login).where(Square.slug == "first-org")) == "requested"

    assert "No such square" in runner.invoke(args=["enable-google", "nope", "--yes"]).output
    assert "no Supabase project" in runner.invoke(args=["enable-google", "local-sq", "--yes"]).output


# ---- seed_square: the platform's admins table first, then the square app's own schema (W6-R35) -----------------------------------------
class _FakeConnection:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        self.log.append("admins table" if "create table" in sql else "first admin" if "insert into admins" in sql else sql)


def test_seed_square_makes_the_admins_table_then_runs_the_square_schema_command(monkeypatch: pytest.MonkeyPatch) -> None:
    steps: list[str] = []
    monkeypatch.setattr(provisioning.psycopg, "connect", lambda *a, **k: _FakeConnection(steps))

    def fake_run(command: str, shell: bool, env: dict[str, str], **kwargs: Any) -> Any:
        steps.append("command")
        assert command == "build-square-tables" and shell is True
        assert env["SQUARE_DATABASE_URL"] == "postgresql://u:p@h/db" and env["SQUARE_SLUG"] == "firstorg" and env["SQUARE_OWNER_EMAIL"] == "o@example.com"
        return type("Done", (), {"returncode": 0})()

    monkeypatch.setattr(provisioning.subprocess, "run", fake_run)
    provisioning.seed_square("postgresql://u:p@h/db", "firstorg", Owner(email="o@example.com", name="O", password_hash=None), "build-square-tables")
    assert steps == ["admins table", "first admin", "command"]  # the platform's table always comes first


def test_seed_square_without_a_command_only_makes_the_admins_table(monkeypatch: pytest.MonkeyPatch) -> None:
    steps: list[str] = []
    monkeypatch.setattr(provisioning.psycopg, "connect", lambda *a, **k: _FakeConnection(steps))
    monkeypatch.setattr(provisioning.subprocess, "run", lambda *a, **k: pytest.fail("no command is configured"))
    provisioning.seed_square("postgresql://u:p@h/db", "firstorg", Owner(email="o@example.com", name="O", password_hash=None), "")
    assert steps == ["admins table", "first admin"]


def test_a_failing_square_schema_command_fails_the_square_without_leaking_the_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provisioning.psycopg, "connect", lambda *a, **k: _FakeConnection([]))
    monkeypatch.setattr(provisioning.subprocess, "run", lambda *a, **k: type("Done", (), {"returncode": 3, "stderr": "boom postgresql://u:SECRET@h/db"})())
    with pytest.raises(RuntimeError) as error:
        provisioning.seed_square("postgresql://u:SECRET@h/db", "firstorg", Owner(email="o@example.com", name="O", password_hash=None), "x")
    assert "exit code 3" in str(error.value) and "SECRET" not in str(error.value)


def test_the_owner_is_linked_even_when_a_square_schema_command_is_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(provisioning, "seed_square", lambda url, slug, owner, cmd: seen.update(cmd=cmd))
    monkeypatch.setattr(provisioning, "create_square_auth_user", lambda secrets, owner: "auth-user-1")
    monkeypatch.setattr(provisioning, "link_owner", lambda url, email, auth_id: seen.update(linked=(email, auth_id)))
    engine = create_engine(f"sqlite:///{tmp_path / 'p.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        org = Organization(name="Club")
        db.add(org)
        db.flush()
        sq = Square(org_id=org.id, name="First", slug="firstorg", theme_id="paper-brick", status=SquareStatus.PROVISIONING)
        db.add(sq)
        db.commit()
        sq_id = sq.id
    owner = Owner(email="o@example.com", name="O", password_hash=None)
    provision_square(factory, make_settings(SQUARE_TEMPLATE_CMD="build-square-tables"), sq_id, owner, StubProvisioner())
    with factory() as db:
        assert db.get(Square, sq_id).status == SquareStatus.READY  # type: ignore[union-attr]
    assert seen["cmd"] == "build-square-tables" and seen["linked"] == ("o@example.com", "auth-user-1")


def test_template_command_default_for_real_providers() -> None:
    """W11-R34: a new square at a real provider gets the square app's tables without a hand-made setting."""
    from types import SimpleNamespace

    from app.platform.provisioning import template_command

    def cfg(provisioner: str, cmd: str = "") -> Any:
        return SimpleNamespace(PROVISIONER=provisioner, SQUARE_TEMPLATE_CMD=cmd)

    assert template_command(cfg("local")) == ""
    assert template_command(cfg("supabase", "mine")) == "mine"
    cmd = template_command(cfg("supabase"))
    assert cmd.endswith("upgrade-env") and "square_db.py" in cmd
