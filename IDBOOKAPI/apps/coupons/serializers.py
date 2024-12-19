from rest_framework import serializers, status
# from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission

# from apps.authentication.models import *
from .models import Coupon
# from booking.models import *
# from carts.models import *
# from coupons.models import *
# from customer.models import *
# from holiday_package.models import *
# from hotel_managements.models import *
# from hotels.models import *
# from org_managements.models import *
from apps.org_resources.models import *
# from payment_gateways.models import *
from IDBOOKAPI.utils import format_custom_id


class CouponSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_null=True)
  
    class Meta:
        model = Coupon
        fields = "__all__"

    def create(self, validated_data):
        coupon = Coupon(**validated_data)
        coupon.code = coupon.generate_unique_code()
        coupon.save()

        return coupon

    
