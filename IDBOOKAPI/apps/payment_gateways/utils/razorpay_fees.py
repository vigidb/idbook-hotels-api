"""
Razorpay platform fee estimates (GST on fee). Rates are policy defaults — verify
against your Razorpay agreement; settlement should use payment.fetch fee/tax.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict


RAZORPAY_GST_RATE = Decimal("0.18")
GST_EXEMPT_CARD_THRESHOLD_RUPEES = Decimal("2000")

# Internal bucket keys for estimation
BUCKET_DOMESTIC_STANDARD = "domestic_standard"  # 2% + GST
BUCKET_PREMIUM = "premium"  # 3% + GST (EMI, intl card, Amex, etc.)
BUCKET_INTL_BANK = "international_bank"  # 1% + GST
BUCKET_RUPAY_UPI = "rupay_credit_upi"  # 2.15% + GST

PLATFORM_FEE_RATE: dict[str, Decimal] = {
    BUCKET_DOMESTIC_STANDARD: Decimal("0.02"),
    BUCKET_PREMIUM: Decimal("0.03"),
    BUCKET_INTL_BANK: Decimal("0.01"),
    BUCKET_RUPAY_UPI: Decimal("0.0215"),
}

# Conservative default for UI when method unknown (matches premium + GST)
WORST_CASE_EFFECTIVE_RATE = Decimal("0.0354")


class FeeEstimate(TypedDict):
    amount_rupees: str
    bucket: str
    platform_fee_rupees: str
    gst_on_fee_rupees: str
    total_fee_rupees: str
    wallet_credit_if_fee_deducted_rupees: str
    gst_exempt: bool
    effective_rate_on_amount: str


def _money_round(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"))


def estimate_razorpay_fee_rupees(
    amount_rupees: Decimal,
    bucket: str = BUCKET_DOMESTIC_STANDARD,
    *,
    is_domestic_card_below_threshold: bool = False,
) -> tuple[Decimal, Decimal, Decimal, bool]:
    """
    Returns (platform_fee, gst_on_fee, total_fee, gst_exempt).
    """
    rate = PLATFORM_FEE_RATE.get(bucket, PLATFORM_FEE_RATE[BUCKET_DOMESTIC_STANDARD])
    platform_fee = _money_round(amount_rupees * rate)
    gst_exempt = bool(
        bucket == BUCKET_DOMESTIC_STANDARD and is_domestic_card_below_threshold
    )
    gst_on_fee = (
        Decimal("0")
        if gst_exempt
        else _money_round(platform_fee * RAZORPAY_GST_RATE)
    )
    total_fee = _money_round(platform_fee + gst_on_fee)
    return platform_fee, gst_on_fee, total_fee, gst_exempt


def build_fee_estimate_response(
    amount_rupees: Decimal, bucket: str
) -> FeeEstimate:
    card_gst_exempt = (
        bucket == BUCKET_DOMESTIC_STANDARD
        and amount_rupees < GST_EXEMPT_CARD_THRESHOLD_RUPEES
    )
    platform_fee, gst_on_fee, total_fee, gst_exempt = estimate_razorpay_fee_rupees(
        amount_rupees,
        bucket=bucket,
        is_domestic_card_below_threshold=card_gst_exempt,
    )
    credit = _money_round(amount_rupees - total_fee)
    eff = (
        _money_round((total_fee / amount_rupees) * Decimal("100"))
        if amount_rupees > 0
        else Decimal("0")
    )
    return FeeEstimate(
        amount_rupees=str(amount_rupees),
        bucket=bucket,
        platform_fee_rupees=str(platform_fee),
        gst_on_fee_rupees=str(gst_on_fee),
        total_fee_rupees=str(total_fee),
        wallet_credit_if_fee_deducted_rupees=str(credit),
        gst_exempt=gst_exempt,
        effective_rate_on_amount=str(eff),
    )


def actual_fee_from_payment_entity(payment_entity: dict[str, Any]) -> dict[str, Any]:
    """Map Razorpay payment entity fields (paise) to rupee floats for storage."""
    fee_paise = payment_entity.get("fee")
    tax_paise = payment_entity.get("tax")
    amount_paise = payment_entity.get("amount")
    out: dict[str, Any] = {
        "fee_paise": int(fee_paise or 0),
        "tax_paise": int(tax_paise or 0),
        "amount_paise": int(amount_paise or 0),
        "method": payment_entity.get("method"),
        "international": payment_entity.get("international"),
    }
    out["fee_rupees"] = str(Decimal(out["fee_paise"]) / Decimal("100"))
    out["tax_rupees"] = str(Decimal(out["tax_paise"]) / Decimal("100"))
    return out


def worst_case_estimate(amount_rupees: Decimal) -> FeeEstimate:
    total_fee = _money_round(amount_rupees * WORST_CASE_EFFECTIVE_RATE)
    platform_fee = _money_round(total_fee / (Decimal("1") + RAZORPAY_GST_RATE))
    gst_on_fee = _money_round(total_fee - platform_fee)
    credit = _money_round(amount_rupees - total_fee)
    return FeeEstimate(
        amount_rupees=str(amount_rupees),
        bucket="worst_case",
        platform_fee_rupees=str(platform_fee),
        gst_on_fee_rupees=str(gst_on_fee),
        total_fee_rupees=str(total_fee),
        wallet_credit_if_fee_deducted_rupees=str(credit),
        gst_exempt=False,
        effective_rate_on_amount=str(WORST_CASE_EFFECTIVE_RATE * Decimal("100")),
    )
