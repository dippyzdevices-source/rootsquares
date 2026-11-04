# ruff: noqa: E501
r"""What it is:   The tool that puts backend/.env.local and backend/.env.staging into the BLOCKS of backend/.env.example, keeping every populated value.
What it does: Reads the two files, writes each again as blocks (a block = the lines that only work together; comment or uncomment a whole block), keeps every value you
              have set, adds a <placeholder> for each value a staging block still needs, and puts a "# CHECK:" line above a value that looks wrong for staging (a local
              address, a Supabase storage key of the wrong length, PROVISIONER=supabase without its token). It never prints a value: only names, counts and lengths.
How to run:   From backend\ (PowerShell). First a dry run, which writes nothing:
                  .venv\Scripts\python.exe -I scripts\env_reformat.py
              then, when the summary looks right, with --apply: the two old files are copied to %USERPROFILE%\env-backups\rootsquares-<date-time>\ (outside the repository)
              and the new ones are written. Delete that folder when you have checked the new files: it holds the same secrets.
Read before:  backend/.env.example (what every block and line means) and docs/setup/13-environment-variables.md.
Read after:   scripts/env_review.py checks the result and the connections (read-only)."""
import datetime
import os
import re
import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "backend"
APPLY = "--apply" in sys.argv


def L(name, ph, core=True):
    return (name, ph, core)


def always(old, kind):
    return True


# Each block: id, title, tag, default-active per file kind, optional "off" kinds (block must stay off there), variants (a choice of ONE) with their lines.
BLOCKS = [
    dict(id="1", title="BASICS", tag="[C+A]", default=dict(local=True, staging=True), variants=[dict(label=None, when=always, lines=[
        L("ENV", "local"), L("LOG_LEVEL", "INFO"), L("DATABASE_URL", "<the address of the database: owner while migrating, then the service role>"),
        L("FERNET_KEY", "<make with the Fernet maker, keep a backup>"), L("SQUARE_DOMAIN_SUFFIX", "rootsquares.com")])]),
    dict(id="2", title="SIGN-IN PROVIDER OF THE PLATFORM", tag="[C+A]", default=dict(local=True, staging=True), variants=[
        dict(label="2A: Supabase", when=lambda o, k: o.get("AUTH_PROVIDER", "supabase") != "neon",
             lines=[L("AUTH_PROVIDER", "supabase"), L("AUTH_URL", "https://<project-ref>.supabase.co"), L("AUTH_ADMIN_KEY", "<service key>", False)]),
        dict(label="2B: Neon Auth (production)", when=lambda o, k: o.get("AUTH_PROVIDER") == "neon",
             lines=[L("AUTH_PROVIDER", "neon"), L("AUTH_URL", "<the Neon Auth URL>")])]),
    dict(id="3", title="STORAGE (the platform's own files)", tag="[C+A]", default=dict(local=True, staging=True), variants=[dict(label=None, when=always, lines=[
        L("STORAGE_S3_ENDPOINT_URL", "https://<project-ref>.storage.supabase.co/storage/v1/s3"), L("STORAGE_S3_ACCESS_KEY", "<s3 access key id, 32 characters>"),
        L("STORAGE_S3_SECRET_KEY", "<s3 secret access key, 64 characters>"), L("STORAGE_S3_REGION", "auto"), L("STORAGE_PUBLIC_BUCKET", "rootsquares-public"),
        L("STORAGE_PRIVATE_BUCKET", "rootsquares-private"),
        L("STORAGE_PUBLIC_BASE_URL", "https://<project-ref>.supabase.co/storage/v1/object/public/rootsquares-public")])]),
    dict(id="4", title="PROVISIONING OF NEW SQUARES (choose ONE of 4A, 4B, 4C)", tag="[C+A]", default=dict(local=True, staging=True), variants=[
        dict(label="4A: Neon", when=lambda o, k: o.get("PROVISIONER", "neon" if k == "staging" else "local") == "neon",
             lines=[L("PROVISIONER", "neon"), L("NEON_API_KEY", "<neon api key>"), L("NEON_REGION", "aws-eu-central-1", False)]),
        dict(label="4B: Supabase", when=lambda o, k: o.get("PROVISIONER") == "supabase",
             lines=[L("PROVISIONER", "supabase"), L("SUPABASE_ACCESS_TOKEN", "<sbp_... personal access token>"), L("SUPABASE_ORG_SLUG", "<org slug>"),
                    L("SUPABASE_REGION", "eu-west-1", False)]),
        dict(label="4C: local", when=lambda o, k: o.get("PROVISIONER") == "local", lines=[L("PROVISIONER", "local")])]),
    dict(id="4x", title="PROVISIONING, OPTIONAL WITH ANY OF THE THREE", tag="[C+A]", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("SQUARE_TEMPLATE_CMD", "", False)])]),
    dict(id="5", title="THE SQUARE SERVER LINK", tag="[C+A]", default=dict(local=False, staging=True), variants=[dict(label=None, when=always, lines=[
        L("SQUARE_SERVER_URL", "https://<the square server's onrender.com address>"), L("SQUARE_INTERNAL_KEY", "<random 40+ characters, equal to PLATFORM_INTERNAL_KEY>")])]),
    dict(id="6", title="THE CUSTOMER SERVICE", tag="[C]", default=dict(local=False, staging=True), variants=[dict(label=None, when=always, lines=[
        L("API_SURFACE", "customer"), L("JWT_SECRET", "<random 32+ characters>"), L("CORS_ORIGINS", "https://rootsquares.com,https://www.rootsquares.com"),
        L("PLATFORM_FRONTEND_URL", "https://rootsquares.com")])]),
    dict(id="7", title="THE ADMIN SERVICE (comment BLOCK 6 and use this one for the admin service)", tag="[A]", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("API_SURFACE", "admin"), L("ADMIN_ORIGINS", "https://admin.rootsquares.com"), L("STAFF_JWT_SECRET", "<random 32+ characters>"),
        L("STAFF_FERNET_KEY", "<make with the Fernet maker>"), L("SUPPORT_SESSION_KEY", "<random 32+ characters, equal to square/backend>")])]),
    dict(id="8", title="RUNNING ON RENDER", tag="[C+A]", default=dict(local=False, staging=True), variants=[dict(label=None, when=always, lines=[
        L("COOKIE_SECURE", "true"), L("PROXY_HOPS", "1"), L("ENV_LABEL", "Staging")])]),
    dict(id="9", title="THE SITE GATE", tag="[C+A]", default=dict(local=False, staging=True), variants=[dict(label=None, when=always, lines=[
        L("SITE_GATE_PASSWORD", "<random 24+ characters, the same on three servers>"), L("SITE_GATE_HOURS", "168", False)])]),
    dict(id="10", title="PLATFORM E-MAIL", tag="[C+A]", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("EMAIL_PROVIDER", "resend"), L("RESEND_API_KEY", "<a Resend key limited to sending>"), L("EMAIL_FROM", "rootsquares <hello@your-verified-domain>"),
        L("EMAIL_REPLY_TO", "hello@your-main-domain", False), L("STAFF_NOTICE_EMAIL", "hello@rootsquares.com", False)])]),
    dict(id="10b", title="A GROVE SQUARE'S OWN SENDING DOMAIN (needs BLOCK 10)", tag="[C+A]", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("RESEND_DOMAINS_API_KEY", "<resend full access key>"), L("RESEND_DOMAINS_REGION", "eu-west-1"), L("MAIL_DOMAIN_AUTO_APPROVE", "true")])]),
    dict(id="11", title="GOOGLE SIGN-IN FOR SQUARES", tag="[C+A]", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("GOOGLE_OAUTH_CLIENT_ID", "<client id>"), L("GOOGLE_OAUTH_CLIENT_SECRET", "<client secret>")])]),
    dict(id="12", title="BILLING (choose ONE of 12A, 12B)", tag="[C+A]", default=dict(local=False, staging=False), variants=[
        dict(label="12A: fake (the default)", when=lambda o, k: o.get("BILLING_PROVIDER", "fake") != "stripe", lines=[L("BILLING_PROVIDER", "fake", False)]),
        dict(label="12B: Stripe", when=lambda o, k: o.get("BILLING_PROVIDER") == "stripe",
             lines=[L("BILLING_PROVIDER", "stripe"), L("STRIPE_SECRET_KEY", "<sk_test_... or sk_live_...>"), L("STRIPE_WEBHOOK_SECRET", "<whsec_...>")])]),
    dict(id="12x", title="BILLING DETAILS (optional, defaults shown)", tag="[C+A]", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("BILLING_ENFORCE", "false", False), L("BILLING_TRIAL_DAYS", "7", False), L("BILLING_GRACE_DAYS", "7", False), L("BILLING_REFUND_DAYS", "14", False),
        L("BILLING_TRIAL_REMINDER_HOURS", "24", False), L("BILLING_TAX_RATES", "NO:25", False), L("STRIPE_TAX_CODE", "txcd_10103001", False),
        L("STRIPE_TEST_CLOCK_ID", "", False)])]),
    dict(id="13", title="THE OWN WEBSITE DOMAIN (Render API)", tag="[A]", default=dict(local=False, staging=False), off=dict(local=True), variants=[dict(label=None, when=always, lines=[
        L("RENDER_API_KEY", "<render api key>"), L("RENDER_SITE_SERVICE_ID", "<srv-...>"), L("CUSTOM_DOMAIN_TARGET", "squares.rootsquares.com", False)])]),
    dict(id="14", title="LOCAL DEVELOPMENT ONLY", tag="[C+A]", default=dict(local=False, staging=False), off=dict(staging=True), variants=[dict(label=None, when=always, lines=[
        L("SEED_ADMIN_EMAIL", "admin@example.com", False), L("SEED_ADMIN_PASSWORD", "change-me-please-123", False), L("STAFF_SECOND_STEP_REQUIRED", "false", False)])]),
    dict(id="15", title="SQUARE LIFE AND SLEEP (optional, defaults shown)", tag="[C+A]", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("PROVIDER_SLEEP", "false", False), L("EVENT_PASS_LIVE_DAYS", "45", False), L("EVENT_PASS_ARCHIVE_DAYS", "45", False), L("EVENT_PASS_SOFT_DELETE_DAYS", "14", False),
        L("EVENT_PASS_PURGE", "false", False), L("SLEEP_ARCHIVE_DAYS", "360", False), L("SLEEP_ARCHIVE_PURGE", "false", False),
        L("SQUARE_EXTRA_REDIRECT_URLS", "https://{slug}.rootsquares.com/**", False)])]),
    dict(id="16", title="SESSIONS AND LIMITS (optional, defaults shown)", tag="[C+A]", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("ACCESS_TTL_MINUTES", "15", False), L("REFRESH_TTL_DAYS", "14", False), L("LOGIN_RATE_LIMIT", "5", False), L("LOGIN_RATE_WINDOW_SECONDS", "60", False),
        L("STAFF_IDLE_MINUTES", "30", False), L("STAFF_SESSION_HOURS", "8", False), L("SQUARE_AUTH_CACHE_SECONDS", "600", False), L("ENABLED_THEME_IDS", "", False)])]),
]
KNOWN = {n for b in BLOCKS for v in b["variants"] for n, _, _ in v["lines"]}
LOCAL_URL_NAMES = {"PLATFORM_FRONTEND_URL", "SQUARE_SERVER_URL", "CORS_ORIGINS", "ADMIN_ORIGINS", "SQUARE_EXTRA_REDIRECT_URLS"}


def fmt(v):
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' if re.search(r"[\s#\"'`]", v) else v


def checks(kind, name, val, old):
    out = []
    if kind == "staging" and name in LOCAL_URL_NAMES and re.search(r"localhost|127\.0\.0\.1", val):
        out.append(f"# CHECK: {name} is a LOCAL address; staging needs the https address (guide 41).")
    if kind == "staging" and name == "PROVISIONER" and val == "supabase" and not (old.get("SUPABASE_ACCESS_TOKEN") and old.get("SUPABASE_ORG_SLUG")):
        out.append("# CHECK: PROVISIONER=supabase needs SUPABASE_ACCESS_TOKEN and SUPABASE_ORG_SLUG in this block, or switch to 4A (Neon).")
    if name == "STORAGE_S3_ACCESS_KEY" and len(val) != 32:
        out.append(f"# CHECK: a Supabase S3 key id has 32 characters (this one has {len(val)}).")
    if name == "STORAGE_S3_SECRET_KEY" and len(val) != 64:
        out.append(f"# CHECK: a Supabase S3 secret has 64 characters (this one has {len(val)}).")
    return out


def render(kind, old, report):
    emitted = set()  # a name that two blocks share (API_SURFACE is in block 6 and block 7) is switched on in the FIRST one only
    lines = [f"# backend/.env.{kind}  -  reformatted {datetime.date.today()} into the BLOCKS of backend/.env.example (read that file for what every line means).",
             "# A line that starts with  # NAME=  is switched off. A <placeholder> is a value still to fill in. Comment or uncomment a WHOLE block, never half of one.", ""]
    for b in BLOCKS:
        off_here = b.get("off", {}).get(kind, False)
        on_default = b["default"][kind] and not off_here
        sel = next((v for v in b["variants"] if v["when"](old, kind)), b["variants"][0])
        shared = {n for v in b["variants"] for n, _, _ in v["lines"] if sum(n == m for w in b["variants"] for m, _, _ in w["lines"]) > 1}
        block = [f"## BLOCK {b['id']}: {b['title']}   {b['tag']}"]
        on = kept = added = 0
        for v in b["variants"]:
            if v["label"]:
                block.append(f"## {v['label']}")
            selected = v is sel
            for name, ph, core in v["lines"]:
                val = old.get(name)
                active_here = selected and not off_here
                if name in emitted:
                    block.append(f"# {name}={ph}")
                    continue
                if val is not None and active_here and not (name in shared and not selected):
                    block += checks(kind, name, val, old)
                    block.append(f"{name}={fmt(val)}")
                    on += 1
                    kept += 1
                    emitted.add(name)
                    report["notes"] += [n for n in checks(kind, name, val, old)]
                elif val is not None and (name not in shared) and not active_here:
                    block.append(f"# {name}={fmt(val)}")
                    report["off_with_value"].append(name)
                elif core and on_default and selected and kind == "staging":
                    block.append(f"{name}={ph}")
                    on += 1
                    added += 1
                    emitted.add(name)
                    report["placeholders"].append(name)
                else:
                    block.append(f"# {name}={ph}")
        report["blocks"].append((b["id"], b["title"].split("(")[0].strip(), "on" if on else "off", kept, added))
        lines += block + [""]
    rest = [n for n in old if n not in KNOWN]
    if rest:
        lines += ["## KEPT FROM YOUR OLD FILE (not a setting of the example; check whether you still need it)"] + [f"{n}={fmt(old[n])}" for n in rest] + [""]
        report["unknown"] += rest
    return "\n".join(lines)


def populated(path):
    raw = dotenv_values(path)
    return {k: v for k, v in raw.items() if v is not None and v.strip() != "" and not re.search(r"<[^>@]*>", v)}, raw


stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
backup_dir = Path(os.environ["USERPROFILE"]) / "env-backups" / f"rootsquares-{stamp}"
results = {}
for kind in ("local", "staging"):
    path = B / f".env.{kind}"
    if not path.exists():
        print(f"\n[{kind}] {path.name} does not exist: skipped")
        continue
    old, raw = populated(path)
    names_in_file = re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)=", path.read_text(encoding="utf-8"), re.M)
    dup = sorted({n for n in names_in_file if names_in_file.count(n) > 1})
    report = dict(notes=[], placeholders=[], off_with_value=[], unknown=[], blocks=[])
    text = render(kind, old, report)
    results[kind] = (path, text, old)
    print(f"\n=== {path.name}: {len(old)} populated values found" + (f"; names written twice (the LAST one wins, the others are dropped): {dup}" if dup else "") + " ===")
    for bid, title, _st, kept, added in report["blocks"]:
        if kept or added:
            print(f"  BLOCK {bid:4} {title[:44]:44} {kept} kept" + (f", {added} placeholder(s) to fill" if added else ""))
    print("  still to fill (placeholders):", sorted(set(report["placeholders"])) or "none")
    if report["off_with_value"]:
        print("  value kept but switched off (its block is off here):", sorted(set(report["off_with_value"])))
    if report["unknown"]:
        print("  kept at the end, not in the example:", sorted(set(report["unknown"])))
    for n in sorted(set(report["notes"])):
        print("  " + n)

if not APPLY:
    print("\nDRY RUN: nothing was written. Add --apply to back up the two files and write the new ones.")
    sys.exit(0)

backup_dir.mkdir(parents=True, exist_ok=True)
for kind, (path, text, old) in results.items():
    shutil.copy2(path, backup_dir / f"backend.{path.name}")
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    new_vals = {k: v for k, v in dotenv_values(path).items() if v is not None and v.strip() != "" and not re.search(r"<[^>@]*>", v)}
    lost = sorted(k for k, v in old.items() if new_vals.get(k) != v)
    print(f"\n[{kind}] written. Values active in the new file: {len(new_vals)} of {len(old)} old ones" + (f"; not active (switched off or dropped as a duplicate): {lost}" if lost else "; none lost"))
print(f"\nBackups of the old files: {backup_dir}\nDelete that folder when you have checked the new files (it holds the same secrets).")
