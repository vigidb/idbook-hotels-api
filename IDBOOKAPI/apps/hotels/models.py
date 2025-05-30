from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit

from apps.org_resources.models import UploadedMedia #, Amenity
from apps.authentication.models import User
from apps.org_resources.models import Address

from IDBOOKAPI.utils import get_default_time, default_address_json
from IDBOOKAPI.basic_resources import (
    SERVICE_CATEGORY_TYPE_CHOICES, IMAGE_TYPE_CHOICES, ROOM_CHOICES,
    ROOM_VIEW_CHOICES, BED_TYPE_CHOICES, ROOM_MEASUREMENT, HOTEL_STATUS,
    PROPERTY_TYPE, RENTAL_FORM, MEAL_OPTIONS, EXTRA_BED_TYPE,
    DISCOUNT_TYPE
)
from django.core.validators import EmailValidator, RegexValidator

from apps.hotels.utils.hotel_policies_utils import default_hotel_policy_json


##class PropertyQuerySet(models.query.QuerySet):
##    def active(self):
##        return self.filter(active=True)
##
##    def featured(self):
##        return self.filter(featured=True, active=True)
##
##    def search(self, query):
##        lookups = (
##            Q(name__icontains=query) |
##            Q(description__icontains=query) |
##            Q(starting_price__icontains=query) |
##            Q(city_name__icontains=query)
##        )
##
##        return self.filter(lookups).distinct()
##
##
##class PropertyManager(models.Manager):
##    def get_queryset(self):
##        return PropertyQuerySet(self.model, using=self._db)
##
##    def all(self):
##        return self.get_queryset().active()
##
##    def featured(self):
##        return self.get_queryset().featured()
##
##    def get_by_id(self, id, slug):
##        qs = self.get_queryset().filter(id=id, slug=slug)
##        return qs.first()
##
##    def search(self, query):
##        return self.get_queryset().active().search(query)

class HotelAmenityCategory(models.Model):
    title = models.CharField(max_length=200, unique=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = 'HotelAmenity_Categories'


class HotelAmenity(models.Model):
    amenity_category = models.ForeignKey(HotelAmenityCategory, on_delete=models.DO_NOTHING,
                                         related_name='hotel_amenity')
    title = models.CharField(max_length=200, unique=True)
    detail =  models.JSONField(null=True, default=dict, help_text='Hotel Amenity') 
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = 'HotelAmenities'

class RoomAmenityCategory(models.Model):
    title = models.CharField(max_length=200, unique=True)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = 'RoomAmenity_Categories'

##{"Mandatory":{"Hairdryer": {"No":[], "Yes":[]},
##              "Hot & Cold Water":{"No":[], "Yes":[]},
##              "Toileteries":{"No":[], "Yes":[['Premium', 'Moisturiser','Shampoo']]}
##              "Air Conditioning": {"No":[], "Yes":[['Centralized', 'Room Controlled','Window AC']], ['All-Weather(Hot & Cold)']}
##              }
##}
##
##{"Mandatory": {"hairdryer" {"No":{}, "Yes":{["Room controlled", "Centralized"], ["All Weather(Hot & Cold)"]}],
## "selectbox": ["Room controlled", "Centralized"],
##               "selectbox-1": ["All Weather(Hot & Cold)"]}}

# [{"type":"choice", "No":[], "Yes":[["Centralized", "Room Controlled","Window AC"], ["All-Weather(Hot & Cold)"]]}]

class RoomAmenity(models.Model):
    room_amenity_category = models.ForeignKey(RoomAmenityCategory, on_delete=models.DO_NOTHING,
                                         related_name='room_amenity')
    title = models.CharField(max_length=200, unique=True)
    detail =  models.JSONField(null=True, default=dict, help_text='room amenity') 
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = 'RoomAmenities'

def default_property_additional_fields_json():
    additional_fields_json = {"comment_count":0, "view_count":0, "no_confirmed_booking":0}
    return additional_fields_json

def default_starting_price_json():
    starting_price_json = {'starting_4hr_price': 0, 'starting_8hr_price': 0,
                           'starting_12hr_price': 0, 'starting_base_price': 0}
    return starting_price_json

class Property(models.Model):
    
    amenity_details =  models.JSONField(null=True, default=dict)
    
    managed_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='property_manager',
                                   help_text="Select a user as the property manager.")
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='property_added_by')
    service_category = models.CharField(max_length=255, choices=SERVICE_CATEGORY_TYPE_CHOICES, default='', help_text="Select the service category for this property.")
    custom_id = models.CharField(max_length=15, blank=True, db_index=True, null=True, help_text="Custom ID for the property.")

    name = models.CharField(max_length=70, db_index=True, help_text="Name of the property.")
    title = models.CharField(max_length=200, blank=True, default='', help_text="Display name of the property.")
    slug = models.SlugField(max_length=200, unique=True, db_index=True, blank=True, help_text="Slug for the property URL.")
    property_type = models.CharField(max_length=50, choices=PROPERTY_TYPE, default='Hotel')
    rental_form = models.CharField(max_length=50, choices=RENTAL_FORM, default='Private room')

    checkin_time = models.TimeField(null=True, help_text="Check-in time for the property.")
    checkout_time = models.TimeField(null=True, help_text="Check-out time for the property.")

    address = models.JSONField(default=default_address_json) 
    area_name = models.CharField(max_length=60, blank=True, default='', help_text="Area name where the property is located.")
    city_name = models.CharField(max_length=35, blank=True, default='', help_text="City name where the property is located.")
    state = models.CharField(max_length=50, blank=True, default='', help_text="State where the property is located.")
    country = models.CharField(max_length=50, blank=True, default='', help_text="Country where the property is located.")

    email = models.EmailField(blank=True, default='', validators=[EmailValidator])
    email_list = models.JSONField(null=True, default=dict, help_text='["email 1", "email 2"]')
    phone_no = models.CharField(max_length=15, blank=True, default='',
                                validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$',
                                                           message='Enter a valid phone number')])
    phone_no_list = models.JSONField(null=True, default=dict, help_text='["phone 1", "phone 2"]')
    description = models.TextField(blank=True, default='')
    website_list = models.JSONField(null=True, default=dict, help_text='["website link 1", "website link 2"]')
    customer_care_no = models.CharField(max_length=15, blank=True, default='')
    # need to remove
    starting_price = models.DecimalField(max_digits=15, decimal_places=4, default=0.0)
    starting_price_details = models.JSONField(null=True, default=default_starting_price_json)

    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, help_text="Rating of the property.")
    total_rooms = models.PositiveIntegerField(default=1, help_text="Total number of rooms in the property.")

    chain_name = models.CharField(max_length=50, blank=True, default='')
    build_year = models.PositiveIntegerField(null=True)
    no_of_restaurant = models.PositiveIntegerField(default=0)
    no_of_kitchen = models.PositiveIntegerField(default=0)
    no_of_banquets = models.PositiveIntegerField(default=0)

    minimum_no_of_nights = models.PositiveIntegerField(default=0)
    maximum_no_of_nights = models.PositiveIntegerField(default=0)

    currency = models.CharField(max_length=50, blank=True, default='')
    vcc_currency = models.CharField(max_length=50, blank=True, default='')
    timezone = models.CharField(max_length=50, blank=True, default='')

    featured = models.BooleanField(default=False, help_text="Whether the property is featured.")
    franchise = models.BooleanField(default=False)
    policies =  models.JSONField(default=dict, help_text="check default policy data in utils")
    property_ownership = models.CharField(max_length=100, blank=True, default='')
    legal_document = models.FileField(upload_to='hotels/property/legal-document/', null=True)

    current_page = models.PositiveIntegerField(default=0, help_text="Pages completed for property in Front End")
    review_star = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, help_text="Review Rating of the property.")
    review_count = models.PositiveIntegerField(default=0, help_text="Total Reviews")
    additional_fields = models.JSONField(null=True, default=default_property_additional_fields_json,
                                         help_text='Additional Fields related to the property')
    status = models.CharField(max_length=50, choices=HOTEL_STATUS, default='In-Progress')
    is_slot_price_enabled = models.BooleanField(default=False)
    property_size = models.PositiveSmallIntegerField(default=0, help_text="Room Size")
    property_measurement_type = models.CharField(max_length=25, choices=ROOM_MEASUREMENT, default='')
    pay_at_hotel = models.BooleanField(default=True, help_text="If true, customer can pay at the hotel.")
    created = models.DateTimeField(auto_now_add=True, help_text="Date and time when the property was created.")
    updated = models.DateTimeField(auto_now=True, help_text="Date and time when the property was last updated.")
    service_agreement_pdf = models.FileField(upload_to='hotels/service_agreements/', blank=True, null=True)
    verify_token = models.CharField(max_length=255, blank=True, default='')
    is_svc_agreement_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_ip = models.CharField(max_length=220, blank=True, default='')

    # objects = models.Manager()  # The default manager.
    # published = PropertyManager()  # Our custom manager.

##    def save(self, *args, **kwargs):
##        self.slug = slugify(self.name)
##        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('-created',)
        verbose_name = 'Property'
        verbose_name_plural = 'Properties'
        index_together = (('id', 'slug'),)


def default_room_occupancy_json():
    room_occupancy_json = {"base_adults":1, "max_adults":1,
                           "max_children":1, "max_occupancy":2}
    return room_occupancy_json

def default_room_price_json():
    room_price_json = {"base_rate":0, "price_4hrs":0, "price_8hrs":0, "price_12hrs":0,
                       "extra_bed_price":0, "extra_bed_price_4hrs":0,
                       "extra_bed_price_8hrs":0, "extra_bed_price_12hrs":0,
                       "child_bed_price":[{"age_limit":[0, 4], "child_bed_price":0,
                                           "child_bed_price_4hrs":0, "child_bed_price_8hrs":0,
                                           "child_bed_price_12hrs":0},
                                          {"age_limit":[5, 12], "child_bed_price":0,
                                           "child_bed_price_4hrs":0, "child_bed_price_8hrs":0,
                                           "child_bed_price_12hrs":0}
                                          ],
                       "pet_charges":0}
    return room_price_json

class Room(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                 null=True, related_name='property_room',
                                 help_text="Select the property this room belongs to.")
    #amenities = models.ManyToManyField(Amenity, related_name='rooms_amenities', help_text="Select amenities available in this room.")
    amenity_details =  models.JSONField(null=True, default=dict)
    custom_id = models.CharField(max_length=30, blank=True, db_index=True, null=True, help_text="Custom ID for the room.")
    
    room_type = models.CharField(max_length=25, choices=ROOM_CHOICES, blank=True, default='')
    room_view = models.CharField(max_length=25, choices=ROOM_VIEW_CHOICES, blank=True, default='')
    bed_type = models.CharField(max_length=25, choices=BED_TYPE_CHOICES, blank=True, default='')
    name = models.CharField(max_length=70, blank=True, default='', help_text="Name of the property.")
    description = models.TextField(blank=True, null=True)

    room_size = models.PositiveSmallIntegerField(default=0, help_text="Room Size")
    room_measurement_type = models.CharField(max_length=25, choices=ROOM_MEASUREMENT, default='')
    no_available_rooms = models.PositiveSmallIntegerField(default=0)
    meal_options = models.CharField(max_length=100, choices=MEAL_OPTIONS, blank=True, default='')
    is_smoking_allowed = models.BooleanField(default=False)
    extra_bed_type = models.CharField(max_length=30, choices=EXTRA_BED_TYPE, blank=True, default='')
    is_extra_bed_available = models.BooleanField(default=False)

    room_occupancy = models.JSONField(default=default_room_occupancy_json)
    
##    bed_count = models.PositiveIntegerField(default=1, help_text="Number of beds in the room.")
##    person_capacity = models.PositiveSmallIntegerField(default=1, help_text="Maximum number of adults the room can accommodate.")
##    child_capacity = models.PositiveSmallIntegerField(default=0, help_text="Maximum number of children the room can accommodate.")

    room_price = models.JSONField(default=default_room_price_json)
    is_slot_price_enabled = models.BooleanField(default=False)

##    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price per night for the room.")
##    price_for_4_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price for a 4-hour stay in the room.")
##    price_for_8_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price for an 8-hour stay in the room.")
##    price_for_12_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price for a 12-hour stay in the room.")
##    price_for_24_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price for a 24-hour stay in the room.")
    discount = models.PositiveSmallIntegerField(default=0, help_text="Discount percentage for the room (maximum 90%).")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE, default='PERCENT')
    start_availability_date = models.DateField(null=True)
    end_availability_date = models.DateField(null=True)

##    availability = models.BooleanField(default=False, help_text="Whether the room is available for booking.")
    active = models.BooleanField(default=True, help_text="Whether the room is active.")
    created = models.DateTimeField(auto_now_add=True, help_text="Date and time when the room was created.")
    updated = models.DateTimeField(auto_now=True, help_text="Date and time when the room was last updated.")

    def save(self, *args, **kwargs):
        self.slug = slugify(str(self.property.name) + str(self.room_type))
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.name)

    class Meta:
        # ordering = ('-price_for_4_hours',)
        verbose_name = 'room'
        verbose_name_plural = 'rooms'
        index_together = (('id', 'room_type'),)

class PropertyGallery(models.Model):
    property = models.ForeignKey(Property, on_delete=models.SET_NULL,
                                 null=True, related_name='gallery_property')
    media = models.FileField(upload_to='hotels/property/media/', blank=True, null=True)
    caption = models.CharField(max_length=200, blank=True, default="")
    featured_image = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    

    class Meta:
        verbose_name_plural = 'PropertyGallery'

class BlockedProperty(models.Model):
    blocked_property = models.ForeignKey(Property, on_delete=models.CASCADE,
                                         related_name='blocked_property')
    blocked_room =  models.ForeignKey(Room, on_delete=models.CASCADE,
                                 null=True, related_name='blocked_room')
    no_of_blocked_rooms = models.PositiveSmallIntegerField(default=0)
    is_entire_property = models.BooleanField(default=False)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'BlockedProperty'
    
    

class RoomGallery(models.Model):
    room = models.ForeignKey(Room, on_delete=models.SET_NULL,
                             null=True, related_name='gallery_room')
    media = models.FileField(upload_to='hotels/room/media/', null=True)
    featured_image = models.BooleanField(default=False)
    caption = models.CharField(max_length=200, default="", blank=True)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    

    class Meta:
        verbose_name_plural = 'RoomGallery'

class Gallery(models.Model):
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True,
                                 related_name='gallery_added_by')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, blank=True, null=True, related_name='property_gallery', help_text="Select the property for which this gallery image belongs.")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, blank=True, null=True, related_name='room_gallery', help_text="Select the room for which this gallery image belongs.")
    media = models.ForeignKey(UploadedMedia, on_delete=models.CASCADE, blank=True, null=True, related_name='media')

    active = models.BooleanField(default=True, help_text="Whether the gallery image is active.")
    created = models.DateTimeField(auto_now_add=True, help_text="Date and time when the gallery image was created.")
    updated = models.DateTimeField(auto_now=True, help_text="Date and time when the gallery image was last updated.")

    def __str__(self):
        return str(self.property.name)

    class Meta:
        verbose_name_plural = 'Gallery'


class Rule(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, blank=True, null=True, related_name='property_rule')
    json_data = models.JSONField()

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('created',)

    def __str__(self):
        return str(self.property.name)


class Inclusion(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, blank=True, null=True,
                                 related_name='property_inclusion')
    json_data = models.JSONField()

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('created',)

    def __str__(self):
        return str(self.property.name)


class FinancialDetail(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, blank=True, null=True,
                                 related_name='property_financial_detail')
    json_data = models.JSONField()

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ('created',)

    def __str__(self):
        return str(self.property)


##class Review(models.Model):
##    property = models.ForeignKey(Property, on_delete=models.CASCADE, null=True,
##                                 related_name='property_review',
##                                 help_text="Select the property for which this review is submitted.")
##    booking =models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, related_name='booking_review')
##    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='user_review')
####    name = models.CharField(max_length=80, help_text="Name of the person submitting the review.")
####    email = models.EmailField(help_text="Email of the person submitting the review.")
##    
####    body = models.TextField(help_text="Body of the review text.")
##
####    check_in_rating = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for check-in experience.")
####    breakfast = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for breakfast quality.")
####    cleanliness = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for cleanliness.")
####    comfort = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for comfort.")
####    hotel_staff = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for hotel staff service.")
####    facilities = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for facilities provided.")
##    property_review = models.JSONField(default=default_property_review_json)
##    overall_rating = models.DecimalField(max_digits=3, decimal_places=2, help_text="Overall rating for the booked service.")
##
##    agency_review = models.JSONField(default=agency_review_json)
##    overall_agency_rating = models.DecimalField(max_digits=3, decimal_places=2, help_text="Overall rating for the agency.")
##
##    created = models.DateTimeField(auto_now_add=True, help_text="Date and time when the review was created.")
##    updated = models.DateTimeField(auto_now=True, help_text="Date and time when the review was last updated.")
##    active = models.BooleanField(default=True, help_text="Whether the review is active.")
##
##    class Meta:
##        ordering = ('created',)
##
##    def __str__(self):
##        return 'Review by {} on {}'.format(self.name, self.property.name)

class FavoriteList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True,
                             related_name='user_favorites')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, null=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

class PropertyBankDetails(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='property_bank')
    account_number = models.CharField(max_length=35)
    ifsc = models.CharField(max_length=25)
    bank_name = models.CharField(max_length=35)
    gstin = models.CharField(max_length=25, blank=True, default='')
    pan = models.CharField(max_length=25, blank=True, default='')
    tan = models.CharField(max_length=25, blank=True, default='')
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

class PolicyDetails(models.Model):
    policy_details =  models.JSONField(null=True, default=default_hotel_policy_json)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    
class PropertyLandmark(models.Model):
    property = models.ForeignKey("Property", on_delete=models.CASCADE, related_name="landmarks", null=True, blank=True)
    landmark = models.CharField(max_length=255, help_text="Name of the landmark.")
    distance = models.DecimalField(max_digits=10, decimal_places=3, help_text="Distance from the property (in meters).")
    
    def __str__(self):
        return self.landmark

class PayAtHotelSpendLimit(models.Model):
    start_limit = models.PositiveIntegerField(default=0, help_text="Start range of bookings for paying at hotel")
    end_limit = models.PositiveIntegerField(default=0, help_text="End range of bookings for paying at hotel")
    spend_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Max allowed spend for this booking range")
    cancel_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Maximum cancellation amount for this booking range")
    cancel_count = models.PositiveIntegerField(default=0, help_text="Number of cancellation for this booking range")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('created',)

class MonthlyPayAtHotelEligibility(models.Model):
    is_eligible = models.BooleanField(default=False, help_text="Is the user eligible for Pay at Hotel this month?")
    eligible_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, help_text="Eligible spend limit for this month")
    spent_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Amount spent by the user in a month")
    total_booking_count = models.PositiveIntegerField(default=0, null=True, help_text="Total bookings made by the user this month")
    cancel_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, help_text="Allowed cancel amount")
    total_cancel_count = models.PositiveIntegerField(default=0, null=True, help_text="Allowed cancel count")
    is_blacklisted = models.BooleanField(default=False, help_text="Is the user blacklisted this month?")
    updated_by = models.CharField(max_length=50, default="Automatic", help_text="Who updated this record?")
    month = models.CharField(max_length=20, blank=True, default='', help_text="Month name like January, February etc.")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='monthly_pay_at_hotel_eligibility')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'month')
        ordering = ('-created',)
