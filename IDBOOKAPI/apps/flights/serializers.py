from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, timedelta

from .models import (
    Airline, Airport, FlightRoute, FlightInventory, FlightSearchSession,
    FlightOption, FlightBooking, PassengerDetail, AncillaryService,
    SeatSelection, FlightBookingPayment
)


class FlightSearchSerializer(serializers.Serializer):
    """Serializer for flight search parameters"""
    origin = serializers.CharField(max_length=3, help_text="IATA code for origin airport")
    destination = serializers.CharField(max_length=3, help_text="IATA code for destination airport")
    departure_date = serializers.DateField(help_text="Departure date in YYYY-MM-DD format")
    return_date = serializers.DateField(required=False, help_text="Return date for round trip")
    trip_type = serializers.ChoiceField(
        choices=['O', 'R', 'Y'],
        default='O',
        help_text="O=One-way, R=Round-trip, Y=Round-trip Special"
    )
    flight_class = serializers.ChoiceField(
        choices=[
            ('E', 'Economy'),
            ('P', 'Premium'),
            ('B', 'Business'),
            ('F', 'First')
        ],
        default='E'
    )
    adults = serializers.IntegerField(min_value=1, max_value=9, default=1)
    children = serializers.IntegerField(min_value=0, max_value=8, default=0)
    infants = serializers.IntegerField(min_value=0, max_value=2, default=0)
    search_mode = serializers.ChoiceField(
        choices=['REALTIME', 'INVENTORY', 'BOTH'],
        default='BOTH',
        help_text="Search in real-time API, pre-booked inventory, or both"
    )
    direct_only = serializers.BooleanField(default=False)
    sort_by = serializers.ChoiceField(
        choices=['price', 'duration', 'departure_time'],
        default='price'
    )
    airline_id = serializers.CharField(max_length=10, required=False, allow_blank=True)
    fare_type = serializers.ChoiceField(
        choices=['N', 'C', 'R'],
        default='N',
        help_text="N=Normal, C=Corporate, R=Retail"
    )

    def validate(self, data):
        """Validate search parameters"""
        # Check dates
        departure_date = data['departure_date']
        if departure_date < timezone.now().date():
            raise serializers.ValidationError("Departure date cannot be in the past")
        
        # Check return date for round trips
        if data.get('trip_type') in ['R', 'Y'] and not data.get('return_date'):
            raise serializers.ValidationError("Return date is required for round trips")
        
        if data.get('return_date') and data.get('return_date') < departure_date:
            raise serializers.ValidationError("Return date must be after departure date")
        
        # Check passenger counts
        total_passengers = data['adults'] + data['children'] + data['infants']
        if total_passengers > 9:
            raise serializers.ValidationError("Maximum 9 passengers allowed")
        
        # Infants cannot exceed adults
        if data['infants'] > data['adults']:
            raise serializers.ValidationError("Number of infants cannot exceed adults")
        
        return data


class AirlineSerializer(serializers.ModelSerializer):
    """Serializer for airline information"""
    class Meta:
        model = Airline
        fields = ['id', 'code', 'name', 'category', 'country', 'logo_url']


class AirportSerializer(serializers.ModelSerializer):
    """Serializer for airport information"""
    class Meta:
        model = Airport
        fields = ['id', 'iata_code', 'name', 'city', 'country', 'timezone']


class FlightOptionSerializer(serializers.ModelSerializer):
    """Serializer for flight options in search results"""
    airline_info = serializers.SerializerMethodField()
    origin_info = serializers.SerializerMethodField()
    destination_info = serializers.SerializerMethodField()
    formatted_departure = serializers.SerializerMethodField()
    formatted_arrival = serializers.SerializerMethodField()
    formatted_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = FlightOption
        fields = [
            'id', 'airiq_flight_id', 'airline_code', 'flight_number', 'origin', 'destination',
            'departure_datetime', 'arrival_datetime', 'flight_class', 'fare_basis',
            'airline_category', 'stops', 'duration_minutes', 'aircraft_type', 'base_fare',
            'taxes', 'total_fare', 'available_seats', 'baggage_info', 'is_refundable',
            'can_hold', 'airline_info', 'origin_info', 'destination_info',
            'formatted_departure', 'formatted_arrival', 'formatted_duration'
        ]

    def get_airline_info(self, obj):
        """Get airline details"""
        try:
            airline = Airline.objects.get(code=obj.airline_code)
            return {
                'code': airline.code,
                'name': airline.name,
                'category': airline.category,
                'logo_url': airline.logo_url
            }
        except Airline.DoesNotExist:
            return {
                'code': obj.airline_code,
                'name': obj.airline_code,
                'category': 'LCC',
                'logo_url': None
            }

    def get_origin_info(self, obj):
        """Get origin airport details"""
        try:
            airport = Airport.objects.get(iata_code=obj.origin)
            return {
                'iata_code': airport.iata_code,
                'name': airport.name,
                'city': airport.city,
                'country': airport.country
            }
        except Airport.DoesNotExist:
            return {
                'iata_code': obj.origin,
                'name': obj.origin,
                'city': obj.origin,
                'country': ''
            }

    def get_destination_info(self, obj):
        """Get destination airport details"""
        try:
            airport = Airport.objects.get(iata_code=obj.destination)
            return {
                'iata_code': airport.iata_code,
                'name': airport.name,
                'city': airport.city,
                'country': airport.country
            }
        except Airport.DoesNotExist:
            return {
                'iata_code': obj.destination,
                'name': obj.destination,
                'city': obj.destination,
                'country': ''
            }

    def get_formatted_departure(self, obj):
        """Format departure datetime"""
        return {
            'date': obj.departure_datetime.strftime('%Y-%m-%d'),
            'time': obj.departure_datetime.strftime('%H:%M'),
            'datetime': obj.departure_datetime.strftime('%Y-%m-%d %H:%M')
        }

    def get_formatted_arrival(self, obj):
        """Format arrival datetime"""
        return {
            'date': obj.arrival_datetime.strftime('%Y-%m-%d'),
            'time': obj.arrival_datetime.strftime('%H:%M'),
            'datetime': obj.arrival_datetime.strftime('%Y-%m-%d %H:%M')
        }

    def get_formatted_duration(self, obj):
        """Format flight duration"""
        hours = obj.duration_minutes // 60
        minutes = obj.duration_minutes % 60
        return f"{hours}h {minutes}m"


class FlightSearchResultSerializer(serializers.Serializer):
    """Serializer for search result response"""
    search_results = FlightOptionSerializer(many=True)
    total_results = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    has_next = serializers.BooleanField()
    search_mode = serializers.CharField()
    search_timestamp = serializers.DateTimeField()


class PassengerCountSerializer(serializers.Serializer):
    """Serializer for passenger count in pricing requests"""
    adults = serializers.IntegerField(min_value=1, max_value=9)
    children = serializers.IntegerField(min_value=0, max_value=8)
    infants = serializers.IntegerField(min_value=0, max_value=2)


class FlightPricingSerializer(serializers.Serializer):
    """Serializer for flight pricing requests"""
    flight_option_id = serializers.IntegerField()
    passenger_count = PassengerCountSerializer()


class PassengerDetailSerializer(serializers.ModelSerializer):
    """Serializer for passenger details"""
    class Meta:
        model = PassengerDetail
        fields = [
            'id', 'passenger_reference', 'passenger_type', 'title', 'first_name', 'last_name',
            'date_of_birth', 'gender', 'nationality', 'id_number', 'id_type',
            'passport_number', 'passport_expiry', 'frequent_flyer_number', 'special_assistance'
        ]
        extra_kwargs = {
            'id_number': {'required': False},
            'passport_number': {'required': False},
            'passport_expiry': {'required': False},
            'frequent_flyer_number': {'required': False},
            'special_assistance': {'required': False}
        }

    def validate_date_of_birth(self, value):
        """Validate date of birth"""
        if value >= timezone.now().date():
            raise serializers.ValidationError("Date of birth cannot be in the future")
        return value

    def validate_passenger_type(self, value):
        """Validate passenger type based on age"""
        if hasattr(self, 'initial_data') and 'date_of_birth' in self.initial_data:
            try:
                dob = datetime.strptime(self.initial_data['date_of_birth'], '%Y-%m-%d').date()
                age = (timezone.now().date() - dob).days // 365
                
                if value == 'ADULT' and age < 12:
                    raise serializers.ValidationError("Adults must be 12 years or older")
                elif value == 'CHILD' and (age < 2 or age >= 12):
                    raise serializers.ValidationError("Children must be between 2-11 years old")
                elif value == 'INFANT' and age >= 2:
                    raise serializers.ValidationError("Infants must be under 2 years old")
            except (ValueError, KeyError):
                pass
        
        return value


class SeatSelectionSerializer(serializers.ModelSerializer):
    """Serializer for seat selection"""
    class Meta:
        model = SeatSelection
        fields = [
            'id', 'passenger', 'seat_number', 'seat_type', 'seat_fee',
            'is_available', 'seat_row', 'seat_column'
        ]
        read_only_fields = ['id', 'is_available']


class AncillaryServiceSerializer(serializers.ModelSerializer):
    """Serializer for ancillary services (meals, baggage, etc.)"""
    class Meta:
        model = AncillaryService
        fields = [
            'id', 'service_type', 'service_code', 'description', 'price',
            'quantity', 'passenger'
        ]


class FlightBookingPaymentSerializer(serializers.ModelSerializer):
    """Serializer for flight booking payments"""
    class Meta:
        model = FlightBookingPayment
        fields = [
            'id', 'payment_mode', 'payment_status', 'amount', 'payment_reference',
            'gateway_response', 'transaction_fee', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BookingCreateSerializer(serializers.Serializer):
    """Serializer for creating flight bookings"""
    flight_option_id = serializers.IntegerField()
    passengers = PassengerDetailSerializer(many=True)
    contact_email = serializers.EmailField()
    contact_phone = serializers.CharField(max_length=15)
    special_requests = serializers.CharField(max_length=500, required=False, allow_blank=True)
    ancillary_services = AncillaryServiceSerializer(many=True, required=False)
    seat_selections = SeatSelectionSerializer(many=True, required=False)
    pricing = serializers.DictField(required=True)

    def validate_flight_option_id(self, value):
        """Validate flight option exists and is available"""
        try:
            flight_option = FlightOption.objects.get(id=value)
            # Check if search session is still valid (not expired)
            if flight_option.search_session.expires_at < timezone.now():
                raise serializers.ValidationError("Flight search session has expired. Please search again.")
            return value
        except FlightOption.DoesNotExist:
            raise serializers.ValidationError("Flight option not found")

    def validate_passengers(self, value):
        """Validate passenger details"""
        if not value:
            raise serializers.ValidationError("At least one passenger is required")
        
        passenger_types = [p['passenger_type'] for p in value]
        
        # Count passenger types
        adults = passenger_types.count('ADULT')
        children = passenger_types.count('CHILD')
        infants = passenger_types.count('INFANT')
        
        # Validate passenger counts
        if adults == 0:
            raise serializers.ValidationError("At least one adult passenger is required")
        
        if infants > adults:
            raise serializers.ValidationError("Number of infants cannot exceed adults")
        
        # Validate required fields for each passenger
        for i, passenger in enumerate(value):
            if not passenger.get('first_name'):
                raise serializers.ValidationError(f"Passenger {i+1}: First name is required")
            if not passenger.get('last_name'):
                raise serializers.ValidationError(f"Passenger {i+1}: Last name is required")
            if not passenger.get('date_of_birth'):
                raise serializers.ValidationError(f"Passenger {i+1}: Date of birth is required")
        
        return value

    def validate_pricing(self, value):
        """Validate pricing information"""
        required_fields = ['base_amount', 'tax_amount', 'total_amount']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Pricing field '{field}' is required")
            try:
                float(value[field])
            except (ValueError, TypeError):
                raise serializers.ValidationError(f"Pricing field '{field}' must be a valid number")
        
        return value


class FlightBookingSerializer(serializers.ModelSerializer):
    """Basic flight booking serializer"""
    passenger_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FlightBooking
        fields = [
            'id', 'booking_reference', 'status', 'booking_mode', 'base_amount',
            'tax_amount', 'total_amount', 'contact_email', 'contact_phone',
            'special_requests', 'created_at', 'updated_at', 'passenger_count'
        ]
        read_only_fields = ['id', 'booking_reference', 'created_at', 'updated_at']

    def get_passenger_count(self, obj):
        """Get passenger count breakdown"""
        passengers = obj.passengers.all()
        return {
            'adults': passengers.filter(passenger_type='ADULT').count(),
            'children': passengers.filter(passenger_type='CHILD').count(),
            'infants': passengers.filter(passenger_type='INFANT').count(),
            'total': passengers.count()
        }


class BookingRetrieveSerializer(serializers.ModelSerializer):
    """Detailed serializer for retrieving booking information"""
    selected_flight = FlightOptionSerializer(read_only=True)
    passengers = PassengerDetailSerializer(many=True, read_only=True)
    seat_selections = SeatSelectionSerializer(many=True, read_only=True)
    ancillary_services = AncillaryServiceSerializer(many=True, read_only=True)
    payments = FlightBookingPaymentSerializer(many=True, read_only=True)
    passenger_count = serializers.SerializerMethodField()
    booking_status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = FlightBooking
        fields = [
            'id', 'booking_reference', 'status', 'booking_status_display', 'booking_mode',
            'base_amount', 'tax_amount', 'total_amount', 'contact_email', 'contact_phone',
            'special_requests', 'airiq_pnr', 'airline_pnr', 'ticket_numbers', 'ticket_status',
            'cancellation_fee', 'refund_amount', 'created_at', 'updated_at', 'cancelled_at',
            'selected_flight', 'passengers', 'seat_selections', 'ancillary_services',
            'payments', 'passenger_count'
        ]

    def get_passenger_count(self, obj):
        """Get passenger count breakdown"""
        passengers = obj.passengers.all()
        return {
            'adults': passengers.filter(passenger_type='ADULT').count(),
            'children': passengers.filter(passenger_type='CHILD').count(),
            'infants': passengers.filter(passenger_type='INFANT').count(),
            'total': passengers.count()
        }


class FlightSearchSessionSerializer(serializers.ModelSerializer):
    """Serializer for flight search sessions"""
    class Meta:
        model = FlightSearchSession
        fields = [
            'id', 'session_id', 'origin', 'destination', 'departure_date', 'return_date',
            'trip_type', 'flight_class', 'adults', 'children', 'infants', 'search_mode',
            'airiq_track_id', 'created_at', 'expires_at'
        ]
        read_only_fields = ['id', 'session_id', 'created_at']


class FlightInventorySerializer(serializers.ModelSerializer):
    """Serializer for flight inventory management"""
    route_info = serializers.SerializerMethodField()
    
    class Meta:
        model = FlightInventory
        fields = [
            'id', 'route', 'flight_number', 'departure_date', 'departure_time',
            'arrival_time', 'flight_class', 'total_seats', 'available_seats',
            'base_price', 'taxes', 'total_price', 'route_info'
        ]

    def get_route_info(self, obj):
        """Get route details"""
        return {
            'origin': obj.route.origin.iata_code,
            'destination': obj.route.destination.iata_code,
            'airline': obj.route.airline.code,
            'aircraft_type': obj.route.aircraft_type
        }