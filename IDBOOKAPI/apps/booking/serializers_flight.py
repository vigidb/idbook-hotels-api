"""
Flight booking serializers for comprehensive booking flow
Handles all aspects of flight booking including passenger details, GST, payments, and notifications
"""

from rest_framework import serializers
from decimal import Decimal
from datetime import datetime, date
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator

from .models import (
    Booking, FlightBooking, FlightPassenger, FlightAncillaryService,
    BookingPaymentDetail, Invoice, BookingMetaInfo
)
from apps.customer.models import Customer
from apps.org_managements.models import BusinessDetail
from IDBOOKAPI.basic_resources import FLIGHT_BOOKING_STATUS, PASSENGER_TYPE

User = get_user_model()


class GSTInfoSerializer(serializers.Serializer):
    """Serializer for GST information"""
    gst_number = serializers.CharField(
        max_length=15, 
        required=False, 
        allow_blank=True,
        validators=[RegexValidator(
            regex=r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]{3}$',
            message='Invalid GST number format. Expected format: 2 digits + 5 letters + 4 digits + 1 letter + 3 alphanumeric (e.g., 27AAEHR8003E1ZC)'
        )]
    )
    company_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    mobile = serializers.CharField(
        max_length=15, 
        required=False, 
        allow_blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message='Invalid mobile number format'
        )]
    )
    
    def validate(self, data):
        """Validate that if GST number is provided, all fields are required"""
        if data.get('gst_number'):
            required_fields = ['company_name', 'address', 'email', 'mobile']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                raise serializers.ValidationError(
                    f"When GST number is provided, these fields are required: {', '.join(missing_fields)}"
                )
        
        return data


class ContactDetailsSerializer(serializers.Serializer):
    """Serializer for contact information"""
    country_code = serializers.CharField(max_length=5, default='91')
    phone = serializers.CharField(
        max_length=15,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message='Invalid phone number format'
        )]
    )
    email = serializers.EmailField()


class FrequentFlyerSerializer(serializers.Serializer):
    """Serializer for frequent flyer information"""
    passenger_ref = serializers.IntegerField(min_value=1)
    airline_code = serializers.CharField(max_length=3)
    flyer_number = serializers.CharField(max_length=20)
    segment_ref = serializers.IntegerField(default=1, min_value=1)
    itin_ref = serializers.IntegerField(default=0)


class PassengerDetailsSerializer(serializers.Serializer):
    """Serializer for passenger details in booking request"""
    passenger_ref = serializers.IntegerField(min_value=1, max_value=9)
    title = serializers.ChoiceField(choices=[
        ('MR', 'Mr'),
        ('MRS', 'Mrs'),
        ('MISS', 'Miss'),
        ('MS', 'Ms'),
        ('MSTR', 'Master'),
        ('DR', 'Dr'),
    ])
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    date_of_birth = serializers.DateField(
        required=False,
        allow_null=True,
        input_formats=['%d/%m/%Y', '%Y-%m-%d']
    )
    gender = serializers.ChoiceField(choices=[('Male', 'Male'), ('Female', 'Female')])
    passenger_type = serializers.ChoiceField(choices=PASSENGER_TYPE)
    
    # Optional passport details
    passport_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    passport_expiry = serializers.DateField(
        required=False, 
        allow_null=True,
        input_formats=['%d/%m/%Y', '%Y-%m-%d']
    )
    passport_issued_date = serializers.DateField(
        required=False, 
        allow_null=True,
        input_formats=['%d/%m/%Y', '%Y-%m-%d']
    )
    passport_country_code = serializers.CharField(max_length=2, required=False, allow_blank=True)
    
    # For infant passengers
    infant_ref = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_date_of_birth(self, value):
        """Validate date of birth"""
        if value is not None and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future")
        return value
    
    def validate(self, data):
        """Validate passenger details based on type and age"""
        from dateutil.relativedelta import relativedelta
        
        dob = data.get('date_of_birth')
        passenger_type = data.get('passenger_type')
        
        if dob and passenger_type:
            age = relativedelta(date.today(), dob).years
            
            if passenger_type == 'ADT' and age < 12:
                raise serializers.ValidationError("Adult passengers must be 12+ years old")
            elif passenger_type == 'CHD' and (age < 2 or age >= 12):
                raise serializers.ValidationError("Child passengers must be 2-11 years old")
            elif passenger_type == 'INF' and age >= 2:
                raise serializers.ValidationError("Infant passengers must be under 2 years old")
        
        return data


class SeatSelectionSerializer(serializers.Serializer):
    """Serializer for seat selection"""
    passenger_ref = serializers.IntegerField(min_value=1)
    seat_id = serializers.CharField(max_length=255)


class AncillaryServiceSerializer(serializers.Serializer):
    """Serializer for ancillary services (baggage, meals, etc.)"""
    service_id = serializers.CharField(max_length=100)
    passenger_ref = serializers.IntegerField(min_value=1)
    service_type = serializers.ChoiceField(choices=[
        ('BAGGAGE', 'Baggage'),
        ('MEAL', 'Meal'),
        ('OTHER', 'Other')
    ])


class FlightSegmentSerializer(serializers.Serializer):
    """Serializer for flight segment details"""
    flight_id = serializers.CharField(max_length=100)
    flight_number = serializers.CharField(max_length=10)
    origin = serializers.CharField(max_length=3)
    destination = serializers.CharField(max_length=3)
    departure_datetime = serializers.CharField()  # DD MMM YYYY HH:MM format
    arrival_datetime = serializers.CharField()    # DD MMM YYYY HH:MM format


class FlightBookingRequestSerializer(serializers.Serializer):
    """Comprehensive flight booking request serializer"""
    
    # Passenger counts
    adult_count = serializers.IntegerField(min_value=1, max_value=9)
    child_count = serializers.IntegerField(min_value=0, max_value=8, default=0)
    infant_count = serializers.IntegerField(min_value=0, max_value=4, default=0)
    
    # Flight and pricing info
    pricing_token = serializers.CharField(max_length=255)
    track_id = serializers.CharField(max_length=255)
    flight_segments = FlightSegmentSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Trip details
    trip_type = serializers.ChoiceField(choices=[('O', 'One-way'), ('R', 'Round-trip')])
    base_origin = serializers.CharField(max_length=3)
    base_destination = serializers.CharField(max_length=3)
    
    # Passenger details
    passengers = PassengerDetailsSerializer(many=True)
    
    # Contact information
    contact = ContactDetailsSerializer()
    
    # Optional services
    seats = SeatSelectionSerializer(many=True, required=False)
    baggage = AncillaryServiceSerializer(many=True, required=False)
    meals = AncillaryServiceSerializer(many=True, required=False)
    other_services = AncillaryServiceSerializer(many=True, required=False)
    
    # Optional GST and frequent flyer info
    gst_info = GSTInfoSerializer(required=False)
    frequent_flyer = FrequentFlyerSerializer(many=True, required=False)
    
    # Booking options
    block_pnr = serializers.BooleanField(default=False)
    
    def validate(self, data):
        """Comprehensive booking validation"""
        adult_count = data.get('adult_count', 0)
        child_count = data.get('child_count', 0)
        infant_count = data.get('infant_count', 0)
        
        # Validate passenger counts
        if adult_count + child_count > 9:
            raise serializers.ValidationError("Total adults and children cannot exceed 9")
        
        if infant_count > 4:
            raise serializers.ValidationError("Maximum 4 infants allowed")
        
        if infant_count > 0 and adult_count == 0:
            raise serializers.ValidationError("Infants cannot travel alone")
        
        # Validate passenger details match counts
        passengers = data.get('passengers', [])
        expected_total = adult_count + child_count + infant_count
        
        if len(passengers) != expected_total:
            raise serializers.ValidationError(
                f"Number of passenger details ({len(passengers)}) doesn't match "
                f"total passenger count ({expected_total})"
            )
        
        # Count passenger types
        adults = len([p for p in passengers if p.get('passenger_type') == 'ADT'])
        children = len([p for p in passengers if p.get('passenger_type') == 'CHD'])
        infants = len([p for p in passengers if p.get('passenger_type') == 'INF'])
        
        if adults != adult_count:
            raise serializers.ValidationError(f"Adult count mismatch: expected {adult_count}, got {adults}")
        if children != child_count:
            raise serializers.ValidationError(f"Child count mismatch: expected {child_count}, got {children}")
        if infants != infant_count:
            raise serializers.ValidationError(f"Infant count mismatch: expected {infant_count}, got {infants}")
        
        return data


class BookingResponseSerializer(serializers.ModelSerializer):
    """Serializer for booking response"""
    passengers = serializers.SerializerMethodField()
    ancillary_services = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    booking_status = serializers.CharField(source='status')
    
    class Meta:
        model = Booking
        fields = [
            'id', 'confirmation_code', 'booking_type', 'booking_status',
            'subtotal', 'gst_amount', 'service_tax', 'final_amount',
            'passengers', 'ancillary_services', 'payment_status',
            'created', 'updated'
        ]
    
    def get_passengers(self, obj):
        if obj.flight_booking:
            return FlightPassengerSerializer(
                obj.flight_booking.passengers.all(), many=True
            ).data
        return []
    
    def get_ancillary_services(self, obj):
        if obj.flight_booking:
            return FlightAncillaryServiceSerializer(
                obj.flight_booking.ancillary_services.all(), many=True
            ).data
        return []
    
    def get_payment_status(self, obj):
        payment_details = obj.booking_payment.filter(is_transaction_success=True)
        total_paid = sum(p.amount for p in payment_details)
        
        return {
            'total_paid': float(total_paid),
            'remaining': float(obj.final_amount - total_paid),
            'is_fully_paid': total_paid >= obj.final_amount
        }


class FlightBookingDetailSerializer(serializers.ModelSerializer):
    """Detailed flight booking serializer with AirIQ data"""
    passengers = FlightPassengerSerializer(many=True, read_only=True)
    ancillary_services = FlightAncillaryServiceSerializer(many=True, read_only=True)
    is_expired = serializers.ReadOnlyField()
    booking_details = serializers.SerializerMethodField()
    
    class Meta:
        model = FlightBooking
        fields = '__all__'
    
    def get_booking_details(self, obj):
        """Get associated booking details"""
        booking = Booking.objects.filter(flight_booking=obj).first()
        if booking:
            return {
                'id': booking.id,
                'confirmation_code': booking.confirmation_code,
                'final_amount': float(booking.final_amount),
                'status': booking.status,
                'invoice_id': booking.invoice_id
            }
        return None


class BookingPaymentRequestSerializer(serializers.Serializer):
    """Serializer for payment request"""
    payment_method = serializers.ChoiceField(choices=[
        ('PHONE_PAY', 'PhonePe'),
        ('PAYU', 'PayU'),
        ('WALLET', 'Wallet'),
        ('DIRECT', 'Direct Payment')
    ])
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    return_url = serializers.URLField(required=False)
    cancel_url = serializers.URLField(required=False)


class InvoiceGenerationRequestSerializer(serializers.Serializer):
    """Serializer for invoice generation request"""
    booking_id = serializers.IntegerField(min_value=1)
    generate_pdf = serializers.BooleanField(default=True)
    email_invoice = serializers.BooleanField(default=True)


class BookingSearchSerializer(serializers.Serializer):
    """Serializer for booking search/filter"""
    booking_reference = serializers.CharField(max_length=50, required=False)
    status = serializers.ChoiceField(
        choices=FLIGHT_BOOKING_STATUS, 
        required=False
    )
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    passenger_name = serializers.CharField(max_length=100, required=False)
    flight_number = serializers.CharField(max_length=10, required=False)
    
    def validate(self, data):
        """Validate date range"""
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError("date_from cannot be after date_to")
        
        return data


class NotificationPreferencesSerializer(serializers.Serializer):
    """Serializer for notification preferences"""
    email_notifications = serializers.BooleanField(default=True)
    sms_notifications = serializers.BooleanField(default=True)
    booking_confirmation = serializers.BooleanField(default=True)
    payment_confirmation = serializers.BooleanField(default=True)
    ticket_issued = serializers.BooleanField(default=True)
    booking_cancelled = serializers.BooleanField(default=True)
    flight_updates = serializers.BooleanField(default=True)


class FlightBookingStatsSerializer(serializers.Serializer):
    """Serializer for booking statistics"""
    total_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    cancelled_bookings = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_booking_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    top_routes = serializers.ListField(child=serializers.DictField())
    monthly_trends = serializers.ListField(child=serializers.DictField())