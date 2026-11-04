"""Tests for keep alive job (4 tests), e.g. start keep alive job is a noop without a url; start keep alive job is a noop under testing even with a url; start keep alive job starts a daemon thread when configured."""
from unittest.mock import MagicMock, patch

import click

from app.jobs.keep_alive import start_keep_alive_job


def test_start_keep_alive_job_is_a_noop_without_a_url():
    app = MagicMock()
    app.config = {"TESTING": False, "KEEP_ALIVE_URL": ""}

    with patch("app.jobs.keep_alive.threading.Thread") as mock_thread:
        start_keep_alive_job(app)

    mock_thread.assert_not_called()


def test_start_keep_alive_job_is_a_noop_under_testing_even_with_a_url():
    app = MagicMock()
    app.config = {"TESTING": True, "KEEP_ALIVE_URL": "https://example.com/api/health"}

    with patch("app.jobs.keep_alive.threading.Thread") as mock_thread:
        start_keep_alive_job(app)

    mock_thread.assert_not_called()


def test_start_keep_alive_job_starts_a_daemon_thread_when_configured():
    app = MagicMock()
    app.config = {"TESTING": False, "KEEP_ALIVE_URL": "https://example.com/api/health"}

    with patch("app.jobs.keep_alive.threading.Thread") as mock_thread:
        start_keep_alive_job(app)

    mock_thread.assert_called_once()
    _, kwargs = mock_thread.call_args
    assert kwargs["args"] == ("https://example.com/api/health",)
    assert kwargs["daemon"] is True
    mock_thread.return_value.start.assert_called_once()


def test_start_keep_alive_job_is_a_noop_inside_a_flask_cli_command():
    app = MagicMock()
    app.config = {"TESTING": False, "KEEP_ALIVE_URL": "https://example.com/api/health"}

    with patch("app.jobs.keep_alive.threading.Thread") as mock_thread:
        with click.Context(click.Command("some-cli-command")):
            start_keep_alive_job(app)

    mock_thread.assert_not_called()
