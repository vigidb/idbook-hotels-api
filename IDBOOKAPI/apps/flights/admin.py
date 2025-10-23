from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Airline, Airport, FlightRoute, FlightInventory, FlightSearchSession,
    FlightOption, AirIQApiLog, AirIQTokenCache
)


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['code', 'name']
    list_editable = ['is_active']
    ordering = ['name']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ['iata_code', 'name', 'city', 'country', 'timezone', 'is_active']
    list_filter = ['country', 'is_active']
    search_fields = ['iata_code', 'name', 'city', 'country']
    list_editable = ['is_active']
    ordering = ['iata_code']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related()


@admin.register(FlightRoute)
class FlightRouteAdmin(admin.ModelAdmin):
    list_display = ['get_route', 'airline', 'aircraft_type', 'duration_minutes', 'distance_km', 'is_active']
    list_filter = ['airline', 'is_active', 'origin__country', 'destination__country']
    search_fields = ['origin__iata_code', 'destination__iata_code', 'airline__name', 'aircraft_type']
    list_editable = ['is_active']
    raw_id_fields = ['origin', 'destination', 'airline']

    def get_route(self, obj):
        return f"{obj.origin.iata_code} → {obj.destination.iata_code}"
    get_route.short_description = 'Route'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('origin', 'destination', 'airline')


@admin.register(FlightInventory)
class FlightInventoryAdmin(admin.ModelAdmin):
    list_display = [
        'get_flight_number', 'get_route', 'flight_date', 'status', 
        'available_seats', 'total_seats', 'is_active'
    ]
    list_filter = [
        'flight_date', 'status', 'is_active', 
        'route__airline', 'route__origin__country'
    ]
    search_fields = [
        'route__flight_number', 'route__origin__iata_code', 
        'route__destination__iata_code', 'route__airline__name'
    ]
    list_editable = ['is_active']
    date_hierarchy = 'flight_date'
    raw_id_fields = ['route']
    
    def get_flight_number(self, obj):
        return obj.route.full_flight_number
    get_flight_number.short_description = 'Flight Number'

    def get_route(self, obj):
        return f"{obj.route.origin.iata_code} → {obj.route.destination.iata_code}"
    get_route.short_description = 'Route'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('route__origin', 'route__destination', 'route__airline')






@admin.register(FlightSearchSession)
class FlightSearchSessionAdmin(admin.ModelAdmin):
    list_display = [
        'session_id', 'get_route', 'departure_date', 'trip_type', 'flight_class', 
        'passenger_count', 'search_mode', 'created_at', 'expires_at'
    ]
    list_filter = [
        'trip_type', 'flight_class', 'search_mode', 'created_at', 'expires_at'
    ]
    search_fields = [
        'session_id', 'origin', 'destination', 'airiq_track_id'
    ]
    readonly_fields = ['session_id', 'created_at']
    date_hierarchy = 'created_at'

    def get_route(self, obj):
        return f"{obj.origin} → {obj.destination}"
    get_route.short_description = 'Route'

    def passenger_count(self, obj):
        return f"A:{obj.adults} C:{obj.children} I:{obj.infants}"
    passenger_count.short_description = 'Passengers'


@admin.register(FlightOption)
class FlightOptionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'airline_code', 'flight_number', 'get_route', 'departure_datetime', 
        'flight_class', 'total_fare', 'available_seats', 'is_refundable'
    ]
    list_filter = [
        'airline_code', 'flight_class', 'departure_datetime', 'is_refundable', 'can_hold'
    ]
    search_fields = [
        'airline_code', 'flight_number', 'origin', 'destination', 'airiq_flight_id'
    ]
    raw_id_fields = ['search_session', 'inventory_flight']
    date_hierarchy = 'departure_datetime'

    def get_route(self, obj):
        return f"{obj.origin} → {obj.destination}"
    get_route.short_description = 'Route'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('search_session', 'inventory_flight')










@admin.register(AirIQApiLog)
class AirIQAPILogAdmin(admin.ModelAdmin):
    list_display = [
        'api_endpoint', 'http_method', 'result_code', 'response_time_ms', 'created_at', 'has_error'
    ]
    list_filter = [
        'api_endpoint', 'http_method', 'result_code', 'created_at'
    ]
    search_fields = ['api_endpoint', 'request_data', 'response_data', 'error_message']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Request Info', {
            'fields': ('api_endpoint', 'http_method', 'request_data')
        }),
        ('Response Info', {
            'fields': ('result_code', 'response_data', 'response_time_ms')
        }),
        ('Error Info', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def has_error(self, obj):
        return bool(obj.error_message)
    has_error.boolean = True
    has_error.short_description = 'Has Error'

    def get_queryset(self, request):
        return super().get_queryset(request)


@admin.register(AirIQTokenCache)
class AirIQTokenCacheAdmin(admin.ModelAdmin):
    list_display = ['id', 'token_preview', 'expires_at', 'is_active', 'is_expired_status', 'created_at']
    list_filter = ['is_active', 'expires_at', 'created_at']
    search_fields = ['token']
    readonly_fields = ['created_at', 'is_expired_status']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def token_preview(self, obj):
        """Show first and last 10 characters of token for security"""
        if len(obj.token) > 20:
            return f"{obj.token[:10]}...{obj.token[-10:]}"
        return obj.token[:20] + '...' if len(obj.token) > 20 else obj.token
    token_preview.short_description = 'Token Preview'
    
    def is_expired_status(self, obj):
        """Show if token is expired"""
        return obj.is_expired
    is_expired_status.boolean = True
    is_expired_status.short_description = 'Is Expired'
    
    actions = ['deactivate_tokens', 'activate_tokens']
    
    def deactivate_tokens(self, request, queryset):
        """Bulk deactivate selected tokens"""
        queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {queryset.count()} tokens.")
    deactivate_tokens.short_description = "Deactivate selected tokens"
    
    def activate_tokens(self, request, queryset):
        """Bulk activate selected tokens"""
        queryset.update(is_active=True)
        self.message_user(request, f"Activated {queryset.count()} tokens.")
    activate_tokens.short_description = "Activate selected tokens"
