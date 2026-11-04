"""scripts/square_db.py (W6-R35): the connection string goes to the child process through its environment only and is never printed."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "square_db.py"


def _load():
    spec = importlib.util.spec_from_file_location("square_db_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_env_passes_the_database_in_the_environment_and_prints_no_secret(monkeypatch, capsys):
    module = _load()
    seen = {}

    def fake_run(command, cwd=None, env=None, **kwargs):
        seen.update(command=command, env=env)

        class Done:
            returncode = 0

        return Done()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "_enable_rls", lambda url: None)  # row level security needs a real database
    monkeypatch.setenv("SQUARE_DATABASE_URL", "postgresql://user:SECRET-PASSWORD@host.example/db")
    monkeypatch.setenv("SQUARE_SLUG", "new-square")

    assert module.main(["square_db.py", "upgrade-env"]) == 0

    assert seen["env"]["DATABASE_URL"] == "postgresql+psycopg://user:SECRET-PASSWORD@host.example/db"  # the driver is named for SQLAlchemy
    assert "SECRET-PASSWORD" not in " ".join(str(part) for part in seen["command"])  # never on the command line
    out = capsys.readouterr().out
    assert "new-square" in out and "SECRET-PASSWORD" not in out


def test_upgrade_env_without_a_database_stops(monkeypatch, capsys):
    module = _load()
    monkeypatch.delenv("SQUARE_DATABASE_URL", raising=False)
    assert module.main(["square_db.py", "upgrade-env"]) == 1
    assert "SQUARE_DATABASE_URL is not set" in capsys.readouterr().out


def test_unknown_usage_prints_help(capsys):
    module = _load()
    assert module.main(["square_db.py"]) == 2
    assert "upgrade-env" in capsys.readouterr().out
