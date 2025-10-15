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
    """Master data for airlines"""
    code = models.CharField(max_length=3, unique=True, help_text="2-letter IATA airline code")
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=3, choices=AIRLINE_CATEGORY, default='LCC')
    logo = models.ImageField(upload_to='airlines/logos/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flights_airline'
        verbose_name = 'Airline'
        verbose_name_plural = 'Airlines'

    def __str__(self):
        return f"{self.code} - {self.name}"


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


class FlightBooking(models.Model):
    """Enhanced flight booking model with AirIQ integration"""
    # Basic booking info
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flight_bookings')
    booking_reference = models.CharField(max_length=20, unique=True)
    
    # Flight selection
    selected_flight = models.ForeignKey(FlightOption, on_delete=models.CASCADE)
    search_session = models.ForeignKey(FlightSearchSession, on_delete=models.CASCADE)
    
    # Booking mode and source
    booking_mode = models.CharField(max_length=10, choices=FLIGHT_BOOKING_MODE, default='REALTIME')
    
    # AirIQ specific fields
    airiq_pnr = models.CharField(max_length=20, blank=True, help_text="AirIQ PNR")
    airline_pnr = models.CharField(max_length=20, blank=True, help_text="Airline PNR")
    airiq_track_id = models.CharField(max_length=255, blank=True)
    airiq_booking_token = models.TextField(blank=True)
    
    # Booking status and workflow
    status = models.CharField(max_length=20, choices=FLIGHT_BOOKING_STATUS, default='BOOKING_INITIATED')
    booking_status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default='pending')
    
    # Pricing details
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Additional services total
    ancillary_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Hold/Expiry management
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Ticket details
    ticket_numbers = models.JSONField(default=list, help_text="List of ticket numbers for passengers")
    ticket_pdf = models.FileField(upload_to='flights/tickets/', blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'flights_booking'
        verbose_name = 'Flight Booking'
        verbose_name_plural = 'Flight Bookings'
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking {self.booking_reference} - {self.selected_flight}"

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.hold_expires_at and timezone.now() > self.hold_expires_at


class PassengerDetail(models.Model):
    """Passenger details for flight booking"""
    booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE, related_name='passengers')
    
    # Passenger identification
    passenger_reference = models.PositiveSmallIntegerField(help_text="Passenger reference number (1, 2, 3...)")
    passenger_type = models.CharField(max_length=3, choices=PASSENGER_TYPE)
    
    # Personal details
    title = models.CharField(max_length=5, choices=PASSENGER_TITLE)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    
    # Travel documents
    passport_number = models.CharField(max_length=20, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    passport_issued_date = models.DateField(null=True, blank=True)
    passport_country_code = models.CharField(max_length=2, blank=True)
    
    # For infant passengers
    infant_with_passenger = models.PositiveSmallIntegerField(null=True, blank=True, 
                                                          help_text="Passenger reference traveling with infant")
    
    # Frequent flyer
    frequent_flyer_number = models.CharField(max_length=20, blank=True)
    frequent_flyer_airline = models.CharField(max_length=3, blank=True)
    
    # Ticket details
    ticket_number = models.CharField(max_length=20, blank=True)
    seat_number = models.CharField(max_length=5, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flights_passenger'
        verbose_name = 'Passenger Detail'
        verbose_name_plural = 'Passenger Details'
        unique_together = ['booking', 'passenger_reference']
        ordering = ['passenger_reference']

    def __str__(self):
        return f"{self.title} {self.first_name} {self.last_name} ({self.passenger_type})"

    @property
    def full_name(self):
        return f"{self.title} {self.first_name} {self.last_name}"


class SeatSelection(models.Model):
    """Seat selections for passengers"""
    passenger = models.ForeignKey(PassengerDetail, on_delete=models.CASCADE, related_name='seat_selections')
    
    # Segment details (for multi-segment flights)
    segment_reference = models.PositiveSmallIntegerField(default=1)
    
    # Seat details from AirIQ
    airiq_seat_id = models.CharField(max_length=255, blank=True)
    seat_number = models.CharField(max_length=10)
    seat_type = models.CharField(max_length=2, choices=SEAT_TYPE, default='NS')
    seat_group = models.CharField(max_length=10, blank=True)
    
    # Seat characteristics
    is_window = models.BooleanField(default=False)
    is_aisle = models.BooleanField(default=False)
    is_emergency_exit = models.BooleanField(default=False)
    
    # Pricing
    seat_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flights_seat_selection'
        verbose_name = 'Seat Selection'
        verbose_name_plural = 'Seat Selections'
        unique_together = ['passenger', 'segment_reference']

    def __str__(self):
        return f"Seat {self.seat_number} for {self.passenger.full_name}"


class AncillaryService(models.Model):
    """Ancillary services like meals, baggage, etc."""
    booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE, related_name='ancillary_services')
    passenger = models.ForeignKey(PassengerDetail, on_delete=models.CASCADE, related_name='ancillary_services')
    
    # Service details
    service_type = models.CharField(max_length=20, choices=SSR_CATEGORY)
    airiq_service_id = models.CharField(max_length=100, blank=True)
    service_code = models.CharField(max_length=20)
    service_description = models.CharField(max_length=200)
    
    # Segment details
    segment_reference = models.PositiveSmallIntegerField(default=1)
    
    # Pricing
    service_price = models.DecimalField(max_digits=8, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flights_ancillary_service'
        verbose_name = 'Ancillary Service'
        verbose_name_plural = 'Ancillary Services'

    def __str__(self):
        return f"{self.service_description} for {self.passenger.full_name} - ₹{self.service_price}"


class FlightBookingPayment(models.Model):
    """Payment details for flight bookings"""
    booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE, related_name='payments')
    
    # Payment identification
    payment_reference = models.CharField(max_length=50, unique=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=1, choices=AIRIQ_PAYMENT_MODE)
    payment_status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    ], default='PENDING')
    
    # Gateway response
    gateway_response = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'flights_payment'
        verbose_name = 'Flight Payment'
        verbose_name_plural = 'Flight Payments'
        ordering = ['-created_at']


class AirIQApiLog(models.Model):
    """Log all AirIQ API calls for debugging and audit"""
    booking = models.ForeignKey(FlightBooking, on_delete=models.CASCADE, null=True, blank=True, related_name='api_logs')
    
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
    def cache_token(cls, token, expires_in_hours=24):
        """Cache a new token"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Deactivate all existing tokens
        cls.objects.filter(is_active=True).update(is_active=False)
        
        # Create new token cache
        expires_at = timezone.now() + timedelta(hours=expires_in_hours)
        return cls.objects.create(
            token=token,
            expires_at=expires_at,
            is_active=True
        )
