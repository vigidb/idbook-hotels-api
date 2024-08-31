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
from IDBOOKAPI.basic_resources import BOOKING_STATUS_CHOICES, TIME_SLOTS, ROOM_CHOICES


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


class Booking(models.Model):
    property = models.ForeignKey(Property, on_delete=models.DO_NOTHING, verbose_name="booking_property")
    room = models.ForeignKey(Room, on_delete=models.DO_NOTHING, verbose_name="booking_room")
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, verbose_name="booking_user")
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, verbose_name="booking_coupon")

    booking_type = models.CharField(max_length=25, choices=TIME_SLOTS, default='24 HOURS', help_text="booking type.")
    room_type = models.CharField(max_length=25, choices=ROOM_CHOICES, default='DELUXE', help_text="booked room type.")
    checkin_time = models.DateField(auto_now=False, auto_now_add=False, help_text="Check-in time for the property.")
    checkout_time = models.DateField(auto_now=False, auto_now_add=False, help_text="Check-out time for the property.")
    bed_count = models.PositiveIntegerField(default=1, help_text="bed count")
    person_capacity = models.PositiveSmallIntegerField(default=1, help_text="adults count")
    child_capacity = models.PositiveSmallIntegerField(default=0, help_text="children count")

    deal_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=100, choices=BOOKING_STATUS_CHOICES, default="pending")

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    # objects = BookingManager()


class AppliedCoupon(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='coupon_applied')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='booking_applied_coupon')
    discount_amount = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])

    def __str__(self):
        return f"{self.coupon.code} applied to {self.booking}"

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
