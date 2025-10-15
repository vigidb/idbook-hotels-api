from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Airline, Airport, FlightRoute, FlightInventory, FlightSearchSession,
    FlightOption, FlightBooking, PassengerDetail, AncillaryService,
    SeatSelection, FlightBookingPayment, AirIQApiLog, AirIQTokenCache
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


class PassengerDetailInline(admin.TabularInline):
    model = PassengerDetail
    extra = 0
    fields = [
        'passenger_reference', 'passenger_type', 'title', 'first_name', 'last_name', 
        'date_of_birth', 'gender'
    ]
    readonly_fields = ['passenger_reference']


class FlightBookingPaymentInline(admin.TabularInline):
    model = FlightBookingPayment
    extra = 0
    fields = ['payment_mode', 'payment_status', 'amount', 'payment_reference']
    readonly_fields = ['payment_reference']


@admin.register(FlightBooking)
class FlightBookingAdmin(admin.ModelAdmin):
    list_display = [
        'booking_reference', 'user_email', 'get_route', 'departure_date', 
        'status', 'total_amount', 'booking_mode', 'created_at'
    ]
    list_filter = [
        'status', 'booking_mode', 'created_at', 'selected_flight__departure_datetime',
        'selected_flight__origin', 'selected_flight__destination'
    ]
    search_fields = [
        'booking_reference', 'user__email', 'contact_email', 'airiq_pnr', 'airline_pnr'
    ]
    readonly_fields = [
        'booking_reference', 'created_at', 'updated_at', 'cancelled_at'
    ]
    date_hierarchy = 'created_at'
    raw_id_fields = ['user', 'selected_flight', 'search_session']
    inlines = [PassengerDetailInline, FlightBookingPaymentInline]

    fieldsets = (
        ('Booking Information', {
            'fields': (
                'booking_reference', 'user', 'selected_flight', 'search_session', 
                'status', 'booking_mode'
            )
        }),
        ('Contact Details', {
            'fields': ('contact_email', 'contact_phone', 'special_requests')
        }),
        ('Pricing', {
            'fields': ('base_amount', 'tax_amount', 'total_amount', 'cancellation_fee', 'refund_amount')
        }),
        ('External References', {
            'fields': ('airiq_pnr', 'airline_pnr', 'ticket_numbers', 'ticket_status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'cancelled_at'),
            'classes': ('collapse',)
        }),
    )

    def user_email(self, obj):
        return obj.user.email if obj.user else '-'
    user_email.short_description = 'User Email'

    def get_route(self, obj):
        if obj.selected_flight:
            return f"{obj.selected_flight.origin} → {obj.selected_flight.destination}"
        return '-'
    get_route.short_description = 'Route'

    def departure_date(self, obj):
        if obj.selected_flight:
            return obj.selected_flight.departure_datetime.date()
        return '-'
    departure_date.short_description = 'Departure Date'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'selected_flight', 'search_session'
        ).prefetch_related('passengers', 'payments')


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


@admin.register(PassengerDetail)
class PassengerDetailAdmin(admin.ModelAdmin):
    list_display = [
        'get_passenger_name', 'passenger_type', 'date_of_birth', 'gender', 
        'get_booking_reference', 'get_departure_date'
    ]
    list_filter = [
        'passenger_type', 'gender', 'booking__status', 'booking__created_at'
    ]
    search_fields = [
        'first_name', 'last_name', 'booking__booking_reference', 
        'passport_number', 'frequent_flyer_number'
    ]
    raw_id_fields = ['booking']

    def get_passenger_name(self, obj):
        return f"{obj.title} {obj.first_name} {obj.last_name}"
    get_passenger_name.short_description = 'Passenger Name'

    def get_booking_reference(self, obj):
        return obj.booking.booking_reference
    get_booking_reference.short_description = 'Booking Reference'

    def get_departure_date(self, obj):
        if obj.booking.selected_flight:
            return obj.booking.selected_flight.departure_datetime.date()
        return '-'
    get_departure_date.short_description = 'Departure Date'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('booking', 'booking__selected_flight')


@admin.register(AncillaryService)
class AncillaryServiceAdmin(admin.ModelAdmin):
    list_display = [
        'service_type', 'service_code', 'service_description', 'service_price',
        'get_passenger_name', 'get_booking_reference'
    ]
    list_filter = ['service_type', 'booking__status']
    search_fields = [
        'service_code', 'service_description', 'passenger__first_name', 
        'passenger__last_name', 'booking__booking_reference'
    ]
    raw_id_fields = ['booking', 'passenger']

    def get_passenger_name(self, obj):
        if obj.passenger:
            return f"{obj.passenger.first_name} {obj.passenger.last_name}"
        return '-'
    get_passenger_name.short_description = 'Passenger'

    def get_booking_reference(self, obj):
        return obj.booking.booking_reference
    get_booking_reference.short_description = 'Booking Reference'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('booking', 'passenger')


@admin.register(SeatSelection)
class SeatSelectionAdmin(admin.ModelAdmin):
    list_display = [
        'seat_number', 'seat_type', 'seat_price', 'get_passenger_name', 
        'get_booking_reference'
    ]
    list_filter = ['seat_type', 'passenger__booking__status']
    search_fields = [
        'seat_number', 'passenger__first_name', 'passenger__last_name', 
        'passenger__booking__booking_reference'
    ]
    raw_id_fields = ['passenger']

    def get_passenger_name(self, obj):
        if obj.passenger:
            return f"{obj.passenger.first_name} {obj.passenger.last_name}"
        return '-'
    get_passenger_name.short_description = 'Passenger'

    def get_booking_reference(self, obj):
        return obj.passenger.booking.booking_reference
    get_booking_reference.short_description = 'Booking Reference'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('passenger__booking')


@admin.register(FlightBookingPayment)
class FlightBookingPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'get_booking_reference', 'payment_mode', 'payment_status', 'amount', 
        'payment_reference', 'created_at'
    ]
    list_filter = ['payment_mode', 'payment_status', 'created_at']
    search_fields = [
        'payment_reference', 'booking__booking_reference', 'booking__user__email'
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['booking']

    def get_booking_reference(self, obj):
        return obj.booking.booking_reference
    get_booking_reference.short_description = 'Booking Reference'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('booking')


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
