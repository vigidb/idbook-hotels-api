from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import random
import string
from IDBOOKAPI.basic_resources import COUPON_TYPES, DISCOUNT_TYPE

from apps.hotels.models import Property


class Coupon(models.Model):
    code = models.CharField(max_length=6, unique=True)
##    valid_from = models.DateTimeField()
##    valid_to = models.DateTimeField()
    is_stay_date = models.BooleanField(default=False)
    stay_start_date = models.DateField(null=True)
    stay_end_date = models.DateField(null=True)
    is_booking_date = models.BooleanField(default=False)
    booking_start_date = models.DateField(null=True)
    booking_end_date = models.DateField(null=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE, default='AMOUNT')
    discount = models.DecimalField(max_digits=15, decimal_places=4, validators=[MinValueValidator(0)])
##    coupon_type = models.CharField(max_length=20, choices=COUPON_TYPES)
    active = models.BooleanField(default=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, null=True,
                                 related_name='property_coupon')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code

    def generate_unique_code(self):
        length = 6
        characters = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choice(characters) for _ in range(length))
            if not Coupon.objects.filter(code=code).exists():
                return code
