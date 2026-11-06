# ruff: noqa: E501
"""render_sites.py (scripts/render_sites.py): suspend or resume the three staging sites on Render. Tested against a fake Render API on a free local port: it only touches the three sites, asks before changing, and never prints the key."""
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("render_sites", REPO / "scripts" / "render_sites.py")
rs = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(rs)  # type: ignore[union-attr]

KEY = "KEYVALUE-for-the-test-0123456789"


class Fake:
    """A stand-in for api.render.com: a few services, the calls it received, a key to accept."""

    def __init__(self):
        self.calls: list[tuple[str, str, str | None]] = []  # method, path, authorization
        self.services = {
            "srv-plat": {"id": "srv-plat", "name": "rootsquares-platform-site-staging", "suspended": "suspended", "autoDeploy": "no"},
            "srv-admin": {"id": "srv-admin", "name": "rootsquares-admin-site-staging", "suspended": "suspended", "autoDeploy": "yes"},
            "srv-sq": {"id": "srv-sq", "name": "rootsquares-square-site-staging", "suspended": "suspended", "autoDeploy": "no"},
            "srv-api": {"id": "srv-api", "name": "rootsquares-platform-api-staging", "suspended": "not_suspended", "autoDeploy": "no"},
        }
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None):
                body = json.dumps(obj if obj is not None else {}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _handle(self, method):
                n = int(self.headers.get("Content-Length") or 0)
                if n:
                    self.rfile.read(n)
                auth = self.headers.get("Authorization")
                fake.calls.append((method, self.path, auth))
                if auth != "Bearer " + KEY:
                    return self._send(401, {"message": "Unauthorized"})
                path = self.path.split("?")[0]
                if method == "GET" and path == "/services":
                    return self._send(200, [{"service": s, "cursor": "c" + s["id"]} for s in fake.services.values()])
                parts = path.strip("/").split("/")
                if len(parts) >= 2 and parts[0] == "services" and parts[1] in fake.services:
                    svc = fake.services[parts[1]]
                    if method == "GET" and len(parts) == 2:
                        return self._send(200, svc)
                    if method == "POST" and parts[2:] == ["suspend"]:
                        svc["suspended"] = "suspended"
                        return self._send(202)
                    if method == "POST" and parts[2:] == ["resume"]:
                        svc["suspended"] = "not_suspended"
                        return self._send(202)
                    if method == "POST" and parts[2:] == ["deploys"]:
                        return self._send(201, {"id": "dep-1"})
                self._send(404, {"message": "not found"})

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def posts(self) -> list[str]:
        return [p for m, p, _ in self.calls if m == "POST"]

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture
def fake():
    f = Fake()
    yield f
    f.close()


def run(fake, argv, env=None, answers=(), values_path=None, getpass_fn=None):
    lines: list[str] = []
    asked: list[str] = []
    it = iter(answers)

    def ask(prompt):
        asked.append(prompt)
        return next(it)

    code = rs.main(
        argv,
        env={"RENDER_API_KEY": KEY} if env is None else env,
        input_fn=ask,
        base=fake.base,
        values_path=values_path or Path("does-not-exist.env"),
        out=lines.append,
        sleep=lambda s: None,
        getpass_fn=getpass_fn or (lambda p: ""),
    )
    return code, "\n".join(lines), asked


def test_status_reads_only_and_warns_about_auto_deploy(fake):
    code, out, _ = run(fake, ["status"])
    assert code == 0
    for name in rs.SITES.values():
        assert name in out
    assert "suspended" in out and "WARNING: Auto-Deploy is ON for rootsquares-admin-site-staging" in out
    assert fake.posts() == []
    assert "rootsquares-platform-api-staging" not in out  # an API is never listed


def test_resume_touches_only_the_named_sites_and_asks_first(fake):
    code, out, asked = run(fake, ["resume", "platform", "admin"], answers=["yes"])
    assert code == 0
    assert asked and "rootsquares-platform-site-staging" in asked[0]
    assert sorted(fake.posts()) == ["/services/srv-admin/resume", "/services/srv-plat/resume"]
    assert fake.services["srv-sq"]["suspended"] == "suspended"  # the square site was not named
    assert fake.services["srv-api"]["suspended"] == "not_suspended"
    assert "running" in out


def test_anything_but_yes_changes_nothing(fake):
    code, out, _ = run(fake, ["resume", "all"], answers=["no"])
    assert code == 1 and "Cancelled" in out
    assert fake.posts() == []


def test_dry_run_changes_nothing_and_does_not_ask(fake):
    code, out, asked = run(fake, ["resume", "all", "--dry-run"])
    assert code == 0 and "Dry run" in out and asked == []
    assert fake.posts() == []


def test_a_site_already_in_the_wanted_state_is_left_alone(fake):
    code, out, _ = run(fake, ["suspend", "all", "--yes"])
    assert code == 0 and "Nothing to do" in out
    assert fake.posts() == []


def test_the_api_service_can_never_be_named(fake):
    code, out, _ = run(fake, ["suspend", "api", "--yes"])
    assert code == 2 and "Unknown site" in out
    assert fake.posts() == []


def test_resume_with_deploy_starts_a_deploy_of_each_named_site(fake):
    code, out, _ = run(fake, ["resume", "platform", "--deploy", "--yes"])
    assert code == 0
    assert fake.posts() == ["/services/srv-plat/resume", "/services/srv-plat/deploys"]
    assert "(deploy dep-1)" in out


def test_deploy_is_refused_with_suspend(fake):
    assert run(fake, ["suspend", "platform", "--deploy"])[0] == 2


def test_a_missing_service_changes_nothing(fake):
    del fake.services["srv-sq"]
    code, out, _ = run(fake, ["resume", "all", "--yes"])
    assert code == 2 and "Not found" in out and "rootsquares-square-site-staging" in out
    assert fake.posts() == []


def test_the_key_is_never_printed_and_a_bad_key_is_reported_without_it(fake):
    _, out, _ = run(fake, ["status"])
    assert KEY not in out
    code, out, _ = run(fake, ["status"], env={"RENDER_API_KEY": "wrong-key-0000"})
    assert code == 1 and "401" in out and "refused the key" in out
    assert "wrong-key-0000" not in out and KEY not in out


def test_key_order_environment_then_values_file_then_hidden_prompt(tmp_path):
    values = tmp_path / "values.staging.env"
    values.write_text("OTHER=1\nRENDER_API_KEY='from-file-key'\n", encoding="utf-8")
    assert rs.find_key({"RENDER_API_KEY": "from-env-key"}, values) == "from-env-key"
    assert rs.find_key({}, values) == "from-file-key"
    assert rs.find_key({}, tmp_path / "none.env", lambda p: " typed-key ") == "typed-key"
    with pytest.raises(rs.RenderError):
        rs.find_key({}, tmp_path / "none.env", lambda p: "")


def test_the_script_has_no_key_in_it():
    src = (REPO / "scripts" / "render_sites.py").read_text(encoding="utf-8")
    assert "rnd_" not in src and "Bearer " in src
    assert set(rs.SITES.values()) == {"rootsquares-platform-site-staging", "rootsquares-admin-site-staging", "rootsquares-square-site-staging"}
