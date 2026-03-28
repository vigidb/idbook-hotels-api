"""Apply partner coupons when persisting a priced booking (query conversion, etc.)."""
import logging
from decimal import Decimal
from typing import Optional

from apps.booking.models import AppliedCoupon
from apps.coupons.models import CouponRedemption
from apps.coupons.services.redemption import (
    validate_coupon_for_context,
    record_coupon_redemption,
)

logger = logging.getLogger(__name__)


def record_applied_coupon_for_booking(booking, coupon, *, discount_amount: Decimal):
    """Ledger row for admin \"claimed\" tab; no redemption until booking is confirmed with payment."""
    if not coupon or not booking or not booking.pk:
        return None
    AppliedCoupon.objects.update_or_create(
        booking_id=booking.id,
        defaults={
            "coupon_id": coupon.id,
            "discount_amount": discount_amount,
        },
    )


def sync_applied_coupon_from_booking(booking):
    """
    Upsert AppliedCoupon whenever booking has a coupon FK and discount fields set.
    Use after any path that sets booking.coupon without going through apply_coupon_to_booking.
    """
    coupon = getattr(booking, "coupon", None)
    if coupon is None or not booking.pk:
        return None
    raw = booking.discount
    if raw is None:
        raw = getattr(booking, "total_discount", None)
    try:
        disc = Decimal(str(raw if raw is not None else "0"))
    except Exception:
        disc = Decimal("0")
    if disc < 0:
        disc = Decimal("0")
    return record_applied_coupon_for_booking(booking, coupon, discount_amount=disc)


def record_booking_coupon_redemption_if_pending(booking) -> Optional[CouponRedemption]:
    """
    Create CouponRedemption when the booking first becomes confirmed (payment rules already applied).
    Idempotent via record_coupon_redemption.
    """
    coupon = getattr(booking, "coupon", None)
    if coupon is None:
        return None
    if CouponRedemption.objects.filter(booking_id=booking.id, coupon_id=coupon.id).exists():
        return CouponRedemption.objects.filter(
            booking_id=booking.id, coupon_id=coupon.id
        ).first()
    subtotal = booking.subtotal or Decimal("0")
    disc = booking.discount or booking.total_discount or Decimal("0")
    try:
        return record_coupon_redemption(
            coupon,
            booking,
            booking_subtotal=subtotal,
            discount_applied=disc,
        )
    except ValueError as e:
        logger.warning(
            "Coupon redemption at confirm failed for booking %s: %s",
            booking.id,
            e,
        )
        return None


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
    Set subtotal/discount/final_amount/coupon FK and write AppliedCoupon (claimed).
    Redemption is recorded only when the booking is later confirmed with payment.
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
    record_applied_coupon_for_booking(booking, coupon, discount_amount=disc)
