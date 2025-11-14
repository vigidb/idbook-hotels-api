from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, timedelta

from .models import (
    Airline, Airport, FlightRoute, FlightInventory, FlightSearchSession,
    FlightOption
)


class FlightSearchSerializer(serializers.Serializer):
    """Serializer for flight search parameters"""
    origin = serializers.CharField(max_length=3, help_text="IATA code for origin airport")
    destination = serializers.CharField(max_length=3, help_text="IATA code for destination airport")
    departure_date = serializers.DateField(help_text="Departure date in YYYY-MM-DD format")
    return_date = serializers.DateField(required=False, allow_null=True, help_text="Return date for round trip")
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
    """Serializer for airline information and metadata.

    This surfaces both OpenFlights fields and internal fields in a
    user-friendly structure for the airline search API.
    """

    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Airline
        fields = [
            'id',
            'openflights_id',
            'code',
            'name',
            'alias',
            'icao_code',
            'callsign',
            'country',
            'category',
            'active',
            'is_active',
            'logo_url',
        ]

    def get_logo_url(self, obj):
        request = self.context.get('request') if hasattr(self, 'context') else None
        url = obj.logo_url
        if url and request is not None:
            return request.build_absolute_uri(url)
        return url


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