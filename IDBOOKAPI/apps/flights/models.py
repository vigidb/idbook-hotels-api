from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from django.contrib.auth import get_user_model

from apps.authentication.models import User
from apps.customer.models import Customer
from IDBOOKAPI.basic_resources import (
    AIRIQ_TRIP_TYPE, AIRIQ_FLIGHT_CLASS, AIRIQ_FARE_TYPE,
    FLIGHT_BOOKING_MODE, FLIGHT_BOOKING_STATUS, PASSENGER_TYPE,
    PASSENGER_TITLE, AIRLINE_CATEGORY, SEAT_TYPE, AIRIQ_PAYMENT_MODE,
    AIRIQ_RESULT_CODES, SSR_CATEGORY, BOOKING_STATUS_CHOICES, GENDER_CHOICES
)


class Airline(models.Model):
    """Master data for airlines.

    Extended to store OpenFlights airline dataset fields so that we can
    provide rich airline search/filter APIs and keep a single source of truth
    for airline metadata.
    """

    # OpenFlights identifier (column 0 in airlines.dat)
    openflights_id = models.IntegerField(
        unique=True, null=True, blank=True,
        help_text="Unique OpenFlights identifier for this airline"
    )

    # Core identification
    code = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        db_index=True,
        help_text="2-letter IATA airline code (may be blank or reused across airlines)"
    )
    name = models.CharField(max_length=200)
    alias = models.CharField(
        max_length=200,
        blank=True,
        help_text="Common alias / marketing name (eg. ANA for All Nippon Airways)"
    )
    icao_code = models.CharField(
        max_length=10,
        blank=True,
        help_text="3-letter ICAO airline code (OpenFlights may contain some longer values)"
    )
    callsign = models.CharField(
        max_length=64,
        blank=True,
        help_text="Airline callsign used in ATC communications"
    )
    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Country or territory where airline is based"
    )

    # Logical flags
    active = models.CharField(
        max_length=1,
        choices=[('Y', 'Active / recently active'), ('N', 'Defunct')],
        default='Y',
        help_text="OpenFlights active flag (Y/N). Not fully reliable."
    )
    category = models.CharField(max_length=3, choices=AIRLINE_CATEGORY, default='LCC')

    # Media / status
    logo = models.ImageField(upload_to='airlines/logos/', blank=True, null=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Internal flag to soft-disable airlines in our APIs"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flights_airline'
        verbose_name = 'Airline'
        verbose_name_plural = 'Airlines'

    def __str__(self):
        display_code = self.code or (self.icao_code or "-")
        return f"{display_code} - {self.name}"

    @property
    def logo_url(self):
        """Public URL for logo, used by serializers and clients."""
        try:
            return self.logo.url if self.logo else None
        except ValueError:
            # In case storage/backing file is missing
            return None


class Airport(models.Model):
    """Master data for airports"""
    iata_code = models.CharField(max_length=3, unique=True, help_text="3-letter IATA airport code")
    icao_code = models.CharField(max_length=4, blank=True, help_text="4-letter ICAO airport code")
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    timezone = models.CharField(max_length=50, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flights_airport'
        verbose_name = 'Airport'
        verbose_name_plural = 'Airports'

    def __str__(self):
        return f"{self.iata_code} - {self.name}, {self.city}"


class FlightRoute(models.Model):
    """Represents flight routes for inventory management"""
    origin = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='routes_as_origin')
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='routes_as_destination')
    airline = models.ForeignKey(Airline, on_delete=models.CASCADE, related_name='routes')
    flight_number = models.CharField(max_length=10, help_text="Flight number without airline code")
    
    # Route characteristics
    duration_minutes = models.PositiveIntegerField(help_text="Flight duration in minutes")
    distance_km = models.PositiveIntegerField(null=True, blank=True, help_text="Distance in kilometers")
    aircraft_type = models.CharField(max_length=50, blank=True)
    
    # Schedule
    departure_time = models.TimeField(help_text="Scheduled departure time")
    arrival_time = models.TimeField(help_text="Scheduled arrival time")
    days_of_week = models.JSONField(default=list, help_text="Days of operation [1=Monday, 7=Sunday]")
    
    # Pricing and availability
    base_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Base price in INR")
    available_classes = models.JSONField(default=list, help_text="Available classes with pricing")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flights_route'
        verbose_name = 'Flight Route'
        verbose_name_plural = 'Flight Routes'
        unique_together = ['origin', 'destination', 'airline', 'flight_number']

    def __str__(self):
        return f"{self.airline.code}{self.flight_number}: {self.origin.iata_code} → {self.destination.iata_code}"

    @property
    def full_flight_number(self):
        return f"{self.airline.code} {self.flight_number}"


class FlightInventory(models.Model):
    """Manages flight inventory for pre-booked tickets"""
    route = models.ForeignKey(FlightRoute, on_delete=models.CASCADE, related_name='inventory')
    flight_date = models.DateField(help_text="Specific date for this flight")
    departure_datetime = models.DateTimeField(help_text="Actual departure date and time")
    arrival_datetime = models.DateTimeField(help_text="Actual arrival date and time")
    
    # Inventory management
    total_seats = models.PositiveIntegerField(default=180)
    available_seats = models.PositiveIntegerField(default=180)
    booked_seats = models.PositiveIntegerField(default=0)
    
    # Class-wise inventory
    economy_total = models.PositiveIntegerField(default=150)
    economy_available = models.PositiveIntegerField(default=150)
    business_total = models.PositiveIntegerField(default=20)
    business_available = models.PositiveIntegerField(default=20)
    first_total = models.PositiveIntegerField(default=10)
    first_available = models.PositiveIntegerField(default=10)
    
    # Pricing
    economy_price = models.DecimalField(max_digits=10, decimal_places=2)
    business_price = models.DecimalField(max_digits=10, decimal_places=2)
    first_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('FULL', 'Fully Booked'),
        ('CANCELLED', 'Cancelled'),
        ('DELAYED', 'Delayed'),
    ], default='ACTIVE')
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flights_inventory'
        verbose_name = 'Flight Inventory'
        verbose_name_plural = 'Flight Inventories'
        unique_together = ['route', 'flight_date']
        ordering = ['flight_date', 'departure_datetime']

    def __str__(self):
        return f"{self.route.full_flight_number} on {self.flight_date}"

    def get_available_seats(self, flight_class='E'):
        """Get available seats for a specific class"""
        class_mapping = {
            'E': self.economy_available,
            'B': self.business_available,
            'F': self.first_available,
        }
        return class_mapping.get(flight_class, 0)

    def get_class_price(self, flight_class='E'):
        """Get price for a specific class"""
        class_mapping = {
            'E': self.economy_price,
            'B': self.business_price,
            'F': self.first_price,
        }
        return class_mapping.get(flight_class, Decimal('0.00'))


class FlightSearchSession(models.Model):
    """Stores flight search sessions for tracking and caching"""
    session_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Search parameters
    origin = models.CharField(max_length=3, help_text="Origin airport IATA code")
    destination = models.CharField(max_length=3, help_text="Destination airport IATA code")
    departure_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    trip_type = models.CharField(max_length=1, choices=AIRIQ_TRIP_TYPE, default='O')
    flight_class = models.CharField(max_length=1, choices=AIRIQ_FLIGHT_CLASS, default='E')
    adults = models.PositiveSmallIntegerField(default=1)
    children = models.PositiveSmallIntegerField(default=0)
    infants = models.PositiveSmallIntegerField(default=0)
    
    # Search results metadata
    results_count = models.PositiveIntegerField(default=0)
    search_mode = models.CharField(max_length=10, choices=FLIGHT_BOOKING_MODE, default='REALTIME')
    
    # AirIQ specific
    airiq_track_id = models.CharField(max_length=255, blank=True)
    airiq_token = models.TextField(blank=True)
    
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'flights_search_session'
        verbose_name = 'Flight Search Session'
        verbose_name_plural = 'Flight Search Sessions'
        ordering = ['-created_at']


class FlightOption(models.Model):
    """Represents a flight option returned from search (either AirIQ or inventory)"""
    search_session = models.ForeignKey(FlightSearchSession, on_delete=models.CASCADE, related_name='flight_options')
    
    # Flight identification
    airiq_flight_id = models.CharField(max_length=100, blank=True, help_text="AirIQ Flight ID")
    inventory_flight = models.ForeignKey(FlightInventory, on_delete=models.CASCADE, null=True, blank=True)
    
    # Flight details
    airline_code = models.CharField(max_length=3)
    flight_number = models.CharField(max_length=10)
    origin = models.CharField(max_length=3)
    destination = models.CharField(max_length=3)
    departure_datetime = models.DateTimeField()
    arrival_datetime = models.DateTimeField()
    
    # Flight characteristics
    flight_class = models.CharField(max_length=1, choices=AIRIQ_FLIGHT_CLASS)
    fare_basis = models.CharField(max_length=20, blank=True)
    airline_category = models.CharField(max_length=3, choices=AIRLINE_CATEGORY)
    stops = models.PositiveSmallIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField()
    aircraft_type = models.CharField(max_length=50, blank=True)
    
    # Pricing
    base_fare = models.DecimalField(max_digits=10, decimal_places=2)
    taxes = models.DecimalField(max_digits=10, decimal_places=2)
    total_fare = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Availability
    available_seats = models.PositiveIntegerField()
    
    # Baggage and policies
    baggage_info = models.JSONField(default=dict)
    fare_rules = models.JSONField(default=dict)
    
    # Booking eligibility
    is_refundable = models.BooleanField(default=False)
    can_hold = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'flights_option'
        verbose_name = 'Flight Option'
        verbose_name_plural = 'Flight Options'
        ordering = ['total_fare', 'departure_datetime']

    def __str__(self):
        return f"{self.airline_code} {self.flight_number}: {self.origin} → {self.destination} at ₹{self.total_fare}"












class AirIQApiLog(models.Model):
    """Log all AirIQ API calls for debugging and audit"""
    booking = models.ForeignKey('booking.FlightBooking', on_delete=models.CASCADE, null=True, blank=True, related_name='api_logs')
    
    # API call details
    api_endpoint = models.CharField(max_length=50)
    http_method = models.CharField(max_length=10)
    request_data = models.JSONField(default=dict)
    response_data = models.JSONField(default=dict)
    
    # Result
    result_code = models.CharField(max_length=2, choices=AIRIQ_RESULT_CODES)
    error_message = models.TextField(blank=True)
    
    # Timing
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'flights_airiq_log'
        verbose_name = 'AirIQ API Log'
        verbose_name_plural = 'AirIQ API Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.http_method} {self.api_endpoint} [{self.result_code}] - {self.created_at}"


class AirIQTokenCache(models.Model):
    """Cache AirIQ authentication tokens to avoid hitting daily limit"""
    token = models.TextField(help_text="Cached authentication token")
    expires_at = models.DateTimeField(help_text="Token expiration datetime")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'airiq_token_cache'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"AirIQ Token expires at {self.expires_at}"
    
    @property
    def is_expired(self):
        """Check if token is expired"""
        from django.utils import timezone
        return timezone.now() >= self.expires_at
    
    @classmethod
    def get_valid_token(cls):
        """Get a valid cached token or None if no valid token exists"""
        from django.utils import timezone
        valid_token = cls.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        return valid_token.token if valid_token else None
    
    @classmethod
    def cache_token(cls, token, expires_in_hours=24, expires_at=None):
        """Cache a new token with optional custom expiry"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Deactivate all existing tokens
        cls.objects.filter(is_active=True).update(is_active=False)
        
        # Determine expiry time
        if expires_at:
            token_expires_at = expires_at
        else:
            token_expires_at = timezone.now() + timedelta(hours=expires_in_hours)
        
        # Create new token cache
        return cls.objects.create(
            token=token,
            expires_at=token_expires_at,
            is_active=True
        )
