from app.coupons.models import Coupon, redemption_count_for_coupon
from app.extensions import db


def deactivate_coupon_if_limit_reached(coupon: Coupon) -> None:
    """Auto-deactivate a coupon once its paid-order redemption count reaches max_redemptions.

    Called right after an order carrying this coupon becomes paid — checkout's zero-amount
    auto-issue path and admin mark-paid's real pending->paid transition (never on the idempotent
    no-op, matching order_marked_paid's own audit-log precedent). A no-op when max_redemptions
    is unset (unlimited) or the coupon is already inactive, so it's always safe to call.
    """
    if coupon.max_redemptions is None or not coupon.is_active:
        return
    if redemption_count_for_coupon(coupon.id) >= coupon.max_redemptions:
        coupon.is_active = False
        db.session.commit()
