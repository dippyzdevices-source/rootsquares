"""Small unit tests that need no database: encryption, passwords, tokens, the Neon provisioner (mock transport, no network), rate limiter."""

from __future__ import annotations

import datetime as dt

import httpx
import pytest
from cryptography.fernet import Fernet

from app.platform.provisioning import NeonProvisioner
from app.platform.schemas import SquareIn
from app.providers.memory.rate_limiter import InMemoryRateLimiter
from app.shared.crypto import Encryptor, hash_password, make_token, read_token, verify_password
from tests.conftest import make_settings


def test_fernet_round_trip_and_wrong_key() -> None:
    enc = Encryptor(Fernet.generate_key().decode())
    token = enc.encrypt("postgresql://u:p@h/db")
    assert "postgresql" not in token and enc.decrypt(token) == "postgresql://u:p@h/db"
    with pytest.raises(ValueError):
        Encryptor(Fernet.generate_key().decode()).decrypt(token)


def test_argon2_password_hash() -> None:
    h = hash_password("correct-horse-1")
    assert h.startswith("$argon2") and verify_password(h, "correct-horse-1") and not verify_password(h, "nope")


def test_tokens_have_a_kind_and_expire() -> None:
    s = make_settings().jwt_secret
    ok = make_token(s, "u1", "access", dt.timedelta(minutes=1))
    assert read_token(s, ok, "access") and read_token(s, ok, "refresh") is None
    assert read_token(s, make_token(s, "u1", "access", dt.timedelta(minutes=-1)), "access") is None
    assert read_token("other-secret-other-secret-other-secret", ok, "access") is None


def _mock_neon(calls: list[tuple[str, str, object]], fail_on: str = "") -> httpx.Client:
    """A pretend Neon API: records (method, path, body) and answers like the real one does (see scripts/neon_check.py)."""
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v2")
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, path, body))
        assert request.headers["Authorization"] == "Bearer test-key"
        if fail_on and path.endswith(fail_on):
            return httpx.Response(400, json={"message": "no way"})
        if path == "/projects":
            return httpx.Response(201, json={"project": {"id": "proj-123"}, "connection_uris": [{"connection_uri": "postgresql://u:p@ep.neon.tech/neondb"}]})
        if path.endswith("/branches"):
            return httpx.Response(200, json={"branches": [{"id": "br-1"}]})
        if path.endswith("/auth"):
            return httpx.Response(201, json={"base_url": "https://ep-x.neonauth.aws.neon.tech/neondb/auth/", "jwks_url": "x"})
        if path.endswith("/storage"):
            return httpx.Response(200, json={"s3_endpoint": "https://br-1.storage.c-1.eu.aws.neon.tech/", "region": "eu-central-1", "force_path_style": True})
        if path.endswith("/credentials"):
            return httpx.Response(201, json={"token_id": "nak_1", "s3_secret_access_key": "nsk_1"})
        if path.endswith("/auth/users"):
            return httpx.Response(201, json={"id": "user-1"})
        return httpx.Response(201, json={})

    return httpx.Client(base_url=NeonProvisioner.API, transport=httpx.MockTransport(handler))


def test_neon_provisioner_makes_the_project_sign_in_and_storage() -> None:
    calls: list[tuple[str, str, object]] = []
    prov = NeonProvisioner("test-key", "aws-eu-central-1", _mock_neon(calls), site_suffix="rootsquares.com", extra_redirects=("http://{slug}.localhost:5274/**",))
    result = prov.create_database("my-square")
    assert result.neon_project_id == "proj-123" and result.branch_id == "br-1" and result.connection_url.startswith("postgresql://")
    assert calls[0] == ("POST", "/projects", {"project": {"name": "rootsquares-my-square", "region_id": "aws-eu-central-1"}})
    base = "/projects/proj-123/branches/br-1"
    assert ("POST", f"{base}/auth", {"auth_provider": "better_auth"}) in calls
    domains = [body["domain"] for method, path, body in calls if path == f"{base}/auth/domains"]  # type: ignore[index]
    assert domains == ["https://my-square.rootsquares.com", "http://my-square.localhost:5274"]
    buckets = [(body["name"], body["access_level"]) for method, path, body in calls if path == f"{base}/buckets"]  # type: ignore[index]
    assert buckets == [("public", "public_read"), ("private", "private")]
    assert result.secrets == {
        "auth_provider": "neon",
        "project_url": "https://ep-x.neonauth.aws.neon.tech/neondb/auth",
        "auth_url": "https://ep-x.neonauth.aws.neon.tech/neondb/auth",
        "neon_branch_id": "br-1",
        "s3_endpoint": "https://br-1.storage.c-1.eu.aws.neon.tech",
        "s3_region": "eu-central-1",
        "s3_access_key": "nak_1",
        "s3_secret_key": "nsk_1",
    }
    from app.platform.provisioning import Owner

    assert prov.create_auth_user(result, Owner(email="o@example.com", name="Owner", password_hash=None)) == "user-1"


def test_neon_provisioner_deletes_the_project_when_a_later_step_fails() -> None:
    from app.platform.provisioning import NeonApiError

    calls: list[tuple[str, str, object]] = []
    prov = NeonProvisioner("test-key", "aws-eu-central-1", _mock_neon(calls, fail_on="/buckets"))
    with pytest.raises(NeonApiError, match="HTTP 400 no way"):
        prov.create_database("my-square")
    assert calls[-1][0] == "DELETE" and calls[-1][1] == "/projects/proj-123"  # a failed square keeps no project


def test_rate_limiter_window() -> None:
    rl = InMemoryRateLimiter()
    assert [rl.allow("k", 2, 60) for _ in range(3)] == [True, True, False] and rl.allow("other", 2, 60)


@pytest.mark.parametrize("slug", ["ab", "-bad", "bad-", "has space", "a" * 41])
def test_bad_slugs(slug: str) -> None:
    with pytest.raises(ValueError):
        SquareIn(name="Name", slug=slug, theme_id="paper-brick")
    assert SquareIn(name="Name", slug="good-slug-1", theme_id="paper-brick").slug == "good-slug-1"



def test_neon_wake_waits_while_the_endpoint_is_locked() -> None:
    """Neon answers 423 Locked while the suspend is still running; the start is retried, any other refusal is raised (scripts/neon_check.py)."""
    calls: list[str] = []
    answers = iter([423, 423, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/endpoints"):
            return httpx.Response(200, json={"endpoints": [{"id": "ep-1"}]})
        calls.append(request.url.path)
        return httpx.Response(next(answers), json={})

    prov = NeonProvisioner("k", "aws-eu-central-1", httpx.Client(base_url=NeonProvisioner.API, transport=httpx.MockTransport(handler)))
    prov._endpoint_action("p-1", "ep-1", "start", sleep=lambda _s: None)
    assert calls == ["/api/v2/projects/p-1/endpoints/ep-1/start"] * 3

    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={})

    bad = NeonProvisioner("k", "aws-eu-central-1", httpx.Client(base_url=NeonProvisioner.API, transport=httpx.MockTransport(refuse)))
    with pytest.raises(httpx.HTTPStatusError):
        bad._endpoint_action("p-1", "ep-1", "suspend", sleep=lambda _s: None)



def _recording_neon(calls: list[tuple[str, str, object]], answers: dict[tuple[str, str], int]) -> NeonProvisioner:
    """A pretend Neon that answers each (method, last path word) with the given status (default 200) and records the calls."""
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v2")
        calls.append((request.method, path, json.loads(request.content) if request.content else None))
        status = answers.get((request.method, path.rsplit("/", 1)[-1]), 200)
        return httpx.Response(status, json={"message": "x"} if status >= 400 else {"success": True})

    return NeonProvisioner("test-key", "aws-eu-central-1", httpx.Client(base_url=NeonProvisioner.API, transport=httpx.MockTransport(handler)))


def test_neon_google_login_on_off_and_already_there() -> None:
    from app.platform.provisioning import NeonApiError

    calls: list[tuple[str, str, object]] = []
    prov = _recording_neon(calls, {})
    prov.set_google_login("p", "b", "cid", "csecret", True)  # the platform's own client
    prov.set_google_login("p", "b", "", "", True)  # Neon's shared development credentials: no client fields
    assert calls[0] == ("POST", "/projects/p/branches/b/auth/oauth_providers", {"id": "google", "client_id": "cid", "client_secret": "csecret"})
    assert calls[1][2] == {"id": "google"}
    calls.clear()
    again = _recording_neon(calls, {("POST", "oauth_providers"): 409})
    again.set_google_login("p", "b", "cid", "csecret", True)  # already there: its credentials are changed instead
    assert [c[0] for c in calls] == ["POST", "PATCH"] and calls[1][1].endswith("/oauth_providers/google")
    assert calls[1][2] == {"client_id": "cid", "client_secret": "csecret"}
    calls.clear()
    _recording_neon(calls, {("DELETE", "google"): 404}).set_google_login("p", "b", "", "", False)  # switching off what is already off is fine
    assert calls == [("DELETE", "/projects/p/branches/b/auth/oauth_providers/google", None)]
    with pytest.raises(NeonApiError):
        _recording_neon([], {("DELETE", "google"): 500}).set_google_login("p", "b", "", "", False)


def test_neon_trusted_addresses_and_email_sender() -> None:
    from app.platform import square_auth
    from app.platform.provisioning import mail_sender

    calls: list[tuple[str, str, object]] = []
    prov = _recording_neon(calls, {("POST", "domains"): 409})  # an address that is already trusted is not an error (Neon says 400 "already exists")
    assert prov.set_redirects("p", "b", ["https://a.example.com", "http://a.localhost:5274"]) == ["https://a.example.com", "http://a.localhost:5274"]
    assert len(calls) == 2
    assert square_auth.trusted_addresses("a", "rootsquares.com", ["http://{slug}.localhost:5274/**"]) == ["https://a.rootsquares.com", "http://a.localhost:5274"]
    assert square_auth.neon_callback_url("https://ep.neonauth.aws.neon.tech/neondb/auth/") == "https://ep.neonauth.aws.neon.tech/neondb/auth/callback/google"
    calls.clear()
    prov.set_email("p", "b", host="smtp.resend.com", port=465, username="resend", password="re_key", sender_email="no-reply@example.com", sender_name="Club")
    assert calls[0][0] == "PATCH" and calls[0][1].endswith("/auth/email_provider") and calls[0][2]["sender_name"] == "Club"  # type: ignore[index]
    sender = mail_sender(make_settings(EMAIL_PROVIDER="resend", RESEND_API_KEY="re_key", EMAIL_FROM="rootsquares <no-reply@example.com>"))
    assert sender == {"host": "smtp.resend.com", "port": 465, "username": "resend", "password": "re_key", "sender_email": "no-reply@example.com"}
    assert mail_sender(make_settings()) is None  # no platform e-mail: Neon's shared sender stays
