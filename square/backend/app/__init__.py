from flask import Flask, app
from flask_cors import CORS

from app.config import get_config, validate_auth_config, validate_production_config
from app.gate import init_gate, validate_gate_config
from app.extensions import db, migrate
from app.email.service import FakeEmailService, NotConfiguredEmailService, ResendEmailService
from app.storage.service import FakeStorageService, S3CompatibleStorage


def create_app(env_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(env_name))
    if not app.config["TESTING"]:
        validate_auth_config(app.config)
        validate_production_config(app.config)
        validate_gate_config(app.config)

    # CORS(app, origins=[app.config["FRONTEND_ORIGIN"]])
    # Split the comma-separated string into a list for Flask-CORS
    origins_list = [o.strip() for o in app.config["FRONTEND_ORIGIN"].split(",") if o.strip()]
    CORS(app, origins=origins_list, supports_credentials=True)

    db.init_app(app)
    migrate.init_app(app, db)

    init_gate(app)  # the site gate (ADR 099): before the square is looked up, so it answers on every host; no passcode = no gate

    from app.tenancy import init_tenancy

    init_tenancy(app)  # many squares from one server when PLATFORM_DATABASE_URL is set (rootsquares W6-R26)

    # Import models to ensure they're registered with SQLAlchemy
    from app.audit.models import AuditLog  # noqa: F401
    from app.analytics import models as _analytics_models  # noqa: F401  (visit counts, ADR 090)

    if app.config["TESTING"]:
        app.extensions["email_service"] = FakeEmailService()
    elif app.config["RESEND_API_KEY"] and app.config["EMAIL_FROM"]:
        app.extensions["email_service"] = ResendEmailService(
            api_key=app.config["RESEND_API_KEY"], from_address=app.config["EMAIL_FROM"]
        )
    else:
        # Lazy failure by design (see app.email.service) — the app still starts (e.g. `flask
        # db migrate` shouldn't need real email credentials), but any real send attempt raises
        # a clear, developer-facing error rather than silently pretending to succeed.
        app.extensions["email_service"] = NotConfiguredEmailService()

    if app.config["TESTING"] or not app.config["STORAGE_S3_ENDPOINT_URL"]:
        # Also covers development before real Supabase Storage credentials are configured —
        # boto3 rejects an empty endpoint_url outright, so fall back to the in-memory fake
        # rather than crash commands (e.g. `flask db migrate`) that don't even touch storage.
        app.extensions["public_storage"] = FakeStorageService()
        app.extensions["private_storage"] = FakeStorageService()
    else:
        app.extensions["public_storage"] = S3CompatibleStorage(
            bucket=app.config["STORAGE_PUBLIC_BUCKET"],
            public=True,
            endpoint_url=app.config["STORAGE_S3_ENDPOINT_URL"],
            access_key=app.config["STORAGE_S3_ACCESS_KEY"],
            secret_key=app.config["STORAGE_S3_SECRET_KEY"],
            region=app.config["STORAGE_S3_REGION"],
            public_base_url=f'{app.config["STORAGE_PUBLIC_BASE_URL"]}/{app.config["STORAGE_PUBLIC_BUCKET"]}',
        )
        # Expense receipts hold real vendor/financial detail — kept in the private bucket
        # (presigned, time-limited URLs via url_for) rather than the public gallery bucket.
        app.extensions["private_storage"] = S3CompatibleStorage(
            bucket=app.config["STORAGE_PRIVATE_BUCKET"],
            public=False,
            endpoint_url=app.config["STORAGE_S3_ENDPOINT_URL"],
            access_key=app.config["STORAGE_S3_ACCESS_KEY"],
            secret_key=app.config["STORAGE_S3_SECRET_KEY"],
            region=app.config["STORAGE_S3_REGION"],
        )

    from app.audit.admin_routes import admin_audit_bp
    from app.auth.cli import register_cli
    from app.auth.routes import auth_bp
    from app.auth.neon_webhooks import neon_webhooks_bp
    from app.auth.admin_routes import admin_users_bp
    from app.accounting.admin_routes import admin_accounting_bp
    from app.accounting.contributions_routes import admin_contributions_bp
    from app.payments.credentials_routes import admin_payment_providers_bp
    from app.accounting.support_routes import event_support_bp
    from app.checkin.admin_routes import checkin_bp
    from app.committee.admin_routes import admin_committee_bp
    from app.committee.routes import committee_bp
    from app.founders.admin_routes import admin_founders_bp
    from app.founders.routes import founders_bp
    from app.lookups.admin_routes import admin_lookups_bp
    from app.lookups.routes import lookups_bp
    from app.magazines.admin_routes import admin_magazines_bp
    from app.magazines.routes import magazines_bp
    from app.sponsors.admin_routes import admin_sponsors_bp
    from app.sponsors.routes import sponsors_bp
    from app.contact.routes import contact_bp
    from app.coupons.admin_routes import admin_coupons_bp
    from app.coupons.routes import coupons_bp
    from app.event_pass import admin_event_pass_bp
    from app.events.admin_routes import admin_events_bp
    from app.events import series_routes  # noqa: F401  (adds the recurring-event routes to admin_events_bp)
    from app.events.routes import events_bp
    from app.gallery.admin_routes import admin_gallery_bp
    from app.gallery.routes import gallery_bp
    from app.health.routes import health_bp
    from app.members.admin_routes import admin_members_bp
    from app.members.routes import members_bp
    from app.memberships.admin_routes import admin_membership_types_bp, admin_memberships_bp
    from app.memberships.drive_routes import membership_drive_bp
    from app.memberships.join_routes import membership_join_bp
    from app.memberships.followup_routes import admin_membership_followup_bp
    from app.memberships.payment_routes import memberships_payment_bp
    from app.memberships.routes import memberships_bp
    from app.news.admin_routes import admin_news_bp
    from app.news.routes import news_bp
    from app.imports.admin_routes import admin_imports_bp
    from app.orders.admin_routes import admin_orders_bp
    from app.payments.admin_routes import admin_payments_bp
    from app.payments.vipps_routes import vipps_public_bp, vipps_webhooks_bp, stripe_public_bp, stripe_webhooks_bp
    from app.donations.admin_routes import admin_donations_bp
    from app.donations.routes import donations_bp
    from app.messages.admin_routes import admin_messages_bp
    from app.messages.routes import messages_bp
    from app.reports.admin_routes import admin_reports_bp
    from app.settings.admin_routes import admin_settings_bp
    from app.settings.routes import settings_bp
    from app.sitemap.routes import sitemap_bp
    from app.testimonials.admin_routes import admin_testimonials_bp
    from app.testimonials.routes import testimonials_bp
    from app.newsletter.admin_routes import admin_newsletter_bp
    from app.newsletter.routes import newsletter_bp
    from app.orders.routes import orders_bp
    from app.tickets.admin_routes import admin_ticket_types_bp, admin_tickets_bp
    from app.tickets.routes import tickets_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(contact_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(admin_events_bp)
    app.register_blueprint(admin_event_pass_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(neon_webhooks_bp)
    app.register_blueprint(admin_audit_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(checkin_bp)
    app.register_blueprint(coupons_bp)
    app.register_blueprint(admin_coupons_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(admin_members_bp)
    app.register_blueprint(memberships_bp)
    app.register_blueprint(memberships_payment_bp)
    app.register_blueprint(admin_memberships_bp)
    app.register_blueprint(admin_membership_types_bp)
    app.register_blueprint(membership_drive_bp)
    app.register_blueprint(membership_join_bp)
    app.register_blueprint(admin_membership_followup_bp)
    app.register_blueprint(gallery_bp)
    app.register_blueprint(admin_gallery_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(admin_news_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(admin_ticket_types_bp)
    app.register_blueprint(admin_tickets_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(admin_orders_bp)
    app.register_blueprint(admin_payments_bp)
    app.register_blueprint(vipps_webhooks_bp)
    app.register_blueprint(donations_bp)
    app.register_blueprint(admin_donations_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(admin_messages_bp)
    app.register_blueprint(vipps_public_bp)
    app.register_blueprint(stripe_webhooks_bp)
    app.register_blueprint(stripe_public_bp)
    app.register_blueprint(admin_reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(admin_settings_bp)
    app.register_blueprint(sitemap_bp)
    from app.module_status import internal_bp

    app.register_blueprint(internal_bp)  # owner-only status per module for the platform (W8-R27); answers only with the shared key
    from app.analytics.routes import analytics_bp, analytics_internal_bp

    app.register_blueprint(analytics_bp)  # the beacon of the public site (ADR 090): counts only when the owner switched counting on
    app.register_blueprint(analytics_internal_bp)  # the aggregates for the owner, over the platform's shared key
    app.register_blueprint(admin_imports_bp)
    app.register_blueprint(testimonials_bp)
    app.register_blueprint(newsletter_bp)
    app.register_blueprint(admin_newsletter_bp)
    app.register_blueprint(admin_testimonials_bp)
    app.register_blueprint(committee_bp)
    app.register_blueprint(admin_committee_bp)
    app.register_blueprint(founders_bp)
    app.register_blueprint(admin_founders_bp)
    app.register_blueprint(lookups_bp)
    app.register_blueprint(admin_lookups_bp)
    app.register_blueprint(magazines_bp)
    app.register_blueprint(admin_magazines_bp)
    app.register_blueprint(sponsors_bp)
    app.register_blueprint(admin_sponsors_bp)
    app.register_blueprint(admin_accounting_bp)
    app.register_blueprint(admin_contributions_bp)
    app.register_blueprint(admin_payment_providers_bp)
    app.register_blueprint(event_support_bp)

    register_cli(app)
    from app.newsletter.cli import register_cli as register_newsletter_cli

    register_newsletter_cli(app)

    from app.jobs.keep_alive import start_keep_alive_job
    from app.jobs.event_series import start_event_series_job
    from app.jobs.messages import start_messages_job
    from app.jobs.privacy import start_privacy_job
    from app.jobs.vipps_sweep import start_vipps_sweep_job

    start_keep_alive_job(app)
    start_vipps_sweep_job(app)  # in many-squares mode these two loop over the squares (app/jobs/squares.py)
    start_privacy_job(app)
    start_messages_job(app)
    start_event_series_job(app)

    from app.common.errors import register_error_handlers

    register_error_handlers(app)

    return app
