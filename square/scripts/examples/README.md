# Examples (kept for reference, not part of the running app)

> - **What it is:** The index of the scripts in `square/scripts/examples/`.
> - **What it does:** Explains the kept-for-reference scripts that do not run as they are.
> - **How to use / run:** Read a script as a worked example; do not run it.
> - **Read before:** `docs/setup/28-payment-keys.md`.
> - **Read after:** `scripts/README.md` (the index of all scripts).

- `register_vipps_webhook.py`: bca-oslo's one-time script that registers a Vipps webhook and prints the signing secret. It reads the `VIPPS_*` environment variables, which no longer exist in the square app (W16-R4): the app now registers the webhook itself when a square connects Vipps (`app/payments/credentials_routes.py`). Kept as a worked example of the Vipps webhook registration call; it will not run as it is.
