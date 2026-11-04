"""Consistency tests (W12-R22): they keep the code, the settings, the frontend prices, the words and the documents in step. When one of these fails, one of two
things changed without the other: change the other one too (this is on purpose, the billing documentation is meant to stay true)."""

import re
from pathlib import Path

from app.platform import billing, subscriptions
from app.platform.models import Organization, Square
from app.shared.config import Settings

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs"
ROUTES = (ROOT / "backend" / "app" / "platform" / "routes.py").read_text(encoding="utf-8")
GUIDE_13 = (DOCS / "setup" / "13-environment-variables.md").read_text(encoding="utf-8")
GUIDE_24 = (DOCS / "setup" / "24-stripe-setup-and-commands.md").read_text(encoding="utf-8")
REFERENCE = (DOCS / "reference" / "billing-and-payments.md").read_text(encoding="utf-8")
# the console has its own wording file (ADR 083)
EN = (ROOT / "frontend" / "ui" / "src" / "i18n" / "en.json").read_text(encoding="utf-8")  # the shared messages moved to the ui package (ADR 084)
EN += (ROOT / "frontend" / "platform" / "src" / "i18n" / "en.json").read_text(encoding="utf-8")  # the customer wording that moved out of ui (ADR 084 stage 6)
EN += (ROOT / "frontend" / "admin" / "src" / "i18n" / "admin.en.json").read_text(encoding="utf-8")
PRICING_TS = (ROOT / "frontend" / "ui" / "src" / "mock" / "pricing.ts").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
BILLING_FIELDS = [
    f for f in Settings.model_fields if f.startswith(("BILLING_", "STRIPE_", "EMAIL_", "RESEND_")) or f in ("PROVIDER_SLEEP", "PLATFORM_FRONTEND_URL")
]


def _number(text: str) -> int:
    return int(text.replace("_", ""))


def test_no_price_is_written_in_the_code() -> None:
    """Prices are data on the platform (W14-R29): neither the backend nor the frontend's pricing helper holds an amount."""
    assert not re.search(r"[Mm]inor:\s*[\d_]+", PRICING_TS), "frontend/ui/src/mock/pricing.ts holds an amount"
    source = (ROOT / "backend" / "app" / "platform" / "billing.py").read_text(encoding="utf-8")
    assert "PRICE_DEFAULTS" not in source and not re.search(r'"(launch|running)\.[a-z.]+": \(\d', source)


def test_every_billing_setting_is_in_the_environment_guide_and_the_example_file() -> None:
    assert len(BILLING_FIELDS) >= 15
    for name in BILLING_FIELDS:
        assert f"`{name}`" in GUIDE_13, f"{name} is not described in docs/setup/13-environment-variables.md"
        assert name in ENV_EXAMPLE, f"{name} is not in backend/.env.example"


def test_every_webhook_event_is_in_the_stripe_guide_and_the_reference() -> None:
    assert len(billing.WEBHOOK_EVENTS) == 5
    for event in billing.WEBHOOK_EVENTS:
        assert event in GUIDE_24, f"{event} is missing in guide 24"
        assert event in REFERENCE, f"{event} is missing in docs/reference/billing-and-payments.md"
    listen = ",".join(billing.WEBHOOK_EVENTS)
    assert listen in GUIDE_24, "the stripe listen command of guide 24 must list the events in the order of WEBHOOK_EVENTS"


def test_every_billing_route_is_in_the_api_table_of_the_reference() -> None:
    routes = re.findall(r'@bp\.(?:get|post|put|delete)\("([^"]+)"\)', ROUTES)
    billing_routes = [r for r in routes if "billing" in r or r.startswith(("/prices", "/owner/subscriptions", "/squares/<uuid:square_id>/running-plan"))]
    assert len(billing_routes) >= 14
    for route in billing_routes:
        short = re.sub(r"<(?:uuid|string):(\w+)>", r"<\1>", route)
        short = short.replace("<square_id>", "<id>").replace("<order_id>", "<id>")
        assert short in REFERENCE, f"{route} (as {short}) is not in the API table of docs/reference/billing-and-payments.md"


def test_every_migration_of_billing_is_listed_in_the_reference() -> None:
    names = sorted(p.name for p in (ROOT / "backend" / "migrations" / "versions").glob("*.py"))
    numbers = [n[:4] for n in names]
    assert numbers == [f"{i:04d}" for i in range(1, len(numbers) + 1)], "migrations must be numbered 0001, 0002, ... without gaps"
    for n in range(7, 17):
        assert f"| {n:04d} |" in REFERENCE, f"migration {n:04d} is not in the table of docs/reference/billing-and-payments.md"


def test_every_billing_audit_action_in_the_code_is_documented() -> None:
    code = "\n".join(
        (ROOT / "backend" / "app" / "platform" / f).read_text(encoding="utf-8")
        for f in ("routes.py", "billing.py", "trial.py", "sleep.py", "notify.py", "event_pass.py")
    )
    actions = set(re.findall(r'"(billing\.[a-z_]+)"', code)) | {m for m in re.findall(r'REMINDER_ACTION = "(billing\.[a-z_]+)"', code)}
    assert {"billing.checkout", "billing.refund", "billing.payment_failed", "billing.lapsed", "billing.trial_reminder"} <= actions
    for action in actions:
        assert action in REFERENCE, f"audit action {action} is not documented"


def test_every_order_kind_and_status_is_documented_and_has_words() -> None:
    kinds = ("upgrade", "running", "event_upgrade", "event_pass", "first")
    for kind in kinds:
        assert f"`{kind}`" in REFERENCE
    for status in ("pending", "paid", "cancelled", "failed", "refunded"):
        assert f"`{status}`" in REFERENCE
        assert f'"{status}"' in EN, f"no words for the order status {status}"
    for state in ("trial", "unpaid", "renewing", "ending", "failed", "asleep", "paid", "expired"):
        assert f'"{state}"' in EN
    # the states the overview can produce are exactly those with words
    code = (ROOT / "backend" / "app" / "platform" / "subscriptions.py").read_text(encoding="utf-8")
    for state in ("failed", "asleep", "trial", "unpaid", "ending", "renewing", "paid", "expired"):
        assert f'"{state}"' in code, f"subscriptions.py no longer produces {state}"
    assert subscriptions.PACKAGES == ("roots", "square", "grove", "event")


def test_the_model_has_the_columns_the_reference_lists() -> None:
    for column in ("stripe_subscription_id", "renewal_cancelled", "payment_failed_at", "paid_until", "billing_interval", "launch_package", "running_plan"):
        assert hasattr(Square, column) and f"`{column}`" in REFERENCE
    for column in ("billing_country", "stripe_customer_id"):
        assert hasattr(Organization, column) and f"`{column}`" in REFERENCE


def test_the_guides_are_in_the_index() -> None:
    index = (DOCS / "setup" / "00-START-HERE-guide-index.md").read_text(encoding="utf-8")
    for guide in ("22-stripe-billing.md", "24-stripe-setup-and-commands.md", "25-platform-email.md"):
        assert guide in index and (DOCS / "setup" / guide).exists()
    assert (DOCS / "reference" / "billing-and-payments.md").exists()
    decisions = (DOCS / "DECISIONS.md").read_text(encoding="utf-8")
    for adr in range(50, 57):
        assert f"## {adr:03d}:" in decisions, f"ADR {adr:03d} is missing"
