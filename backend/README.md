# rootsquares backend (platform)

Flask 3, Python 3.12 or 3.13. This backend is the **platform**: accounts, organisations, squares and their provisioning, owner console, audit log, public square data and the square token verifier. The square application code (events, tickets, ...) is not built. Every square has its own project with its own database, sign-in and storage (ADR 026, 028); the platform database stores only the encrypted keys and connection strings.

Step-by-step setup lives in **`../docs/setup/`** (start with `README.md` there); this file is the short reference.

## Run (Windows PowerShell)

First time only:
```
cd C:\diPpY_devLocal\Digital\Master_RootSquares\rootsquares\backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env      # then fill it: ../docs/setup/13-environment-variables.md
```
Every time (restart after any change of `.env` or code; it does not reload):
```
powershell -NoProfile -ExecutionPolicy Bypass -File C:\diPpY_devLocal\Digital\Master_RootSquares\rootsquares\backend\scripts\dev.ps1
```
It checks the local Postgres only when `DATABASE_URL` points at this machine, runs `db upgrade` (Alembic migrations, row level security; a database made by `init-db` is adopted once), seeds the password admin when `SEED_ADMIN_EMAIL` is set, and starts the API on http://localhost:5001 (`/healthz`, `/readyz`, OpenAPI `/apidoc/openapi.json`, Swagger `/apidoc/swagger/`).

## Commands (`.\.venv\Scripts\flask.exe --app app.main:create_app <command>`; `flask` is not on PATH)

| Command | Does |
|---|---|
| `db upgrade` / `db downgrade` / `db current` / `db history` / `db revision -m` | Alembic migrations of the platform database (`migrations/`), row level security on Postgres |
| `init-db` | older way (tests, throwaway databases): creates missing tables, adds missing nullable columns, switches on row level security |
| `seed-admin` | creates or updates the password platform admin from `SEED_ADMIN_EMAIL`/`SEED_ADMIN_PASSWORD`; a changed password ends that admin's sessions |
| `promote-admin <email> [--revoke]` | makes an existing user the platform admin (they must have signed in once) |
| `enable-google <slug> [--disable] [--yes]` | switches Google sign-in on for a square's project with the platform's Google client and marks it enabled |
| `sync-square-auth <slug>` | sets the square project's Site URL and allowed redirect URLs again |
| `check-square-token <slug> <token>` | verifies a token of a square's own auth project and shows who it is |

## API (all under /api/platform/v1; JSON; problem+json errors; cookies need the header `X-Requested-With: rootsquares` on mutating calls)

- **Auth (own password login):** `POST /auth/signup`, `/auth/login`, `/auth/logout`, `/auth/logout-all`, `/auth/refresh`, `GET /auth/me`, `POST /auth/password-reset` (stub, sends nothing). Argon2; httpOnly cookies `rs_access` (15 min), `rs_refresh` (14 days, single use); revocable sessions; login rate limit.
- **Provider sign-in:** any endpoint that needs a user also accepts `Authorization: Bearer <Supabase or Neon token>` when `AUTH_PROVIDER` is set (the user row is created on first sight). `POST /organizations {name}` creates the caller's organisation.
- **Squares:** `GET /squares`, `POST /squares {name, slug, theme_id}` (202, provisions in the background), `GET /squares/{id}`, `POST /squares/{id}/retry` (failed only), `DELETE /squares/{id} {confirm_slug, force?}` (provider project first, then the row).
- **Account:** `GET /me/export` (JSON file), `DELETE /me {confirm_email}`.
- **Owner (platform admin):** `GET /owner/squares`, `POST /owner/squares/{id}/google {enabled}`.
- **Public (no sign-in, open to every origin, no credentials):** `GET /public/squares/{slug}`, `GET /public/hosts/{host}`, `GET /public/squares/{slug}/me` (Bearer = the square's own token).
- **Provisioning:** `PROVISIONER=supabase` (a real Supabase project per square through the Management API), `local` (a database in the local Postgres, offline), `neon` (Neon API, never run). Details: `../docs/setup/07-creating-squares.md`.

## Checks (from `backend\`)

```
.venv\Scripts\python -m pytest          # 102 tests, about 10 s, no network, no cloud
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy
.venv\Scripts\python scripts\smoke.py   # real local Postgres on 5432 (role rs_admin): two squares = two databases, tenant separation; drops what it creates
```
What each test file covers and the live checks against Supabase: `../docs/setup/14-testing-and-checks.md`.

## Configuration

See `.env.example` (every setting, commented) and `../docs/setup/13-environment-variables.md`. Production requires `JWT_SECRET` (32+ chars), `FERNET_KEY`, `DATABASE_URL`, `COOKIE_SECURE=true`, `AUTH_PROVIDER=neon`, real S3 storage and `PROVISIONER=neon`; it refuses to start otherwise. Never change `FERNET_KEY` while squares exist.

## About uv (optional)

`pyproject.toml` and `uv.lock` exist for uv users; the pinned `requirements.txt` and `requirements-dev.txt` are generated from the lock (`python -m uv export --no-hashes --no-dev --no-emit-project -o requirements.txt`, and `--only-dev` for the dev file). The virtual environment in this repository was made by uv and has no `pip`: use `python -m uv add <package>` (ask before adding dependencies; approved list: `../docs/reference/architecture.md` section 10).
