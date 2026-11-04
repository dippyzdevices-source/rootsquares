# ruff: noqa: F811  (the `api` fixture is imported from another test module, so test arguments shadow it)
"""A Grove square's own sending domain (ADR 091, 095): the Resend calls, the package gate, the owner's request, staff's approval, the e-mails, the hourly job.
No network: a fake stands in for Resend and a recorder for the e-mail service."""

import httpx
import pytest
from flask import Flask

from app.platform import mail_domain
from app.platform.models import Square
from app.providers.resend_domains import DomainApiError, ResendDomains
from app.shared.config import Settings
from app.shared.errors import ValidationFailedError
from tests.staff_client import as_admin
from tests.test_auth_storage import HEADERS, PREFIX, RecordingExecutor, api  # noqa: F401  (api: the app fixture)

DOMAIN_ID = "11111111-1111-1111-1111-111111111111"


class FakeDomains:
    """What Resend answers, in the shape of its reference; `status` is what a check will read."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.status = "not_started"
        self.fail_on: str | None = None

    def _go(self, what: str, arg: str) -> None:
        self.calls.append((what, arg))
        if self.fail_on == what:
            raise DomainApiError("The domain is already registered", 409)

    def create(self, name: str) -> dict:
        self._go("create", name)
        rec = {"record": "DKIM", "type": "TXT", "name": "resend._domainkey.mail", "value": "p=abc", "status": "not_started", "ttl": "Auto"}
        return {"id": DOMAIN_ID, "status": "not_started", "records": [rec]}

    def verify(self, domain_id: str) -> dict:
        self._go("verify", domain_id)
        return {"object": "domain", "id": domain_id}

    def get(self, domain_id: str) -> dict:
        self._go("get", domain_id)
        return {
            "status": self.status,
            "records": [{"record": "DKIM", "type": "TXT", "name": "resend._domainkey.mail", "value": "p=abc", "status": self.status}],
        }

    def delete(self, domain_id: str) -> dict:
        self._go("delete", domain_id)
        return {"object": "domain", "id": domain_id, "deleted": True}


class Outbox:
    """The e-mail service of the platform: keeps what was sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to, subject, body, html=None, inline_images=None):
        self.sent.append((to, subject, body))

    def to(self, address: str) -> list[tuple[str, str, str]]:
        return [m for m in self.sent if m[0] == address]


STAFF = "hello@rootsquares.test"


def _setup(api: Flask, fake: FakeDomains | None = None, auto: bool = False) -> tuple[FakeDomains, Outbox]:
    fake = fake or FakeDomains()
    box = Outbox()
    api.extensions["resend_domains"] = fake
    api.extensions["providers"].email = box
    api.extensions["settings"] = api.extensions["settings"].model_copy(update={"STAFF_NOTICE_EMAIL": STAFF, "MAIL_DOMAIN_AUTO_APPROVE": auto})
    return fake, box


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


def _url(sid: str, tail: str = "") -> str:
    return f"{PREFIX}/squares/{sid}/mail-domain{tail}"


def _staff(sid: str, tail: str = "") -> str:
    return f"{PREFIX}/owner/squares/{sid}/mail-domain{tail}"


def test_the_resend_calls_use_the_documented_addresses_and_show_resends_own_message() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST" and request.url.path == "/domains":
            return httpx.Response(422, json={"name": "validation_error", "message": "The domain name is invalid"})
        return httpx.Response(200, json={"id": DOMAIN_ID})

    client = ResendDomains("re_full", "eu-west-1", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(DomainApiError) as err:
        client.create("bad")
    assert err.value.status == 422 and "invalid" in str(err.value) and "re_full" not in str(err.value)
    assert seen[0].headers["authorization"] == "Bearer re_full" and b'"region":"eu-west-1"' in seen[0].content.replace(b" ", b"")
    client.verify(DOMAIN_ID)
    client.get(DOMAIN_ID)
    client.delete(DOMAIN_ID)
    assert [(r.method, r.url.path) for r in seen[1:]] == [
        ("POST", f"/domains/{DOMAIN_ID}/verify"),
        ("GET", f"/domains/{DOMAIN_ID}"),
        ("DELETE", f"/domains/{DOMAIN_ID}"),
    ]
    with pytest.raises(DomainApiError):
        client.get("../../api-keys")  # an id that is not an id never reaches the URL


def test_domain_and_name_are_checked_and_the_platforms_own_domain_is_refused() -> None:
    s = Settings(SQUARE_DOMAIN_SUFFIX="rootsquares.com", EMAIL_FROM="rootsquares <hello@mail.rootsquares.com>")
    assert mail_domain.clean_domain(" Mail.BCAOslo.no. ", s) == "mail.bcaoslo.no"
    for bad in ("", "no-dot", "https://x.org", "a@b.org", "x y.org", "rootsquares.com", "mail.rootsquares.com", "club.rootsquares.com"):
        with pytest.raises(ValidationFailedError):
            mail_domain.clean_domain(bad, s)
    assert mail_domain.clean_local("Tickets") == "tickets" and mail_domain.clean_local("") == "hello"
    for bad in ("a b", "-x", "a@b", "x" * 70):
        with pytest.raises(ValidationFailedError):
            mail_domain.clean_local(bad)


def test_only_grove_may_ask_and_the_request_needs_no_key(api: Flask) -> None:
    fake, box = _setup(api)
    api.extensions["resend_domains"] = None  # no full access key: asking still works, setting up does not
    c, h = _login(api, "md1")
    grove, lower = _square(c, h, "md-grove"), _square(c, h, "md-square", "square")
    assert c.get(_url(grove), headers=h).json["allowed"] is True and c.get(_url(lower), headers=h).json["allowed"] is False
    r = c.post(_url(lower, "/request"), json={"domain": "mail.club.no"}, headers=h)
    assert r.status_code == 403 and r.json["code"] == "package_required"
    r = c.post(_url(grove, "/request"), json={"domain": "mail.club.no", "local_part": "Tickets"}, headers=h)
    assert r.status_code == 200 and r.json["state"] == "requested" and r.json["requested_domain"] == "mail.club.no" and r.json["requested_local"] == "tickets"
    ca = as_admin(api, c)
    r = ca.post(_staff(grove, "/approve"), json={}, headers=h)
    assert r.status_code == 503 and r.json["code"] == "mail_domain_not_ready"


def test_the_whole_flow_request_approve_records_check_name_remove(api: Flask) -> None:
    fake, box = _setup(api)
    c, h = _login(api, "md2")
    sid = _square(c, h, "md-flow")
    # 1. the owner asks: nothing is registered, staff get an e-mail
    r = c.post(_url(sid, "/request"), json={"domain": "mail.club.no", "local_part": "tickets"}, headers=h)
    assert r.json["state"] == "requested" and fake.calls == []
    notice = box.to(STAFF)
    assert len(notice) == 1 and "Own sending domain requested" in notice[0][1] and "tickets@mail.club.no" in notice[0][2]
    # a customer cannot reach the staff routes
    assert c.post(_staff(sid, "/approve"), json={}, headers=h).status_code == 404
    # 2. staff set it up: the domain is registered at Resend, the request is cleared, the owner is told
    ca = as_admin(api, c)
    r = ca.post(_staff(sid, "/approve"), json={}, headers=h)
    assert r.status_code == 200 and r.json["state"] == "registered" and r.json["domain"] == "mail.club.no" and r.json["requested_domain"] is None
    assert fake.calls == [("create", "mail.club.no")] and r.json["records"][0]["type"] == "TXT"
    told = box.to("md2@example.com")
    assert len(told) == 1 and "one step for you" in told[0][1] and "mail.club.no" in told[0][2]
    # the owner sends the records to the person who looks after the domain
    r = c.post(_url(sid, "/instructions"), json={"to": "web@example.org"}, headers=h)
    assert r.status_code == 200
    web = box.to("web@example.org")
    assert len(web) == 1 and "resend._domainkey.mail" in web[0][2] and "Type: TXT" in web[0][2] and "mail.club.no" in web[0][1]
    # 3. the owner checks: Resend finds the DNS
    fake.status = "verified"
    r = c.post(_url(sid, "/check"), headers=h)
    assert r.json["state"] == "verified" and r.json["from_address"] == "tickets@mail.club.no" and ("verify", DOMAIN_ID) in fake.calls
    # 4. the name before the @ changes without Resend
    before = len(fake.calls)
    assert c.put(_url(sid, "/name"), json={"local_part": "Info"}, headers=h).json["from_address"] == "info@mail.club.no" and len(fake.calls) == before
    # 5. the owner removes it: deleted at Resend, back to nothing
    r = c.delete(_url(sid), headers=h)
    assert r.json["state"] == "none" and r.json["domain"] is None and ("delete", DOMAIN_ID) in fake.calls
    assert c.post(_url(sid, "/check"), headers=h).status_code == 409


def test_staff_can_turn_a_request_down_and_the_owner_can_withdraw_it(api: Flask) -> None:
    fake, box = _setup(api)
    c, h = _login(api, "md3")
    sid = _square(c, h, "md-no")
    c.post(_url(sid, "/request"), json={"domain": "mail.club.no"}, headers=h)
    ca = as_admin(api, c)
    r = ca.post(_staff(sid, "/reject"), json={"note": "That domain is not yours"}, headers=h)
    assert r.json["state"] == "none" and r.json["requested_domain"] is None and fake.calls == []
    told = box.to("md3@example.com")
    assert len(told) == 1 and "That domain is not yours" in told[0][2]
    assert ca.post(_staff(sid, "/reject"), json={}, headers=h).status_code == 409  # nothing left to turn down
    c.post(_url(sid, "/request"), json={"domain": "mail.club.no"}, headers=h)
    assert c.delete(_url(sid, "/request"), headers=h).json["state"] == "none"


def test_a_domain_cannot_be_shared_and_a_refusal_by_resend_is_explained(api: Flask) -> None:
    fake, box = _setup(api)
    c, h = _login(api, "md4")
    a, b = _square(c, h, "md-a"), _square(c, h, "md-b")
    assert c.post(_url(a, "/request"), json={"domain": "mail.one.no"}, headers=h).status_code == 200
    r = c.post(_url(b, "/request"), json={"domain": "mail.one.no"}, headers=h)  # already asked for by another square
    assert r.status_code == 409 and r.json["code"] == "mail_domain_taken"
    assert c.post(_url(a, "/request"), json={"domain": "mail.one.no"}, headers=h).status_code == 200  # the same square may ask again
    c.post(_url(b, "/request"), json={"domain": "mail.two.no"}, headers=h)
    ca = as_admin(api, c)
    fake.fail_on = "create"
    r = ca.post(_staff(b, "/approve"), json={}, headers=h)
    assert r.status_code == 502 and "already registered" in r.json["detail"]
    assert ca.get(_staff(b), headers=h).json["domain"] is None  # nothing half-saved
    fake.fail_on = None
    assert ca.post(_staff(b, "/approve"), json={}, headers=h).status_code == 200
    r = c.post(_url(b, "/request"), json={"domain": "mail.three.no"}, headers=h)  # it already has a domain
    assert r.status_code == 409 and r.json["code"] == "mail_domain_exists"


def test_the_owner_can_ask_for_help_and_staff_are_told(api: Flask) -> None:
    fake, box = _setup(api)
    c, h = _login(api, "md5")
    sid = _square(c, h, "md-help")
    c.put(f"{PREFIX}/squares/{sid}/mail-contact", json={"email": "club@example.org"}, headers=h)
    r = c.post(_url(sid, "/help"), headers=h)
    assert r.status_code == 200 and r.json["help_requested"] is True
    mails = box.to(STAFF)
    assert len(mails) == 1 and "IT help asked" in mails[0][1] and "small one-time support fee" in mails[0][2] and "club@example.org" in mails[0][2]
    # the help request belongs to the domain: removing the domain, withdrawing or turning down the request clears it (W25-R33)
    c.post(_url(sid, "/request"), json={"domain": "mail.club.no"}, headers=h)
    assert c.delete(_url(sid, "/request"), headers=h).json["help_requested"] is False
    c.post(_url(sid, "/request"), json={"domain": "mail.club.no"}, headers=h)
    assert c.post(_url(sid, "/help"), headers=h).json["help_requested"] is True
    ca = as_admin(api, c)
    assert ca.post(_staff(sid, "/approve"), json={}, headers=h).json["help_requested"] is True  # still wanted while it is being set up
    assert c.delete(_url(sid), headers=h).json["help_requested"] is False


def test_staff_see_what_waits_for_them_and_an_item_goes_when_it_is_handled(api: Flask) -> None:
    """W25-R33: `GET /owner/attention` lists the request and the help ask; handling them removes them."""
    _setup(api)
    c, h = _login(api, "md9")
    sid = _square(c, h, "md-att")
    assert c.get(f"{PREFIX}/owner/attention", headers=h).status_code == 404  # a customer cannot see it
    ca = as_admin(api, c)

    def mine() -> list[str]:
        r = ca.get(f"{PREFIX}/owner/attention", headers=h)
        assert r.status_code == 200 and r.json["count"] == len(r.json["items"])
        return [i["kind"] for i in r.json["items"] if i["square_id"] == sid]

    assert mine() == []
    c.post(_url(sid, "/request"), json={"domain": "mail.club.no"}, headers=h)
    c.post(_url(sid, "/help"), headers=h)
    assert mine() == ["mail_domain_requested", "mail_domain_help"]
    item = [i for i in ca.get(f"{PREFIX}/owner/attention", headers=h).json["items"] if i["kind"] == "mail_domain_requested"][0]
    assert item["detail"] == "mail.club.no" and item["slug"] == "md-att"
    ca.post(_staff(sid, "/approve"), json={}, headers=h)  # set up: the request is handled, the help ask stays until the domain works
    assert mine() == ["mail_domain_help"]
    c.delete(_url(sid), headers=h)  # removed: the help ask belongs to the domain
    assert mine() == []


def test_the_owner_sees_what_waits_for_them_and_nobody_else_does(api: Flask) -> None:
    """W25-R35: `GET /attention` (customer API) lists the records to add, or a failed domain; verified or removed, the item is gone."""
    fake, _ = _setup(api)
    c, h = _login(api, "md10")
    sid = _square(c, h, "md-mine")

    def mine(client=c, headers=h) -> list[tuple[str, str | None]]:
        r = client.get(f"{PREFIX}/attention", headers=headers)
        assert r.status_code == 200 and r.json["count"] == len(r.json["items"])
        return [(i["kind"], i["detail"]) for i in r.json["items"]]

    assert mine() == []
    c.post(_url(sid, "/request"), json={"domain": "mail.club.no"}, headers=h)
    assert mine() == []  # asked, staff will set it up: nothing for the owner to do yet
    as_admin(api, api.test_client()).post(_staff(sid, "/approve"), json={}, headers=h)
    assert mine() == [("mail_domain_records", "mail.club.no")]
    fake.status = "failed"
    c.post(_url(sid, "/check"), headers=h)
    assert mine() == [("mail_domain_failed", "mail.club.no")]
    fake.status = "verified"
    c.post(_url(sid, "/check"), headers=h)
    assert mine() == []
    c2, h2 = _login(api, "md11")  # another customer
    assert mine(c2, h2) == []
    assert api.test_client().get(f"{PREFIX}/attention").status_code == 401


def test_the_hourly_job_updates_the_status_and_tells_the_owner_once(api: Flask) -> None:
    fake, box = _setup(api)
    c, h = _login(api, "md6")
    sid = _square(c, h, "md-job")
    c.post(_url(sid, "/request"), json={"domain": "mail.club.no", "local_part": "tickets"}, headers=h)
    as_admin(api, c).post(_staff(sid, "/approve"), json={}, headers=h)
    box.sent.clear()
    settings = api.extensions["settings"]

    def run(apply: bool):
        db = api.extensions["db_factory"]()()
        try:
            with api.app_context():  # the command line runs inside the application too
                actions = mail_domain.run(db, fake, settings, apply)
            db.commit()
            return actions
        finally:
            db.close()

    assert run(True) == []  # nothing changed at Resend: nothing to do
    fake.status = "verified"
    assert [a["now"] for a in run(False)] == ["verified"] and box.sent == []  # a dry run changes and sends nothing
    assert run(True)[0]["notice"] == "ready"
    ready = box.to("md6@example.com")
    assert len(ready) == 1 and "is ready" in ready[0][1] and "tickets@mail.club.no" in ready[0][2]
    assert run(True) == [] and len(box.sent) == 1  # told once
    fake.status = "temporary_failure"  # a verified domain Resend cannot see any more: the square stops using it
    assert run(True)[0]["now"] == "temporary_failure"
    db = api.extensions["db_factory"]()()
    try:
        assert db.query(Square).filter(Square.slug == "md-job").one().mail_domain_status == "temporary_failure"
    finally:
        db.close()
    fake.status = "failed"
    assert run(True)[0]["notice"] == "failed" and len(box.to("md6@example.com")) == 2
    assert run(True) == [] and len(box.to("md6@example.com")) == 2  # the failure is told once too


def test_another_customer_cannot_see_or_change_it(api: Flask) -> None:
    _setup(api)
    c, h = _login(api, "md7")
    sid = _square(c, h, "md-private")
    c2, h2 = _login(api, "md8")
    assert c2.get(_url(sid), headers=h2).status_code == 404
    assert c2.post(_url(sid, "/request"), json={"domain": "mail.thief.no"}, headers=h2).status_code == 404
    assert c2.post(_url(sid, "/help"), headers=h2).status_code == 404


def test_with_automatic_approval_a_request_is_set_up_at_once(api: Flask) -> None:
    fake, box = _setup(api, auto=True)
    c, h = _login(api, "md9")
    sid = _square(c, h, "md-auto")
    assert c.get(_url(sid), headers=h).json["auto_approve"] is True
    r = c.post(_url(sid, "/request"), json={"domain": "mail.club.no", "local_part": "tickets"}, headers=h)
    assert r.status_code == 200 and r.json["state"] == "registered" and r.json["domain"] == "mail.club.no" and r.json["requested_domain"] is None
    assert fake.calls == [("create", "mail.club.no")] and r.json["records"][0]["type"] == "TXT"
    owner = box.to("md9@example.com")
    assert len(owner) == 1 and "one step for you" in owner[0][1]
    staff = box.to(STAFF)
    assert len(staff) == 1 and "Own sending domain set up" in staff[0][1] and "tickets@mail.club.no" in staff[0][2]  # staff are told, nothing waits for them
    fake.status = "verified"
    assert c.post(_url(sid, "/check"), headers=h).json["state"] == "verified"


def test_automatic_approval_shows_resends_refusal_and_saves_nothing_and_waits_without_a_key(api: Flask) -> None:
    fake, box = _setup(api, auto=True)
    c, h = _login(api, "md10")
    sid = _square(c, h, "md-auto2")
    fake.fail_on = "create"
    r = c.post(_url(sid, "/request"), json={"domain": "mail.club.no"}, headers=h)
    assert r.status_code == 502 and "already registered" in r.json["detail"]
    d = c.get(_url(sid), headers=h).json
    assert d["state"] == "none" and d["requested_domain"] is None  # nothing half-saved
    api.extensions["resend_domains"] = None  # no key: the request waits for staff
    r = c.post(_url(sid, "/request"), json={"domain": "mail.club.no"}, headers=h)
    assert r.status_code == 200 and r.json["state"] == "requested"
    assert any("Own sending domain requested" in m[1] for m in box.to(STAFF))
