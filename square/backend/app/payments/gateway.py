"""The online payment providers behind one door (rootsquares W16-R6): Vipps app and Stripe card.

The call sites (tickets, memberships) ask for "start this payment" and "sync this payment" and never care which provider it is; what differs
(Vipps' own reference, Stripe's Checkout Session id) stays in here.
"""

from app.payments import stripe_gateway, vipps
from app.payments.errors import GatewayError
from app.payments.models import Payment

ONLINE_PROVIDERS = vipps.ONLINE_PROVIDERS
PROVIDER_NAMES = {vipps.PROVIDER: "Vipps", stripe_gateway.PROVIDER: "Stripe"}


def is_online(provider: str) -> bool:
    return provider in ONLINE_PROVIDERS


def is_public(provider: str) -> bool:
    """Whether customers may choose this provider right now (connected, switched on, a currency it takes)."""
    if provider == vipps.PROVIDER:
        return vipps.is_public()
    if provider == stripe_gateway.PROVIDER:
        return stripe_gateway.is_public()
    return False


def client_for(provider: str):
    return vipps.client_for(provider)


def start_payment(payment: Payment, return_url_template: str, description: str) -> str:
    """Opens the provider's hosted payment page for `payment` and returns where to send the customer.

    `return_url_template` may contain `{ref}`: the provider's reference of this payment (Vipps: ours, made here; Stripe: the Checkout Session
    id, which Stripe fills in when the customer comes back). Sets `payment.provider_transaction_id`; the caller commits. Raises GatewayError.
    """
    if payment.provider == vipps.PROVIDER:
        payment.provider_transaction_id = vipps.new_vipps_reference(payment)
        created = vipps.VippsClient().create_payment(
            payment.provider_transaction_id, payment.amount, return_url_template.replace("{ref}", payment.provider_transaction_id), description
        )
    elif payment.provider == stripe_gateway.PROVIDER:
        created = stripe_gateway.StripeClient().create_payment(
            payment.payment_reference or f"PAY-{payment.id}", payment.amount, return_url_template.replace("{ref}", "{CHECKOUT_SESSION_ID}"), description
        )
        payment.provider_transaction_id = created["id"]
    else:
        raise GatewayError("Not an online payment provider")
    redirect_url = created.get("redirectUrl")
    if not redirect_url:
        raise GatewayError("The payment provider did not return a page to send the customer to")
    return redirect_url


def sync(payment: Payment) -> Payment:
    return vipps.sync_vipps_payment(payment)
