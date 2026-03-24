"""Apply partner coupons when persisting a priced booking (query conversion, etc.)."""
from decimal import Decimal

from apps.coupons.services.redemption import (
    validate_coupon_for_context,
    record_coupon_redemption,
)


def apply_coupon_to_booking(
    booking,
    coupon_code: str,
    quote_amount: Decimal,
    *,
    user_id,
    booking_type: str,
    checkin_date=None,
    booking_date=None,
):
    """
    Set subtotal/discount/final_amount/coupon FK and write CouponRedemption.
    Raises ValueError with user-facing message on failure.
    """
    code = (coupon_code or "").strip()
    if not code:
        return
    ctx = validate_coupon_for_context(
        code,
        booking_type=booking_type,
        amount=quote_amount,
        user_id=user_id,
        checkin_date=checkin_date,
        booking_date=booking_date,
    )
    if not ctx["valid"]:
        raise ValueError(ctx.get("user_message") or ctx.get("reason_code") or "Invalid coupon")
    coupon = ctx["coupon"]
    disc = ctx["discount_applied"]
    payable = ctx["payable_after_discount"]
    booking.subtotal = quote_amount
    booking.discount = disc
    booking.total_discount = disc
    booking.final_amount = payable
    booking.coupon = coupon
    booking.coupon_code = coupon.code
    booking.save(
        update_fields=[
            "subtotal",
            "discount",
            "total_discount",
            "final_amount",
            "coupon",
            "coupon_code",
            "updated",
        ]
    )
    record_coupon_redemption(
        coupon,
        booking,
        booking_subtotal=quote_amount,
        discount_applied=disc,
    )
