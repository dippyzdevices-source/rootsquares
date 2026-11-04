import click
from flask import Flask


def register_cli(app: Flask) -> None:
    @app.cli.group("newsletter")
    def newsletter_group():
        """Newsletter commands."""

    @newsletter_group.command("fold-in")
    def fold_in_command():
        """Copy the old newsletter issues into Messages (idempotent, deletes nothing; every square in many-squares mode)."""
        from app.jobs.squares import run_everywhere
        from app.newsletter.fold_in import IssueSendingError, copy_issues_to_messages

        def work() -> int:
            from app.modules import module_enabled

            if not module_enabled("messages"):
                click.echo("A square has the Newsletter but not Messages: switch Messages on first, then copy.", err=True)
                return 0
            try:
                result = copy_issues_to_messages()
            except IssueSendingError as exc:
                click.echo(str(exc), err=True)
                return 0
            if result["extras_dropped"]:
                click.echo(f"Check issue(s) {result['extras_dropped']}: they were meant for the subscribers and pasted addresses; only the subscribers were kept.")
            return result["copied"]

        click.echo(f"Copied {run_everywhere(_app(), work, module='newsletter')} issue(s).")


def _app():
    from flask import current_app

    return current_app._get_current_object()
