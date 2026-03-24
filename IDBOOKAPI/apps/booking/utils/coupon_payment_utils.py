"""Validate payment initiate amounts for partial-pay holiday (and similar) bookings."""
from decimal import Decimal


def uses_partial_payment_rules(booking) -> bool:
    if getattr(booking, "booking_type", None) != "HOLIDAYPACK":
        return False
    if booking.min_payment_percent is not None or booking.min_payment_amount is not None:
        return True
    paid = booking.total_payment_made or Decimal("0")
    return paid > 0


def validate_initiate_payment_amount(booking, request_amount: float) -> tuple[bool, str]:
    """
    HOLIDAYPACK payment rules: full payable unless partial rules apply (min fields or prior payments).
    """
    from apps.booking.utils.booking_utils import get_booking_payable_amount

    if getattr(booking, "booking_type", None) != "HOLIDAYPACK":
        return False, "This validator applies to holiday package bookings only"

    try:
        amt = Decimal(str(request_amount))
    except Exception:
        return False, "Invalid amount format"

    if amt <= 0:
        return False, "Amount must be positive"

    payable_full = Decimal(str(get_booking_payable_amount(booking)))
    balance = booking.balance_due()
    if balance <= 0:
        return False, "No balance due for this booking"

    if not uses_partial_payment_rules(booking):
        if amt != payable_full:
            return False, f"Amount mismatch. Expected amount: {float(payable_full)}"
        return True, ""

    if amt > balance:
        return False, f"Amount exceeds balance due: {float(balance)}"

    paid_so_far = booking.total_payment_made or Decimal("0")
    if paid_so_far <= 0:
        min_req = booking.minimum_first_payment_amount()
        if min_req > 0 and amt < min_req:
            return (
                False,
                f"Minimum first payment is {float(min_req)} for this booking",
            )

    return True, ""
