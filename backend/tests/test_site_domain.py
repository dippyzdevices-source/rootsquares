# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""A Grove square's own website domain (ADR 098): the domain is checked, only Grove may ask, the owner asks and staff activate, the DNS check, the host lookup,
the e-mails. No network: the DNS lookup is replaced and a recorder stands in for the e-mail service."""

import uuid

import httpx
import pytest
from flask import Flask

from app.platform import site_domain
from app.platform.models import Square, SquareStatus
from app.providers.render_domains import RenderApiError, RenderDomains
from app.shared.config import Settings
from app.shared.errors import ValidationFailedError
from tests.staff_client import as_admin
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)
from tests.test_mail_domain import STAFF, Outbox

TARGET = "squares.rootsquares.test"


def _setup(api: Flask) -> Outbox:
    box = Outbox()
    api.extensions["providers"].email = box
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"STAFF_NOTICE_EMAIL": STAFF, "CUSTOM_DOMAIN_TARGET": TARGET})
    return box


def _login(api: Flask, who: str):
    api.extensions["executor"] = RecordingExecutor()
    c = api.test_client()
    h = {**HEADERS, "Authorization": f"Bearer fake:u-{who}:{who}@example.com"}
    assert c.post(f"{PREFIX}/organizations", json={"name": f"Club {who}"}, headers=h).status_code == 201
    return c, h


def _square(c, h, slug: str, package: str = "grove") -> str:
    r = c.post(f"{PREFIX}/squares", json={"name": f"Club {slug}", "slug": slug, "theme_id": "paper-brick", "launch_package": package}, headers=h)
    assert r.status_code in (201, 202), r.json
    return r.json["id"]


def _set(api: Flask, sid: str, **fields) -> Square:
    """Change a square row directly (the public lookup serves only ready squares; a package is lost)."""
    with api.extensions["db_factory"]()() as db:
        sq = db.get(Square, uuid.UUID(sid))
        assert sq is not None
        for key, value in fields.items():
            setattr(sq, key, value)
        db.commit()
        db.refresh(sq)
        db.expunge(sq)
        return sq


def _url(sid: str, tail: str = "") -> str:
    return f"{PREFIX}/squares/{sid}/site-domain{tail}"


def _staff(sid: str, tail: str = "") -> str:
    return f"{PREFIX}/owner/squares/{sid}/site-domain{tail}"


def test_the_domain_is_checked_and_rootsquares_names_are_refused() -> None:
    s = Settings(SQUARE_DOMAIN_SUFFIX="rootsquares.com", CUSTOM_DOMAIN_TARGET="squares.rootsquares.com")
    assert site_domain.clean_domain(" WWW.BCA-Oslo.org. ", s) == "www.bca-oslo.org"
    for bad in ("", "no-dot", "https://x.org", "a@b.org", "x y.org", "x.org:443", "rootsquares.com", "club.rootsquares.com", "squares.rootsquares.com"):
        with pytest.raises(ValidationFailedError):
            site_domain.clean_domain(bad, s)


def test_dns_state_compares_the_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    table = {"www.club.no": {"1.2.3.4"}, "other.club.no": {"9.9.9.9"}, TARGET: {"1.2.3.4", "5.6.7.8"}}
    monkeypatch.setattr(site_domain, "_addresses", lambda host: table.get(host))
    assert site_domain.dns_state("www.club.no", TARGET) == "pointing"
    assert site_domain.dns_state("other.club.no", TARGET) == "not_pointing"
    assert site_domain.dns_state("missing.club.no", TARGET) == "unknown"


def test_only_grove_may_ask(api: Flask) -> None:
    _setup(api)
    c, h = _login(api, "sd1")
    grove, lower = _square(c, h, "sd-grove"), _square(c, h, "sd-square", "square")
    got = c.get(_url(grove), headers=h).json
    assert got["allowed"] is True and got["target"] == TARGET and got["state"] == "none"
    assert c.get(_url(lower), headers=h).json["allowed"] is False
    r = c.post(_url(lower, "/request"), json={"domain": "www.club.no"}, headers=h)
    assert r.status_code == 403 and r.json["code"] == "package_required"


def test_the_whole_flow_request_activate_serve_check_remove(api: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    box = _setup(api)
    c, h = _login(api, "sd2")
    sid = _square(c, h, "sd-flow")
    _set(api, sid, status=SquareStatus.READY)  # the public lookup serves only ready squares
    # 1. the owner asks: staff get an e-mail, nothing is served yet
    r = c.post(_url(sid, "/request"), json={"domain": "WWW.Club.no"}, headers=h)
    assert r.status_code == 200 and r.json["state"] == "requested" and r.json["requested_domain"] == "www.club.no"
    notice = box.to(STAFF)
    assert len(notice) == 1 and "Own website domain requested" in notice[0][1] and "www.club.no" in notice[0][2]
    assert c.get(f"{PREFIX}/public/hosts/www.club.no").status_code == 404
    # staff see the request in the Needs attention list until it is answered
    ca = as_admin(api, c)
    listed = [i for i in ca.get(f"{PREFIX}/owner/attention", headers=h).json["items"] if i["square_id"] == sid and i["kind"] == "site_domain_requested"]
    assert len(listed) == 1 and listed[0]["detail"] == "www.club.no"
    # a second request is refused while one is open; a customer cannot reach the staff routes
    assert c.post(_url(sid, "/request"), json={"domain": "www.other.no"}, headers=h).json["code"] == "site_domain_exists"
    assert c.post(_staff(sid, "/activate"), json={}, headers=h).status_code == 404
    # 2. the owner looks the DNS up (a replaced lookup, no network)
    monkeypatch.setattr(site_domain, "_addresses", lambda host: {"1.2.3.4"} if host in ("www.club.no", TARGET) else None)
    assert c.post(_url(sid, "/check"), headers=h).json["dns"] == "pointing"
    # 3. staff activate: the square is served on the domain and on its own address, the owner is told
    r = ca.post(_staff(sid, "/activate"), json={}, headers=h)
    assert r.status_code == 200 and r.json["state"] == "active" and r.json["domain"] == "www.club.no" and r.json["requested_domain"] is None
    told = box.to("sd2@example.com")
    assert len(told) == 1 and "Your own domain is ready" in told[0][1] and "www.club.no" in told[0][2]
    own = c.get(f"{PREFIX}/public/hosts/www.club.no")
    assert own.status_code == 200 and own.json["slug"] == "sd-flow"
    default = _set(api, sid).domain
    assert c.get(f"{PREFIX}/public/hosts/{default}").status_code == 200
    # 4. a lost package stops the serving and keeps the data
    kept = _set(api, sid, launch_package="square")
    assert c.get(f"{PREFIX}/public/hosts/www.club.no").status_code == 404 and kept.site_domain == "www.club.no"
    _set(api, sid, launch_package="grove")
    # 5. the owner removes it: not served, staff are told to remove it on the host
    r = c.delete(_url(sid), headers=h)
    assert r.status_code == 200 and r.json["state"] == "none"
    assert c.get(f"{PREFIX}/public/hosts/www.club.no").status_code == 404
    assert "Own website domain removed" in box.to(STAFF)[-1][1]


def test_withdraw_reject_and_a_domain_used_by_another_square(api: Flask) -> None:
    box = _setup(api)
    c, h = _login(api, "sd3")
    first, second = _square(c, h, "sd-one"), _square(c, h, "sd-two")
    assert c.post(_url(first, "/request"), json={"domain": "www.club.no"}, headers=h).status_code == 200
    r = c.post(_url(second, "/request"), json={"domain": "www.club.no"}, headers=h)
    assert r.status_code == 409 and r.json["code"] == "site_domain_taken"
    assert c.delete(_url(first, "/request"), headers=h).json["state"] == "none"
    assert c.post(_url(second, "/request"), json={"domain": "www.club.no"}, headers=h).status_code == 200
    ca = as_admin(api, c)
    r = ca.post(_staff(second, "/reject"), json={"note": "Not a domain we can reach"}, headers=h)
    assert r.status_code == 200 and r.json["state"] == "none"
    told = box.to("sd3@example.com")
    assert len(told) == 1 and "Not a domain we can reach" in told[0][2]
    assert ca.post(_staff(second, "/reject"), json={}, headers=h).json["code"] == "site_domain_missing"


SERVICE = "srv-abc123def"


def test_the_render_calls_use_the_documented_addresses_and_never_show_the_key() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST" and request.url.path.endswith("/custom-domains"):
            return httpx.Response(201, json=[{"id": "cdm-1", "name": "www.club.no", "verificationStatus": "unverified"}, {"id": "cdm-2", "name": "club.no"}])
        if request.method == "POST" and request.url.path.endswith("/verify"):
            return httpx.Response(202)
        if request.method == "DELETE":
            return httpx.Response(204)
        if "missing" in request.url.path:
            return httpx.Response(404, json={"id": "x", "message": "domain not found"})
        return httpx.Response(200, json={"id": "cdm-1", "name": "www.club.no", "verificationStatus": "verified"})

    client = RenderDomains("rnd_secret", SERVICE, httpx.Client(transport=httpx.MockTransport(handler)))
    assert [d["name"] for d in client.create("WWW.Club.no")] == ["www.club.no", "club.no"]
    client.verify("www.club.no")
    assert client.get("www.club.no")["verificationStatus"] == "verified"
    client.delete("www.club.no")
    base = f"/v1/services/{SERVICE}/custom-domains"
    assert [(r.method, r.url.path) for r in seen] == [
        ("POST", base),
        ("POST", f"{base}/www.club.no/verify"),
        ("GET", f"{base}/www.club.no"),
        ("DELETE", f"{base}/www.club.no"),
    ]
    assert seen[0].headers["authorization"] == "Bearer rnd_secret" and seen[0].content == b'{"name":"www.club.no"}'
    with pytest.raises(RenderApiError) as err:
        client.get("missing.club.no")
    assert err.value.status == 404 and "not found" in str(err.value) and "rnd_secret" not in str(err.value)
    for bad in ("../x", "a b.org", "no-dot", ""):
        with pytest.raises(RenderApiError):
            client.get(bad)  # a name that is not a domain never reaches the address
    with pytest.raises(RenderApiError):
        RenderDomains("k", "../services")


class FakeRender:
    """What Render answers, in the shape of its reference; `domains` is what it holds, `fail` makes one call answer with a status."""

    def __init__(self) -> None:
        self.domains: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []
        self.fail: tuple[str, int] | None = None

    def _go(self, what: str, name: str) -> None:
        self.calls.append((what, name))
        if self.fail and self.fail[0] == what:
            raise RenderApiError("Render refused: payment required", self.fail[1])

    def create(self, name: str) -> list[dict]:
        self._go("create", name)
        self.domains[name] = "unverified"
        return [{"name": name}]

    def verify(self, name: str) -> None:
        self._go("verify", name)

    def get(self, name: str) -> dict:
        self._go("get", name)
        if name not in self.domains:
            raise RenderApiError("not found", 404)
        return {"name": name, "verificationStatus": self.domains[name]}

    def delete(self, name: str) -> None:
        self._go("delete", name)
        if name not in self.domains:
            raise RenderApiError("not found", 404)
        del self.domains[name]


def test_with_the_render_key_activate_adds_the_domain_and_remove_deletes_it(api: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(api)
    fake = FakeRender()
    api.extensions["render_domains"] = fake
    monkeypatch.setattr(site_domain, "_addresses", lambda host: {"1.2.3.4"})
    c, h = _login(api, "sd5")
    sid = _square(c, h, "sd-render")
    assert c.post(_url(sid, "/request"), json={"domain": "www.club.no"}, headers=h).status_code == 200
    ca = as_admin(api, c)
    # before: Render does not hold it; the staff view says so
    assert ca.get(_staff(sid), headers=h).json["render"] == "not_added"
    # a refusal by Render (payment required) is shown, and nothing is saved: the request stays
    fake.fail = ("create", 402)
    r = ca.post(_staff(sid, "/activate"), json={}, headers=h)
    assert r.status_code == 502 and r.json["code"] == "site_domain_host_error" and "payment required" in r.json["detail"]
    assert ca.get(_staff(sid), headers=h).json["state"] == "requested"
    fake.fail = None
    # activate adds it on Render, asks Render to verify, and saves the domain
    r = ca.post(_staff(sid, "/activate"), json={}, headers=h)
    assert r.status_code == 200 and r.json["state"] == "active" and r.json["render"] == "unverified"
    assert ("create", "www.club.no") in fake.calls and ("verify", "www.club.no") in fake.calls
    # staff check asks Render again; once Render says verified the card says so
    fake.domains["www.club.no"] = "verified"
    assert ca.post(_staff(sid, "/check"), headers=h).json["render"] == "verified"
    # the customer API never asks Render (the key is not there): the owner's view says off
    assert c.get(_url(sid), headers=h).json["render"] == "off"
    # remove deletes the domain and its twin (the twin is not on Render: 404 is fine) and clears the square
    r = ca.delete(_staff(sid), headers=h)
    assert r.status_code == 200 and r.json["state"] == "none"
    assert ("delete", "www.club.no") in fake.calls and ("delete", "club.no") in fake.calls and fake.domains == {}


def test_a_refused_delete_keeps_the_domain(api: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(api)
    fake = FakeRender()
    api.extensions["render_domains"] = fake
    c, h = _login(api, "sd6")
    sid = _square(c, h, "sd-keep")
    c.post(_url(sid, "/request"), json={"domain": "www.keep.no"}, headers=h)
    ca = as_admin(api, c)
    assert ca.post(_staff(sid, "/activate"), json={}, headers=h).status_code == 200
    fake.fail = ("delete", 500)
    assert ca.delete(_staff(sid), headers=h).status_code == 502
    assert ca.get(_staff(sid), headers=h).json["state"] == "active"


def test_the_owner_can_ask_for_it_help_and_staff_see_it(api: Flask) -> None:
    box = _setup(api)
    c, h = _login(api, "sd7")
    sid = _square(c, h, "sd-help")
    assert c.get(_url(sid), headers=h).json["help_requested"] is False
    assert c.post(_url(sid, "/request"), json={"domain": "www.help.no"}, headers=h).status_code == 200
    r = c.post(_url(sid, "/help"), headers=h)
    assert r.status_code == 200 and r.json["help_requested"] is True
    mail = [m for m in box.to(STAFF) if "IT help asked" in m[1]]
    assert len(mail) == 1 and "www.help.no" in mail[0][2] and "one-time support fee" in mail[0][2]
    ca = as_admin(api, c)
    kinds = [i["kind"] for i in ca.get(f"{PREFIX}/owner/attention", headers=h).json["items"] if i["square_id"] == sid]
    assert "site_domain_help" in kinds and "site_domain_requested" in kinds
    # withdrawing the request ends the call for help
    assert c.delete(_url(sid, "/request"), headers=h).json["help_requested"] is False
    kinds = [i["kind"] for i in ca.get(f"{PREFIX}/owner/attention", headers=h).json["items"] if i["square_id"] == sid]
    assert "site_domain_help" not in kinds
    # a square below Grove cannot ask
    low = _square(c, h, "sd-help-low", "square")
    assert c.post(_url(low, "/help"), headers=h).status_code == 403
