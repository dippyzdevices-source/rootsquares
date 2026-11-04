import os


def _normalize_database_url(url: str) -> str:
    """SQLAlchemy needs an explicit driver; Neon/psql give plain postgresql:// URLs."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _engine_options(database_uri: str) -> dict:
    """Postgres (Neon) only: Neon suspends idle compute, so pre-ping replaces a pooled connection
    that died across a suspend, and connect_timeout stops a stalled wake-up from hanging a worker.
    SQLite (the test suite) rejects connect_timeout, so it gets no options.
    """
    if not database_uri.startswith("postgresql"):
        return {}
    return {"pool_pre_ping": True, "connect_args": {"connect_timeout": 10}}


VALID_AUTH_PROVIDERS = ("supabase", "neon")


def validate_auth_config(config) -> None:
    """Refuse to start on a missing/unknown auth provider or an empty auth URL.

    There is deliberately no default: a wrong guess would verify tokens against the wrong
    identity provider. Not run under TESTING (TestingConfig pins its own values).
    """
    provider = config.get("AUTH_PROVIDER")
    if provider not in VALID_AUTH_PROVIDERS:
        raise RuntimeError(
            f"AUTH_PROVIDER must be one of {', '.join(VALID_AUTH_PROVIDERS)} (got {provider!r}). "
            "Set it in the environment — see backend/.env.example."
        )
    if not config.get("AUTH_URL"):
        raise RuntimeError(
            "AUTH_URL must be set to the active auth provider's base URL. "
            "Set it in the environment — see backend/.env.example."
        )


# rootsquares W6-R37 (hardcodings 5): bca-oslo fell back to a built-in secret key and to its own production web addresses in every environment.
DEV_SECRET_KEY = "dev-secret-key-change-me"  # development and tests only; production refuses to start with it
MIN_SECRET_KEY_LENGTH = 32


def validate_production_config(config) -> None:
    """Production must bring its own secret: refuse to start with the development key or a short one."""
    if not config.get("IS_PRODUCTION"):
        return
    key = config.get("SECRET_KEY") or ""
    if key == DEV_SECRET_KEY or len(key) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY must be set to your own value of at least {MIN_SECRET_KEY_LENGTH} characters in production "
            "(not the development default). Set it in the environment — see backend/.env.example."
        )


def default_frontend_origins(app_env: str) -> str:
    """Browser origins allowed to call the API when FRONTEND_ORIGIN is not set. Development: the square site's own dev server. Production: none
    (the site is served by the same server, so browsers call it from the same origin and CORS is not needed)."""
    return "" if app_env == "production" else "http://localhost:5274,http://127.0.0.1:5274"


class Config:
    IS_PRODUCTION = False
    # The site gate (ADR 099, W26-R20): one shared passcode in front of every /api/ request, for a staging deploy that must stay private. Empty = no gate. At least 16
    # characters. SITE_GATE_HOURS is how long a pass lasts; PROXY_HOPS is the number of proxies in front (Render: 1) so the caller's address can be read for the limit on
    # wrong tries. Set the same passcode as the platform's, so one passcode opens all of staging.
    SITE_GATE_PASSWORD = os.environ.get("SITE_GATE_PASSWORD", "")
    SITE_GATE_HOURS = int(os.environ.get("SITE_GATE_HOURS", "168") or 168)
    PROXY_HOPS = int(os.environ.get("PROXY_HOPS", "0") or 0)
    # The platform's public address (the customer app, for example https://rootsquares.com): locked features link to it so the owner can change the package
    # (W26-R17). Empty = no link is shown.
    PLATFORM_SITE_URL = os.environ.get("PLATFORM_SITE_URL", "")
    SECRET_KEY = os.environ.get("SECRET_KEY", DEV_SECRET_KEY)
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.environ.get("DATABASE_URL", ""))
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(SQLALCHEMY_DATABASE_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Hard cap on any request body (REQ-002) — Flask rejects larger ones with 413 before reading.
    # 26MB: the magazine PDF upload allows 25MB (see app/magazines/admin_routes.py) plus multipart overhead.
    MAX_CONTENT_LENGTH = 26 * 1024 * 1024
    FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", default_frontend_origins(os.environ.get("APP_ENV", "development")))
    # Public base URL of this API (e.g. https://bca-oslo-api.onrender.com) — only used to build the
    # one-click `List-Unsubscribe` POST URL in newsletter emails. Empty = header carries just the
    # normal unsubscribe page link (no one-click).
    API_PUBLIC_URL = os.environ.get("API_PUBLIC_URL", "").rstrip("/")
    STORAGE_S3_ENDPOINT_URL = os.environ.get("STORAGE_S3_ENDPOINT_URL", "")
    STORAGE_S3_ACCESS_KEY = os.environ.get("STORAGE_S3_ACCESS_KEY", "")
    STORAGE_S3_SECRET_KEY = os.environ.get("STORAGE_S3_SECRET_KEY", "")
    STORAGE_S3_REGION = os.environ.get("STORAGE_S3_REGION", "auto")
    STORAGE_PUBLIC_BUCKET = os.environ.get("STORAGE_PUBLIC_BUCKET", "public")  # the bucket names rootsquares gives every square
    STORAGE_PUBLIC_BASE_URL = os.environ.get("STORAGE_PUBLIC_BASE_URL", "")
    STORAGE_PRIVATE_BUCKET = os.environ.get("STORAGE_PRIVATE_BUCKET", "private")
    # Single-tenant identity (rootsquares W6-R40): a served square uses its own name, domain and order prefix (app/common/site.py).
    SITE_NAME = os.environ.get("SITE_NAME", "BCA Oslo")
    SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "localhost")
    SITE_ORDER_PREFIX = os.environ.get("SITE_ORDER_PREFIX", "BCA")
    SITE_CURRENCY = os.environ.get("SITE_CURRENCY", "NOK")
    SITE_PHONE_COUNTRY = os.environ.get("SITE_PHONE_COUNTRY", "NO")
    # Many squares from one server (rootsquares, W6-R26). With PLATFORM_DATABASE_URL set, the host name picks the square: its own database,
    # sign-in project and settings come from the platform database. Empty = single tenant, as in bca-oslo.
    PLATFORM_DATABASE_URL = os.environ.get("PLATFORM_DATABASE_URL", "")
    FERNET_KEY = os.environ.get("FERNET_KEY", "")  # the platform's key that encrypts each square's connection string and keys
    SQUARE_DOMAIN_SUFFIX = os.environ.get("SQUARE_DOMAIN_SUFFIX", "rootsquares.com")
    ANALYTICS_SALT_SECRET = os.environ.get("ANALYTICS_SALT_SECRET", "")  # a long random value: makes the daily visitor hash of the visit counter (ADR 090); empty = counting is off
    ANALYTICS_ENABLED = False  # a single-tenant server counts visits only when this is true (a many-squares server uses the owner's switch on the platform)
    SUPPORT_SESSION_KEY = os.environ.get("SUPPORT_SESSION_KEY", "")  # verifies the token of a rootsquares support session (ADR 089); empty = support access is off
    PLATFORM_INTERNAL_KEY = os.environ.get("PLATFORM_INTERNAL_KEY", "")  # shared secret with the platform server: lets it ask what a module holds and has pending (W8-R27); empty = off
    SQUARE_ALLOW_LOCALHOST = os.environ.get("APP_ENV", "development") != "production"  # <slug>.localhost works while developing only
    # Which identity provider verifies JWTs, and its base URL. Env-only (no APP_ENV coupling,
    # no default) — validated in create_app() via validate_auth_config().
    AUTH_PROVIDER = os.environ.get("AUTH_PROVIDER", "").strip().lower()
    AUTH_URL = os.environ.get("AUTH_URL", "")
    # Vipps and Stripe keys are NOT configured here: each square's admin enters its own on Settings -> Payments and they are stored encrypted
    # in that square's database (app/payments/credentials.py). There is deliberately no environment fallback.
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
    CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")
    # Set only in production (e.g. to this app's own https://.../api/health) — see
    # app/jobs/keep_alive.py. Left empty everywhere else so dev/tests never start the thread.
    KEEP_ALIVE_URL = os.environ.get("KEEP_ALIVE_URL", "")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    # Pinned, not env-driven: the test suite's ES256 fake-JWT pattern depends on "supabase".
    AUTH_PROVIDER = "supabase"
    AUTH_URL = "https://example.supabase.co"
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(SQLALCHEMY_DATABASE_URI)


class ProductionConfig(Config):
    DEBUG = False
    IS_PRODUCTION = True


CONFIG_BY_NAME: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str | None = None) -> type[Config]:
    env_name = env_name or os.environ.get("APP_ENV", "development")
    return CONFIG_BY_NAME.get(env_name, DevelopmentConfig)
