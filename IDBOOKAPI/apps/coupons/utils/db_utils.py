# db utils
from apps.coupons.models import Coupon
from apps.coupons.services.redemption import get_coupon_by_code


def get_coupon_from_code(code):
    if not code:
        return None
    return get_coupon_by_code(code)
