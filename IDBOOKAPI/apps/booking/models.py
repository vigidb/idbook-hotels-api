from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db import models
from decimal import Decimal
from django.urls import reverse
from django.db.models.signals import post_save, pre_save

from apps.coupons.models import Coupon
from apps.authentication.models import User
from apps.hotels.models import Property, Room
from apps.customer.models import Customer
from apps.holiday_package.models import TourPackage
from apps.vehicle_management.models import VehicleDetail
from apps.org_resources.models import CompanyDetail
from apps.org_managements.models import BusinessDetail

from IDBOOKAPI.basic_resources import (
    BOOKING_STATUS_CHOICES, TIME_SLOTS,
    ROOM_CHOICES, BOOKING_TYPE, VEHICLE_TYPE,
    FLIGHT_TRIP, FLIGHT_CLASS, GST_TYPE, MATH_COMPARE_SYMBOLS, TRANSACTION_FOR,
    STATUS_CHOICES, PAYMENT_MODES)

from IDBOOKAPI.basic_resources import(
    PAYMENT_TYPE, PAYMENT_MEDIUM, REFERENCE_CHOICES)


# class BookingManager(models.Manager):
#     def new_or_get(self, request):
#         user = request.user
#         guest_email_id = request.session.get('guest_email_id')
#         created = False
#         obj = None
#         if user.is_authenticated:
#             'logged in user checkout; remember payment stuff'
#             obj, created = self.model.objects.get_or_create(
#                             user=user, email=user.email)
#         else:
#             pass
#         return obj, created

# confirmed_room_details = [{"room_id": 2, "price": 2400, "no_of_rooms": 2, "tax_in_percent": 12, "tax_amount":1200 }]


def default_confirmed_room_json():
    confirmed_room_json = [{"room_id": 0, "room_type":"", "price": "", "no_of_rooms": 0,
                      "tax_in_percent": 0, "tax_amount": 0, "total_tax_amount": 0,
                      "no_of_days": 0, "total_room_amount":0, "final_room_total": 0,
                      "booking_slot":0}]
    return confirmed_room_json


class HotelBooking(models.Model):
    enquired_property = models.CharField(max_length=255, null=True, blank=True)
    confirmed_property = models.ForeignKey(Property, on_delete=models.DO_NOTHING,
                                           null=True, blank=True,
                                           verbose_name="booking_property")
    room = models.ForeignKey(Room, on_delete=models.DO_NOTHING,
                             null=True, blank=True,
                             verbose_name="booking_room")
    booking_slot = models.CharField(max_length=25, choices=TIME_SLOTS,
                                    default='24 Hrs', help_text="booking type.")
    
    room_type = models.CharField(max_length=25, choices=ROOM_CHOICES,
                                 default='DELUXE', help_text="booked room type.")
    checkin_time = models.DateTimeField(blank=True, null=True,
                                        help_text="Check-in time for the property.")
    checkout_time = models.DateTimeField(blank=True, null=True,
                                         help_text="Check-out time for the property.")
    bed_count = models.PositiveIntegerField(default=1, help_text="bed count")

    requested_room_no = models.PositiveIntegerField(default=1, help_text="Requested room count")
    confirmed_room_details = models.JSONField(null=True, default=default_confirmed_room_json)
    confirmed_checkin_time = models.DateTimeField(
        blank=True, null=True, help_text="Confirmed Check-in time for the property.")
    confirmed_checkout_time = models.DateTimeField(
        blank=True, null=True, help_text="Confirmed Check-out time for the property.")
    cancel_policy = models.JSONField(null=True, blank=True, 
                                    help_text="Sorted cancellation policies for the property")
    cancellation_details = models.JSONField(null=True, blank=True, 
                                              help_text="Applied cancellation policy for this booking")
##    room_subtotal = models.DecimalField(
##        max_digits=10, decimal_places=2, default=0.0, help_text="Price for stay in the room.")
##    service_tax =  models.DecimalField(
##        max_digits=10, decimal_places=2, default=0.0, help_text="Service tax for the room.")
    

class HolidayPackageBooking(models.Model):
    no_days = models.PositiveIntegerField(default=0, help_text="planned days")
    available_start_date = models.DateTimeField(null=True, blank=True) 
    enquired_holiday_package = models.CharField(max_length=255, null=True, blank=True)
    confirmed_holiday_package = models.ForeignKey(TourPackage, on_delete=models.DO_NOTHING,
                                                  null=True, blank=True, verbose_name="holiday_package")
##    holidaypack_subtotal = models.DecimalField(
##        max_digits=10, decimal_places=2, default=0.0, help_text="Holiday Package Price")
##    service_tax =  models.DecimalField(
##        max_digits=10, decimal_places=2, default=0.0, help_text="Service tax for the Holiday package.")
    


class VehicleBooking(models.Model):
    pickup_addr = models.CharField(max_length=255, null=True, blank=True)
    dropoff_addr = models.CharField(max_length=255, null=True, blank=True)
    pickup_time = models.DateTimeField(blank=True, null=True, help_text="Pickup date and time")
    vehicle_type = models.CharField(max_length=25, choices=VEHICLE_TYPE,
                                    default='CAR', help_text="vehicle type.")
    
    confirmed_vehicle = models.ForeignKey(
        VehicleDetail, on_delete=models.DO_NOTHING,
        null=True, blank=True, verbose_name="confirmed_vehicle_booking")
##    vehicle_subtotal = models.DecimalField(
##        max_digits=10, decimal_places=2, default=0.0, help_text="Vehicle Rental Price.")
##    service_tax =  models.DecimalField(
##        max_digits=10, decimal_places=2, default=0.0, help_text="Service tax for the vehicle rental.")


    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name_plural = 'VehicleBookings'
    

class FlightBooking(models.Model):
    flight_no = models.CharField(max_length=50, default='', blank=True)
    flight_trip = models.CharField(max_length=25, choices=FLIGHT_TRIP,
                                   default='ROUND', help_text="flight trip (one-way or round).")
    flight_class  = models.CharField(max_length=25, choices=FLIGHT_CLASS,
                                   default='ECONOMY', help_text="flight class")
    departure_date = models.DateTimeField(null=True, blank=True, help_text="Departure Date")
    arrival_date = models.DateTimeField(null=True, blank=True, help_text="Arrival Date")
    return_date = models.DateTimeField(blank=True, null=True, help_text="Return Date")
    return_arrival_date = models.DateTimeField(blank=True, null=True, help_text="Return Date")
    
    flying_from = models.CharField(max_length=255, null=True, blank=True)
    flying_to = models.CharField(max_length=255, null=True, blank=True)
    return_from = models.CharField(max_length=255, null=True, blank=True)
    return_to = models.CharField(max_length=255, null=True, blank=True)
##    flight_subtotal = models.DecimalField(
##        max_digits=10, decimal_places=2, default=0.0, help_text="Flight Ticket Price.")
##    service_tax =  models.DecimalField(
##        max_digits=10, decimal_places=2, default=0.0, help_text="Service tax for flight ticket.")
    flight_ticket = models.FileField(upload_to='booking/flight/', blank=True, null=True)
    
    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name_plural = 'FlightBookings'
    


class Booking(models.Model):

    user = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                             null=True, blank=True,
                             verbose_name="booking_user")
    company = models.ForeignKey(CompanyDetail, on_delete=models.DO_NOTHING,
                                null=True)
    reference_code = models.CharField(max_length=500, null=True, blank=True)
    confirmation_code = models.CharField(max_length=500, null=True, blank=True)
    invoice_id = models.CharField(max_length=500, null=True, blank=True)

    booking_type = models.CharField(max_length=25, choices=BOOKING_TYPE,
                                    default='HOTEL', help_text="booking type.")
    hotel_booking = models.ForeignKey(HotelBooking, on_delete=models.DO_NOTHING,
                                      null=True, blank=True,
                                      verbose_name="hotel_booking")
    holiday_package_booking = models.ForeignKey(HolidayPackageBooking, on_delete=models.DO_NOTHING,
                                                null=True, blank=True,
                                                verbose_name="hotel_package_booking")
    vehicle_booking = models.ForeignKey(VehicleBooking, on_delete=models.DO_NOTHING,
                                        null=True, blank=True, verbose_name="vehicle_booking")
    flight_booking = models.ForeignKey(FlightBooking, on_delete=models.DO_NOTHING,
                                        null=True, blank=True, verbose_name="flight_booking")
    

    adult_count = models.PositiveSmallIntegerField(default=1, help_text="adults count")
    child_count = models.PositiveSmallIntegerField(default=0, help_text="children count")
    child_age_list = models.JSONField(null=True, default=list)
    infant_count = models.PositiveSmallIntegerField(default=0, help_text="infant count")

    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL,
                               null=True, blank=True,
                               verbose_name="booking_coupon")

    # deal_price = models.DecimalField(default=0, decimal_places=6)
    coupon_code = models.CharField(max_length=20, blank=True, default='')
    discount = models.DecimalField(default=0, max_digits=15, decimal_places=6)
    pro_member_discount_percent = models.PositiveSmallIntegerField(default=0, help_text="Discount percent for pro member")
    pro_member_discount_value = models.PositiveSmallIntegerField(default=0, help_text="Discount value")

    subtotal = models.DecimalField(default=0.0, max_digits=20, decimal_places=6, help_text="Price for the booking")
    gst_percentage = models.DecimalField(default=0.0, max_digits=20, decimal_places=6, help_text="GST % for the booking")
    gst_amount = models.DecimalField(default=0.0, max_digits=20, decimal_places=6, help_text="GST amount for the booking")
    gst_type = models.CharField(max_length=25, choices=GST_TYPE, default='', blank=True, help_text="GST Type")
    service_tax =  models.DecimalField(default=0.0, max_digits=20, decimal_places=6,
                                       help_text="Service tax for the booking")
    
    final_amount = models.DecimalField(default=0, max_digits=20, decimal_places=6,
                                       help_text="Final amount after considering gst, discount")
    total_payment_made = models.DecimalField(
        max_digits=20, decimal_places=6, default=0.0, help_text="Total Payment made")
    
    status = models.CharField(max_length=100, choices=BOOKING_STATUS_CHOICES, default="pending")
    on_hold_end_time = models.DateTimeField(null=True)
    
    description = models.TextField(default='', blank=True)
    additional_notes = models.TextField(default='', blank=True)

    active = models.BooleanField(default=True)
    is_reviewed = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_checkin = models.BooleanField(default=False, help_text="Check_in status")
    is_checkout = models.BooleanField(default=False, help_text="Check_out status")

    # objects = BookingManager()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cached_status = self.status

class HolidayPackageHotelDetail(models.Model):
    hotel_booking = models.ForeignKey(HotelBooking, on_delete=models.DO_NOTHING,
                                 null=True, blank=True,
                                 verbose_name="hotel_booking")
    holiday_package_booking = models.ForeignKey(HolidayPackageBooking, on_delete=models.DO_NOTHING,
                                 null=True, blank=True,
                                 verbose_name="holiday_package_booking")

class Invoice(models.Model):

    logo = models.CharField(max_length=255, default='', blank=True)
    header = models.CharField(max_length=255, default='', blank=True)
    footer = models.CharField(max_length=255, default='', blank=True)
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True, default='')
    invoice_date = models.DateField()
    due_date = models.DateField(null=True)
    notes = models.CharField(max_length=255, default='', blank=True)
    invoice_pdf = models.FileField(upload_to='booking/invoices/', blank=True, null=True)

    billed_by = models.ForeignKey(BusinessDetail, on_delete=models.CASCADE, related_name='invoices_billed_by')
    billed_by_details = models.JSONField(default=dict, null=True)

    # billed_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices_billed_to')
    billed_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices_billed_to', null=True, blank=True)

    billed_to_details = models.JSONField(default=dict, null=True)

    supply_details = models.JSONField(default=dict, null=True)
    items = models.JSONField(default=list, null=True)

    GST = models.PositiveIntegerField(default=0)
    GST_type = models.CharField(max_length=20, default='CGST/SGST', blank=True)
    total = models.PositiveIntegerField(default=0)
    total_amount = models.PositiveIntegerField(default=0)
    total_tax = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    next_schedule_date = models.DateField(null=True)
    tags = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=20, choices=REFERENCE_CHOICES, default='Other')
    discount = models.DecimalField(default=0, max_digits=15, decimal_places=6)
    created_by = models.CharField(max_length=50, default='', blank=True)
    updated_by = models.CharField(max_length=50, default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

class BookingPaymentDetail(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='booking_payment')
    merchant_transaction_id = models.CharField(max_length=150, unique=True)
    transaction_id = models.CharField(max_length=150, blank=True, default='')
    code = models.CharField(max_length=50, blank=True, default='')
    message = models.CharField(max_length=150, blank=True, default='')
    payment_type = models.CharField(max_length=50, choices=PAYMENT_TYPE, null=True)
    payment_medium = models.CharField(max_length=50, choices=PAYMENT_MEDIUM, null=True)
    amount = models.DecimalField(null=True, max_digits=20, decimal_places=6)
    is_transaction_success = models.BooleanField(default=False)
    transaction_for = models.CharField(max_length=30, choices=TRANSACTION_FOR, default="others")
    transaction_details = models.JSONField(null=True, default=dict)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='Other')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, related_name='payment_history')
    reference = models.CharField(max_length=20, choices=REFERENCE_CHOICES, default='Other')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
class BookingMetaInfo(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='meta_info')
    booking_created_date = models.DateTimeField(auto_now_add=True)
    booking_confirmed_date = models.DateTimeField(null=True, blank=True)
    booking_cancelled_date = models.DateTimeField(null=True, blank=True)
    booking_completed_date = models.DateTimeField(null=True, blank=True)
    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Meta Info for Booking {self.booking_id}"

    class Meta:
        verbose_name = 'Booking Meta Info'
        verbose_name_plural = 'Booking Meta Infos'


class BookingCommission(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='commission_info')
    commission = models.DecimalField(max_digits=20, decimal_places=6)
    commission_type = models.CharField(max_length=20)
    tax_percentage = models.DecimalField(max_digits=20, decimal_places=6)
    tax_amount = models.DecimalField(max_digits=20, decimal_places=6)
    com_amnt = models.DecimalField(max_digits=20, decimal_places=6)
    com_amnt_withtax = models.DecimalField(max_digits=20, decimal_places=6)
    tcs = models.DecimalField(default=0.0, max_digits=20, decimal_places=6)
    tds = models.DecimalField(default=0.0, max_digits=20, decimal_places=6)
    hotelier_amount = models.DecimalField(default=0.0, max_digits=20, decimal_places=6)
    hotelier_amount_with_tax = models.DecimalField(default=0.0, max_digits=20, decimal_places=6)
    

class AppliedCoupon(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='coupon_applied')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='booking_applied_coupon')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    def __str__(self):
        return f"{self.coupon.code} applied to {self.booking}"

    
class TaxRule(models.Model):
    booking_type = models.CharField(max_length=25, choices=BOOKING_TYPE,
                                    default='HOTEL', help_text="booking type.")
    math_compare_symbol = models.CharField(max_length=50, choices=MATH_COMPARE_SYMBOLS,
                                    default='EQUALS', help_text="for comparison")
    tax_rate_in_percent = models.DecimalField(default=0, max_digits=6, decimal_places=2,
                                       help_text="gst rate in percent")
    amount1 = models.PositiveIntegerField()
    amount2 = models.PositiveIntegerField(null=True)
    created = models.DateTimeField(auto_now_add=True, null=True)
    updated = models.DateTimeField(auto_now=True, null=True)

def default_property_review_json():
    property_review_json = {"check_in_rating":0, "food_rating":0, "cleanliness_rating":0,
                            "comfort_rating":0, "hotel_staff_rating":0 ,
                            "facilities_rating":0, "body":""}
    return property_review_json

def default_agency_review_json():
    agency_review_json = {"booking_experience_rating":0, "cancellation_experience_rating": 0,
                          "search_property_experience_rating":0, "body":""}

class Review(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, null=True,
                                 related_name='property_review',
                                 help_text="Select the property for which this review is submitted.")
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, related_name='booking_review')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='user_review')
##    name = models.CharField(max_length=80, help_text="Name of the person submitting the review.")
##    email = models.EmailField(help_text="Email of the person submitting the review.")
    
##    body = models.TextField(help_text="Body of the review text.")

##    check_in_rating = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for check-in experience.")
##    breakfast = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for breakfast quality.")
##    cleanliness = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for cleanliness.")
##    comfort = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for comfort.")
##    hotel_staff = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for hotel staff service.")
##    facilities = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for facilities provided.")
    property_review = models.JSONField(default=default_property_review_json)
    overall_rating = models.DecimalField(max_digits=3, decimal_places=2, help_text="Overall rating for the booked service.")

    agency_review = models.JSONField(null=True, default=default_agency_review_json)
    overall_agency_rating = models.DecimalField(max_digits=3, decimal_places=2,
                                                null=True, help_text="Overall rating for the agency.")

    created = models.DateTimeField(auto_now_add=True, help_text="Date and time when the review was created.")
    updated = models.DateTimeField(auto_now=True, help_text="Date and time when the review was last updated.")
    active = models.BooleanField(default=True, help_text="Whether the review is active.")

    class Meta:
        ordering = ('created',)

##    def __str__(self):
##        return 'Review by {} on {}'.format(self.name, self.property.name)

    

    # def __str__(self):
    #     if self.full_name:
    #         return str(self.full_name)
    #     if self.email:
    #         return str(self.email)
    #     return str(self.first_name,self.email)
    #
    # # def get_total_cost(self):
    # #     total_cost = sum(item.get_cost() for item in self.items.all())
    # #     return total_cost - total_cost * (self.discount / Decimal('100'))
    #
    # def get_short_address(self):
    #     for_name = self.full_name
    #     if self.first_name:
    #         for_name = "{} | {},".format( self.first_name, for_name)
    #     return "{for_name} {line1}, {city}".format(
    #             for_name = for_name or "",
    #             line1 = self.street_address,
    #             city = self.city
    #         )
    #
    # def get_address(self):
    #     return "{for_name}\n{line1}\n{city}\n{state}, {postal}\n{country}".format(
    #             for_name = self.name or "",
    #             line1 = self.street_address,
    #             city = self.city,
    #             state = self.state,
    #             postal= self.postal_code,
    #             country = self.country
    #         )
    #
    # def charge(self, order_obj, card=None):
    #     return Charge.objects.do(self, order_obj, card)
    #
    # def get_cards(self):
    #     return self.card_set.all()
    #
    # def get_payment_method_url(self):
    #     return reverse('booking-payment-method')
    #
    # @property
    # def has_card(self):  # instance.has_card
    #     card_qs = self.get_cards()
    #     return card_qs.exists()  # True or False
    #
    # @property
    # def default_card(self):
    #     default_cards = self.get_cards().filter(active=True, default=True)
    #     if default_cards.exists():
    #         return default_cards.first()
    #     return None
    #
    # def set_cards_inactive(self):
    #     cards_qs = self.get_cards()
    #     cards_qs.update(active=False)
    #     return cards_qs.filter(active=True).count()

#
# def booking_created_receiver(sender, instance, *args, **kwargs):
#     if not instance.customer_id and instance.email:
#         print("ACTUAL API REQUEST Send to stripe/braintree")
#         customer = stripe.Customer.create(
#             email=instance.email
#         )
#         print(customer)
#         instance.customer_id = customer.id
#
#
# pre_save.connect(booking_created_receiver, sender=Booking)

#
# def user_created_receiver(sender, instance, created, *args, **kwargs):
#     if created and instance.email:
#         Booking.objects.get_or_create(user=instance, email=instance.email)
#
#
# post_save.connect(user_created_receiver, sender=User)

#
# class CardManager(models.Manager):
#     def all(self, *args, **kwargs):  # ModelKlass.objects.all() --> ModelKlass.objects.filter(active=True)
#         return self.get_queryset().filter(active=True)
#
#     def add_new(self, booking, token):
#         if token:
#             customer = stripe.Customer.retrieve(booking.customer_id)
#             stripe_card_response = customer.sources.create(source=token)
#             new_card = self.model(
#                 booking=booking,
#                 stripe_id=stripe_card_response.id,
#                 brand=stripe_card_response.brand,
#                 country=stripe_card_response.country,
#                 exp_month=stripe_card_response.exp_month,
#                 exp_year=stripe_card_response.exp_year,
#                 last4=stripe_card_response.last4
#             )
#             new_card.save()
#             return new_card
#         return None
#
#
# class Card(models.Model):
#     booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.CASCADE)
#     stripe_id = models.CharField(max_length=120)
#     brand = models.CharField(max_length=120, null=True, blank=True)
#     country = models.CharField(max_length=20, null=True, blank=True)
#     exp_month = models.IntegerField(null=True, blank=True)
#     exp_year = models.IntegerField(null=True, blank=True)
#     last4 = models.CharField(max_length=4, null=True, blank=True)
#     default = models.BooleanField(default=True)
#     active = models.BooleanField(default=True)
#     timestamp = models.DateTimeField(auto_now_add=True)
#
#     objects = CardManager()
#
#     def __str__(self):
#         return "{} {}".format(self.brand, self.last4)
#
#
# def new_card_post_save_receiver(sender, instance, created, *args, **kwargs):
#     if instance.default:
#         booking = instance.booking
#         qs = Card.objects.filter(booking=booking).exclude(pk=instance.pk)
#         qs.update(default=False)
#
#
# post_save.connect(new_card_post_save_receiver, sender=Card)


# stripe.Charge.create(
#   amount = int(order_obj.total * 100),
#   currency = "usd",
#   customer =  BillingProfile.objects.filter(email='hello@teamcfe.com').first().stripe_id,
#   source = Card.objects.filter(booking__email='hello@teamcfe.com').first().stripe_id, # obtained with Stripe.js
#   description="Charge for elijah.martin@example.com"
# )
#
# class ChargeManager(models.Manager):
#     def do(self, booking, order_obj, card=None):  # Charge.objects.do()
#         card_obj = card
#         if card_obj is None:
#             cards = booking.card_set.filter(default=True)  # card_obj.booking
#             if cards.exists():
#                 card_obj = cards.first()
#         if card_obj is None:
#             return False, "No cards available"
#         c = stripe.Charge.create(
#             amount=int(order_obj.total * 100),  # 39.19 --> 3919
#             currency="usd",
#             customer=booking.customer_id,
#             source=card_obj.stripe_id,
#             metadata={"order_id": order_obj.order_id},
#         )
#         new_charge_obj = self.model(
#             booking=booking,
#             stripe_id=c.id,
#             paid=c.paid,
#             refunded=c.refunded,
#             outcome=c.outcome,
#             outcome_type=c.outcome['type'],
#             seller_message=c.outcome.get('seller_message'),
#             risk_level=c.outcome.get('risk_level'),
#         )
#         new_charge_obj.save()
#         return new_charge_obj.paid, new_charge_obj.seller_message
#
#
# class Charge(models.Model):
#     booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.CASCADE)
#     stripe_id = models.CharField(max_length=120)
#     paid = models.BooleanField(default=False)
#     refunded = models.BooleanField(default=False)
#     outcome = models.TextField(null=True, blank=True)
#     outcome_type = models.CharField(max_length=120, null=True, blank=True)
#     seller_message = models.CharField(max_length=120, null=True, blank=True)
#     risk_level = models.CharField(max_length=120, null=True, blank=True)
#
#     objects = ChargeManager()
#



# class BookingItem(models.Model):
#     booking         = models.ForeignKey(Booking, related_name='booking item', on_delete=models.CASCADE)
#     hotel           = models.ForeignKey(Hotel, related_name='booked_hotels', null=True,blank=True, on_delete=models.CASCADE)
#     room_type       = models.CharField(max_length=200,default=None)
#     booked_rooms    = models.IntegerField(default=1)
#     no_of_persons   = models.IntegerField(default=1)
#     no_of_child     = models.IntegerField(default=0)
#     start_date      = models.DateTimeField(name='start date',auto_now=False,default=None)
#     end_date        = models.DateTimeField(name='end date',auto_now=False,default=None)
#     time_slot       = models.IntegerField(null=True,blank=True)
#     price           = models.DecimalField(max_digits=10, decimal_places=2)
#
#     def __str__(self):
#         return '{}'.format(self.id)
#
#     def get_cost(self):
#         return self.price * self.no_of_persons
