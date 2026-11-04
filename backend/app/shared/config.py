"""Settings from the environment, validated at startup (a bad config stops the app from booting)."""

from __future__ import annotations

import base64
import hashlib
import os
from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Local and test only: fixed development keys so a restart can still read what was encrypted before. Production must set its own.
_DEV_JWT_SECRET = "dev-only-jwt-secret-do-not-use-in-production-0123456789"
_DEV_FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"dev-only-fernet-key").digest()).decode()
LOCAL_CORS_ORIGIN = "http://localhost:5273"
LOCAL_ADMIN_ORIGIN = "http://localhost:5275"
# The file the settings are read from (W26-R51): `.env.local` in the backend folder, WHEREVER the process was started (a path relative to the start folder would
# silently find nothing from another folder). ENV_FILE (a variable of the process, not a line inside a file) names another one, for example
# `.env.staging` (looked up in the backend folder) or a full path, to run a migration against staging from this machine. A value set in the real environment
# (Render's dashboard, the shell) always wins over the file. No file at all is fine: the defaults and the environment are used.
BACKEND_DIR = Path(__file__).resolve().parents[2]
_env_name = os.environ.get("ENV_FILE", "").strip() or ".env.local"
ENV_FILE = str(Path(_env_name) if Path(_env_name).is_absolute() else BACKEND_DIR / _env_name)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore", frozen=True)

    ENV: Literal["local", "test", "production"] = "local"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Comma separated explicit origins, never "*". Local only default: the Vite dev server.
    CORS_ORIGINS: str = ""
    # Origins of the admin application (ADR 083): the only pages that may call /api/admin/v1. Never the same as the customer origins.
    ADMIN_ORIGINS: str = ""
    # Which routes this process serves (ADR 084): "customer" = the customer API and the public square data, "admin" = the staff API only, "all" = both (local
    # development and tests). Production runs two services from the same code, one of each; a service answers 404 for the other's addresses.
    API_SURFACE: Literal["customer", "admin", "all"] = "all"

    # Platform database (postgresql+psycopg://...). local Postgres service on 5432 for dev, Neon later.
    DATABASE_URL: str = Field(default="", repr=False)

    # Sessions: JWT in httpOnly cookies. Secrets come from the environment.
    JWT_SECRET: str = Field(default="", repr=False)
    # Staff secrets (ADR 084, database option B): the staff cookie is signed with STAFF_JWT_SECRET, the staff TOTP secrets are encrypted with STAFF_FERNET_KEY,
    # so a customer-service secret never opens a staff login. Outside production an empty value falls back to the shared key above (local development and the
    # secrets of staff already enrolled keep working); production requires both on the admin service and forbids them on the customer service.
    STAFF_JWT_SECRET: str = Field(default="", repr=False)
    STAFF_FERNET_KEY: str = Field(default="", repr=False)
    # Support access (ADR 089): the admin service signs a support session token with SUPPORT_SESSION_KEY and each square server verifies it with the same
    # key. The customer service never holds it (production refuses it there); outside production an empty value falls back to the staff signing secret.
    SUPPORT_SESSION_KEY: str = Field(default="", repr=False)
    ACCESS_TTL_MINUTES: int = 15
    REFRESH_TTL_DAYS: int = 14
    COOKIE_SECURE: bool = False
    LOGIN_RATE_LIMIT: int = 5  # attempts per window and (ip, email)
    LOGIN_RATE_WINDOW_SECONDS: int = 60
    # The staff sign-in asks for an authenticator code after the password (ADR 083). False = the password alone signs in, for local development only
    # (W26-R11): production refuses to start with it off.
    STAFF_SECOND_STEP_REQUIRED: bool = True
    # The site gate (ADR 099, W26-R20): one shared passcode in front of the whole API, for a staging deploy that must stay private. Empty = no gate
    # (development, tests). Set = at least 16 characters; every request without the cookie the passcode earns is refused. SITE_GATE_HOURS is how long a
    # pass lasts. PROXY_HOPS is how many proxies stand in front of the service (Render: 1), so the caller's own address can be read from
    # X-Forwarded-For for the limit on wrong tries.
    SITE_GATE_PASSWORD: str = Field(default="", repr=False)
    SITE_GATE_HOURS: int = 168
    # Which copy of rootsquares this is, shown as a strip above every page (W26-R25), DISPLAY ONLY: nothing behaves differently because of it.
    # Set it to Staging on a staging deploy; empty = Local when ENV is local, and nothing in test and production (no strip).
    ENV_LABEL: str = ""
    PROXY_HOPS: int = 0
    STAFF_IDLE_MINUTES: int = 30  # a staff login ends after this long without a request
    STAFF_SESSION_HOURS: int = 8  # and in any case after this long

    # Service key of the PLATFORM auth project (Supabase: service_role or sb_secret_...). Only used to delete a person's sign-in account when they
    # delete their account. Without it the platform data is still deleted and the answer says the provider account remains.
    AUTH_ADMIN_KEY: str = Field(default="", repr=False)

    # Encrypts each square's database connection string stored in the platform database (Fernet key, urlsafe base64, 32 bytes).
    FERNET_KEY: str = Field(default="", repr=False)

    # Square provisioning. "local" creates a database in the local Postgres, "neon" calls the Neon API (implemented, not run in dev).
    PROVISIONER: Literal["local", "neon", "supabase"] = "local"
    SQUARE_TEMPLATE_CMD: str = ""  # run AFTER the admins table is made in each new square database (W6-R35); env: SQUARE_DATABASE_URL, SLUG, OWNER_*
    SQUARE_DOMAIN_SUFFIX: str = "rootsquares.com"
    # The one name a square's own website domain points to with a CNAME (ADR 098): at the DNS host it is a CNAME to the Render address,
    # so owners never see Render
    CUSTOM_DOMAIN_TARGET: str = "squares.rootsquares.com"
    # Render's Custom Domains API (W26-R8, ADR 098): an account API key and the id of the square SITE service (srv-...). Both set = staff's Activate adds the
    # domain on Render and Remove deletes it; either empty = staff add it by hand. Admin service only (the key reaches the whole Render account).
    RENDER_API_KEY: str = Field(default="", repr=False)
    RENDER_SITE_SERVICE_ID: str = ""
    # The shared square server (square/backend), for the owner's Modules screen (W8-R27): what a module holds and what is pending in it. The key must equal
    # the square server's PLATFORM_INTERNAL_KEY. Either empty = the platform cannot ask, and the screen simply shows no stored data and no warnings.
    SQUARE_SERVER_URL: str = ""  # e.g. http://127.0.0.1:5002 locally
    SQUARE_INTERNAL_KEY: str = Field(default="", repr=False)
    NEON_API_KEY: str = Field(default="", repr=False)
    NEON_REGION: str = "aws-eu-central-1"
    # PROVISIONER=supabase (local/test, ADR 028): one Supabase project per square through the Management API.
    SUPABASE_ACCESS_TOKEN: str = Field(default="", repr=False)  # personal access token
    SUPABASE_ORG_SLUG: str = ""
    SUPABASE_REGION: str = "eu-west-1"
    # Platform billing (docs/reference/billing-and-payments.md, guides 22 and 24).
    # "fake" = a test checkout page in the platform frontend, no money moves (local, test).
    # "stripe" = Stripe Checkout in US dollars (production requires it). The keys are never printed or logged.
    BILLING_PROVIDER: Literal["fake", "stripe"] = "fake"
    BILLING_TRIAL_DAYS: int = 7  # a new square (not an event pass) starts with this many days of Live paid for (W10-R45)
    BILLING_REFUND_DAYS: int = 14  # a platform admin may refund a first payment this many days after it was paid (W12-R19)
    BILLING_GRACE_DAYS: int = 7  # days a lapsed paid period keeps the site live before the daily trial-run job puts it to sleep
    EVENT_PASS_LIVE_DAYS: int = 45  # an Event pass is live this many days from payment (W11, ADR 044)
    EVENT_PASS_ARCHIVE_DAYS: int = 45  # then this many days of archive: owner only, read-only, to save the reports
    EVENT_PASS_SOFT_DELETE_DAYS: int = 14  # then it leaves service; its project is deleted for good this many days later
    EVENT_PASS_PURGE: bool = False  # false: the daily job only says what it would delete (nothing is deleted at a provider until the user switches it on)
    SLEEP_ARCHIVE_DAYS: int = 360  # asleep with nothing paid this many days (12 months of 30) = archived, after three reminders (W13-R48, ADR 059)
    SLEEP_ARCHIVE_PURGE: bool = False  # false: the daily job only sends reminders and says what it would archive; nothing is deleted at a provider
    # Countries whose tax is inside the listed price, as COUNTRY:PERCENT pairs (W13-R51, ADR 060): we send Stripe the price without it, Stripe adds it, and
    # the customer pays the listed price in all. A country not listed is sent the listed price as it is. Add a country when you know its rate.
    BILLING_TAX_RATES: str = "NO:25"
    BILLING_ENFORCE: bool = False  # false: waking a sleeping square is free; true: it needs a paid running period (paid_until in the future)
    STRIPE_SECRET_KEY: str = Field(default="", repr=False)
    STRIPE_WEBHOOK_SECRET: str = Field(default="", repr=False)
    # Platform e-mail (W12-R14): "none" sends nothing; "resend" needs RESEND_API_KEY and EMAIL_FROM (an address on a domain verified at Resend)
    EMAIL_PROVIDER: Literal["none", "resend"] = "none"
    RESEND_API_KEY: str = Field(default="", repr=False)
    EMAIL_FROM: str = ""
    # A Grove square's own sending domain (ADR 091, W25-R24): a FULL ACCESS Resend key (domains can only be managed with one;
    # the sending key above must not be it) and the region of new domains
    RESEND_DOMAINS_API_KEY: str = Field(default="", repr=False)
    RESEND_DOMAINS_REGION: str = "eu-west-1"
    # where the platform tells its own staff about a request (an own sending domain, a call for IT help): hello@rootsquares.com; empty = no notice
    STAFF_NOTICE_EMAIL: str = ""
    # Own sending domain (ADR 095, W25-R32): True = a Grove owner's request is set up at once (the plan allows it); False = staff set up each request
    # in the admin application
    MAIL_DOMAIN_AUTO_APPROVE: bool = True
    EMAIL_REPLY_TO: str = ""  # optional: where replies to the platform's mails go (W25-R4), e.g. a mailbox when EMAIL_FROM only sends
    BILLING_TRIAL_REMINDER_HOURS: int = 24  # the trial reminder goes out when this many hours or fewer are left (day 6 of 7)
    STRIPE_TEST_CLOCK_ID: str = ""  # test keys only: new Stripe customers are attached to this test clock so renewals can be tried by moving time (guide 24)
    STRIPE_TAX_CODE: str = "txcd_10103001"  # Stripe product tax code (Managed Payments needs one); SaaS business use, confirm with the accountant
    # Keep = true sleep (W10-R44): pause the square's project at Supabase or Neon and restore it on wake. Off by default: nothing is paused at a provider
    # until you set it.
    PROVIDER_SLEEP: bool = False
    PLATFORM_FRONTEND_URL: str = "http://localhost:5273"  # where the owner returns after a checkout
    # keep equal to frontend ui/src/themes/index.ts ENABLED_THEME_IDS (paper-brick and the launch set since W10-R8)
    ENABLED_THEME_IDS: str = "paper-brick,canopy-grove,softform,japandi-atelier,clay-pastel,pearl,product,mela-noir,lotus-hour,kash-meadow,denim-linen,terracotta-hall,hush-pond,linen-arch,ledger-gazette,marquee-showbill,product-console,sage-round"  # noqa: E501

    # Identity provider for bearer tokens (ADR 028): "supabase" in local/test, "neon" (Neon Auth) in production, "" = off (own cookie login only).
    AUTH_PROVIDER: Literal["", "supabase", "neon"] = ""
    AUTH_URL: str = ""  # the provider's base URL (Supabase project URL, or the Neon Auth URL)

    # Object storage, S3-compatible via boto3 (ADR 028): Supabase Storage in local/test, Neon Object Storage in production.
    # Empty endpoint = in-memory fake (refused in production).
    STORAGE_S3_ENDPOINT_URL: str = ""
    STORAGE_S3_ACCESS_KEY: str = Field(default="", repr=False)
    STORAGE_S3_SECRET_KEY: str = Field(default="", repr=False)
    STORAGE_S3_REGION: str = "auto"
    STORAGE_PUBLIC_BUCKET: str = "rootsquares-public"  # public-read; URL = STORAGE_PUBLIC_BASE_URL/<key>
    STORAGE_PUBLIC_BASE_URL: str = ""
    STORAGE_PRIVATE_BUCKET: str = "rootsquares-private"  # presigned, time-limited URLs

    # Extra redirect URLs allowed in every new square's auth (comma separated; {slug} is replaced by the square's slug). Empty + ENV=local = the Vite
    # dev server and the square's own local host, e.g. http://first-org.localhost:5273/**.
    SQUARE_EXTRA_REDIRECT_URLS: str = ""

    # How long the square token verifier keeps a square's decrypted secrets and key set in memory.
    SQUARE_AUTH_CACHE_SECONDS: int = 600

    # The Google OAuth client that squares use for Google sign-in (flask enable-google <slug>). The callback URL of each square project must be
    # added to this client in Google Cloud Console by an admin first.
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = Field(default="", repr=False)

    # Seed of the first staff account (flask seed-staff; ADR 083)
    SEED_ADMIN_EMAIL: str = ""
    SEED_ADMIN_PASSWORD: str = Field(default="", repr=False)

    @field_validator("DATABASE_URL")
    @classmethod
    def _database_driver(cls, v: str) -> str:
        """Providers hand out plain postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver named."""
        return "postgresql+psycopg://" + v.removeprefix("postgresql://") if v.startswith("postgresql://") else v

    @cached_property
    def cors_origins(self) -> list[str]:
        items = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if not items and self.ENV == "local":
            items = [LOCAL_CORS_ORIGIN]
        return items

    @property
    def env_label(self) -> str:
        """The word of the environment strip: ENV_LABEL, else Local on a development machine, else nothing."""
        return self.ENV_LABEL.strip() or ("Local" if self.ENV == "local" else "")

    @cached_property
    def admin_origins(self) -> list[str]:
        items = [o.strip() for o in self.ADMIN_ORIGINS.split(",") if o.strip()]
        if not items and self.ENV == "local":
            items = [LOCAL_ADMIN_ORIGIN, LOCAL_ADMIN_ORIGIN.replace("localhost", "127.0.0.1")]
        return items

    @cached_property
    def jwt_secret(self) -> str:
        return self.JWT_SECRET or (_DEV_JWT_SECRET if self.ENV != "production" else "")

    @cached_property
    def fernet_key(self) -> str:
        return self.FERNET_KEY or (_DEV_FERNET_KEY if self.ENV != "production" else "")

    @cached_property
    def staff_jwt_secret(self) -> str:
        return self.STAFF_JWT_SECRET or (self.jwt_secret if self.ENV != "production" else "")

    @cached_property
    def support_session_key(self) -> str:
        return self.SUPPORT_SESSION_KEY or (self.staff_jwt_secret if self.ENV != "production" else "")

    @cached_property
    def staff_fernet_key(self) -> str:
        return self.STAFF_FERNET_KEY or (self.fernet_key if self.ENV != "production" else "")

    @property
    def serves_customer(self) -> bool:
        return self.API_SURFACE in ("customer", "all")

    @property
    def serves_admin(self) -> bool:
        return self.API_SURFACE in ("admin", "all")

    @cached_property
    def square_extra_redirects(self) -> list[str]:
        items = [x.strip() for x in self.SQUARE_EXTRA_REDIRECT_URLS.split(",") if x.strip()]
        return items or ([f"{LOCAL_CORS_ORIGIN}/**", "http://{slug}.localhost:5273/**", "http://{slug}.localhost:5274/**"] if self.ENV == "local" else [])

    @cached_property
    def auth_url(self) -> str:
        return self.AUTH_URL.strip().rstrip("/")

    @cached_property
    def enabled_theme_ids(self) -> list[str]:
        return [x.strip() for x in self.ENABLED_THEME_IDS.split(",") if x.strip()]

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        for origin in self.cors_origins:
            if "*" in origin or not origin.startswith(("http://", "https://")):
                raise ValueError("CORS_ORIGINS must be explicit http(s) origins, never '*'")
        for origin in self.admin_origins:
            if "*" in origin or not origin.startswith(("http://", "https://")):
                raise ValueError("ADMIN_ORIGINS must be explicit http(s) origins, never '*'")
            if origin in self.cors_origins:
                raise ValueError("ADMIN_ORIGINS must not include a customer origin (CORS_ORIGINS)")
        if self.ENV == "production":
            if not self.STAFF_SECOND_STEP_REQUIRED:
                raise ValueError("STAFF_SECOND_STEP_REQUIRED must be true in production: staff sign in with a password and an authenticator code (ADR 083)")
            if self.API_SURFACE == "all":
                raise ValueError("API_SURFACE must be customer or admin in production: two services, one of each (ADR 084)")
            if not self.FERNET_KEY:
                raise ValueError("FERNET_KEY is required in production")  # both services open the squares' connection strings
            if self.API_SURFACE == "customer":
                if len(self.JWT_SECRET) < 32:
                    raise ValueError("JWT_SECRET (at least 32 characters) is required in production")
                if self.STAFF_JWT_SECRET or self.STAFF_FERNET_KEY or self.SUPPORT_SESSION_KEY:
                    raise ValueError("The customer service must not hold STAFF_JWT_SECRET, STAFF_FERNET_KEY or SUPPORT_SESSION_KEY (admin service only)")
                if self.RENDER_API_KEY:
                    raise ValueError("The customer service must not hold RENDER_API_KEY (admin service only: it reaches the whole Render account)")
            else:
                if not self.admin_origins:
                    raise ValueError("ADMIN_ORIGINS is required in production (the address of the admin application)")
                if len(self.STAFF_JWT_SECRET) < 32:
                    raise ValueError("STAFF_JWT_SECRET (at least 32 characters) is required on the admin service in production")
                if not self.STAFF_FERNET_KEY:
                    raise ValueError("STAFF_FERNET_KEY is required on the admin service in production")
                if len(self.SUPPORT_SESSION_KEY) < 32:
                    raise ValueError("SUPPORT_SESSION_KEY (at least 32 characters) is required on the admin service in production (support access, ADR 089)")
                if self.SUPPORT_SESSION_KEY in (self.JWT_SECRET, self.STAFF_JWT_SECRET):
                    raise ValueError("SUPPORT_SESSION_KEY must differ from JWT_SECRET and STAFF_JWT_SECRET")
                if self.STAFF_JWT_SECRET == self.JWT_SECRET or self.STAFF_FERNET_KEY == self.FERNET_KEY:
                    raise ValueError("STAFF_JWT_SECRET and STAFF_FERNET_KEY must differ from JWT_SECRET and FERNET_KEY (separate secrets, ADR 084)")
            if not self.DATABASE_URL:
                raise ValueError("DATABASE_URL is required in production")
            if not self.COOKIE_SECURE:
                raise ValueError("COOKIE_SECURE must be true in production")
        if self.AUTH_PROVIDER and not self.auth_url:
            raise ValueError("AUTH_URL is required when AUTH_PROVIDER is set")
        if self.ENV == "production":
            if self.AUTH_PROVIDER != "neon":
                raise ValueError("AUTH_PROVIDER must be neon in production (Supabase Auth is for local and test only)")
            if not (self.STORAGE_S3_ENDPOINT_URL and self.STORAGE_S3_ACCESS_KEY and self.STORAGE_S3_SECRET_KEY and self.STORAGE_PUBLIC_BASE_URL):
                raise ValueError("STORAGE_S3_ENDPOINT_URL, STORAGE_S3_ACCESS_KEY, STORAGE_S3_SECRET_KEY and STORAGE_PUBLIC_BASE_URL are required in production")
        if self.PROVISIONER == "supabase" and not (self.SUPABASE_ACCESS_TOKEN and self.SUPABASE_ORG_SLUG):
            raise ValueError("SUPABASE_ACCESS_TOKEN and SUPABASE_ORG_SLUG are required when PROVISIONER=supabase")
        if self.ENV == "production" and self.PROVISIONER != "neon":
            raise ValueError("PROVISIONER must be neon in production")
        if self.BILLING_PROVIDER == "stripe" and not (self.STRIPE_SECRET_KEY and self.STRIPE_WEBHOOK_SECRET):
            raise ValueError("STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET are required when BILLING_PROVIDER=stripe")
        if self.ENV == "production" and self.BILLING_PROVIDER != "stripe":
            raise ValueError("BILLING_PROVIDER must be stripe in production")
        if self.STRIPE_TEST_CLOCK_ID and not self.STRIPE_SECRET_KEY.startswith(("sk_test_", "rk_test_")):
            raise ValueError("STRIPE_TEST_CLOCK_ID is for Stripe test mode only: it needs a test key (sk_test_...) and must be empty with a live key")
        if self.EMAIL_PROVIDER == "resend" and not (self.RESEND_API_KEY and self.EMAIL_FROM):
            raise ValueError("RESEND_API_KEY and EMAIL_FROM are required when EMAIL_PROVIDER=resend")
        if self.PROVISIONER == "neon" and not self.NEON_API_KEY:
            raise ValueError("NEON_API_KEY is required when PROVISIONER=neon")
        if self.SITE_GATE_PASSWORD and len(self.SITE_GATE_PASSWORD) < 16:
            raise ValueError("SITE_GATE_PASSWORD must be at least 16 characters (a gate with a short passcode is no gate)")
        return self
