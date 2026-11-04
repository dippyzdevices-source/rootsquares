"""Many squares, one server (rootsquares change W6-R26; not in bca-oslo).

bca-oslo serves one association from one database. Here the request's host name (first-org.localhost, first-org.rootsquares.com or a custom
domain) says which square is being served. The platform database (read only, PLATFORM_DATABASE_URL) holds, per square, the encrypted connection
string of the square's OWN database and the encrypted keys of its OWN sign-in project. This module:

- finds the square for a host (`TenantDirectory`), cached for a short time so a suspended or deleted square disappears quickly;
- gives every square its own SQLAlchemy engine (`engine_for`);
- makes `db.session` use that engine for the whole request (`TenantSession`, see app/extensions.py);
- tells the frontend which sign-in project to use (`GET /api/square/config`, public: project url and publishable key only).

Without PLATFORM_DATABASE_URL nothing changes: the app is single-tenant exactly as in bca-oslo (the test suite relies on that).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from datetime import date, datetime, timezone
from dataclasses import dataclass, field

from cryptography.fernet import Fernet, InvalidToken
from flask import Blueprint, Flask, current_app, g, jsonify, request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from werkzeug.security import check_password_hash

from app.common.phone import phone_rule
from app.features import features_for
from app.modules import MODULE_KEYS, core_off_of, init_modules, parse_modules

_DEV_FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"dev-only-fernet-key").digest()).decode()  # same as the platform's local default
LOOKUP_TTL_SECONDS = 30
EVENT_PASS = "event"  # platform squares.launch_package of an Event pass (W11, ADR 044)
SLEEP_OPEN_PATHS = ("/api/square/config", "/api/health")  # these (and /api/internal/*) still answer while a square sleeps; they do not read the square's data


def _json_dict(stored: object) -> dict | None:
    try:
        value = json.loads(stored) if isinstance(stored, str) and stored else None
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _overrides_of(stored: object) -> dict | None:
    """The platform's JSON text of squares.theme_overrides as a dict; anything else (empty, damaged, not an object) means the theme as designed.
    The owner's shared draft (key "draft", W18-R47) and the seasons (key "seasons", W18-R49) are not part of it; the seasons reach the browser only as the look of the one that is on."""
    value = _json_dict(stored)
    if value is not None:
        value.pop("draft", None)
        value.pop("seasons", None)
    return value or None


def _seasons_of(stored: object) -> tuple[dict, ...]:
    """The owner's seasonal looks from the same column (key "seasons"), the well-formed ones only."""
    value = _json_dict(stored)
    items = value.get("seasons") if value else None
    return tuple(x for x in items if isinstance(x, dict) and isinstance(x.get("look"), dict)) if isinstance(items, list) else ()


def season_covers(season: dict, today: date) -> bool:
    """Does the season cover this day? Yearly seasons repeat and may cross the new year. The platform has the same rule (theme_overrides.season_active; tests compare them)."""
    try:
        start, end = date.fromisoformat(str(season["start"])), date.fromisoformat(str(season["end"]))
    except (KeyError, ValueError):
        return False
    if season.get("yearly") is True:
        a, b, t = (start.month, start.day), (end.month, end.day), (today.month, today.day)
        return a <= t <= b if a <= b else (t >= a or t <= b)
    return start <= today <= end


def active_season(seasons: tuple[dict, ...], today: date) -> dict | None:
    """The first season in the owner's list that covers today, or None."""
    return next((s for s in seasons if season_covers(s, today)), None)


def _draft_of(stored: object) -> dict | None:
    """The owner's shared draft look from the same column (key "draft"): {look, token, expires_at, passcode_hash?}; only the draft endpoint reads it."""
    value = _json_dict(stored)
    draft = value.get("draft") if value else None
    return draft if isinstance(draft, dict) and draft else None


def _own_from_address(row) -> str:
    """`<name>@<domain>` when the square's own sending domain is verified at Resend and its package has the feature (Grove, a square made before packages, or a
    custom package with Messages); otherwise empty. A lost package only stops the use: the platform keeps the domain."""
    domain = str(row.get("mail_domain") or "").strip().lower()
    local = str(row.get("mail_from_local") or "hello").strip().lower()
    package = str(row.get("launch_package") or "")
    has_feature = package in ("", "grove") or (package == "custom" and "messages" in str(row.get("custom_modules") or ""))
    return f"{local}@{domain}" if domain and "@" not in domain and str(row.get("mail_domain_status") or "") == "verified" and has_feature else ""


@dataclass(frozen=True)
class Tenant:
    slug: str
    name: str
    theme_id: str
    domain: str
    db_url: str  # SQLAlchemy URL of the square's own database
    auth_provider: str  # supabase | neon
    auth_url: str  # the square's own sign-in project
    auth_public_key: str  # publishable key: public by design
    # The square's own storage (rootsquares W6-R43): its Supabase project and the project's service key, which never leaves the server.
    currency: str = "NOK"  # chosen when the square was created (platform squares.currency)
    phone_country: str = "NO"  # chosen when the square was created (platform squares.phone_country, W6-R52)
    logo_dark_url: str = ""  # the logo for dark backgrounds (footer, dark mode), or empty (platform squares.logo_dark_url, W6-R65)
    theme_overrides: dict | None = None  # the owner's own colours and font pair on top of the theme (platform squares.theme_overrides, W18-R18); the browser checks every value
    look_seasons: tuple[dict, ...] = field(default=(), repr=False)  # the owner's seasonal looks (W18-R49); the config shows the one that is on today (UTC)
    look_draft: dict | None = field(default=None, repr=False)  # the owner's shared draft with its token and passcode hash: never sent to a browser except through /api/square/look-draft (W18-R47)
    logo_url: str = ""  # public URL of the square's logo, or empty (the site then shows a letter mark; platform squares.logo_url, W6-R53)
    storage_url: str = ""
    storage_key: str = field(default="", repr=False)
    # A Neon square's storage is Neon Object Storage (S3 compatible), not the Supabase project above (W17-R15): the branch's endpoint, region and one credential.
    s3_endpoint: str = ""
    s3_region: str = ""
    s3_access_key: str = field(default="", repr=False)
    s3_secret_key: str = field(default="", repr=False)
    core_off: tuple[str, ...] = ()  # the always-on parts a custom package leaves out (W19-R24)
    modules: tuple[str, ...] | None = None  # the optional modules the owner turned on (platform squares.modules, W8-R9); None = every module
    sleeping: bool = False  # Keep (W10-R41, W10-R44): the square is asleep: its project may be paused, so the server touches no square data and answers with 503
    sleep_contact: tuple[tuple[str, str], ...] = ()  # the public contact details copied by the platform when it went to sleep, for the back-soon page
    google_login: bool = True  # Google sign-in is switched on in this square's own sign-in project (platform squares.google_login = 'enabled', W23-R86); True when the platform cannot say
    analytics: bool = False  # the owner switched visit counting on (platform squares.analytics_enabled, ADR 090)
    # the address the square sends from while its own domain is verified and its package allows it (platform squares.mail_domain, ADR 091); empty = the shared sending domain
    mail_from_address: str = ""
    mail_contact_email: str = ""  # where the square's contact-form messages and payment notices go and where replies to its mails go (platform squares.mail_contact_email, ADR 093); empty = the public contact address
    group_type: str = ""  # the kind of group (platform squares.group_type, W14-R10): cultural | religious; empty for a square made before starter sets
    package: str = ""  # the launch package (platform squares.launch_package); 'event' = an Event pass (W11, ADR 044)
    event_phase: str = ""  # an Event pass: 'live' or 'archive' (owner only, read-only); empty for every other square
    event_live_until: str = ""  # ISO time the live days end (the archive starts), or empty
    event_archive_until: str = ""  # ISO time the archive ends (the square leaves service), or empty


def _sqlalchemy_url(url: str) -> str:
    """The platform stores plain postgresql:// URLs; SQLAlchemy needs the psycopg 3 driver named."""
    return "postgresql+psycopg://" + url.removeprefix("postgresql://") if url.startswith("postgresql://") else url


def _engine_options(url: str) -> dict[str, object]:
    if not url.startswith("postgresql"):
        return {}  # sqlite (the test suite) rejects connect_timeout and pool sizes
    pooled = "pooler.supabase.com" in url or ":6543/" in url  # Supabase's transaction pooler cannot keep prepared statements
    options: dict[str, object] = {"pool_pre_ping": True, "pool_size": 2, "max_overflow": 3}
    options["connect_args"] = {"connect_timeout": 10, **({"prepare_threshold": None} if pooled else {})}
    return options


def _as_time(value: object) -> datetime | None:
    """A time from the platform database: a datetime (Postgres) or an ISO string (SQLite in tests); naive means UTC."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _iso(value: object) -> str:
    moment = _as_time(value)
    return moment.isoformat() if moment else ""


def event_phase_of(package: str, live_until: object, archive_until: object, now: datetime | None = None) -> str:
    """'live' or 'archive' for an Event pass, '' for any other square. After the archive the platform takes the square out of service itself."""
    if package != EVENT_PASS:
        return ""
    now = now or datetime.now(timezone.utc)
    live, archive = _as_time(live_until), _as_time(archive_until)
    if live is None or now < live:
        return "live"
    if archive is not None and now < archive:
        return "archive"
    return "archive"  # past the archive but not yet removed by the daily job: still read-only, never live again


class TenantDirectory:
    def __init__(self, platform_url: str, fernet_key: str, domain_suffix: str, allow_localhost: bool) -> None:
        self._platform = create_engine(_sqlalchemy_url(platform_url), pool_pre_ping=True, pool_size=1, max_overflow=2)
        self._fernet = Fernet((fernet_key or _DEV_FERNET_KEY).encode())
        self._suffix = domain_suffix.strip().lower().lstrip(".")
        self._allow_localhost = allow_localhost
        self._cache: dict[str, tuple[float, Tenant | None]] = {}
        self._engines: dict[str, tuple[str, Engine]] = {}
        self._lock = threading.Lock()

    # ---- host name to square -----------------------------------------------------------------------------------------------------
    def slug_for_host(self, host: str) -> str | None:
        """first-org.localhost (development only) or first-org.<SQUARE_DOMAIN_SUFFIX> give the slug; any other host may be a custom domain."""
        name = host.strip().lower().split(":")[0]
        if self._allow_localhost and name.endswith(".localhost"):
            return name.removesuffix(".localhost") or None
        if name.endswith("." + self._suffix):
            return name.removesuffix("." + self._suffix) or None
        return None

    def lookup(self, host: str) -> Tenant | None:
        name = host.strip().lower().split(":")[0]
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(name)
            if hit and now - hit[0] < LOOKUP_TTL_SECONDS:
                return hit[1]
        tenant = self._load(self.slug_for_host(name), name)
        with self._lock:
            self._cache[name] = (now, tenant)
        return tenant

    def _own_domain_slug(self, host: str) -> str | None:
        """The slug of the square whose own website domain (ADR 098, platform `squares.site_domain`) is this host, only while its package has the feature
        (Grove; no package = a square made before packages). A platform database without the column answers nothing."""
        try:
            with self._platform.connect() as conn:
                row = conn.execute(
                    text(
                        "select slug from squares where site_domain = :host and status = 'ready' and suspended_at is null "
                        "and (launch_package is null or launch_package = '' or launch_package = 'grove')"
                    ),
                    {"host": host},
                ).first()
        except (ProgrammingError, OperationalError):
            return None
        return str(row[0]) if row else None

    def _load(self, slug: str | None, host: str) -> Tenant | None:
        if slug is None and (own := self._own_domain_slug(host)):
            slug = own  # the host is a square's own website domain: serve that square (its default address keeps working as well)
        query = (
            "select slug, name, theme_id, domain, db_connection, provider_secrets{extra} from squares "
            "where status = 'ready' and suspended_at is null and (slug = :slug or domain = :host)"
        )
        params = {"slug": slug or "", "host": host}
        # A platform database that has not been upgraded yet lacks the newer columns: try the full list, then fewer. Missing currency counts as NOK
        # and a missing phone country as NO (the Norwegian rule) until it is upgraded.
        row = None
        for extra in [e + g for e in (", currency, phone_country, logo_url, logo_dark_url, modules, running_plan, sleep_state, sleep_contact, launch_package, event_live_until, event_archive_until, group_type, theme_overrides, custom_modules, analytics_enabled, mail_contact_email, mail_domain, mail_domain_status, mail_from_local", ", currency, phone_country, logo_url, logo_dark_url, modules, running_plan, sleep_state, sleep_contact, launch_package, event_live_until, event_archive_until, group_type, theme_overrides, custom_modules, analytics_enabled, mail_contact_email", ", currency, phone_country, logo_url, logo_dark_url, modules, running_plan, sleep_state, sleep_contact, launch_package, event_live_until, event_archive_until, group_type, theme_overrides, custom_modules, analytics_enabled", ", currency, phone_country, logo_url, logo_dark_url, modules, running_plan, sleep_state, sleep_contact, launch_package, event_live_until, event_archive_until, group_type, theme_overrides, custom_modules", ", currency, phone_country, logo_url, logo_dark_url, modules, running_plan, sleep_state, sleep_contact, launch_package, event_live_until, event_archive_until, group_type, theme_overrides", ", currency, phone_country, logo_url, logo_dark_url, modules, running_plan, sleep_state, sleep_contact, launch_package, event_live_until, event_archive_until, group_type", ", currency, phone_country, logo_url, logo_dark_url, modules, running_plan, sleep_state, sleep_contact, launch_package, event_live_until, event_archive_until", ", currency, phone_country, logo_url, logo_dark_url, modules, running_plan, sleep_state, sleep_contact", ", currency, phone_country, logo_url, logo_dark_url, modules, running_plan", ", currency, phone_country, logo_url, logo_dark_url, modules", ", currency, phone_country, logo_url, logo_dark_url", ", currency, phone_country, logo_url", ", currency, phone_country", ", currency", "") for g in (", google_login", "")]:
            try:
                with self._platform.connect() as conn:
                    row = conn.execute(text(query.format(extra=extra)), params).mappings().first()
                break
            except (ProgrammingError, OperationalError):
                if extra == "":
                    raise
        if row is None or not row["db_connection"]:
            return None
        try:
            db_url = self._fernet.decrypt(row["db_connection"].encode()).decode()
            secrets = json.loads(self._fernet.decrypt(row["provider_secrets"].encode()).decode()) if row["provider_secrets"] else {}
        except InvalidToken:
            current_app.logger.error("tenancy: cannot decrypt the secrets of square %s (wrong FERNET_KEY?)", row["slug"])
            return None
        return Tenant(
            slug=row["slug"],
            name=row["name"],
            theme_id=row["theme_id"],
            domain=row["domain"],
            currency=str(row.get("currency") or "NOK"),
            phone_country=str(row.get("phone_country") or "NO"),
            logo_url=_web_url(row.get("logo_url")),
            logo_dark_url=_web_url(row.get("logo_dark_url")),
            theme_overrides=_overrides_of(row.get("theme_overrides")),
            look_draft=_draft_of(row.get("theme_overrides")),
            look_seasons=_seasons_of(row.get("theme_overrides")),
            modules=parse_modules(row.get("modules")),
            core_off=core_off_of(str(row.get("launch_package") or ""), row.get("custom_modules")),
            sleeping=str(row.get("running_plan") or "live") == "keep" or str(row.get("sleep_state") or "awake") != "awake",
            sleep_contact=_contact_of(row.get("sleep_contact")),
            package=str(row.get("launch_package") or ""),
            group_type=str(row.get("group_type") or ""),
            analytics=bool(row.get("analytics_enabled") or False),
            mail_contact_email=str(row.get("mail_contact_email") or "").strip(),
            mail_from_address=_own_from_address(row),
            google_login=(row.get("google_login") == "enabled") if "google_login" in row else True,  # an older platform database cannot say: the button stays
            event_phase=event_phase_of(str(row.get("launch_package") or ""), row.get("event_live_until"), row.get("event_archive_until")),
            event_live_until=_iso(row.get("event_live_until")),
            event_archive_until=_iso(row.get("event_archive_until")),
            db_url=_sqlalchemy_url(db_url),
            auth_provider=str(secrets.get("auth_provider") or "supabase"),
            auth_url=str(secrets.get("project_url") or "").rstrip("/"),
            auth_public_key=str(secrets.get("publishable") or secrets.get("anon") or ""),
            storage_url=str(secrets.get("project_url") or "").rstrip("/"),
            storage_key=str(secrets.get("service_role") or secrets.get("secret") or ""),
            s3_endpoint=str(secrets.get("s3_endpoint") or "").rstrip("/"),
            s3_region=str(secrets.get("s3_region") or ""),
            s3_access_key=str(secrets.get("s3_access_key") or ""),
            s3_secret_key=str(secrets.get("s3_secret_key") or ""),
        )

    def all_tenants(self) -> list[Tenant]:
        """Every ready, not suspended square (for the background jobs). Not cached: a job run is rare compared with requests."""
        with self._platform.connect() as conn:
            rows = conn.execute(text("select slug, domain from squares where status = 'ready' and suspended_at is null order by slug")).all()
        tenants = [self._load(slug, str(domain or "").lower()) for slug, domain in rows]
        return [t for t in tenants if t is not None]

    # ---- one engine per square -----------------------------------------------------------------------------------------------------
    def engine_for(self, tenant: Tenant) -> Engine:
        with self._lock:
            cached = self._engines.get(tenant.slug)
            if cached and cached[0] == tenant.db_url:
                return cached[1]
            if cached:
                cached[1].dispose()  # the square's database was replaced
            engine = create_engine(tenant.db_url, **_engine_options(tenant.db_url))
            self._engines[tenant.slug] = (tenant.db_url, engine)
            return engine


tenancy_bp = Blueprint("tenancy", __name__)


def _contact_of(raw: object) -> tuple[tuple[str, str], ...]:
    """The copy of the public contact details the platform keeps while the square sleeps (JSON text), as pairs; anything unreadable counts as none."""
    try:
        data = json.loads(str(raw or "{}"))
    except ValueError:
        return ()
    if not isinstance(data, dict):
        return ()
    return tuple((k, str(data.get(k) or "")) for k in ("contact_email", "contact_phone", "contact_address"))


def _web_url(value: object) -> str:
    """Only a real web address counts as a logo (a platform running on the in-memory fake storage has fake:// addresses)."""
    text = str(value or "").strip()
    return text if text.startswith(("https://", "http://")) else ""


def _platform_url() -> str:
    """The platform's public address from PLATFORM_SITE_URL, only if it is a real web address (nothing else is ever handed to the browser)."""
    value = str(current_app.config.get("PLATFORM_SITE_URL") or "").strip().rstrip("/")
    return value if value.startswith(("https://", "http://")) else ""


@tenancy_bp.get("/api/square/config")
def square_config():
    """What the browser needs to know about this square: its name and theme, and its own sign-in project (url and publishable key, both public)."""
    tenant: Tenant | None = g.get("tenant")
    if tenant is None:
        return jsonify({"error": "This server is not serving a square"}), 404
    season = active_season(tenant.look_seasons, datetime.now(timezone.utc).date())  # a season that is on wears its own theme and look until its last day
    return jsonify(
        {
            "slug": tenant.slug,
            "name": tenant.name,
            "theme_id": (season.get("theme_id") if season else None) or tenant.theme_id,
            "theme_overrides": season["look"] if season else tenant.theme_overrides,
            "currency": tenant.currency,
            "phone": phone_rule(tenant.phone_country).public(),
            "logo_url": tenant.logo_url,
            "logo_dark_url": tenant.logo_dark_url,
            "modules": list(MODULE_KEYS if tenant.modules is None else tenant.modules),
            **({"core_off": list(tenant.core_off)} if tenant.core_off else {}),  # only a custom package that leaves parts out says so (W19-R24)
            "features": features_for(tenant.package, tenant.modules),  # the gated features this square's package includes (W14-R25)
            "own_mail_domain": bool(tenant.mail_from_address),  # the square sends from its own verified domain: a newsletter may go out (ADR 091, W26-R18)
            "platform_url": _platform_url(),  # where a locked feature sends the owner to change the package (W26-R17)
            "group_type": tenant.group_type,
            "google_login": tenant.google_login,  # the sign-in pages offer Google only when it is on in the square's sign-in project (W23-R86)
            "analytics": tenant.analytics,  # the site sends its visit beacon only when this is true (ADR 090)
            "sleeping": tenant.sleeping,
            "event_pass": (
                {"phase": tenant.event_phase, "live_until": tenant.event_live_until, "archive_until": tenant.event_archive_until} if tenant.package == EVENT_PASS else None
            ),
            "sleep_contact": dict(tenant.sleep_contact) if tenant.sleeping else {},
            "auth": {"provider": tenant.auth_provider, "url": tenant.auth_url, "public_key": tenant.auth_public_key},
        }
    )


_DRAFT_FAILS: dict[str, list[float]] = {}  # per square: when wrong tokens or passcodes were tried (this process only)
DRAFT_FAIL_LIMIT = 10  # wrong tries per square in DRAFT_FAIL_WINDOW seconds, then 429
DRAFT_FAIL_WINDOW = 600


@tenancy_bp.post("/api/square/look-draft")
def square_look_draft():
    """The owner's shared draft look (W18-R47): the committee opens the site with `?look=<token>` and the browser asks here. The token must match (and not be expired), and when the
    owner set a passcode it must match too. Nothing is answered about a square that has no draft except 'invalid'. Public, but a wrong guess is counted and too many are refused."""
    tenant: Tenant | None = g.get("tenant")
    if tenant is None:
        return jsonify({"error": "This server is not serving a square"}), 404
    body = request.get_json(silent=True) or {}
    token = str(body.get("token") or "")
    passcode = str(body.get("passcode") or "")
    now = time.time()
    fails = [t for t in _DRAFT_FAILS.get(tenant.slug, []) if now - t < DRAFT_FAIL_WINDOW]
    if len(fails) >= DRAFT_FAIL_LIMIT:
        return jsonify({"error": "too_many"}), 429
    draft = tenant.look_draft
    good = bool(draft) and isinstance(draft.get("token"), str) and hmac.compare_digest(draft["token"].encode(), token.encode())
    if good:
        try:
            if datetime.fromisoformat(str(draft.get("expires_at"))) <= datetime.now(timezone.utc):
                return jsonify({"error": "expired"}), 410
        except ValueError:
            good = False
    if good and draft.get("passcode_hash"):
        if not passcode:
            return jsonify({"error": "passcode_required"}), 401
        good = check_password_hash(str(draft["passcode_hash"]), passcode)
    if not good:
        _DRAFT_FAILS[tenant.slug] = [*fails, now]
        return jsonify({"error": "invalid"}), 403
    return jsonify({"look": draft.get("look") or {}, "theme_id": draft.get("theme_id") or None})


def init_tenancy(app: Flask) -> None:
    """Switch the app to many-squares mode when PLATFORM_DATABASE_URL is set; otherwise leave it single-tenant."""
    app.extensions["tenancy"] = None
    platform_url = app.config.get("PLATFORM_DATABASE_URL", "")
    if not platform_url:
        return
    directory = TenantDirectory(
        platform_url,
        app.config.get("FERNET_KEY", ""),
        app.config.get("SQUARE_DOMAIN_SUFFIX", "rootsquares.com"),
        bool(app.config.get("SQUARE_ALLOW_LOCALHOST", False)),
    )
    app.extensions["tenancy"] = directory
    app.register_blueprint(tenancy_bp)

    @app.before_request
    def _resolve_square():
        if request.path == "/api/health":
            return None  # the server's own health, not a square's
        tenant = directory.lookup(request.host)
        if tenant is None:
            return jsonify({"error": "Unknown square"}), 404
        g.tenant = tenant
        return None

    from app.support import init_support

    init_support(app, directory)  # a request that carries a support token is checked against the owner's grant (ADR 089)
    init_modules(app)  # after the lookup above: a module that is off answers 404

    @app.before_request
    def _sleep_guard():
        # A sleeping square (Keep, W10-R41, W10-R44) is a true sleep: its project may be paused, so nothing that needs its data works. Only the config (the back-soon
        # page reads the contact copy from it), the server's own health and the platform's internal calls answer; every other request gets 503 without touching
        # the square's database.
        tenant = g.get("tenant")
        if tenant is None or not tenant.sleeping:
            return None
        if request.path in SLEEP_OPEN_PATHS or request.path.startswith("/api/internal"):
            return None
        return jsonify({"error": "This site is resting. Please come back soon.", "code": "sleeping"}), 503

    @app.before_request
    def _archive_guard():
        # An Event pass in its archive (W11, ADR 044): the event is over. Only the owner's admin area can be read (to save the reports); nothing can be
        # changed, nobody can buy, volunteers and door staff have no access. Every refusal is 403 `event_over`, without touching the square's data.
        tenant = g.get("tenant")
        if tenant is None or tenant.event_phase != "archive":
            return None
        if request.path.startswith("/api/internal") or request.path in SLEEP_OPEN_PATHS:
            return None
        if request.path.startswith("/api/auth/"):
            return None  # signing in is how the owner gets to the archive
        if request.method in ("GET", "HEAD", "OPTIONS") and (request.path.startswith(("/api/admin/", "/api/lookups/")) or request.path == "/api/settings"):
            return None if not request.path.startswith("/api/admin/checkin") else _event_over()
        return _event_over()


def _event_over():
    return jsonify({"error": "This event is over. The site is in its archive: only the owner can read it, to save the reports.", "code": "event_over"}), 403


def current_tenant() -> Tenant | None:
    return g.get("tenant") if g else None


def tenant_engine() -> Engine | None:
    """The engine of the square being served, or None (single-tenant mode, CLI commands, background jobs)."""
    tenant = current_tenant()
    directory: TenantDirectory | None = current_app.extensions.get("tenancy")
    return directory.engine_for(tenant) if tenant is not None and directory is not None else None
