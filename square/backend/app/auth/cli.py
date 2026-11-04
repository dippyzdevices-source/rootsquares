import click
from flask import Flask

from app.auth.models import User
from app.extensions import db

VALID_ROLES = ("member", "volunteer", "admin")


def register_cli(app: Flask) -> None:
    @app.cli.group("users")
    def users_group():
        """User management commands."""

    @users_group.command("promote")
    @click.argument("email")
    @click.argument("role")
    def promote(email: str, role: str):
        """Set an existing user's role, e.g. `flask users promote a@b.com admin`."""
        if role not in VALID_ROLES:
            click.echo(f"Role must be one of {VALID_ROLES}", err=True)
            raise SystemExit(1)

        user = User.query.filter_by(email=email).first()
        if user is None:
            click.echo(
                f"No user found with email {email!r}. They must log in at least once first.",
                err=True,
            )
            raise SystemExit(1)

        user.role = role
        db.session.commit()
        click.echo(f"{email} is now {role}.")
