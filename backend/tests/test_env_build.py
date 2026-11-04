# ruff: noqa: E501
"""env_build.py (scripts/env_build.py, manifest env/manifest.py): the builder writes one clean file per piece, forbids what an environment must not have, and never prints a value."""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "env"))
spec = importlib.util.spec_from_file_location("env_build", REPO / "scripts" / "env_build.py")
env_build = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(env_build)  # type: ignore[union-attr]

SECRET = "pw-SECRET-VALUE-0123456789"
STAGING = {
    "DATABASE_URL": "postgresql://u:" + SECRET + "@host/db",
    "AUTH_URL": "https://auth.example/neondb/auth",
    "STORAGE_S3_ENDPOINT_URL": "https://s3.example",
    "STORAGE_S3_ACCESS_KEY": "a" * 32,
    "STORAGE_S3_SECRET_KEY": "b" * 64,
    "STORAGE_S3_REGION": "eu",
    "STORAGE_PUBLIC_BUCKET": "public",
    "STORAGE_PRIVATE_BUCKET": "private",
    "STORAGE_PUBLIC_BASE_URL": "https://s3.example/public",
    "NEON_API_KEY": "napi_" + "c" * 40,
    "BILLING_PROVIDER": "stripe",
    "STRIPE_SECRET_KEY": "sk_test_" + "s" * 40,
    "STRIPE_WEBHOOK_SECRET": "whsec_" + "w" * 40,
    "SQUARE_SERVER_URL": "https://squares.example",
    "CORS_ORIGINS": "https://app.example",
    "PLATFORM_FRONTEND_URL": "https://app.example",
    "ADMIN_ORIGINS": "https://admin.example",
    "CUSTOMER_API_URL": "https://api.example",
    "ADMIN_API_URL": "https://admin-api.example",
    "VITE_PLATFORM_HOSTS": "app.example,www.app.example",
}


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    (tmp_path / "env").mkdir()
    monkeypatch.setattr(env_build, "ROOT", tmp_path)
    return tmp_path


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["env_build.py", *args])
    return env_build.main()


def write_values(repo, env, data):
    (repo / "env" / f"values.{env}.env").write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n", encoding="utf-8")


def test_staging_builds_two_services_with_shared_and_separate_secrets(repo, monkeypatch, capsys):
    write_values(repo, "staging", STAGING)
    assert run(monkeypatch, "staging", "--make-secrets") == 0
    out = repo / "env" / "out" / "staging"
    c = (out / "customer_api.env").read_text()
    a = (out / "admin_api.env").read_text()
    assert "API_SURFACE=customer" in c and "API_SURFACE=admin" in a
    assert "JWT_SECRET=" in c and "STAFF_JWT_SECRET" not in c and "STAFF_FERNET_KEY" not in c and "SUPPORT_SESSION_KEY" not in c
    assert "STAFF_JWT_SECRET=" in a and "\nJWT_SECRET=" not in a and "CORS_ORIGINS" not in a
    shared = [ln for ln in c.splitlines() if ln.startswith(("FERNET_KEY=", "SITE_GATE_PASSWORD=", "SQUARE_INTERNAL_KEY="))]
    assert len(shared) == 3 and all(ln in a for ln in shared)
    assert "ENV=production" in c and "COOKIE_SECURE=true" in c and "PROXY_HOPS=1" in c and "ENV_LABEL=Staging" in c
    printed = capsys.readouterr().out
    assert SECRET not in printed and not any(ln.split("=", 1)[1] in printed for ln in shared)


def test_a_missing_required_value_writes_nothing(repo, monkeypatch, capsys):
    data = dict(STAGING)
    del data["NEON_API_KEY"]
    write_values(repo, "staging", data)
    assert run(monkeypatch, "staging", "--make-secrets") == 1
    assert "NEON_API_KEY is required" in capsys.readouterr().out
    assert not (repo / "env" / "out").exists()


def test_a_placeholder_and_a_short_secret_are_refused(repo, monkeypatch, capsys):
    write_values(repo, "staging", {**STAGING, "NEON_API_KEY": "<neon api key>", "SQUARE_INTERNAL_KEY": "short"})
    assert run(monkeypatch, "staging", "--make-secrets") == 1
    out = capsys.readouterr().out
    assert "NEON_API_KEY still has a <placeholder>" in out and "SQUARE_INTERNAL_KEY has 5 characters" in out


def test_customer_and_admin_origin_must_differ(repo, monkeypatch, capsys):
    write_values(repo, "staging", {**STAGING, "ADMIN_ORIGINS": "https://app.example"})
    assert run(monkeypatch, "staging", "--make-secrets") == 1
    assert "share an origin" in capsys.readouterr().out


def test_local_is_one_file_without_surface_and_ignores_the_gate_and_never_makes_a_fernet_key(repo, monkeypatch, capsys):
    old = repo / "old.env"
    old.write_text(
        'ENV=local\nDATABASE_URL="postgresql://x:y@h/db"\nAUTH_URL=https://auth.example/neondb/auth\nNEON_API_KEY=napi_' + "d" * 40 + "\nSITE_GATE_PASSWORD=" + "g" * 20
        + "\nEMAIL_FROM=<placeholder>\nSOMETHING_ELSE=1\n",
        encoding="utf-8",
    )
    assert run(monkeypatch, "local", "--import", "old.env", "--make-secrets") == 0
    text = (repo / "env" / "out" / "local" / "platform_api.env").read_text()
    assert "API_SURFACE" not in text and "SITE_GATE_PASSWORD" not in text and "FERNET_KEY" not in text
    assert "DATABASE_URL=postgresql://x:y@h/db" in text and "ENV=local" in text and "SQUARE_SERVER_URL=http://localhost:5002" in text
    out = capsys.readouterr().out
    assert "SITE_GATE_PASSWORD is in the values file but is not used in local" in out
    assert "EMAIL_FROM" in out and "SOMETHING_ELSE" in out  # skipped as a placeholder, reported as unknown
    assert "postgresql://x:y@h/db" not in out


def test_import_keeps_what_is_already_in_the_values_file(repo, monkeypatch):
    write_values(repo, "local", {"NEON_API_KEY": "keep-me-" + "k" * 20})
    (repo / "old.env").write_text("NEON_API_KEY=other\nAUTH_URL=https://a.example/x\n", encoding="utf-8")
    run(monkeypatch, "local", "--import", "old.env")
    got = env_build.parse(repo / "env" / "values.local.env")
    assert got["NEON_API_KEY"].startswith("keep-me-") and got["AUTH_URL"] == "https://a.example/x"


def test_install_backs_up_the_old_file(repo, monkeypatch):
    (repo / "backend").mkdir()
    for d in ("square/backend", "square/frontend", "frontend/platform", "frontend/admin"):
        (repo / d).mkdir(parents=True)
    (repo / "backend" / ".env.local").write_text("OLD=1\n", encoding="utf-8")
    write_values(repo, "local", {"AUTH_URL": "https://a.example/x", "DATABASE_URL": "postgresql://x:y@h/db", "NEON_API_KEY": "napi_" + "e" * 40})
    assert run(monkeypatch, "local", "--install") == 0
    assert "DATABASE_URL=" in (repo / "backend" / ".env.local").read_text()
    baks = list((repo / "backend").glob(".env.local.bak-*"))
    assert len(baks) == 1 and baks[0].read_text() == "OLD=1\n"


def line(text, name):
    return next(ln for ln in text.splitlines() if ln.startswith(name + "="))


def test_square_server_shares_the_platform_secrets_and_has_its_own(repo, monkeypatch, capsys):
    write_values(repo, "staging", STAGING)
    assert run(monkeypatch, "staging", "--make-secrets") == 0
    out = repo / "env" / "out" / "staging"
    c, a, s = ((out / f"{n}.env").read_text() for n in ("customer_api", "admin_api", "square_server"))
    for name in ("FERNET_KEY", "SITE_GATE_PASSWORD"):
        assert line(s, name) == line(c, name) == line(a, name)
    assert line(s, "SUPPORT_SESSION_KEY") == line(a, "SUPPORT_SESSION_KEY")
    assert line(s, "PLATFORM_INTERNAL_KEY").split("=", 1)[1] == line(c, "SQUARE_INTERNAL_KEY").split("=", 1)[1]
    assert line(s, "PLATFORM_DATABASE_URL").split("=", 1)[1] == STAGING["DATABASE_URL"]
    assert "APP_ENV=production" in s and "PROXY_HOPS=1" in s and len(line(s, "SECRET_KEY").split("=", 1)[1]) >= 32 and "ANALYTICS_SALT_SECRET=" in s
    assert "JWT_SECRET" not in s and "STAFF_" not in s and "API_SURFACE" not in s and "NEON_API_KEY" not in s
    assert "FRONTEND_ORIGIN" not in s and "PLATFORM_SITE_URL=https://app.example" in s
    assert STAGING["DATABASE_URL"] not in capsys.readouterr().out


def test_square_server_internal_key_must_match_the_platform_key(repo, monkeypatch, capsys):
    write_values(repo, "staging", {**STAGING, "SQUARE_INTERNAL_KEY": "x" * 45, "PLATFORM_INTERNAL_KEY": "y" * 45})
    assert run(monkeypatch, "staging", "--make-secrets") == 1
    assert "PLATFORM_INTERNAL_KEY must equal SQUARE_INTERNAL_KEY" in capsys.readouterr().out


def test_local_square_server_is_development_with_the_localhost_platform_address(repo, monkeypatch):
    write_values(repo, "local", {"AUTH_URL": "https://a.example/x", "DATABASE_URL": "postgresql://x:y@h/db", "NEON_API_KEY": "napi_" + "e" * 40, "SITE_GATE_PASSWORD": "g" * 20})
    assert run(monkeypatch, "local") == 0
    s = (repo / "env" / "out" / "local" / "square_server.env").read_text()
    assert "DATABASE_URL=postgresql+psycopg://unused:unused@localhost:5432/unused" in s and "APP_ENV=development" in s and "PLATFORM_SITE_URL=http://localhost:5273" in s and "SITE_GATE_PASSWORD" not in s and "PROXY_HOPS" not in s and "SECRET_KEY" not in s


def test_the_three_sites_take_the_platform_sign_in_pair_and_the_square_site_calls_its_own_address(repo, monkeypatch, capsys):
    write_values(repo, "staging", STAGING)
    assert run(monkeypatch, "staging", "--make-secrets") == 0
    out = repo / "env" / "out" / "staging"
    p, d, q = ((out / f"{n}.env").read_text() for n in ("platform_site", "admin_site", "square_site"))
    assert "VITE_API_BASE_URL=https://api.example" in p and "VITE_AUTH_PROVIDER=neon" in p and f"VITE_AUTH_URL={STAGING['AUTH_URL']}" in p and "VITE_PLATFORM_HOSTS=app.example,www.app.example" in p
    assert "VITE_USE_MOCK" not in p and "VITE_SQUARE_APP_PORT" not in p
    assert d.splitlines()[-1] == "VITE_ADMIN_API_BASE_URL=https://admin-api.example"
    assert "\nVITE_API_BASE_URL=\n" in q and f"VITE_AUTH_URL={STAGING['AUTH_URL']}" in q
    assert not any(secret in (p + d + q) for secret in (STAGING["DATABASE_URL"], STAGING["NEON_API_KEY"], STAGING["STORAGE_S3_SECRET_KEY"]))


def test_a_site_needs_its_api_address_in_staging(repo, monkeypatch, capsys):
    write_values(repo, "staging", {k: v for k, v in STAGING.items() if k not in ("CUSTOMER_API_URL", "ADMIN_API_URL", "VITE_PLATFORM_HOSTS")})
    assert run(monkeypatch, "staging", "--make-secrets") == 1
    out = capsys.readouterr().out
    assert "platform_site: VITE_API_BASE_URL is required" in out and "admin_site: VITE_ADMIN_API_BASE_URL is required" in out and "VITE_PLATFORM_HOSTS is required" in out


def test_local_sites_default_to_the_local_apis(repo, monkeypatch):
    write_values(repo, "local", {"AUTH_URL": "https://a.example/x", "DATABASE_URL": "postgresql://x:y@h/db", "NEON_API_KEY": "napi_" + "e" * 40})
    assert run(monkeypatch, "local") == 0
    out = repo / "env" / "out" / "local"
    assert "VITE_API_BASE_URL=http://localhost:5001" in (out / "platform_site.env").read_text()
    assert "VITE_ADMIN_API_BASE_URL=http://localhost:5001" in (out / "admin_site.env").read_text()
    assert "VITE_API_BASE_URL=\n" in (out / "square_site.env").read_text()


def test_import_overwrite_replaces_a_value_fixed_by_hand_and_keeps_the_rest(repo, monkeypatch, capsys):
    write_values(repo, "local", {"AUTH_URL": "https://a.example/x", "DATABASE_URL": "postgresql://x:OLD@h/db", "NEON_API_KEY": "napi_" + "e" * 40})
    (repo / "fixed.env").write_text("DATABASE_URL=postgresql://x:NEW@h/db\nAUTH_URL=https://a.example/x\n", encoding="utf-8")
    run(monkeypatch, "local", "--import", "fixed.env")
    assert env_build.parse(repo / "env" / "values.local.env")["DATABASE_URL"].endswith(":OLD@h/db")
    run(monkeypatch, "local", "--import", "fixed.env", "--overwrite")
    got = env_build.parse(repo / "env" / "values.local.env")
    assert got["DATABASE_URL"].endswith(":NEW@h/db") and got["AUTH_URL"] == "https://a.example/x" and got["NEON_API_KEY"].startswith("napi_")
    out = capsys.readouterr().out
    assert "replaced: DATABASE_URL" in out and "NEW" not in out


# ---- the examples are the bible: every setting they document is built or deliberately not built, and the manifest holds nothing they do not document ----
NAME_LINE = __import__("re").compile(r"^#?\s*([A-Z][A-Z0-9_]+)=")
NOT_BUILT = env_build.M.NOT_BUILT


def example_names(folder):
    return {m.group(1) for ln in (REPO / folder / ".env.example").read_text(encoding="utf-8").splitlines() if (m := NAME_LINE.match(ln))}


@pytest.mark.parametrize(
    "folder, variables",
    [
        ("backend", env_build.M.PLATFORM_VARS),
        ("square/backend", env_build.M.SQUARE_SERVER_VARS),
        ("frontend/platform", env_build.M.PLATFORM_SITE_VARS),
        ("frontend/admin", env_build.M.ADMIN_SITE_VARS),
        ("square/frontend", env_build.M.SQUARE_SITE_VARS),
    ],
)
def test_the_manifest_and_the_env_example_document_the_same_settings(folder, variables):
    documented = example_names(folder)
    built = {v.name for v in variables}
    assert documented - built - NOT_BUILT[folder] == set(), f"documented in {folder}/.env.example but neither built nor listed as not built: add a Var to env/manifest.py or a name to NOT_BUILT"
    assert built - documented == set(), f"in env/manifest.py but not documented in {folder}/.env.example: document it there (the example is the bible)"
    assert NOT_BUILT[folder] - documented == set(), f"listed as not built but not in {folder}/.env.example any more: remove it from NOT_BUILT"


def test_every_run_copies_the_examples_with_a_do_not_edit_header(repo, monkeypatch):
    for src in env_build.EXAMPLES:
        f = repo / src
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("# the bible\nNAME=1\n", encoding="utf-8")
    write_values(repo, "local", {"AUTH_URL": "https://a.example/x", "DATABASE_URL": "postgresql://x:y@h/db", "NEON_API_KEY": "napi_" + "e" * 40})
    assert run(monkeypatch, "local") == 0
    copy = (repo / "env" / "examples" / "platform_api.env.example").read_text()
    assert copy.startswith("# COPY of backend/.env.example") and copy.endswith("# the bible\nNAME=1\n")
    assert len(list((repo / "env" / "examples").iterdir())) == 10 and (repo / "env" / "examples" / "platform_api.env.example.md").read_text().startswith("# Platform API")


def test_the_markdown_reference_has_a_row_for_every_documented_setting_and_marks_secrets():
    sys.path.insert(0, str(REPO / "env"))
    import reference

    for folder, (variables, title) in env_build.REFERENCE.items():
        text = (REPO / folder / ".env.example").read_text(encoding="utf-8")
        md = reference.reference_markdown("x", title, f"{folder}/.env.example", variables, NOT_BUILT[folder], env_build.M.SURFACE_NAME, text).replace(r"\|", "|")
        rows = {ln.split("`")[1] for ln in md.splitlines() if ln.startswith("| `")}
        assert example_names(folder) <= rows, f"{folder}: no row for {sorted(example_names(folder) - rows)}"
        assert md.count("(secret)") - 1 == sum(1 for v in variables if v.secret)  # minus the legend line
    platform = reference.reference_markdown("x", "t", "backend/.env.example", env_build.M.PLATFORM_VARS, NOT_BUILT["backend"], "API_SURFACE", (REPO / "backend" / ".env.example").read_text(encoding="utf-8"))
    assert "| `FERNET_KEY` (secret) | both | optional | required | required |" in platform
    assert "## BLOCK 4: PROVISIONING OF NEW SQUARES: 4A: Neon" in platform
    assert "FERNET_KEY (SECRET)" not in platform  # the description does not repeat the name


def test_production_mode_needs_neon_and_stripe_like_the_backend(repo, monkeypatch, capsys):
    data = {k: v for k, v in STAGING.items() if k not in ("BILLING_PROVIDER", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET")}
    write_values(repo, "staging", {**data, "AUTH_PROVIDER": "supabase"})
    assert run(monkeypatch, "staging", "--make-secrets") == 1
    out = capsys.readouterr().out
    assert "ENV=production needs AUTH_PROVIDER=neon" in out and "ENV=production needs BILLING_PROVIDER=stripe" in out
    write_values(repo, "staging", {**data, "BILLING_PROVIDER": "stripe"})
    assert run(monkeypatch, "staging") == 1
    assert "BILLING_PROVIDER=stripe needs STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET" in capsys.readouterr().out
    write_values(repo, "staging", {**data, "ENV": "local", "BILLING_PROVIDER": "fake", "AUTH_PROVIDER": "supabase"})
    assert run(monkeypatch, "staging", "--make-secrets") == 0  # staging can still be run in local mode by choice


def test_init_writes_every_name_empty_fills_the_domain_and_never_overwrites(repo, monkeypatch, capsys):
    assert run(monkeypatch, "staging", "--init", "--domain", "example.test") == 0
    text = (repo / "env" / "values.staging.env").read_text()
    got = env_build.parse(repo / "env" / "values.staging.env")
    assert got["CORS_ORIGINS"] == "https://example.test,https://www.example.test" and got["ADMIN_ORIGINS"] == "https://admin.example.test"
    assert got["CUSTOMER_API_URL"] == "https://api.example.test" and got["CUSTOMER_DATABASE_URL"] == "" and got["NEON_API_KEY"] == ""
    assert "\nSTRIPE_WEBHOOK_SECRET=\n" in text and "\nBILLING_PROVIDER=stripe\n" in text and "\nRESEND_API_KEY=\n" in text and "# FERNET_KEY=   (made by --make-secrets; leave it)" in text and "\nVITE_API_BASE_URL" not in text
    assert "# the OWNER address" in text and "PLATFORM_DATABASE_URL" not in text.replace("# PLATFORM_DATABASE_URL", "")
    first = capsys.readouterr().out
    assert "to fill:" in first and "AUTH_URL" in first
    # a second run completes nothing and keeps a value that was filled in
    (repo / "env" / "values.staging.env").write_text(text.replace("NEON_API_KEY=\n", "NEON_API_KEY=napi_keep_me_0123456789\n"), encoding="utf-8")
    assert run(monkeypatch, "staging", "--init") == 0
    assert env_build.parse(repo / "env" / "values.staging.env")["NEON_API_KEY"] == "napi_keep_me_0123456789"
    assert "already has every name" in capsys.readouterr().out


def test_init_for_local_asks_only_what_local_needs(repo, monkeypatch):
    run(monkeypatch, "local", "--init")
    text = (repo / "env" / "values.local.env").read_text()
    assert "\nAUTH_URL=\n" in text and "SITE_GATE_PASSWORD" not in text and "STAFF_SECOND_STEP_REQUIRED" in text and "\nCORS_ORIGINS" not in text


def test_every_option_of_the_tool_is_in_the_readme_the_guide_and_the_script_index():
    flags = sorted(set(__import__("re").findall(r'add_argument\("(--[a-z-]+)"', (REPO / "scripts" / "env_build.py").read_text(encoding="utf-8"))))
    assert flags, "no options found in scripts/env_build.py"
    for doc in ("env/README.md", "docs/setup/43-env-builder.md", "scripts/README.md"):
        text = (REPO / doc).read_text(encoding="utf-8")
        for flag in flags:
            assert flag in text, f"{doc} does not mention {flag}: the tool changed, the documentation did not"


def test_a_cloud_file_that_holds_the_owner_address_says_so(repo, monkeypatch, capsys):
    write_values(repo, "staging", STAGING)
    assert run(monkeypatch, "staging", "--make-secrets") == 0
    out = capsys.readouterr().out
    assert "customer_api: DATABASE_URL is the OWNER address" in out and "admin_api: DATABASE_URL is the OWNER address" in out
    write_values(repo, "staging", {**STAGING, "CUSTOMER_DATABASE_URL": "postgresql://customer_app:x@h/db", "ADMIN_DATABASE_URL": "postgresql://admin_app:x@h/db"})
    assert run(monkeypatch, "staging", "--make-secrets") == 0
    assert "OWNER address" not in capsys.readouterr().out


def test_the_readme_lists_every_secret_the_builder_makes_and_where():
    text = (REPO / "env" / "README.md").read_text(encoding="utf-8")
    section = text.split("## Secrets: what `--make-secrets` makes", 1)[1].split("## Cheat sheet", 1)[0]
    made = {v.name: v for v in env_build.M.PLATFORM_VARS + env_build.M.SQUARE_SERVER_VARS if v.gen}
    assert made, "no secret is made by the builder?"
    for name, var in made.items():
        row = next((ln for ln in section.splitlines() if ln.startswith(f"| `{name}` |")), None)
        assert row, f"env/README.md does not describe {name} in its Secrets table"
        want = "staging only" if var.gen_envs == ("staging",) else "staging, production"
        assert want in row, f"env/README.md says the wrong environments for {name}: the manifest makes it for {var.gen_envs}"
