from rest_framework import serializers, status
from django.contrib.auth.models import Permission, Group
from rest_framework.permissions import IsAuthenticated

from authentication.models import *
from booking.models import *
from carts.models import *
from coupons.models import *
from customer.models import *
from holiday_package.models import *
from hotel_managements.models import *
from hotels.models import *
from org_managements.models import *
from org_resources.models import *
from payment_gateways.models import *


class ORGMUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'custom_id', 'email', 'password', 'mobile_number', 'first_name', 'last_name', 'last_login', 'roles')
