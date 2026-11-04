# ruff: noqa: E501
r"""What it is:   The tool that puts square/backend/.env.local and square/backend/.env.staging (the SQUARE SERVER) into the BLOCKS of square/backend/.env.example.
What it does: Reads the two files, writes each again as blocks (a block = the lines that only work together; comment or uncomment a whole block), keeps every value you
              have set, adds a <placeholder> for each value a staging block still needs (an empty staging file becomes a full template), and puts a "# CHECK:" line above a
              value that looks wrong for staging (APP_ENV not production, a short SECRET_KEY, a local address) or that must equal the platform's (FERNET_KEY, SUPPORT_SESSION_KEY,
              SITE_GATE_PASSWORD, PLATFORM_INTERNAL_KEY = SQUARE_INTERNAL_KEY, AUTH_*): it compares with backend/.env.<same kind> and says only "differs", never a value.
              It never prints a value: only names, counts and lengths. The platform backend has its own tool, scripts/env_reformat.py.
How to run:   From backend\ (PowerShell). First a dry run, which writes nothing:
                  .venv\Scripts\python.exe -I scripts\env_reformat_square.py
              then, when the summary looks right, with --apply: the old files are copied to %USERPROFILE%\env-backups\rootsquares-<date-time>\ (outside the repository) and
              the new ones are written. Delete that folder when you have checked the new files: it holds the same secrets.
Read before:  square/backend/.env.example (what every block and line means) and docs/setup/13-environment-variables.md.
Read after:   scripts/env_review.py checks the platform backend's file and its connections (read-only); the square server has no review tool yet."""
import datetime
import os
import re
import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "square" / "backend"
PEER_DIR = ROOT / "backend"
APPLY = "--apply" in sys.argv


def L(name, ph, core=True):
    return (name, ph, core)


def always(old, kind):
    return True


BLOCKS = [
    dict(id="1", title="BASICS", default=dict(local=True, staging=True), variants=[dict(label=None, when=always, lines=[
        L("APP_ENV", dict(local="development", staging="production")), L("SECRET_KEY", "<random 32+ characters>")])]),
    dict(id="2", title="THE LINK TO THE PLATFORM (many-squares mode)", default=dict(local=True, staging=True), variants=[dict(label=None, when=always, lines=[
        L("PLATFORM_DATABASE_URL", "<the customer_app address of the platform database>"), L("FERNET_KEY", "<the platform's FERNET_KEY, the same value>"),
        L("PLATFORM_INTERNAL_KEY", "<equal to SQUARE_INTERNAL_KEY of the platform>"), L("SQUARE_DOMAIN_SUFFIX", "rootsquares.com"),
        L("PLATFORM_SITE_URL", "https://rootsquares.com")])]),
    dict(id="3", title="THE SIGN-IN FALLBACK", default=dict(local=True, staging=True), variants=[dict(label=None, when=always, lines=[
        L("AUTH_PROVIDER", "supabase"), L("AUTH_URL", "https://<project-ref>.supabase.co")])]),
    dict(id="4", title="THE SITE GATE AND THE PROXY (a private staging)", default=dict(local=False, staging=True), variants=[dict(label=None, when=always, lines=[
        L("SITE_GATE_PASSWORD", "<the same passcode as on the customer API and the admin API>"), L("SITE_GATE_HOURS", "168", False), L("PROXY_HOPS", "1")])]),
    dict(id="5", title="SUPPORT ACCESS", default=dict(local=False, staging=True), variants=[dict(label=None, when=always, lines=[
        L("SUPPORT_SESSION_KEY", "<equal to SUPPORT_SESSION_KEY of the admin API>")])]),
    dict(id="6", title="ANALYTICS", default=dict(local=False, staging=True), variants=[dict(label=None, when=always, lines=[
        L("ANALYTICS_SALT_SECRET", "<random 32+ characters>")])]),
    dict(id="7", title="KEEP THE SERVER AWAKE", default=dict(local=False, staging=False), off=dict(local=True), variants=[dict(label=None, when=always, lines=[
        L("KEEP_ALIVE_URL", "https://<its onrender address>/api/health", False)])]),
    dict(id="8", title="E-MAIL", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("RESEND_API_KEY", "<resend sending key>", False), L("EMAIL_FROM", "rootsquares <hello@your-verified-domain>", False), L("CONTACT_EMAIL", "hello@rootsquares.com", False)])]),
    dict(id="9", title="SERVER-WIDE FILE STORAGE (a fallback)", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("STORAGE_S3_ENDPOINT_URL", "", False), L("STORAGE_S3_ACCESS_KEY", "", False), L("STORAGE_S3_SECRET_KEY", "", False), L("STORAGE_S3_REGION", "auto", False),
        L("STORAGE_PUBLIC_BUCKET", "public", False), L("STORAGE_PRIVATE_BUCKET", "private", False), L("STORAGE_PUBLIC_BASE_URL", "", False)])]),
    dict(id="10", title="THE LOCAL DEVELOPMENT SITE", default=dict(local=False, staging=False), off=dict(staging=True), variants=[dict(label=None, when=always, lines=[
        L("FRONTEND_ORIGIN", "http://localhost:5274", False)])]),
    dict(id="11", title="SINGLE-TENANT MODE (a bca-oslo-style server)", default=dict(local=False, staging=False), off=dict(staging=True), variants=[dict(label=None, when=always, lines=[
        L("DATABASE_URL", "postgresql+psycopg://rs_admin:<password>@localhost:5432/square_dev", False), L("SITE_NAME", "BCA Oslo", False), L("SITE_DOMAIN", "localhost", False),
        L("SITE_ORDER_PREFIX", "BCA", False), L("SITE_CURRENCY", "NOK", False), L("SITE_PHONE_COUNTRY", "NO", False), L("TEST_DATABASE_URL", "", False)])]),
    dict(id="12", title="OTHER (all optional)", default=dict(local=False, staging=False), variants=[dict(label=None, when=always, lines=[
        L("API_PUBLIC_URL", "", False), L("DATA_RETENTION_YEARS", "5", False), L("ERASE_DELETE_PROVIDER_ACCOUNT", "true", False), L("APP_VERSION", "", False)])]),
]
KNOWN = {n for b in BLOCKS for v in b["variants"] for n, _, _ in v["lines"]}
LOCAL_URL_NAMES = {"PLATFORM_SITE_URL", "PLATFORM_DATABASE_URL", "AUTH_URL"}
PEER_NAME = {"FERNET_KEY": "FERNET_KEY", "SUPPORT_SESSION_KEY": "SUPPORT_SESSION_KEY", "SITE_GATE_PASSWORD": "SITE_GATE_PASSWORD", "PLATFORM_INTERNAL_KEY": "SQUARE_INTERNAL_KEY",
             "AUTH_PROVIDER": "AUTH_PROVIDER", "AUTH_URL": "AUTH_URL"}


def phv(ph, kind):
    return ph if isinstance(ph, str) else ph[kind]


def fmt(v):
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"' if re.search(r"[\s#\"'`]", v) else v


def populated(path):
    raw = dotenv_values(path)
    return {k: v for k, v in raw.items() if v is not None and v.strip() != "" and not re.search(r"<[^>@]*>", v)}, raw


def checks(kind, name, val, peer):
    out = []
    if kind == "staging":
        if name == "APP_ENV" and val != "production":
            out.append("# CHECK: staging runs APP_ENV=production (this server has its own production mode).")
        if name == "SECRET_KEY" and (len(val) < 32 or val == "dev-secret-key-change-me"):
            out.append(f"# CHECK: SECRET_KEY needs 32+ characters and not the built-in one (this one has {len(val)}).")
        if name in LOCAL_URL_NAMES and re.search(r"localhost|127\.0\.0\.1", val):
            out.append(f"# CHECK: {name} is a LOCAL address; staging needs the staging one (guide 41).")
        if name == "SITE_GATE_PASSWORD" and len(val) < 16:
            out.append(f"# CHECK: SITE_GATE_PASSWORD needs 16+ characters (this one has {len(val)}).")
        if name in ("FRONTEND_ORIGIN", "DATABASE_URL"):
            out.append(f"# CHECK: {name} must stay empty on Render (many-squares mode, same origin).")
    peer_val = peer.get(PEER_NAME.get(name, ""))
    if peer_val and name in PEER_NAME and peer_val != val:
        out.append(f"# CHECK: {name} differs from {PEER_NAME[name]} in backend/.env.{kind}; they must be the same value.")
    return out


def render(kind, old, peer, report):
    emitted = set()
    lines = [f"# square/backend/.env.{kind}  -  reformatted {datetime.date.today()} into the BLOCKS of square/backend/.env.example (read that file for what every line means).",
             "# A line that starts with  # NAME=  is switched off. A <placeholder> is a value still to fill in. Comment or uncomment a WHOLE block, never half of one.", ""]
    for b in BLOCKS:
        off_here = b.get("off", {}).get(kind, False)
        on_default = b["default"][kind] and not off_here
        sel = next((v for v in b["variants"] if v["when"](old, kind)), b["variants"][0])
        block = [f"## BLOCK {b['id']}: {b['title']}"]
        on = kept = added = 0
        for v in b["variants"]:
            selected = v is sel
            for name, ph0, core in v["lines"]:
                ph = phv(ph0, kind)
                val = old.get(name)
                active_here = selected and not off_here
                if name in emitted:
                    block.append(f"# {name}={ph}")
                    continue
                if val is not None and active_here:
                    notes = checks(kind, name, val, peer)
                    block += notes + [f"{name}={fmt(val)}"]
                    report["notes"] += notes
                    on += 1
                    kept += 1
                    emitted.add(name)
                elif val is not None and not active_here:
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
        report["blocks"].append((b["id"], b["title"].split("(")[0].strip(), kept, added))
        lines += block + [""]
    rest = [n for n in old if n not in KNOWN]
    if rest:
        lines += ["## KEPT FROM YOUR OLD FILE (not a setting this server reads; check whether you still need it)"] + [f"{n}={fmt(old[n])}" for n in rest] + [""]
        report["unknown"] += rest
    return "\n".join(lines)


stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
backup_dir = Path(os.environ["USERPROFILE"]) / "env-backups" / f"rootsquares-{stamp}"
results = {}
for kind in ("local", "staging"):
    path = B / f".env.{kind}"
    if not path.exists():
        print(f"\n[{kind}] {path} does not exist: skipped")
        continue
    old, raw = populated(path)
    peer_path = PEER_DIR / f".env.{kind}"
    peer = populated(peer_path)[0] if peer_path.exists() else {}
    names_in_file = re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)=", path.read_text(encoding="utf-8"), re.M)
    dup = sorted({n for n in names_in_file if names_in_file.count(n) > 1})
    report = dict(notes=[], placeholders=[], off_with_value=[], unknown=[], blocks=[])
    text = render(kind, old, peer, report)
    results[kind] = (path, text, old)
    print(f"\n=== square/backend/{path.name}: {len(old)} populated values found" + (f"; names written twice (the LAST one wins, the others are dropped): {dup}" if dup else "") + " ===")
    for bid, title, kept, added in report["blocks"]:
        if kept or added:
            print(f"  BLOCK {bid:3} {title[:44]:44} {kept} kept" + (f", {added} placeholder(s) to fill" if added else ""))
    print("  still to fill (placeholders):", sorted(set(report["placeholders"])) or "none")
    if report["off_with_value"]:
        print("  value kept but switched off (its block is off here):", sorted(set(report["off_with_value"])))
    if report["unknown"]:
        print("  kept at the end, not a setting this server reads:", sorted(set(report["unknown"])))
    for n in sorted(set(report["notes"])):
        print("  " + n)

if not APPLY:
    print("\nDRY RUN: nothing was written. Add --apply to back up the old files and write the new ones.")
    sys.exit(0)

backup_dir.mkdir(parents=True, exist_ok=True)
for kind, (path, text, old) in results.items():
    shutil.copy2(path, backup_dir / f"square-backend.{path.name}")
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    new_vals = {k: v for k, v in dotenv_values(path).items() if v is not None and v.strip() != "" and not re.search(r"<[^>@]*>", v)}
    lost = sorted(k for k, v in old.items() if new_vals.get(k) != v)
    print(f"\n[{kind}] written. Values active in the new file: {len(new_vals)} of {len(old)} old ones" + (f"; not active (switched off or dropped as a duplicate): {lost}" if lost else "; none lost"))
print(f"\nBackups of the old files: {backup_dir}\nDelete that folder when you have checked the new files (it holds the same secrets).")
