from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit

from apps.org_resources.models import Amenity, UploadedMedia
from apps.authentication.models import User
from apps.org_resources.models import Address
from IDBOOKAPI.utils import get_default_time
from IDBOOKAPI.basic_resources import (
    SERVICE_CATEGORY_TYPE_CHOICES, IMAGE_TYPE_CHOICES, ROOM_CHOICES, ROOM_VIEW_CHOICES, BED_TYPE_CHOICES
)


class PropertyQuerySet(models.query.QuerySet):
    def active(self):
        return self.filter(active=True)

    def featured(self):
        return self.filter(featured=True, active=True)

    def search(self, query):
        lookups = (
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(starting_price__icontains=query) |
            Q(city_name__icontains=query)
        )

        return self.filter(lookups).distinct()


class PropertyManager(models.Manager):
    def get_queryset(self):
        return PropertyQuerySet(self.model, using=self._db)

    def all(self):
        return self.get_queryset().active()

    def featured(self):
        return self.get_queryset().featured()

    def get_by_id(self, id, slug):
        qs = self.get_queryset().filter(id=id, slug=slug)
        return qs.first()

    def search(self, query):
        return self.get_queryset().active().search(query)


class Property(models.Model):
    amenity = models.ManyToManyField(Amenity, related_name='property_amenities', blank=True, help_text="Select amenities for this property.")
    managed_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='property_manager', help_text="Select a user as the property manager.")
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='property_added_by')
    service_category = models.CharField(max_length=255, choices=SERVICE_CATEGORY_TYPE_CHOICES, default='', help_text="Select the service category for this property.")
    address = models.TextField(blank=True, null=True) 
    custom_id = models.CharField(max_length=15, blank=True, db_index=True, null=True, help_text="Custom ID for the property.")

    name = models.CharField(max_length=70, db_index=True, help_text="Name of the property.")
    display_name = models.CharField(max_length=70, blank=True, null=True, help_text="Display ame of the property.")
    slug = models.SlugField(max_length=200, db_index=True, blank=True, null=True, help_text="Slug for the property URL.")

    checkin_time = models.TimeField(default=get_default_time, help_text="Check-in time for the property.")
    checkout_time = models.TimeField(default=get_default_time, help_text="Check-out time for the property.")

    location = models.CharField(max_length=255, blank=True, null=True, help_text="Google map URL for the property location.")
    area_name = models.CharField(max_length=60, blank=True, null=True, help_text="Area name where the property is located.")
    city_name = models.CharField(max_length=35, blank=True, null=True, help_text="City name where the property is located.")
    latitude = models.FloatField(default=0, help_text="Latitude of the property location.")
    longitude = models.FloatField(default=0, help_text="Longitude of the property location.")

    email = models.EmailField(blank=True, null=True, )
    email_list = models.TextField(blank=True, null=True)
    phone_no = models.CharField(max_length=15, blank=True, null=True)
    phone_no_list = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    website_list = models.TextField(blank=True, null=True)
    customer_care_no = models.CharField(max_length=15, blank=True, null=True)
    starting_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, help_text="Rating of the property.")
    featured_image = models.URLField(max_length=255, default='', help_text="URL of the featured image for the property.")
    total_rooms = models.PositiveIntegerField(default=1, help_text="Total number of rooms in the property.")

    chain_name = models.CharField(max_length=50, blank=True, null=True)
    build_year = models.CharField(max_length=50, blank=True, null=True)
    no_of_restaurant = models.CharField(max_length=50, blank=True, null=True)
    no_of_rooms = models.CharField(max_length=50, blank=True, null=True)
    no_of_floors = models.CharField(max_length=50, blank=True, null=True)
    currency = models.CharField(max_length=50, blank=True, null=True)
    vcc_currency = models.CharField(max_length=50, blank=True, null=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)

    checkin_24_hours = models.BooleanField(default=False, help_text="Whether 24 Hrs Check In.")
    featured = models.BooleanField(default=False, help_text="Whether the property is featured.")
    franchise = models.BooleanField(default=False)
    active = models.BooleanField(default=False, help_text="Whether the property is active.")
    created = models.DateTimeField(auto_now_add=True, help_text="Date and time when the property was created.")
    updated = models.DateTimeField(auto_now=True, help_text="Date and time when the property was last updated.")

    objects = models.Manager()  # The default manager.
    published = PropertyManager()  # Our custom manager.

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('-created',)
        verbose_name = 'Property'
        verbose_name_plural = 'Properties'
        index_together = (('id', 'slug'),)


class Room(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, blank=True, null=True, related_name='property_room', help_text="Select the property this room belongs to.")
    amenities = models.ManyToManyField(Amenity, related_name='rooms_amenities', help_text="Select amenities available in this room.")
    custom_id = models.CharField(max_length=30, blank=True, db_index=True, null=True, help_text="Custom ID for the room.")
    room_type = models.CharField(max_length=25, choices=ROOM_CHOICES, default='DELUXE')
    room_view = models.CharField(max_length=25, choices=ROOM_VIEW_CHOICES, default='')
    bed_type = models.CharField(max_length=25, choices=BED_TYPE_CHOICES, default='KING')
    description = models.TextField(blank=True, null=True)

    carpet_area = models.PositiveSmallIntegerField(default=100, help_text="Carpet area of the room in square feet.")
    bed_count = models.PositiveIntegerField(default=1, help_text="Number of beds in the room.")
    person_capacity = models.PositiveSmallIntegerField(default=1, help_text="Maximum number of adults the room can accommodate.")
    child_capacity = models.PositiveSmallIntegerField(default=0, help_text="Maximum number of children the room can accommodate.")

    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price per night for the room.")
    price_for_4_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price for a 4-hour stay in the room.")
    price_for_8_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price for an 8-hour stay in the room.")
    price_for_12_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price for a 12-hour stay in the room.")
    price_for_24_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, help_text="Price for a 24-hour stay in the room.")
    discount = models.PositiveSmallIntegerField(default=0, help_text="Discount percentage for the room (maximum 90%).")

    availability = models.BooleanField(default=False, help_text="Whether the room is available for booking.")
    active = models.BooleanField(default=True, help_text="Whether the room is active.")
    created = models.DateTimeField(auto_now_add=True, help_text="Date and time when the room was created.")
    updated = models.DateTimeField(auto_now=True, help_text="Date and time when the room was last updated.")

    def save(self, *args, **kwargs):
        self.slug = slugify(str(self.property.name) + str(self.room_type))
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.custom_id)

    class Meta:
        ordering = ('-price_for_4_hours',)
        verbose_name = 'room'
        verbose_name_plural = 'rooms'
        index_together = (('id', 'room_type'),)


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


class Review(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, blank=True, null=True, related_name='property_review', help_text="Select the property for which this review is submitted.")
    name = models.CharField(max_length=80, help_text="Name of the person submitting the review.")
    email = models.EmailField(help_text="Email of the person submitting the review.")
    body = models.TextField(help_text="Body of the review text.")

    check_in_rating = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for check-in experience.")
    breakfast = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for breakfast quality.")
    cleanliness = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for cleanliness.")
    comfort = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for comfort.")
    hotel_staff = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for hotel staff service.")
    facilities = models.DecimalField(max_digits=3, decimal_places=2, help_text="Rating for facilities provided.")
    over_all = models.DecimalField(max_digits=3, decimal_places=2, help_text="Overall rating for the property.")

    created = models.DateTimeField(auto_now_add=True, help_text="Date and time when the review was created.")
    updated = models.DateTimeField(auto_now=True, help_text="Date and time when the review was last updated.")
    active = models.BooleanField(default=True, help_text="Whether the review is active.")

    class Meta:
        ordering = ('created',)

    def __str__(self):
        return 'Review by {} on {}'.format(self.name, self.property.name)

