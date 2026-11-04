"""One error for "the payment provider refused or could not be reached", whichever provider it is (Vipps, Stripe)."""


class GatewayError(Exception):
    """A payment provider call failed (network error or a refusal). `status_code` is the provider's answer when there was one."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
