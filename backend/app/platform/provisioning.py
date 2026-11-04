"""Square provisioning (ADR 026: every square has its own database). The platform only creates the project/database, runs the template
command, seeds the first admin for the owner and stores the encrypted connection string. No square code lives here.

SquareProvisioner has three implementations: LocalProvisioner (a new empty database in the local Postgres, offline development), SupabaseProvisioner
(one Supabase project per square through the Management API; local/test, ADR 028) and NeonProvisioner (Neon API with NEON_API_KEY; production,
implemented, not run in development)."""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import httpx
import psycopg
import structlog
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.platform.models import AuditLog, Square, SquareStatus
from app.shared.config import Settings
from app.shared.crypto import Encryptor

log = structlog.get_logger("app.provisioning")

# Always created in a new square's database (W6-R35): the platform's own checks read it (who owns the square, the token verifier, the owner console).
# SQUARE_TEMPLATE_CMD then adds the square app's own tables on top.
BOOTSTRAP_SQL = """
create table if not exists admins (
    id uuid primary key,
    email text not null unique,
    name text not null default '',
    password_hash text,
    auth_user_id text,
    role text not null default 'owner',
    created_at timestamptz not null default now()
)
"""


@dataclass(frozen=True)
class Owner:
    email: str
    name: str
    password_hash: str | None  # None for owners who sign in through the identity provider


@dataclass(frozen=True)
class ProvisionResult:
    connection_url: str  # libpq/SQLAlchemy URL of the square's own database
    neon_project_id: str | None = None
    branch_id: str | None = None  # the main branch of the square's Neon project (its Neon Auth and storage live on the branch)
    project_ref: str | None = None  # the square's own Supabase project
    secrets: dict[str, str] | None = None  # project url and API keys of that project, stored encrypted


class SquareProvisioner(Protocol):
    def create_database(self, slug: str) -> ProvisionResult: ...


def to_libpq(url: str) -> str:
    """postgresql+psycopg://u:p@h/db -> postgresql://u:p@h/db (what psycopg connects with)."""
    return re.sub(r"^postgresql\+[a-z0-9]+://", "postgresql://", url)


class LocalProvisioner:
    """Creates a new empty database in the local Postgres next to the platform database (the platform role needs CREATEDB)."""

    def __init__(self, platform_url: str) -> None:
        self._platform = make_url(platform_url)
        if self._platform.host not in (None, "", "localhost", "127.0.0.1", "::1"):
            # a square database must never be created inside a hosted platform database (use PROVISIONER=supabase or neon)
            raise RuntimeError("LocalProvisioner only works with a platform database on this machine")

    def drop_database(self, name: str) -> None:
        """Drop a square database made by create_database. Refuses any other name."""
        if not re.fullmatch(r"rs_sq_[a-z0-9_]+_[0-9a-f]{8}", name):
            raise RuntimeError("Refusing to drop a database that was not made for a square")
        admin = self._platform.set(database="postgres")
        with psycopg.connect(to_libpq(admin.render_as_string(hide_password=False)), autocommit=True) as conn:
            conn.execute(sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(name)))

    def create_database(self, slug: str) -> ProvisionResult:
        name = f"rs_sq_{slug.replace('-', '_')}_{secrets.token_hex(4)}"
        admin = self._platform.set(database="postgres")
        with psycopg.connect(to_libpq(admin.render_as_string(hide_password=False)), autocommit=True) as conn:
            conn.execute(sql.SQL("create database {}").format(sql.Identifier(name)))
        own = self._platform.set(database=name)
        return ProvisionResult(connection_url=own.render_as_string(hide_password=False))


class NeonApiError(RuntimeError):
    """A Neon API call was refused. The text (status, the call's last path word, Neon's own message) holds no secrets and is shown on the square."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class NeonProvisioner:
    """One Neon project per square (ADR 028), created through the Neon API with NEON_API_KEY. Steps, each tried against the real API by
    scripts/neon_check.py: create the project (the database), find its main branch, enable Neon Auth (Managed Better Auth) on the branch, trust the
    square's address, create the public and private storage buckets and one storage credential. If a step after the project exists fails, the project is
    deleted again so a failed square does not keep one. The square's sign-in address and storage credential are returned as `secrets` (stored encrypted)."""

    API = "https://console.neon.tech/api/v2"
    PUBLIC_BUCKET, PRIVATE_BUCKET = "public", "private"

    def __init__(
        self,
        api_key: str,
        region: str,
        client: httpx.Client | None = None,
        site_suffix: str = "",
        extra_redirects: tuple[str, ...] = (),
    ) -> None:
        self._client = client or httpx.Client(base_url=self.API, timeout=30.0)
        self._headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json", "Content-Type": "application/json"}
        self._region = region
        self._suffix = site_suffix
        self._extra_redirects = extra_redirects

    def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        r = self._client.request(method, path, headers=self._headers, **kwargs)
        if r.is_success:
            return r.json() if r.content else {}
        try:
            message = str(r.json().get("message", ""))[:160]
        except (ValueError, AttributeError):
            message = ""
        raise NeonApiError(f"Neon refused {method} .../{path.rstrip('/').rsplit('/', 1)[-1]}: HTTP {r.status_code} {message}".strip(), r.status_code)

    def create_database(self, slug: str) -> ProvisionResult:
        body = self._call("POST", "/projects", json={"project": {"name": f"rootsquares-{slug}", "region_id": self._region}})
        uris = body.get("connection_uris") or []
        if not uris:
            raise RuntimeError("Neon response has no connection_uris")
        project_id = str(body["project"]["id"])
        try:
            branches = self._call("GET", f"/projects/{project_id}/branches").get("branches") or []
            if not branches:
                raise RuntimeError("Neon returned no branch")
            branch_id = str(branches[0]["id"])
            secrets_ = self._sign_in_and_storage(project_id, branch_id, slug)
        except Exception:
            self._delete_quietly(project_id)
            raise
        return ProvisionResult(connection_url=uris[0]["connection_uri"], neon_project_id=project_id, branch_id=branch_id, secrets=secrets_)

    def _sign_in_and_storage(self, project_id: str, branch_id: str, slug: str) -> dict[str, str]:
        base = f"/projects/{project_id}/branches/{branch_id}"
        auth = self._call("POST", f"{base}/auth", json={"auth_provider": "better_auth"})
        auth_url = str(auth["base_url"]).rstrip("/")
        if self._suffix:  # the addresses a sign-in may come back to: the square's own site and the development hosts
            for address in [f"https://{slug}.{self._suffix}", *(u.replace("{slug}", slug).removesuffix("/**") for u in self._extra_redirects)]:
                self._call("POST", f"{base}/auth/domains", json={"domain": address, "auth_provider": "better_auth"})
        store = self._call("GET", f"{base}/storage")
        for name, access in ((self.PUBLIC_BUCKET, "public_read"), (self.PRIVATE_BUCKET, "private")):
            self._call("POST", f"{base}/buckets", json={"name": name, "access_level": access})
        wanted = {"scopes": ["storage:read", "storage:write"], "principal_type": "user", "name": f"square-{slug}"}
        credential = self._call("POST", f"{base}/credentials", json=wanted)
        return {
            "auth_provider": "neon",
            "project_url": auth_url,  # the square server reads the sign-in address here ...
            "auth_url": auth_url,  # ... and the platform's square verifier here
            "neon_branch_id": branch_id,
            "s3_endpoint": str(store["s3_endpoint"]).rstrip("/"),
            "s3_region": str(store.get("region") or ""),
            "s3_access_key": str(credential["token_id"]),
            "s3_secret_key": str(credential["s3_secret_access_key"]),
        }

    def create_auth_user(self, result: ProvisionResult, owner: Owner) -> str:
        """Create the owner in the square's Neon Auth (no password: they sign in with the provider's own flow). Returns the new user's id."""
        user = self._call("POST", f"/projects/{result.neon_project_id}/branches/{result.branch_id}/auth/users", json={"email": owner.email, "name": owner.name})
        return str(user["id"])

    def set_google_login(self, project_id: str, branch_id: str, client_id: str, client_secret: str, enabled: bool) -> None:
        """Switch Google sign-in on or off for the square's Neon Auth. With a client id and secret it is the platform's own Google OAuth client (the square's
        callback `<auth address>/callback/google` must be in that client first); without them Neon's shared development credentials are used."""
        path = f"/projects/{project_id}/branches/{branch_id}/auth/oauth_providers"
        if not enabled:
            try:
                self._call("DELETE", f"{path}/google")
            except NeonApiError as exc:
                if exc.status != 404:  # already off
                    raise
            return
        body: dict[str, str] = {"id": "google"}
        if client_id and client_secret:
            body.update(client_id=client_id, client_secret=client_secret)
        try:
            self._call("POST", path, json=body)
        except NeonApiError as exc:
            if exc.status not in (400, 409):
                raise
            self._call("PATCH", f"{path}/google", json={k: v for k, v in body.items() if k != "id"})  # already there: change its credentials

    def set_redirects(self, project_id: str, branch_id: str, addresses: list[str]) -> list[str]:
        """Trust these addresses as places a sign-in may return to (already trusted ones are fine). Returns the list."""
        for address in addresses:
            try:
                self._call("POST", f"/projects/{project_id}/branches/{branch_id}/auth/domains", json={"domain": address, "auth_provider": "better_auth"})
            except NeonApiError as exc:
                if exc.status != 409 and "already exists" not in str(exc):  # Neon answers a repeated address with 400 "Domain already exists"
                    raise
        return addresses

    def set_email(self, project_id: str, branch_id: str, *, host: str, port: int, username: str, password: str, sender_email: str, sender_name: str) -> None:
        """Send the square's sign-in e-mails (verification code, password reset) through our own SMTP sender instead of Neon's shared one."""
        body = {"type": "standard", "host": host, "port": port, "username": username, "password": password}
        body.update(sender_email=sender_email, sender_name=sender_name)
        self._call("PATCH", f"/projects/{project_id}/branches/{branch_id}/auth/email_provider", json=body)

    def send_test_email(self, project_id: str, branch_id: str, recipient: str) -> None:
        """Send one test e-mail through the square's saved SMTP settings (Neon refuses it for the shared sender)."""
        answer = self._call("POST", f"/projects/{project_id}/branches/{branch_id}/auth/email_provider/test", json={"recipient_email": recipient})
        if not answer.get("success"):
            raise NeonApiError(f"Neon could not send the test e-mail: {str(answer.get('error_message', ''))[:160]}")

    def discard(self, result: ProvisionResult) -> None:
        """Delete a project that was created but could not be finished."""
        if result.neon_project_id:
            self._delete_quietly(result.neon_project_id)

    def _delete_quietly(self, project_id: str) -> None:
        try:
            self.destroy_project(project_id)
        except httpx.HTTPError:
            log.warning("neon_project_cleanup_failed")

    def _endpoint_ids(self, project_id: str) -> list[str]:
        r = self._client.get(f"/projects/{project_id}/endpoints", headers=self._headers)
        r.raise_for_status()
        return [str(e["id"]) for e in (r.json().get("endpoints") or [])]

    def _endpoint_action(self, project_id: str, endpoint_id: str, action: str, wait_seconds: float = 90.0, sleep: Callable[[float], None] = time.sleep) -> None:
        """POST suspend or start for one endpoint. Neon answers 423 Locked while an earlier operation on the endpoint is still running (a start right after a
        suspend), so a 423 is retried for up to `wait_seconds`; any other refusal is raised at once. Run against the real Neon API in scripts/neon_check.py."""
        end = time.monotonic() + wait_seconds
        while True:
            r = self._client.post(f"/projects/{project_id}/endpoints/{endpoint_id}/{action}", headers=self._headers)
            if r.status_code != 423 or time.monotonic() >= end:
                r.raise_for_status()
                return
            sleep(3.0)

    def suspend_project(self, project_id: str) -> None:
        """Sleep (Keep, W10-R44): suspend every compute endpoint of the project; data and the project stay. Neon also suspends idle computes by itself.
        Written from the Neon API document, not run."""
        for endpoint_id in self._endpoint_ids(project_id):
            self._endpoint_action(project_id, endpoint_id, "suspend")

    def start_project(self, project_id: str) -> None:
        """Wake: start the compute endpoints again (they also start by themselves on the first connection). Written from the Neon API document, not run."""
        for endpoint_id in self._endpoint_ids(project_id):
            self._endpoint_action(project_id, endpoint_id, "start")

    def destroy_project(self, project_id: str) -> bool:
        """Delete a square's Neon project. False = no such project (404). Written from the Neon API, not run."""
        r = self._client.delete(f"/projects/{project_id}", headers=self._headers)
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return True


class SupabaseApiError(RuntimeError):
    """A Management API or Storage API call was refused. The text (status, call, the API's own message) holds no secrets and is shown on the square."""


class SupabaseProvisioner:
    """One Supabase project per square (ADR 028), created through the Management API with a personal access token. Steps: create the project,
    wait until it is healthy, read the pooler connection, read the API keys, create the square's buckets, set the auth site URL. If a step after
    the project exists fails, the new project is deleted again so a failed square does not keep a project slot (the free plan allows few).
    Written from the published OpenAPI document; not run against a real organisation yet."""

    API = "https://api.supabase.com"
    PUBLIC_BUCKET, PRIVATE_BUCKET = "public", "private"

    def __init__(
        self,
        access_token: str,
        org_slug: str,
        region: str,
        site_suffix: str = "",
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        db_ready: Callable[[str], None] | None = None,
        wait_seconds: float = 900.0,
        extra_redirects: tuple[str, ...] = (),
    ) -> None:
        self._extra_redirects = extra_redirects
        self._client = client or httpx.Client(base_url=self.API, timeout=60.0)
        self._headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-Type": "application/json"}
        self._org, self._region, self._suffix = org_slug, region, site_suffix
        self._sleep, self._wait = sleep, wait_seconds
        self._db_ready = db_ready or self._connect_once

    def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        r = self._client.request(method, path, headers=self._headers, **kwargs)
        self._check(r, f"{method} {path}")
        return r.json() if r.content else None

    @staticmethod
    def _check(r: httpx.Response, call: str) -> None:
        if r.is_success:
            return
        try:
            message = str(r.json().get("message", ""))
        except ValueError:
            message = ""
        raise SupabaseApiError(f"Supabase answered {r.status_code} to {call}: {message[:200]}".rstrip(": "))

    def create_database(self, slug: str) -> ProvisionResult:
        db_pass = secrets.token_hex(16)
        project = self._call(
            "POST",
            "/v1/projects",
            json={
                "name": f"rootsquares-{slug}",
                "organization_slug": self._org,
                "db_pass": db_pass,
                "region_selection": {"type": "specific", "code": self._region},
            },
        )
        ref = project["ref"]
        try:
            self._wait_for(lambda: self._is_healthy(ref), f"project {ref} to become healthy")
            connection_url = self._connection_url(ref, db_pass)
            self._wait_for(lambda: self._try(self._db_ready, connection_url), "the database to accept connections")
            keys = self._api_keys(ref)
            url = f"https://{ref}.supabase.co"
            self._create_buckets(url, keys)
            if self._suffix:
                site = f"https://{slug}.{self._suffix}"
                allow = ",".join([f"{site}/**", *(u.replace("{slug}", slug) for u in self._extra_redirects)])
                self._call("PATCH", f"/v1/projects/{ref}/config/auth", json={"site_url": site, "uri_allow_list": allow})
        except Exception:
            self._delete_quietly(ref)
            raise
        return ProvisionResult(connection_url=connection_url, project_ref=ref, secrets={"project_url": url, **keys})

    def _is_healthy(self, ref: str) -> bool:
        status = self._call("GET", f"/v1/projects/{ref}")["status"]
        if status in ("INIT_FAILED", "REMOVED", "RESTORE_FAILED"):
            raise RuntimeError(f"Supabase project {ref} failed to start")
        return bool(status == "ACTIVE_HEALTHY")

    def _wait_for(self, done: Callable[[], bool], what: str) -> None:
        waited = 0.0
        while not done():
            if waited >= self._wait:
                raise TimeoutError(f"timed out waiting for {what}")
            self._sleep(5.0)
            waited += 5.0

    @staticmethod
    def _try(fn: Callable[[str], None], arg: str) -> bool:
        try:
            fn(arg)
            return True
        except Exception:  # noqa: BLE001 (any connection error means: not ready yet)
            return False

    @staticmethod
    def _connect_once(connection_url: str) -> None:
        with psycopg.connect(to_libpq(connection_url), connect_timeout=10, prepare_threshold=None) as conn:
            conn.execute("select 1")

    def _connection_url(self, ref: str, db_pass: str) -> str:
        """The pooler entry of the project with our password filled in (the API returns it with a placeholder)."""
        entries = self._call("GET", f"/v1/projects/{ref}/config/database/pooler")
        entry = next((e for e in entries if e.get("database_type") == "PRIMARY"), entries[0] if entries else None)
        if entry is None:
            raise RuntimeError("Supabase returned no pooler configuration")
        user = quote(entry["db_user"], safe="")
        return f"postgresql+psycopg://{user}:{quote(db_pass, safe='')}@{entry['db_host']}:{entry['db_port']}/{entry['db_name']}"

    def _api_keys(self, ref: str) -> dict[str, str]:
        found: dict[str, str] = {}
        for k in self._call("GET", f"/v1/projects/{ref}/api-keys", params={"reveal": "true"}):
            if not k.get("api_key"):
                continue
            if k.get("name") in ("anon", "service_role"):
                found[k["name"]] = k["api_key"]
            elif k.get("type") in ("publishable", "secret"):
                found.setdefault(k["type"], k["api_key"])
        if not (found.get("service_role") or found.get("secret")):
            raise RuntimeError("Supabase returned no service key")
        return found

    def _create_buckets(self, url: str, keys: dict[str, str]) -> None:
        headers = service_headers(keys)
        for name, public in ((self.PUBLIC_BUCKET, True), (self.PRIVATE_BUCKET, False)):
            r = self._client.post(f"{url}/storage/v1/bucket", headers=headers, json={"id": name, "name": name, "public": public})
            self._check(r, "POST /storage/v1/bucket")

    def pause_project(self, ref: str) -> None:
        """Sleep (Keep, W10-R44): pause the project; its data is kept and no compute is paid. Written from the Management API document, not run."""
        self._call("POST", f"/v1/projects/{ref}/pause")

    def resume_project(self, ref: str) -> None:
        """Wake: restore the paused project and wait until it is healthy (can take a few minutes). Written from the Management API document, not run."""
        self._call("POST", f"/v1/projects/{ref}/restore")
        self._wait_for(lambda: self._is_healthy(ref), f"project {ref} to wake")

    def destroy_project(self, ref: str) -> bool:
        """Delete a square's project. False = the API says there is no such project for this token (404)."""
        r = self._client.delete(f"/v1/projects/{ref}", headers=self._headers)
        if r.status_code == 404:
            return False
        self._check(r, f"DELETE /v1/projects/{ref}")
        return True

    def discard(self, result: ProvisionResult) -> None:
        """Remove the project of a result that a later step could not use (frees the project slot)."""
        if result.project_ref:
            self._delete_quietly(result.project_ref)

    def _delete_quietly(self, ref: str) -> None:
        try:
            self._call("DELETE", f"/v1/projects/{ref}")
            log.warning("supabase_project_removed_after_failure", project_ref=ref)
        except Exception as exc:  # noqa: BLE001
            log.error("supabase_project_cleanup_failed", project_ref=ref, error_type=type(exc).__name__)


def neon_target(sq: Square, enc: Encryptor) -> tuple[str, str, str] | None:
    """(project id, branch id, sign-in address) of a square made at Neon, or None for any other square."""
    if not sq.neon_project_id or not sq.provider_secrets:
        return None
    secrets_ = json.loads(enc.decrypt(sq.provider_secrets))
    if not secrets_.get("neon_branch_id"):
        return None
    return sq.neon_project_id, str(secrets_["neon_branch_id"]), str(secrets_.get("auth_url") or secrets_.get("project_url") or "")


def mail_sender(settings: Settings) -> dict[str, Any] | None:
    """Resend's SMTP settings for the sign-in e-mails of a Neon square, from the platform's own Resend setup (EMAIL_PROVIDER=resend), else None
    (Neon's shared sender stays). The sending address must be on a domain verified at Resend (guide 25)."""
    if settings.EMAIL_PROVIDER != "resend" or not (settings.RESEND_API_KEY and settings.EMAIL_FROM):
        return None
    address = parseaddr(settings.EMAIL_FROM)[1]
    if not address:
        return None
    return {"host": "smtp.resend.com", "port": 465, "username": "resend", "password": settings.RESEND_API_KEY, "sender_email": address}


def service_headers(secrets_: dict[str, str]) -> dict[str, str]:
    """Headers for the square project's Auth and Storage APIs with its service key. Legacy service_role keys are JWTs (apikey and Bearer);
    the newer secret keys (sb_secret_...) go in the apikey header only."""
    key = secrets_.get("service_role") or secrets_["secret"]
    headers = {"apikey": key, "Content-Type": "application/json"}
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def create_square_auth_user(secrets_: dict[str, str], owner: Owner, client: httpx.Client | None = None) -> str:
    """Create the owner as a confirmed user in the square's own Supabase Auth (no password: they sign in with an email link, a reset link, or
    Google once it is enabled for the square). Returns the new user's id."""
    r = (client or httpx).post(
        f"{secrets_['project_url']}/auth/v1/admin/users",
        headers=service_headers(secrets_),
        json={"email": owner.email, "email_confirm": True, "user_metadata": {"full_name": owner.name}},
        timeout=30.0,
    )
    SupabaseProvisioner._check(r, "POST /auth/v1/admin/users")
    return str(r.json()["id"])


def verify_neon_owner(connection_url: str, auth_user_id: str) -> None:
    """Mark the owner's e-mail as verified in the square's Neon Auth. The platform created the owner from an account whose e-mail it already knows; left
    unverified, Better Auth refuses to link a later Google sign-in to that user (no session is made) - found by trying it in a browser (W17-R18)."""
    with psycopg.connect(to_libpq(connection_url), autocommit=True, prepare_threshold=None) as conn:
        conn.execute('update neon_auth."user" set "emailVerified" = true where id::text = %s', (auth_user_id,))


def link_owner(connection_url: str, email: str, auth_user_id: str) -> None:
    """Remember the owner's auth user id on the built-in admins row."""
    with psycopg.connect(to_libpq(connection_url), autocommit=True, prepare_threshold=None) as conn:
        conn.execute("update admins set auth_user_id = %s where email = %s", (auth_user_id, email))


def seed_square(connection_url: str, slug: str, owner: Owner, template_cmd: str) -> None:
    """Two steps (W6-R35). 1) Always: the platform's `admins` table with the owner as first admin. 2) When SQUARE_TEMPLATE_CMD is set: that command,
    which builds the square app's own tables in the same database (for the square app: `square/backend/scripts/square_db.py upgrade-env`). The
    command gets the connection string and the owner in its ENVIRONMENT (never on its command line, never in a log)."""
    with psycopg.connect(to_libpq(connection_url), autocommit=True) as conn:
        conn.execute(BOOTSTRAP_SQL)
        conn.execute(
            "insert into admins (id, email, name, password_hash, role) values (%s, %s, %s, %s, 'owner') on conflict (email) do nothing",
            (uuid.uuid4(), owner.email, owner.name, owner.password_hash),
        )
    if template_cmd:
        env = {
            **os.environ,
            "SQUARE_DATABASE_URL": connection_url,
            "SQUARE_SLUG": slug,
            "SQUARE_OWNER_EMAIL": owner.email,
            "SQUARE_OWNER_NAME": owner.name,
            "SQUARE_OWNER_PASSWORD_HASH": owner.password_hash or "",
        }
        done = subprocess.run(template_cmd, shell=True, env=env, capture_output=True, text=True, timeout=600)  # noqa: S602 (trusted config)
        if done.returncode != 0:
            raise RuntimeError(f"SQUARE_TEMPLATE_CMD failed with exit code {done.returncode}")


def template_command(settings: Settings) -> str:
    """The command that builds the square app's tables in a new square. `SQUARE_TEMPLATE_CMD` wins. When it is empty and squares are made at a
    real provider, the square app next to this folder is used, so a new square works without anyone running a command by hand (W11-R34)."""
    if settings.SQUARE_TEMPLATE_CMD or settings.PROVISIONER not in ("supabase", "neon"):
        return settings.SQUARE_TEMPLATE_CMD
    backend = Path(__file__).resolve().parents[3] / "square" / "backend"
    script = backend / "scripts" / "square_db.py"
    for py in (backend / ".venv" / "Scripts" / "python.exe", backend / ".venv" / "bin" / "python"):
        if py.exists() and script.exists():
            return f'"{py}" "{script}" upgrade-env'
    return ""


def make_provisioner(settings: Settings) -> SquareProvisioner:
    if settings.PROVISIONER == "neon":
        return NeonProvisioner(
            settings.NEON_API_KEY,
            settings.NEON_REGION,
            site_suffix=settings.SQUARE_DOMAIN_SUFFIX,
            extra_redirects=tuple(settings.square_extra_redirects),
        )
    if settings.PROVISIONER == "supabase":
        return SupabaseProvisioner(
            settings.SUPABASE_ACCESS_TOKEN,
            settings.SUPABASE_ORG_SLUG,
            settings.SUPABASE_REGION,
            settings.SQUARE_DOMAIN_SUFFIX,
            extra_redirects=tuple(settings.square_extra_redirects),
        )
    return LocalProvisioner(settings.DATABASE_URL)


def provision_square(
    app_factory: sessionmaker[Session], settings: Settings, square_id: uuid.UUID, owner: Owner, provisioner: SquareProvisioner | None = None
) -> None:
    """Background job: create the database, seed the owner, store the encrypted connection string, set status ready or failed.
    `app_factory` is a sessionmaker; the job uses its own session."""
    enc = Encryptor(settings.fernet_key)
    with app_factory() as db:
        sq = db.get(Square, square_id)
        if sq is None:
            return
        prov = provisioner or make_provisioner(settings)
        result: ProvisionResult | None = None
        mail = "n/a"  # how the square's sign-in e-mails are sent: n/a (not a Neon square), shared, resend or failed
        try:
            result = prov.create_database(sq.slug)
            seed_square(result.connection_url, sq.slug, owner, template_command(settings))
            if result.project_ref and result.secrets:
                link_owner(result.connection_url, owner.email, create_square_auth_user(result.secrets, owner))
            elif isinstance(prov, NeonProvisioner) and result.neon_project_id and result.secrets:
                owner_id = prov.create_auth_user(result, owner)
                verify_neon_owner(result.connection_url, owner_id)
                link_owner(result.connection_url, owner.email, owner_id)
                sender = mail_sender(settings)
                mail = "shared"
                if sender and result.branch_id:
                    try:  # a refused sender must not stop the square: Neon's shared sender keeps working
                        prov.set_email(result.neon_project_id, result.branch_id, sender_name=sq.name, **sender)
                        mail = "resend"
                    except NeonApiError as exc:
                        log.warning("neon_email_setup_failed", square_id=str(square_id), status=exc.status)
                        mail = "failed"
            sq.db_connection = enc.encrypt(result.connection_url)
            sq.neon_project_id = result.neon_project_id
            sq.provider_project_ref = result.project_ref
            sq.provider = settings.PROVISIONER
            sq.provider_secrets = enc.encrypt(json.dumps(result.secrets)) if result.secrets else None
            sq.status = SquareStatus.READY
            sq.error = None
            db.add(
                AuditLog(
                    action="square.ready",
                    entity="square",
                    entity_id=str(sq.id),
                    org_id=sq.org_id,
                    data={"provisioner": settings.PROVISIONER, "auth_mail": mail},
                )
            )
        except Exception as exc:  # the status shows the failure; the message never contains connection strings
            log.warning("provisioning_failed", square_id=str(square_id), error_type=type(exc).__name__)
            discard = getattr(prov, "discard", None)
            if result is not None and discard is not None:
                discard(result)  # a project that was created but could not be finished must not keep a slot
            db.rollback()
            sq = db.get(Square, square_id)
            if sq is not None:
                sq.status = SquareStatus.FAILED
                sq.error = f"{type(exc).__name__}: {exc}" if isinstance(exc, (SupabaseApiError, NeonApiError)) else f"{type(exc).__name__}: provisioning failed"
                db.add(
                    AuditLog(
                        action="square.failed",
                        entity="square",
                        entity_id=str(sq.id),
                        org_id=sq.org_id,
                        data={"error_type": type(exc).__name__},
                    )
                )
        db.commit()
