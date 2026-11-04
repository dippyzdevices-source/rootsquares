"""Composition root: wires settings, providers and the platform API (ADR 026: squares are separate Neon projects)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog
from flask import Flask
from flask_cors import CORS

from app.platform import register_platform
from app.platform.billing import build_billing
from app.platform.cli import register_cli
from app.platform.square_verifier import SquareAuthVerifier
from app.providers.auth import build_auth_provider
from app.providers.email import build_email
from app.providers.memory.rate_limiter import InMemoryRateLimiter
from app.providers.render_domains import build_render_domains
from app.providers.resend_domains import build_resend_domains
from app.providers.storage import build_storage
from app.shared.config import Settings
from app.shared.db import init_db
from app.shared.errors import register_error_handlers
from app.shared.gate import register_gate
from app.shared.health import register_health
from app.shared.interfaces import Providers
from app.shared.logging import configure_logging
from app.shared.request_context import install_request_context


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings()
    configure_logging(settings.LOG_LEVEL)

    app = Flask(__name__)
    app.config["TESTING"] = settings.ENV == "test"
    app.extensions["settings"] = settings
    # Providers are wired here and kept in app.extensions.
    storage, private_storage = build_storage(settings)
    app.extensions["providers"] = Providers(
        auth=build_auth_provider(settings),
        storage=storage,
        private_storage=private_storage,
        rate_limiter=InMemoryRateLimiter(),
        email=build_email(settings),
    )
    # Square provisioning runs in the background and updates the square's status (jobs table and a worker process come later).
    app.extensions["resend_domains"] = build_resend_domains(settings)  # None without RESEND_DOMAINS_API_KEY (the own sending domain is then not switched on)
    # None without RENDER_API_KEY and RENDER_SITE_SERVICE_ID: staff then add the domains on Render by hand
    app.extensions["render_domains"] = build_render_domains(settings)
    app.extensions["billing"] = build_billing(settings)  # the fake checkout in local and test, Stripe once the user has integrated it (W10-R42)
    app.extensions["executor"] = ThreadPoolExecutor(max_workers=2, thread_name_prefix="provision")

    # The public square data (/public/...) is read by square sites on any host (<slug>.localhost, <slug>.rootsquares.com, custom domains), so it answers
    # every origin, but without credentials: the square token travels in the Authorization header, never in cookies. Everything else: explicit origins.
    resources: dict[str | re.Pattern[str], dict[str, Any]] = {}
    if settings.serves_customer:
        resources[r"/api/platform/v1/public/*"] = {"origins": "*", "supports_credentials": False, "allow_headers": ["Content-Type", "Authorization"]}
    if settings.serves_admin and settings.admin_origins:  # the staff API answers the admin application only (the longer pattern wins)
        resources[r"/api/admin/v1/*"] = {
            "origins": settings.admin_origins,
            "supports_credentials": True,
            "allow_headers": ["Content-Type", "X-Requested-With", "X-Request-ID"],
        }
    if settings.serves_customer and settings.cors_origins:  # the admin service answers no customer origin at all
        resources[r"/*"] = {
            "origins": settings.cors_origins,
            "supports_credentials": True,
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "X-Request-ID"],
        }
    # The gate's own address (ADR 099) answers the sites of every surface this process serves, with the cookie: the customer app and the admin
    # application each ask it at start-up (the passcode, and the word of the environment strip). One entry for both, because the longest pattern
    # wins and would otherwise shut the other one out.
    gate_origins = [*(settings.cors_origins if settings.serves_customer else []), *(settings.admin_origins if settings.serves_admin else [])]
    if gate_origins:
        resources[r"/gate"] = {"origins": gate_origins, "supports_credentials": True, "allow_headers": ["Content-Type"]}
    CORS(app, resources=resources)

    install_request_context(app)
    register_gate(app, settings)  # the site gate (ADR 099): empty SITE_GATE_PASSWORD = no gate
    register_error_handlers(app)
    register_health(app)
    init_db(app, settings)
    app.extensions["square_auth"] = SquareAuthVerifier(app.extensions["db_factory"], settings)  # for the square API (not built yet)
    register_platform(app)
    register_cli(app, settings)
    structlog.get_logger("app.main").info("api_surface", surface=settings.API_SURFACE)  # which routes this process serves (ADR 084)
    return app
