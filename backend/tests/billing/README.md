# The billing and payments test suite

One folder, one file per topic, numbered in the order the money moves. Run all of it (plus lint, types, the frontend part) with `scripts\test-billing.ps1` from the repository root; one file with `python -m pytest tests\billing\test_14_webhook_route.py -q` from `backend\`. The whole system these tests describe: `docs/reference/billing-and-payments.md`.

## Rules of this suite

- **No network, ever.** `conftest.py` blocks `requests` (which the Stripe library uses) and `httpx`. A test that needs Stripe replaces the one service method it uses (for example `stripe.checkout._session_service.SessionService.create`) with a fake. A test that tries the network fails with "a billing test tried to use the network".
- **Real signatures.** Webhook tests sign their bodies with the same HMAC scheme as Stripe, so the signature check is genuinely exercised (a wrong secret, a missing header and a good one).
- **Real code, fake edges.** Tests go through the Flask routes and the database (SQLite in a temp folder). Only Stripe, the e-mail service and the clock are fake.
- **Settings are changed on the app** with `api.extensions["settings"].model_copy(update=...)`, never in the environment.
- **Docs are tested.** `test_17_consistency.py` fails when the code, the frontend prices, the settings, the routes, the migrations, the audit actions or the guides drift apart. If it fails after you changed something, update the document it names.
- The shared helpers are in `helpers.py`: `_square(api, who, package, country)` makes a signed-in fake owner with an organisation and a square `sq-<who>`; `_checkout(...)`; `_set(...)` moves a square's paid time; `_run(...)` runs one pass of the trial job at the fixed clock `NOW` (2026-10-20 12:00 UTC).

## The map

| File | What it proves |
|---|---|
| `test_01_prices.py` | prices are data with the decided defaults; only a platform admin changes one; a bad amount or key is refused |
| `test_02_orders.py` | an upgrade costs the difference and applies only when paid; a cancelled checkout changes nothing; nothing to upgrade to from the top or sideways; a running period sets and adds `paid_until`; an Event pass has no running period; other people cannot pay or look; the fake provider has no webhook; the default billing period |
| `test_03_trial_and_first_payment.py` | 7 free days; the first payment is the package plus the first Live period; with money on the first payment comes before upgrades and running periods; a higher package can be chosen at the first payment, a lower one is refused |
| `test_04_event_pass_payment.py` | an Event pass is built and its clock started only when paid (money on); it starts at once (money off) |
| `test_05_enforce_and_config.py` | waking needs a paid period only with `BILLING_ENFORCE`; Stripe needs its keys; a test clock needs a test key |
| `test_06_trial_job.py` | the trial job: nothing without enforcing, an ended trial sleeps, grace days for a paid square, Event pass and old squares left alone, the day-6 reminder once and only when sent, the reminder text |
| `test_07_renewals_cancel.py` | a renewal extends the time once and a replay does nothing; cancel keeps the plan; resume; the end of the subscription |
| `test_08_failed_renewal.py` | a failed renewal is remembered once, the owner is told once, a payment clears it |
| `test_09_refund.py` | only a platform admin; only a paid first payment inside the days; once; the square is unpaid and asleep afterwards |
| `test_10_portal_and_country.py` | the card page needs a customer; the billing country is kept on the organisation and required when money is on |
| `test_11_subscriptions_overview.py` | the Subscriptions numbers and states; admin only |
| `test_12_stripe_adapter.py` | what is sent to Stripe for each order kind (modes, lines, tax code, address, customer, test clock); Stripe errors are hidden; the webhook parsing for every event, both invoice shapes, bad signatures; portal, refund (found through the session or the invoice), ending a subscription |
| `test_13_email.py` | Resend call shape, key only in the header, errors without the key, settings |
| `test_14_webhook_route.py` | **end to end through the Flask route with real signatures**: bad signature refused; paid first checkout applies once and a replay changes nothing; expired cancels and a later paid report does not revive it; unpaid, unknown and other events are acknowledged and ignored; a renewal extends once; a failed renewal is recorded once with one e-mail; the end of a subscription; an Event pass is built once; a refund ends the subscription at Stripe and the paid time |
| `test_15_commands.py` | `trial-run` (no enforcing, dry run, apply, twice) and `email-test` |
| `test_16_money_rules.py` | the money rules as plain functions: default prices, the upgrade difference for every pair, the Event pass credit, money on or off, the refund window to the second, what a refund marks, who owes a first payment, refusals, paying early and a year |
| `test_17_consistency.py` | code, prices, settings, routes, migrations, audit actions and guides stay in step |

Frontend (from `frontend\`, `npm run test:billing`, file `tests/billing.test.mjs`): the built-in prices, ten months for twelve, money formatting, the words every order kind, status and Subscriptions state needs, the Billing page boxes' words, no fixed currency in the pay buttons or the landing line, the start flow (`startFlow.ts`), Pricing and Templates not pointing at the prototype wizard, no preselected country or currency.

Related tests elsewhere that billing builds on (run by `test-billing.ps1`): `tests/test_square_plans.py` (packages and modules), `tests/test_event_pass.py` (the Event pass life), `tests/test_migrations.py`, `tests/test_config.py`, `tests/test_sleep.py`.

## What these tests cannot prove

They never talk to Stripe, so they cannot tell whether Stripe's real answers still look like our fakes. After a Stripe library or API-version upgrade, or before going live, do the recipes of guide 24 section 7 once by hand against the sandbox.

## Adding a test

1. Put it in the file of its topic (or a new numbered file).
2. Use `_square` and the settings trick; fake only the Stripe service method or the e-mail sender you need.
3. If you add a route, a setting, an audit action, an order kind or a migration, add it to `docs/reference/billing-and-payments.md` (and the settings to guide 13 and `.env.example`) or `test_17_consistency.py` will fail.
