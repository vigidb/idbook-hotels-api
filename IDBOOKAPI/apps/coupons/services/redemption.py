"""
Partner / campaign coupon validation, discount computation, limits, and redemption ledger.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional, Tuple

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.coupons.models import Coupon, CouponCampaign, CouponAmountSlab, CouponRedemption
from apps.booking.models import Booking
from apps.booking.utils.db_utils import check_user_used_coupon


USER_MESSAGES = {
    "CODE_INVALID": "This coupon code is not valid.",
    "CODE_INACTIVE": "This coupon is not active.",
    "BOOKING_TYPE_NOT_ALLOWED": "This offer does not apply to this type of booking.",
    "CAMPAIGN_NOT_STARTED": "This offer is not active yet.",
    "CAMPAIGN_ENDED": "This offer has expired.",
    "SLAB_MISMATCH": "This offer does not apply to this booking amount.",
    "BUDGET_EXHAUSTED": "This offer has reached its usage limit.",
    "PER_USER_CAP": "You have already used this offer the maximum number of times.",
    "LEGACY_ONE_PER_USER": "This coupon has already been used on a confirmed booking.",
}


def normalize_coupon_code(code: Optional[str]) -> str:
    if not code:
        return ""
    return str(code).strip().upper()


def get_coupon_by_code(code: str) -> Optional[Coupon]:
    n = normalize_coupon_code(code)
    if not n:
        return None
    return Coupon.objects.filter(code__iexact=n).select_related("campaign", "partner").first()


def _campaign_booking_type_allowed(campaign: CouponCampaign, booking_type: str) -> bool:
    allowed = campaign.allowed_booking_types or []
    if not allowed:
        return True
    return booking_type in allowed


def _campaign_dates_ok(campaign: CouponCampaign) -> bool:
    now = timezone.now()
    if campaign.campaign_valid_from and now < campaign.campaign_valid_from:
        return False
    if campaign.campaign_valid_to and now > campaign.campaign_valid_to:
        return False
    return True


def pick_slab(slabs, amount: Decimal) -> Optional[CouponAmountSlab]:
    qs = slabs.order_by("sort_order", "id")
    for slab in qs:
        if amount < slab.min_amount:
            continue
        if slab.max_amount is not None and amount >= slab.max_amount:
            continue
        return slab
    return None


def _slab_discount_amount(slab: CouponAmountSlab, amount: Decimal) -> Decimal:
    if slab.discount_type == "AMOUNT":
        d = slab.discount_value
    else:
        d = (slab.discount_value * amount) / Decimal("100")
    if slab.max_discount_per_booking is not None:
        d = min(d, slab.max_discount_per_booking)
    d = min(d, amount)
    return d.quantize(Decimal("0.000001"))


def compute_discount_for_coupon(coupon: Coupon, amount: Decimal) -> Tuple[Decimal, Decimal]:
    """
    Returns (discount_applied, amount_after_discount).
    """
    if amount < 0:
        amount = Decimal("0")
    campaign = coupon.campaign

    # 1) If campaign slabs exist, always compute slab-based discount first.
    #    This ensures slab eligibility/mismatch rules remain applicable even
    #    when a coupon "override" is enabled.
    if campaign and campaign.slabs.exists():
        slab = pick_slab(campaign.slabs.all(), amount)
        if not slab:
            return Decimal("0"), amount

        disc_from_slabs = _slab_discount_amount(slab, amount)
        amount_after_slabs = (amount - disc_from_slabs).quantize(Decimal("0.000001"))

        # 2) If coupon value override is enabled, treat coupon.discount as a MAX
        #    discount cap over the slab-based discount.
        if coupon.use_coupon_value_override:
            disc_cap_val = coupon.discount
            dtype = coupon.discount_type
            if dtype == "AMOUNT":
                disc_cap = min(disc_cap_val, amount)
            else:
                disc_cap = (disc_cap_val * amount) / Decimal("100")
                disc_cap = min(disc_cap, amount)

            disc = min(disc_from_slabs, disc_cap)
            return disc, (amount - disc).quantize(Decimal("0.000001"))

        return disc_from_slabs, amount_after_slabs

    # Legacy flat discount on Coupon row (no campaign slabs)
    disc_val = coupon.discount
    dtype = coupon.discount_type
    if dtype == "AMOUNT":
        disc = min(disc_val, amount)
    else:
        disc = (disc_val * amount) / Decimal("100")
        disc = min(disc, amount)
    return disc.quantize(Decimal("0.000001")), (amount - disc).quantize(Decimal("0.000001"))


def assert_coupon_limits(
    coupon: Coupon,
    user_id: Optional[int],
    *,
    skip_legacy_one_per_user: bool = False,
    proposed_discount: Optional[Decimal] = None,
) -> Tuple[bool, str]:
    """
    Returns (ok, reason_code).
    proposed_discount: include this booking's discount when checking max_total_discount_budget.
    """
    # Coupon-level caps (applies for every coupon irrespective of campaign)
    coupon_qs = CouponRedemption.objects.filter(
        coupon=coupon,
        status=CouponRedemption.RedemptionStatus.CONFIRMED,
    )
    if coupon.max_redemptions_total is not None:
        if coupon_qs.count() >= coupon.max_redemptions_total:
            return False, "BUDGET_EXHAUSTED"
    if coupon.max_total_discount_budget is not None:
        coupon_total_disc = coupon_qs.aggregate(s=Sum("discount_applied"))["s"] or Decimal("0")
        coupon_budget = coupon.max_total_discount_budget
        if proposed_discount is not None:
            if coupon_total_disc + proposed_discount > coupon_budget:
                return False, "BUDGET_EXHAUSTED"
        elif coupon_total_disc >= coupon_budget:
            return False, "BUDGET_EXHAUSTED"
    if user_id and coupon.max_redemptions_per_user is not None:
        coupon_count_user = coupon_qs.filter(user_id=user_id).count()
        if coupon_count_user >= coupon.max_redemptions_per_user:
            return False, "PER_USER_CAP"

    campaign = coupon.campaign
    if campaign:
        if not campaign.active:
            return False, "CODE_INACTIVE"
        # Redemption counts for campaign (all coupons under campaign)
        coupon_ids = list(
            Coupon.objects.filter(campaign=campaign).values_list("id", flat=True)
        )
        qs = CouponRedemption.objects.filter(
            coupon_id__in=coupon_ids,
            status=CouponRedemption.RedemptionStatus.CONFIRMED,
        )
        if campaign.max_redemptions_total is not None:
            if qs.count() >= campaign.max_redemptions_total:
                return False, "BUDGET_EXHAUSTED"
        if campaign.max_total_discount_budget is not None:
            total_disc = qs.aggregate(s=Sum("discount_applied"))["s"] or Decimal("0")
            budget = campaign.max_total_discount_budget
            if proposed_discount is not None:
                if total_disc + proposed_discount > budget:
                    return False, "BUDGET_EXHAUSTED"
            elif total_disc >= budget:
                return False, "BUDGET_EXHAUSTED"
        if user_id and campaign.max_redemptions_per_user is not None:
            count_user = qs.filter(user_id=user_id).count()
            if count_user >= campaign.max_redemptions_per_user:
                return False, "PER_USER_CAP"
        return True, ""

    # Legacy: one confirmed booking per user per code
    if not skip_legacy_one_per_user and user_id:
        if check_user_used_coupon(coupon.code, user_id):
            return False, "LEGACY_ONE_PER_USER"
    return True, ""


def validate_coupon_for_context(
    code: str,
    *,
    booking_type: str = "HOTEL",
    amount: Optional[Decimal] = None,
    user_id: Optional[int] = None,
    checkin_date=None,
    booking_date=None,
) -> dict[str, Any]:
    """
    Full validation for API: validity, booking type, campaign dates, slabs.
    amount may be None for lightweight checks (slab not evaluated).
    """
    n = normalize_coupon_code(code)
    if not n:
        return {
            "valid": False,
            "reason_code": "CODE_INVALID",
            "user_message": USER_MESSAGES["CODE_INVALID"],
            "coupon": None,
            "discount_applied": None,
            "payable_after_discount": None,
        }

    coupon = get_coupon_by_code(n)
    if not coupon or not coupon.active:
        return {
            "valid": False,
            "reason_code": "CODE_INVALID",
            "user_message": USER_MESSAGES["CODE_INVALID"],
            "coupon": None,
            "discount_applied": None,
            "payable_after_discount": None,
        }

    if coupon.is_stay_date and not checkin_date:
        return {
            "valid": False,
            "reason_code": "COUPON_DATE_ERROR",
            "user_message": "This coupon requires a check-in date. Please provide checkin_date.",
            "coupon": coupon,
            "discount_applied": None,
            "payable_after_discount": None,
        }
    if coupon.is_booking_date and not booking_date:
        return {
            "valid": False,
            "reason_code": "COUPON_DATE_ERROR",
            "user_message": "This coupon requires a booking date. Please provide booking_date.",
            "coupon": coupon,
            "discount_applied": None,
            "payable_after_discount": None,
        }

    campaign = coupon.campaign
    if campaign:
        if not campaign.active:
            return {
                "valid": False,
                "reason_code": "CODE_INACTIVE",
                "user_message": USER_MESSAGES["CODE_INACTIVE"],
                "coupon": coupon,
                "discount_applied": None,
                "payable_after_discount": None,
            }
        if not _campaign_booking_type_allowed(campaign, booking_type):
            return {
                "valid": False,
                "reason_code": "BOOKING_TYPE_NOT_ALLOWED",
                "user_message": USER_MESSAGES["BOOKING_TYPE_NOT_ALLOWED"],
                "coupon": coupon,
                "discount_applied": None,
                "payable_after_discount": None,
            }
        if not _campaign_dates_ok(campaign):
            now = timezone.now()
            if campaign.campaign_valid_from and now < campaign.campaign_valid_from:
                msg = USER_MESSAGES["CAMPAIGN_NOT_STARTED"]
                rc = "CAMPAIGN_NOT_STARTED"
            else:
                msg = USER_MESSAGES["CAMPAIGN_ENDED"]
                rc = "CAMPAIGN_ENDED"
            return {
                "valid": False,
                "reason_code": rc,
                "user_message": msg,
                "coupon": coupon,
                "discount_applied": None,
                "payable_after_discount": None,
            }

    # Date rules on coupon (stay / booking) — reuse existing semantics
    if coupon.is_stay_date and checkin_date:
        if coupon.stay_start_date and checkin_date < coupon.stay_start_date:
            return {
                "valid": False,
                "reason_code": "COUPON_DATE_ERROR",
                "user_message": "Check-in date is outside the coupon validity window.",
                "coupon": coupon,
                "discount_applied": None,
                "payable_after_discount": None,
            }
        if coupon.stay_end_date and checkin_date > coupon.stay_end_date:
            return {
                "valid": False,
                "reason_code": "COUPON_DATE_ERROR",
                "user_message": "Check-in date is outside the coupon validity window.",
                "coupon": coupon,
                "discount_applied": None,
                "payable_after_discount": None,
            }
    if coupon.is_booking_date and booking_date:
        if coupon.booking_start_date and booking_date < coupon.booking_start_date:
            return {
                "valid": False,
                "reason_code": "COUPON_DATE_ERROR",
                "user_message": "Booking date is outside the coupon validity window.",
                "coupon": coupon,
                "discount_applied": None,
                "payable_after_discount": None,
            }
        if coupon.booking_end_date and booking_date > coupon.booking_end_date:
            return {
                "valid": False,
                "reason_code": "COUPON_DATE_ERROR",
                "user_message": "Booking date is outside the coupon validity window.",
                "coupon": coupon,
                "discount_applied": None,
                "payable_after_discount": None,
            }

    disc = None
    payable = None
    if amount is not None:
        disc, payable = compute_discount_for_coupon(coupon, amount)
        if campaign and campaign.slabs.exists() and disc <= 0:
            return {
                "valid": False,
                "reason_code": "SLAB_MISMATCH",
                "user_message": USER_MESSAGES["SLAB_MISMATCH"],
                "coupon": coupon,
                "discount_applied": None,
                "payable_after_discount": None,
            }

    ok, lim_reason = assert_coupon_limits(
        coupon, user_id, proposed_discount=disc
    )
    if not ok:
        return {
            "valid": False,
            "reason_code": lim_reason,
            "user_message": USER_MESSAGES.get(lim_reason, USER_MESSAGES["CODE_INVALID"]),
            "coupon": coupon,
            "discount_applied": None,
            "payable_after_discount": None,
        }

    if amount is not None:
        return {
            "valid": True,
            "reason_code": "",
            "user_message": "",
            "coupon": coupon,
            "discount_applied": disc,
            "payable_after_discount": payable,
            "campaign_name": campaign.name if campaign else "",
        }

    return {
        "valid": True,
        "reason_code": "",
        "user_message": "",
        "coupon": coupon,
        "discount_applied": None,
        "payable_after_discount": None,
        "campaign_name": campaign.name if campaign else "",
    }


@transaction.atomic
def record_coupon_redemption(
    coupon: Coupon,
    booking: Booking,
    *,
    booking_subtotal: Decimal,
    discount_applied: Decimal,
) -> CouponRedemption:
    """Idempotent: returns existing row if already present."""
    existing = CouponRedemption.objects.filter(
        booking=booking, coupon=coupon
    ).first()
    if existing:
        return existing

    if coupon.campaign_id:
        CouponCampaign.objects.select_for_update().filter(pk=coupon.campaign_id).first()

    ok, reason = assert_coupon_limits(
        coupon,
        booking.user_id if booking.user_id else None,
        proposed_discount=discount_applied,
    )
    if not ok:
        raise ValueError(f"Coupon limits not satisfied: {reason}")

    return CouponRedemption.objects.create(
        coupon=coupon,
        booking=booking,
        user=booking.user,
        booking_type=booking.booking_type,
        booking_subtotal=booking_subtotal,
        discount_applied=discount_applied,
        status=CouponRedemption.RedemptionStatus.CONFIRMED,
    )
