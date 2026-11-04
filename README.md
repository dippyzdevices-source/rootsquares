# rootsquares

> - **What it is:** The front door of the repository.
> - **What it does:** Says what rootsquares is and points to the first things to read.
> - **How to use / run:** Read it top to bottom once; nothing to run.
> - **Read before:** Nothing.
> - **Read after:** `docs/STATUS.md`, then `docs/setup/00-START-HERE-guide-index.md`.

A platform where small associations (cultural groups, religious communities, language schools) launch a full website in under an hour: events, tickets, membership, committee, gallery, articles, accounting, custom domain, flat monthly fee. BCA Oslo is the first tenant and the reference project.

Status (2026-10-09): the **platform** is real (accounts, organisations, squares, sign-in with Google and email through Supabase, one Supabase project per square, owner console, data export and deletion). The **square's own site** is a hello-world page with real sign-in; the full console and public site are still the clickable prototype with mock data. Read `docs/STATUS.md` first.

## Start here

| Need | Read |
|---|---|
| Current state, what is next | `docs/STATUS.md` |
| Set everything up, step by step | `docs/setup/00-START-HERE-guide-index.md` (16 guides: local machine, platform project, database, login for rootsquares, storage, a Supabase account for squares, creating squares, login for squares, Google for squares, hosts and domains, privacy, production on Neon, environment variables, tests, troubleshooting, reuse from bca-oslo) |
| Why things are the way they are | `docs/DECISIONS.md` (ADR 026 to 031), `docs/reference/architecture.md`, `docs/reference/auth-and-providers.md` |
| What changed and when | `docs/CHANGELOG.md`, `docs/waves/` |
| Working rules for the assistant | `CLAUDE.md` |

## Run (Windows)

```
powershell -NoProfile -ExecutionPolicy Bypass -File backend\scripts\dev.ps1     # API on http://localhost:5001
cd frontend; npm run dev                                                          # http://localhost:5273
```
First time: `docs/setup/01-local-machine.md`. A square's site: `http://<slug>.localhost:5273/` (or `http://localhost:5273/s/<slug>`).

## Layout

```
backend/    Flask 3 platform API (Python 3.12/3.13): accounts, organisations, squares, provisioning, billing, the staff API (admin console), audit log, public square data
frontend/   npm workspace of three packages (ADR 084): platform/ (Vue 3 + TypeScript + Vite + Tailwind v4, the customer app: platform pages, square hello-world site, the clickable prototype on mock data; port 5273), admin/ (the staff application, port 5275, guide 34) and ui/ (the design system both use); tests/ read across them
design/     design files (Brass platform design, ten tenant themes)
docs/       index docs/README.md: STATUS, CHANGELOG, MEMORY, DECISIONS, setup/, waves/, reference/, plans/, hand-tests/, reviews/, prompts/
```

## The idea in one paragraph

One **platform project** (its own database, sign-in and storage) and one **project per square** (an association's website, with its own database, sign-in and storage, fully isolated). The platform database stores only the encrypted keys and connection strings needed to reach each square. Local and test: Supabase for everything. Production: Neon (not run yet).

## Prototype (mock data)

The marketing pages (`/`, `/pricing`, `/templates`, `/case-study/bca`, `/contact`), the onboarding wizard (`/start`), the square console (`/admin/...`), the tenant site in ten themes (`/site/:themeId/...`) and the owner console layout are the original clickable prototype. They use mock data and save nothing (only the language and light/dark choice are kept in localStorage); `VITE_USE_MOCK=true` also mocks the platform API. Theme ids: `paper-brick` (the only one enabled), `harvest-hall`, `stillwater`, `fjord-modern`, `pencil-club`, `olive-linen`, `berry-courtyard`, `atrium`, `ledger`, `marquee`.

Design: platform UI follows `design/rootsquares-platform-v2/` (Brass tokens); the tenant site is styled only by the `--t-*` variables of the tenant theme. Fonts are self-hosted (`docs/reference/fonts.md`).

## Known limits

Not tested on real devices (desktop browser only). Norwegian is out of scope. No CI. See `docs/OPEN_QUESTIONS.md` and `docs/LEGAL_TODO.md`.
