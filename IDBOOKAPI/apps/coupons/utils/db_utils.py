# db utils
from apps.coupons.models import Coupon

def get_coupon_from_code(code):
    coupon = Coupon.objects.filter(code=code, active=True).first()
    return coupon
