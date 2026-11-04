# ruff: noqa: E501
"""scripts/env_check.py: the read-only check of an environment's values prints no value, skips what is not filled in and fails what is wrong (no network, no database: all faked)."""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("env_check", REPO / "scripts" / "env_check.py")
env_check = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(env_check)  # type: ignore[union-attr]

PW = "very-SECRET-pw-0123456789"


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    (tmp_path / "env").mkdir()
    monkeypatch.setattr(env_check, "ROOT", tmp_path)
    return tmp_path


def write(repo, env, data):
    (repo / "env" / f"values.{env}.env").write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n", encoding="utf-8")


def test_a_missing_values_file_is_exit_2(repo, capsys):
    assert env_check.main(["staging"]) == 2
    assert "does not exist" in capsys.readouterr().out


def test_an_unknown_check_is_exit_2(repo, capsys):
    write(repo, "staging", {"AUTH_URL": ""})
    assert env_check.main(["staging", "--only", "nope"]) == 2


def test_what_is_not_filled_in_is_skipped_not_failed(repo, capsys):
    write(repo, "staging", {"AUTH_URL": "", "DATABASE_URL": ""})
    assert env_check.main(["staging", "--only", "auth,storage,db,roles,neon,stripe"]) == 0
    out = capsys.readouterr().out
    assert out.count("SKIP") == 6 and "FAIL" not in out.replace("0 fail", "")


def test_a_failure_never_prints_a_value(repo, capsys, monkeypatch):
    url = f"postgresql://neondb_owner:{PW}@ep-x-pooler.example.test/neondb"
    write(repo, "staging", {"DATABASE_URL": url, "NEON_API_KEY": "napi_" + PW, "STRIPE_SECRET_KEY": "sk_test_" + PW, "BILLING_PROVIDER": "stripe"})

    def boom(*a, **k):
        raise RuntimeError(f"cannot reach {a} {k} with {url} and napi_{PW} and sk_test_{PW}")

    import psycopg

    monkeypatch.setattr(psycopg, "connect", boom)
    monkeypatch.setattr(env_check.httpx, "get", boom)
    assert env_check.main(["staging", "--only", "db,neon,stripe"]) == 1
    out = capsys.readouterr().out
    assert "FAIL db: cannot connect" in out and "FAIL neon: cannot reach" in out and "FAIL stripe: cannot reach" in out
    assert PW not in out


def test_the_psql_wrapper_and_a_live_key_in_staging_are_failures(repo, capsys):
    write(repo, "staging", {"DATABASE_URL": "psql 'postgresql://a:b@h/db'", "STRIPE_SECRET_KEY": "sk_live_" + "x" * 30, "BILLING_PROVIDER": "stripe"})
    assert env_check.main(["staging", "--only", "db,stripe"]) == 1
    out = capsys.readouterr().out
    assert "starts with psql" in out and "LIVE key in staging" in out


def test_a_role_with_a_right_it_should_not_have_is_a_failure(repo, capsys, monkeypatch):
    write(repo, "staging", {"CUSTOMER_DATABASE_URL": "postgresql://customer_app:x@h-pooler.t/db", "ADMIN_DATABASE_URL": "postgresql://admin_app:x@h-pooler.t/db"})

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql):
            return self

        def fetchone(self):
            return (0,)

    import psycopg

    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: Conn())
    assert env_check.main(["staging", "--only", "roles"]) == 1
    out = capsys.readouterr().out
    assert "FAIL roles: customer_app reads from staff_users: allowed (WRONG" in out and "PASS roles: customer_app reads from users: allowed" in out


def test_the_webhook_events_are_the_ones_the_backend_handles():
    sys.path.insert(0, str(REPO / "backend"))
    from app.platform.billing import WEBHOOK_EVENTS

    assert set(env_check.WEBHOOK_EVENTS) == set(WEBHOOK_EVENTS)


def test_built_files_older_than_the_values_file_are_a_warning(repo, capsys):
    import os

    write(repo, "staging", {"AUTH_URL": ""})
    out = repo / "env" / "out" / "staging"
    out.mkdir(parents=True)
    f = out / "x.env"
    f.write_text("A=1\n", encoding="utf-8")
    old = (repo / "env" / "values.staging.env").stat().st_mtime - 100
    os.utime(f, (old, old))
    assert env_check.main(["staging", "--only", "built"]) == 0
    assert "WARN built" in capsys.readouterr().out


def test_the_checker_and_its_options_are_in_the_readme_the_guide_and_the_script_index():
    import re

    source = (REPO / "scripts" / "env_check.py").read_text(encoding="utf-8")
    flags = sorted(set(re.findall(r'add_argument\("(--[a-z-]+)"', source)))
    checks = re.search(r"ALL_CHECKS = \(([^)]*)\)", source).group(1).replace('"', "").replace(" ", "").split(",")
    for doc in ("env/README.md", "docs/setup/43-env-builder.md", "scripts/README.md"):
        text = (REPO / doc).read_text(encoding="utf-8")
        assert "env_check.py" in text, f"{doc} does not mention env_check.py"
        for flag in flags:
            assert flag in text, f"{doc} does not mention {flag} of env_check.py"
    for doc in ("env/README.md", "docs/setup/43-env-builder.md"):
        text = (REPO / doc).read_text(encoding="utf-8")
        for name in checks:
            assert name in text, f"{doc} does not mention the check '{name}'"


def test_guide_41_names_the_five_webhook_events_the_backend_handles():
    sys.path.insert(0, str(REPO / "backend"))
    from app.platform.billing import WEBHOOK_EVENTS

    guide = (REPO / "docs" / "setup" / "41-deploy-to-render-staging.md").read_text(encoding="utf-8")
    for event in WEBHOOK_EVENTS:
        assert f"`{event}`" in guide, f"guide 41 does not name the webhook event {event}"
