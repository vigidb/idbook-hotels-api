from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import (EmailValidator, RegexValidator)
from apps.org_resources.models import Amenity, RoomType, Occupancy
from IDBOOKAPI.basic_resources import INCLUSION_EXCLUSION_CHOICES, TOUR_DURATION_CHOICES

User = get_user_model()


class TourPackage(models.Model):
    trip_id = models.CharField(max_length=10, blank=True, db_index=True)
    trip_name = models.CharField(max_length=50, blank=True)
    # short_code = models.CharField(max_length=10, blank=True)
    customer_fullname = models.CharField(max_length=50)
    tour_duration = models.CharField(max_length=50, choices=TOUR_DURATION_CHOICES, default=1)
    date_of_journey = models.DateField()
    adults = models.PositiveSmallIntegerField(default=1)
    tour_start_city = models.CharField(max_length=50)
    total_booking_amount = models.FloatField(default=0)
    advance_amount_to_pay_for_the_trip_confirmation = models.CharField(max_length=50)
    payment_link = models.URLField(default='', blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.trip_id


class Accommodation(models.Model):
    hotel_name = models.CharField(max_length=50, blank=True)
    no_of_room = models.PositiveSmallIntegerField(default=1)
    tour = models.ForeignKey(TourPackage, on_delete=models.DO_NOTHING, related_name='tour_accommodation')
    room_type = models.ForeignKey(RoomType, on_delete=models.DO_NOTHING, related_name='room_type')
    occupancy = models.ForeignKey(Occupancy, on_delete=models.DO_NOTHING, related_name='occupancy_detail')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)


class Executive(models.Model):
    email = models.EmailField(db_index=True, validators=[EmailValidator], unique=True)
    mobile_number = models.CharField(max_length=10, db_index=True, unique=True,
                                     validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                                                message='Enter a valid phone number')],
                                     )
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30, null=True, blank=True, )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)


class InclusionExclusion(models.Model):
    body = models.TextField()
    status = models.CharField(max_length=50, choices=INCLUSION_EXCLUSION_CHOICES, default='INCLUSION')
    tour = models.ForeignKey(TourPackage, on_delete=models.DO_NOTHING, related_name='tour_inclusion_and_exclusion')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tour', 'status',)


class Vehicle(models.Model):
    vehicle_type = models.CharField(max_length=50)
    tour = models.ForeignKey(TourPackage, on_delete=models.DO_NOTHING, related_name='tour_vehicle')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tour', 'vehicle_type',)


class DailyPlan(models.Model):
    title = models.CharField(max_length=10)
    plan_date = models.DateField()
    stay = models.CharField(max_length=50)
    check_in = models.DateTimeField(auto_now_add=False)
    check_out = models.DateTimeField(auto_now_add=False)
    detailed_plan = models.TextField()
    tour = models.ForeignKey(TourPackage, on_delete=models.DO_NOTHING, related_name='tour_daily_plan')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('tour', 'title',)


class TourBankDetail(models.Model):
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=15, blank=True, null=True)
    repeat_account_number = models.CharField(max_length=15, blank=True, null=True)
    ifsc = models.CharField(max_length=15, blank=True, null=True)
    paytm_number = models.CharField(max_length=10, blank=True, null=True)
    google_pay_number = models.CharField(max_length=10, blank=True, null=True)
    phonepe_number = models.CharField(max_length=10, blank=True, null=True)
    upi = models.CharField(max_length=50, blank=True, null=True)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.account_holder_name)


class CustomerTourEnquiry(models.Model):
    full_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(db_index=True, validators=[EmailValidator], unique=True)
    mobile_number = models.CharField(max_length=10, db_index=True, unique=True,
                                     validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                                                message='Enter a valid phone number')],
                                     )

    tour_destination = models.CharField(max_length=100, blank=True, null=True)
    tour_start_date = models.DateField()
    tour_end_date = models.DateField()
    tour_duration = models.CharField(max_length=50, help_text="enter duration like 4N/5D")
    date_of_journey = models.DateField()
    adults = models.PositiveSmallIntegerField(default=1)
    children = models.PositiveSmallIntegerField(default=0)
    tour_start_city = models.CharField(max_length=50)
    flight_required = models.BooleanField(default=False)
    private_transfer = models.BooleanField(default=False)

    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{} - {}'.format(self.full_name, self.tour_destination)

