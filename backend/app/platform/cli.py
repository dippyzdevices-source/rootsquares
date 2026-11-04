"""Flask CLI for the platform database:  flask --app app.main:create_app db upgrade   and   flask --app app.main:create_app seed-staff"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable

import click
from alembic import command
from flask import Flask
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform import (
    email_html,
    models,  # noqa: F401  (registers the tables on Base.metadata)
    square_auth,
    staff,
)
from app.platform.models import AuditLog, Square, User
from app.platform.provisioning import NeonApiError, NeonProvisioner, neon_target
from app.platform.square_verifier import SquareAuthError
from app.shared.config import Settings
from app.shared.crypto import Encryptor, verify_password
from app.shared.db import Base, add_missing_columns
from app.shared.migrations import alembic_config, enable_rls, upgrade


def _notify_owner(app: Flask, settings: Settings) -> Callable[[Square, int], None]:
    """A reminder e-mail to the owner, when an e-mail provider is wired (not yet: the reminder is still recorded and shown on the portal)."""

    def notify(sq: Square, day: int) -> None:
        email = app.extensions["providers"].email
        if email is None:
            return
        db = app.extensions["db_factory"]()()
        try:
            owner = db.scalar(
                select(User)
                .join(models.Membership, models.Membership.user_id == User.id)
                .where(models.Membership.org_id == sq.org_id, models.Membership.role == models.MembershipRole.OWNER)
            )
            if owner is not None:
                text = reminder_text(sq, day)
                mail = email_html.from_text(text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Event pass", heading=f"Day {day} of your Event pass")
                email.send(owner.email, f"Your Event pass {sq.name}: day {day}", text, **mail)
        finally:
            db.close()

    return notify


def reminder_text(sq: Square, day: int) -> str:
    return (
        f"Your Event pass site {sq.name} is {day} days old. Remember to download the accounting report, the attendee and order list and the people list "
        "while the site is in its archive; the site and all its data are deleted at day 90."
    )


def register_cli(app: Flask, settings: Settings) -> None:
    @app.cli.command("event-pass-run")
    @click.option("--apply", is_flag=True, help="Do it. Without this the command only says what it would do (a dry run).")
    def event_pass_run(apply: bool) -> None:
        """The daily job of the Event pass (ADR 044): record reminders, take a pass that ended out of service, and delete one for good a few days later
        (that last step only when EVENT_PASS_PURGE=true). Run it once a day."""
        from app.platform import event_pass
        from app.platform.lifecycle import delete_square

        db = app.extensions["db_factory"]()()
        try:
            actions = event_pass.run(
                db, settings, apply=apply, notify=_notify_owner(app, settings), purge=lambda session, sq: delete_square(session, settings, sq, None)
            )
            if apply:
                db.commit()
        finally:
            db.close()
        for a in actions:
            click.echo(("done: " if apply else "would: ") + " ".join(f"{k}={v}" for k, v in a.items()))
        click.echo(f"{len(actions)} action(s)" + ("" if apply else " (dry run: nothing was changed; add --apply)"))

    @app.cli.command("support-run")
    @click.option("--apply", is_flag=True, help="Do it. Without this the command only says what it would do (a dry run).")
    def support_run(apply: bool) -> None:
        """The job of support access (ADR 089): close the sessions of grants that ran out and mail the owner once when a grant ends soon. Run every 10 min."""
        import datetime as dt

        from app.platform import notify as notify_service
        from app.platform import support

        def tell(sq: Square, grant: object) -> bool:
            link = f"{settings.PLATFORM_FRONTEND_URL.rstrip('/')}/squares/{sq.id}/support"
            subject, text = support.mail_ends_soon(sq, grant, link)  # type: ignore[arg-type]
            mail = email_html.from_text(
                text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Support access", heading="Support access ends soon", button_label="Open Support access"
            )
            return notify_service.send_to_owner(app, db, sq, subject, text, **mail)

        db = app.extensions["db_factory"]()()
        try:
            actions = support.run(db, dt.datetime.now(dt.UTC), tell, apply)
            if apply:
                db.commit()
        finally:
            db.close()
        for a in actions:
            click.echo(("done: " if apply else "would: ") + " ".join(f"{k}={v}" for k, v in a.items()))
        click.echo(f"{len(actions)} action(s)" + ("" if apply else " (dry run: nothing was changed; add --apply)"))

    @app.cli.command("mail-domain-run")
    @click.option("--apply", is_flag=True, help="Do it. Without this the command only says what it would do (a dry run).")
    def mail_domain_run(apply: bool) -> None:
        """The job of the own sending domain (ADR 095): read every registered domain from Resend, keep its status, tell the owner once when it is
        verified and once
        when it failed. Needs RESEND_DOMAINS_API_KEY. Run it every hour."""
        from app.platform import mail_domain

        client = app.extensions.get("resend_domains")
        if client is None:
            raise click.ClickException("RESEND_DOMAINS_API_KEY is not set: there is nothing to ask (docs/setup/25-platform-email.md section 11)")
        db = app.extensions["db_factory"]()()
        try:
            actions = mail_domain.run(db, client, settings, apply)
            if apply:
                db.commit()
        finally:
            db.close()
        for a in actions:
            click.echo(("done: " if apply else "would: ") + " ".join(f"{k}={v}" for k, v in a.items()))
        click.echo(f"{len(actions)} action(s)" + ("" if apply else " (dry run: nothing was changed; add --apply)"))

    @app.cli.command("email-test")
    @click.argument("to")
    def email_test(to: str) -> None:
        """Send one test e-mail through the platform's e-mail service (EMAIL_PROVIDER) to check the key, the domain and the from address."""
        email = app.extensions["providers"].email
        if email is None:
            raise click.ClickException("EMAIL_PROVIDER is none: set EMAIL_PROVIDER=resend with RESEND_API_KEY and EMAIL_FROM (docs/setup/25-platform-email.md)")
        try:
            text = "This is a test from the rootsquares platform. If you can read it, e-mail works.\n"
            mail = email_html.from_text(text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Test", heading="E-mail works")
            email.send(to, "rootsquares test e-mail", text, **mail)
        except Exception as exc:  # noqa: BLE001 - say what failed without the key
            raise click.ClickException(f"The e-mail service refused it ({type(exc).__name__}: {exc})") from exc
        click.echo(f"sent a test e-mail to {to}")

    @app.cli.command("trial-run")
    @click.option("--apply", is_flag=True, help="Do it. Without this the command only says what it would do (a dry run).")
    def trial_run(apply: bool) -> None:
        """The daily job of the trial end (W12-R9): a square whose trial or paid time has run out without payment goes to sleep (Keep) until the owner pays.
        Works only with BILLING_ENFORCE=true. Run it once a day."""
        from app.platform import archive, trial
        from app.platform import sleep as sleep_service
        from app.platform.lifecycle import destroy_square_resources

        def put_to_sleep(_session: object, sq: Square) -> None:
            contact = sleep_service.fetch_contact(settings, sq)
            sq.running_plan = "keep"
            sq.sleep_state = sleep_service.SLEEPING
            sleep_service.mark_asleep(sq)
            if contact is not None or not sq.sleep_contact:
                sq.sleep_contact = json.dumps(contact or {})
            app.extensions["executor"].submit(sleep_service.run_pause, app.extensions["db_factory"](), settings, sq.id)

        def remind_owner(session: Session, sq: Square) -> bool:
            email = app.extensions["providers"].email
            if email is None:
                return False  # no e-mail service yet: not recorded, so it goes out once there is one
            owner = session.scalar(
                select(User)
                .join(models.Membership, models.Membership.user_id == User.id)
                .where(models.Membership.org_id == sq.org_id, models.Membership.role == models.MembershipRole.OWNER)
            )
            if owner is None:
                return False
            subject, text = trial.reminder_text(session, settings, sq)
            try:
                mail = email_html.from_text(
                    text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Your trial", heading="Your trial ends soon", button_label="Go to Billing"
                )
                email.send(owner.email, subject, text, **mail)
            except Exception:  # noqa: BLE001 - not recorded, so the next run tries again
                return False
            return True

        def notify_asleep(session: Session, sq: Square, reason: str) -> bool:
            email = app.extensions["providers"].email
            if email is None:
                return False  # no e-mail service yet: not recorded, so it goes out once there is one
            owner = session.scalar(
                select(User)
                .join(models.Membership, models.Membership.user_id == User.id)
                .where(models.Membership.org_id == sq.org_id, models.Membership.role == models.MembershipRole.OWNER)
            )
            if owner is None:
                return False
            subject, text = trial.asleep_text(settings, sq, reason)
            try:
                mail = email_html.from_text(
                    text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Your square", heading="Your square is asleep", button_label="Go to Billing"
                )
                email.send(owner.email, subject, text, **mail)
            except Exception:  # noqa: BLE001 - not recorded, so the next run tries again
                return False
            return True

        def notify_keep(session: Session, sq: Square, _reason: str) -> bool:
            email = app.extensions["providers"].email
            if email is None:
                return False  # no e-mail service yet: not recorded, so it goes out once there is one
            owner = session.scalar(
                select(User)
                .join(models.Membership, models.Membership.user_id == User.id)
                .where(models.Membership.org_id == sq.org_id, models.Membership.role == models.MembershipRole.OWNER)
            )
            if owner is None:
                return False
            subject, text = trial.keep_started_text(session, settings, sq)
            try:
                mail = email_html.from_text(
                    text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Your plan", heading="Your plan is now Keep", button_label="Go to Billing"
                )
                email.send(owner.email, subject, text, **mail)
            except Exception:  # noqa: BLE001 - not recorded, so the next run tries again
                return False
            return True

        def remind_archive(session: Session, sq: Square, n: int, delete_on: dt.datetime) -> bool:
            email = app.extensions["providers"].email
            if email is None:
                return False  # no e-mail service yet: not recorded, so it goes out once there is one
            owner = session.scalar(
                select(User)
                .join(models.Membership, models.Membership.user_id == User.id)
                .where(models.Membership.org_id == sq.org_id, models.Membership.role == models.MembershipRole.OWNER)
            )
            if owner is None:
                return False
            subject, text = archive.notice_text(sq, n, delete_on, f"{settings.PLATFORM_FRONTEND_URL.rstrip('/')}/squares/{sq.id}/billing")
            try:
                mail = email_html.from_text(
                    text, site_url=settings.PLATFORM_FRONTEND_URL, eyebrow="Your square", heading="Your square will be archived", button_label="Go to Billing"
                )
                email.send(owner.email, subject, text, **mail)
            except Exception:  # noqa: BLE001 - not recorded, so the next run tries again
                return False
            return True

        def archive_square(_session: Session, sq: Square) -> None:
            destroy_square_resources(settings, sq)  # raises when the provider cannot remove it: the next run tries again
            sq.provider_project_ref = sq.neon_project_id = sq.db_connection = sq.provider_secrets = None

        db = app.extensions["db_factory"]()()
        try:
            actions = trial.run(db, settings, apply=apply, sleep=put_to_sleep, remind=remind_owner, notify=notify_asleep, notify_keep=notify_keep)
            actions += archive.run(db, settings, apply=apply, remind=remind_archive, archive=archive_square)
            if apply:
                db.commit()
        finally:
            db.close()
        for a in actions:
            click.echo(("done: " if apply else "would: ") + " ".join(f"{k}={v}" for k, v in a.items()))
        click.echo(f"{len(actions)} action(s)" + ("" if apply else " (dry run: nothing was changed; add --apply)"))
        if not settings.BILLING_ENFORCE:
            click.echo("BILLING_ENFORCE is false: nothing is put to sleep for lack of payment")

    @app.cli.command("init-db")
    def init_db() -> None:
        """Create the platform tables (no migrations yet, see ADR 027)."""
        engine = app.extensions["db_engine"]()
        Base.metadata.create_all(engine)
        for column in add_missing_columns(engine):
            click.echo(f"added column {column}")
        enable_rls(engine)
        click.echo("platform tables ready")

    @app.cli.group("db")
    def db_group() -> None:
        """Migrations of the platform database (Alembic): upgrade, downgrade, current, history, revision."""

    @db_group.command("upgrade")
    @click.argument("revision", default="head")
    def db_upgrade(revision: str) -> None:
        """Bring the platform database to a revision (default: head). A database made by init-db is adopted first."""
        for note in upgrade(settings, app.extensions["db_engine"](), revision):
            click.echo(note)
        click.echo("platform database up to date")

    @db_group.command("downgrade")
    @click.argument("revision")
    def db_downgrade(revision: str) -> None:
        """Go back to a revision (for example -1)."""
        command.downgrade(alembic_config(settings), revision)

    @db_group.command("current")
    def db_current() -> None:
        """Show the revision the database is at."""
        command.current(alembic_config(settings), verbose=True)

    @db_group.command("history")
    def db_history() -> None:
        """List all revisions."""
        command.history(alembic_config(settings), verbose=False)

    @db_group.command("revision")
    @click.option("-m", "--message", required=True)
    @click.option("--rev-id", default=None, help="Use this revision id instead of a random one (the baseline is 0001).")
    @click.option("--autogenerate/--empty", default=True, help="Compare the models with the database and write the difference.")
    def db_revision(message: str, rev_id: str | None, autogenerate: bool) -> None:
        """Write a new migration file in migrations/versions."""
        command.revision(alembic_config(settings), message=message, autogenerate=autogenerate, rev_id=rev_id)

    @app.cli.command("seed-staff")
    def seed_staff() -> None:
        """Create or update a staff account (ADR 083) from SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD (environment or .env; at least 12 characters)."""
        email, password = staff.normalise_email(settings.SEED_ADMIN_EMAIL), settings.SEED_ADMIN_PASSWORD
        if not email or len(password) < staff.MIN_PASSWORD:
            raise click.ClickException(f"Set SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD (at least {staff.MIN_PASSWORD} characters)")
        with app.extensions["db_factory"]()() as db:
            member = staff.get_staff(db, email)
            if member is None:
                staff.create_staff(db, email, password, name="Platform admin")
                action = "created"
            elif verify_password(member.password_hash, password):
                action = "unchanged"  # dev.ps1 runs this on every start: only a CHANGED password ends the existing logins
            else:
                staff.set_password(db, member, password)
                action = "updated"
            db.add(AuditLog(action=f"staff.seed_{action}", entity="staff", entity_id=str(member.id if member else ""), data={}))
            db.commit()
        click.echo(f"staff account {action}")

    @app.cli.command("staff-create")
    @click.argument("email")
    @click.option("--name", default="", help="The person's name.")
    @click.password_option(
        prompt=f"Password (at least {staff.MIN_PASSWORD} characters)", confirmation_prompt=True, help="Leave it out: you are asked, and the typing is hidden."
    )
    def staff_create(email: str, name: str, password: str) -> None:
        """Create a staff account. The first sign-in on the admin address enrols the second step (TOTP)."""
        with app.extensions["db_factory"]()() as db:
            try:
                staff.create_staff(db, email, password, name=name)
            except staff.StaffError as e:
                raise click.ClickException(str(e)) from e
            db.commit()
        click.echo("staff account created; the first sign-in sets up the authenticator app")

    @app.cli.command("staff-disable")
    @click.argument("email")
    @click.option("--enable", is_flag=True, help="Switch the account on again.")
    def staff_disable(email: str, enable: bool) -> None:
        """Switch a staff account off (ends its logins) or on again."""
        with app.extensions["db_factory"]()() as db:
            member = staff.get_staff(db, email)
            if member is None:
                raise click.ClickException("No such staff account")
            staff.set_disabled(db, member, not enable)
            db.commit()
        click.echo("staff account enabled" if enable else "staff account disabled")

    @app.cli.command("staff-reset-2fa")
    @click.argument("email")
    def staff_reset_2fa(email: str) -> None:
        """Lost phone: remove the second step (and every login) so the person enrols again at the next sign-in."""
        with app.extensions["db_factory"]()() as db:
            member = staff.get_staff(db, email)
            if member is None:
                raise click.ClickException("No such staff account")
            staff.reset_second_step(db, member)
            db.commit()
        click.echo("second step removed; the next sign-in sets it up again")

    @app.cli.command("staff-list")
    def staff_list() -> None:
        """List the staff accounts (no secrets)."""
        with app.extensions["db_factory"]()() as db:
            rows = db.scalars(select(models.StaffUser).order_by(models.StaffUser.created_at)).all()
            for m in rows:
                state = "disabled" if m.disabled_at else "active"
                second = "on" if m.totp_enabled else "not set up"
                last = m.last_login_at.isoformat() if m.last_login_at else "never"
                click.echo(f"{m.email}  {state}  second step {second}  last sign-in {last}")
            if not rows:
                click.echo("no staff accounts")

    @app.cli.command("enable-google")
    @click.argument("slug")
    @click.option("--disable", is_flag=True, help="Switch Google sign-in off again.")
    @click.option("--yes", is_flag=True, help="Do not ask whether the callback URL is already in Google Cloud Console.")
    def enable_google(slug: str, disable: bool, yes: bool) -> None:
        """Turn Google sign-in on for a square's own sign-in project (Supabase, or Neon Auth at Neon) with the platform OAuth client; mark it enabled."""
        with app.extensions["db_factory"]()() as db:
            sq = db.scalar(select(Square).where(Square.slug == slug))
            if sq is None:
                raise click.ClickException("No such square")
            if sq.neon_project_id:
                _enable_google_neon(db, sq, disable, yes)
                return
            if not settings.SUPABASE_ACCESS_TOKEN:
                raise click.ClickException("Set SUPABASE_ACCESS_TOKEN")
            if not disable and not (settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET):
                raise click.ClickException("Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET")
            if not sq.provider_project_ref:
                raise click.ClickException("This square has no Supabase project of its own")
            if not disable:
                click.echo("Add this under Authorised redirect URIs of the Google OAuth client (Google Cloud Console):")
                click.echo(f"  {square_auth.callback_url(sq.provider_project_ref)}")
                if not yes and not click.confirm("Is it added?"):
                    raise click.Abort()
            square_auth.set_google_login(
                settings.SUPABASE_ACCESS_TOKEN, sq.provider_project_ref, settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET, not disable
            )
            sq.google_login = "requested" if disable else "enabled"
            db.add(AuditLog(action="square.google_login", entity="square", entity_id=str(sq.id), org_id=sq.org_id, data={"enabled": not disable, "via": "cli"}))
            db.commit()
        click.echo("Google sign-in switched off" if disable else "Google sign-in switched on")

    def _enable_google_neon(db: Session, sq: Square, disable: bool, yes: bool) -> None:
        """Google sign-in for a square made at Neon. With GOOGLE_OAUTH_CLIENT_ID and _SECRET set it is the platform's own client (its callback must be added in
        Google Cloud Console first); without them Neon's shared development credentials are used (development only)."""
        target = neon_target(sq, Encryptor(settings.fernet_key))
        if target is None or not settings.NEON_API_KEY:
            raise click.ClickException("This square has no Neon project of its own, or NEON_API_KEY is not set")
        own = bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)
        if not disable and own:
            click.echo("Add this under Authorised redirect URIs of the Google OAuth client (Google Cloud Console):")
            click.echo(f"  {square_auth.neon_callback_url(target[2])}")
            if not yes and not click.confirm("Is it added?"):
                raise click.Abort()
        elif not disable:
            click.echo("No GOOGLE_OAUTH_CLIENT_ID/SECRET set: using Neon's shared development credentials (not for real users).")
        try:
            NeonProvisioner(settings.NEON_API_KEY, settings.NEON_REGION).set_google_login(
                target[0], target[1], settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET, not disable
            )
        except NeonApiError as exc:
            raise click.ClickException(str(exc)) from exc
        sq.google_login = "requested" if disable else "enabled"
        data = {"enabled": not disable, "via": "cli", "own_client": own}
        db.add(AuditLog(action="square.google_login", entity="square", entity_id=str(sq.id), org_id=sq.org_id, data=data))
        db.commit()
        click.echo("Google sign-in switched off" if disable else "Google sign-in switched on")

    @app.cli.command("check-square-token")
    @click.argument("slug")
    @click.argument("token")
    def check_square_token(slug: str, token: str) -> None:
        """Verify a token issued by a square's own auth project and show who it is (a check for the square token verifier; prints no secrets)."""
        with app.extensions["db_factory"]()() as db:
            square_id = db.scalar(select(Square.id).where(Square.slug == slug))
        if square_id is None:
            raise click.ClickException("No such square")
        try:
            who = app.extensions["square_auth"].authenticate(square_id, token)
        except SquareAuthError as exc:
            raise click.ClickException(f"{exc.code}: {exc}") from exc
        if who is None:
            raise click.ClickException("invalid_token: the token is invalid or expired for this square")
        click.echo(f"valid token: sub={who.sub} email={who.email}")
        click.echo(f"admin of the square: {who.admin.role}" if who.admin else "not an admin of the square")

    @app.cli.command("sync-square-auth")
    @click.argument("slug")
    def sync_square_auth(slug: str) -> None:
        """Set the Site URL and the allowed redirect URLs of an existing square's auth project again (after changing SQUARE_EXTRA_REDIRECT_URLS, or
        after staff activated the square's own website domain, ADR 098)."""
        with app.extensions["db_factory"]()() as db:
            sq = db.scalar(select(Square).where(Square.slug == slug))
            if sq is not None and sq.neon_project_id:
                target = neon_target(sq, Encryptor(settings.fernet_key))
                if target is None or not settings.NEON_API_KEY:
                    raise click.ClickException("This square has no Neon project of its own, or NEON_API_KEY is not set")
                addresses = square_auth.trusted_addresses(sq.slug, settings.SQUARE_DOMAIN_SUFFIX, list(settings.square_extra_redirects))
                if sq.site_domain:
                    addresses.append(f"https://{sq.site_domain}")  # the square's own website domain (ADR 098)
                try:
                    NeonProvisioner(settings.NEON_API_KEY, settings.NEON_REGION).set_redirects(target[0], target[1], addresses)
                except NeonApiError as exc:
                    raise click.ClickException(str(exc)) from exc
                click.echo(f"trusted addresses: {', '.join(addresses)}")
                return
            if not settings.SUPABASE_ACCESS_TOKEN:
                raise click.ClickException("Set SUPABASE_ACCESS_TOKEN")
            if sq is None or not sq.provider_project_ref:
                raise click.ClickException("No such square with a Supabase project of its own")
            allow = square_auth.set_redirects(
                settings.SUPABASE_ACCESS_TOKEN,
                sq.provider_project_ref,
                f"https://{sq.slug}.{settings.SQUARE_DOMAIN_SUFFIX}",
                [u.replace("{slug}", sq.slug) for u in settings.square_extra_redirects] + ([f"https://{sq.site_domain}/**"] if sq.site_domain else []),
            )
        click.echo(f"allowed redirect URLs: {allow}")
