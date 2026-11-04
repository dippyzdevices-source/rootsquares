"""The ways a customer can pay — one place for the stored names and what each one means.

* cash       — paid in person; a person confirms it ("manual approval").
* vipps_qr   — paid to the association's fixed Vipps QR / number; a person confirms it ("manual approval").
* vipps_app  — the real Vipps ePayment flow; Vipps confirms it itself ("automatic approval").
* stripe     — card payment through Stripe Checkout; Stripe confirms it itself ("automatic approval").

Older rows used "manual" (ticket QR payments and membership-drive payments) and "vipps" (membership
QR payments). Both were the Vipps QR flow, so they were renamed to "vipps_qr" (migration
d1f3b6a9c2e5); `normalize_method()` still maps "vipps" for an older client.
"""

CASH = "cash"
VIPPS_QR = "vipps_qr"
VIPPS_APP = "vipps_app"
STRIPE = "stripe"
BANK = "bank_transfer"  # paid by a transfer to the square's account; a person confirms it ("manual approval")

# How a payment of each method gets approved.
APPROVAL = {CASH: "manual", VIPPS_QR: "manual", BANK: "manual", VIPPS_APP: "auto", STRIPE: "auto"}

# Only "vipps" is still accepted from a client (an older frontend sending a membership QR payment);
# "manual" was never a valid choice for a member and stays rejected.
_LEGACY = {"vipps": VIPPS_QR}


def normalize_method(value):
    """Maps an old name a client may still send to the current one; anything else passes through."""
    return _LEGACY.get(value, value)
