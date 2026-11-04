r"""What it is:   A kept example, not a working script.
What it does: Shows bca-oslo's one-time Vipps webhook registration call; the square app now registers the webhook itself.
How to run:   Do not run it (it reads removed VIPPS_* variables); read it as a worked example.
Read before:  docs/setup/28-payment-keys.md.
Read after:   square/backend/app/payments/credentials_routes.py (the live code).

One-time: register this app's webhook URL with Vipps and print the signing secret.

Vipps webhooks are registered by an API call (this script), not in the Vipps portal.
Registration is per sales unit AND per environment (test and production are separate).

Run from the backend/ folder, in PowerShell, with the project's venv Python (the system `python`
does not have Flask). Copy-paste, filling in the <...> values.

=== PRODUCTION ===================================================================================
backend/.env normally holds the TEST Vipps keys, and values set in the shell override .env, so set
the production values in the shell first (they last only for that PowerShell window):

$env:VIPPS_ENV = "production"
$env:VIPPS_CLIENT_ID = "<production client_id>"
$env:VIPPS_CLIENT_SECRET = "<production client_secret>"
$env:VIPPS_SUBSCRIPTION_KEY = "<production Ocp-Apim-Subscription-Key, primary or secondary>"
$env:VIPPS_MSN = "<production Merchant Serial Number>"
.\.venv\Scripts\python.exe scripts/register_vipps_webhook.py https://api.bca-oslo.org/api/webhooks/vipps

=== TEST =========================================================================================
Uses the values already in backend/.env. Vipps must be able to reach the URL (e.g. an ngrok tunnel):

.\.venv\Scripts\python.exe scripts/register_vipps_webhook.py https://<id>.ngrok-free.app/api/webhooks/vipps

=== AFTER IT RUNS ================================================================================
It prints:

VIPPS_WEBHOOK_SECRET=<secret>

Vipps shows the secret ONLY ONCE: copy it straight into the backend environment
(VIPPS_WEBHOOK_SECRET) and restart/redeploy the backend. Do not paste it into chat or commit it.
To change the URL later, run the script again.

Check the venv path exists with:   Test-Path .\.venv\Scripts\python.exe
Subscribed events: epayments.payment.authorized/aborted/expired/terminated .v1
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Run as `python scripts/register_vipps_webhook.py ...` from backend/: put backend/ on the path
# (so `import app` works) and read backend/.env.local (or the file named by ENV_FILE). Variables already set in the shell win over
# the file — use that to pass the PRODUCTION values without editing it.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / (os.environ.get("ENV_FILE", "").strip() or ".env.local"))  # W26-R51

from app import create_app  # noqa: E402
from app.payments import vipps  # noqa: E402

EVENTS = [
    "epayments.payment.authorized.v1",
    "epayments.payment.aborted.v1",
    "epayments.payment.expired.v1",
    "epayments.payment.terminated.v1",
]

if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
        sys.exit("Usage: .\.venv\Scripts\python.exe scripts/register_vipps_webhook.py https://<public-host>/api/webhooks/vipps")
    app = create_app()
    with app.app_context():
        if not vipps.is_enabled():
            sys.exit("VIPPS_* credentials are not set in the environment.")
        result = vipps.VippsClient().register_webhook(sys.argv[1], EVENTS)
        print("Webhook id:", result.get("id"))
        print("VIPPS_WEBHOOK_SECRET=" + str(result.get("secret")))
