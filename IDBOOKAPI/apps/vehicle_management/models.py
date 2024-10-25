from django.db import models
from IDBOOKAPI.basic_resources import VEHICLE_TYPE
from django.core.validators import (EmailValidator, RegexValidator)

# Create your models here.

class VehicleDetail(models.Model):
    vehicle_type = models.CharField(
        max_length=25, choices=VEHICLE_TYPE,
        default='CAR', help_text="vehicle type.")

    vehicle_no = models.CharField(max_length=50, unique=True, db_index=True)
    driver_name = models.CharField(max_length=50)
    contact_email = models.EmailField(
        validators=[EmailValidator], null=True, blank=True,
        help_text="Email address of the vehicle driver.")
    contact_number = models.CharField(
        max_length=10, validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message='Enter a valid phone number')],
        help_text="Mobile number of the vehicle driver (10 digits only).")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.vehicle_no
