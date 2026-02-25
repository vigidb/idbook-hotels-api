from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Booking,
    HotelBooking,
    HolidayPackageBooking,
    VehicleBooking,
    FlightBooking,
    TaxRule,
    BookingPaymentDetail,
    Review,
    BookingCommission,
    Invoice,
    FlightPassenger,
    FlightAncillaryService,
    VisaBooking,
    EventBooking,
    Query,
    QueryCommunication,
)

# Register your models here.


class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "booking_type",
        "confirmation_code",
        "invoice_id",
        "status",
        "created",
        "updated",
    )
    actions = ["trigger_manual_refund"]

    @admin.action(description="Trigger manual refund")
    def trigger_manual_refund(self, request, queryset):
        from apps.booking.utils.booking_utils import process_manual_refund

        success_count = 0
        for booking in queryset:
            success, refund_status, result = process_manual_refund(booking)
            if success:
                success_count += 1
                self.message_user(
                    request,
                    f"Booking {booking.id} ({booking.confirmation_code}): refund initiated ({refund_status}).",
                    messages.SUCCESS,
                )
            else:
                self.message_user(
                    request,
                    f"Booking {booking.id} ({booking.confirmation_code}): {refund_status} - {result.get('error', result)}",
                    messages.ERROR,
                )
        if success_count:
            self.message_user(
                request,
                f"Manual refund initiated for {success_count} booking(s).",
                messages.SUCCESS,
            )


class BookingPaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "is_transaction_success", "created", "updated")


class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice_number",
        "invoice_type",
        "invoice_date",
        "total_amount",
        "status",
        "has_documents",
        "source_query_link",
        "created_at",
    )
    list_filter = ("invoice_type", "status", "created_at")
    search_fields = ("invoice_number",)
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("id", "invoice_number", "invoice_type", "invoice_date", "due_date", "status")
        }),
        ("Billing Details", {
            "fields": ("billed_by", "billed_by_details", "billed_to", "billed_to_details")
        }),
        ("Amounts", {
            "fields": ("total", "total_amount", "total_tax", "GST", "GST_type", "discount", "pro_member_discount")
        }),
        ("Documents", {
            "fields": ("proforma_pdf", "invoice_pdf", "receipt_pdf", "credit_note_pdf", "voucher_pdf", "other_documents"),
            "classes": ("collapse",),
        }),
        ("Items & Details", {
            "fields": ("items", "supply_details", "payment_details", "additional_options", "notes"),
            "classes": ("collapse",),
        }),
        ("Relationships", {
            "fields": ("source_query",)
        }),
        ("Metadata", {
            "fields": ("reference", "tags", "next_schedule_date", "created_by", "updated_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    
    def source_query_link(self, obj):
        if obj.source_query:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse("admin:booking_query_change", args=[obj.source_query.id])
            return format_html('<a href="{}">{}</a>', url, obj.source_query.query_reference)
        return "-"
    source_query_link.short_description = "Source Query"
    
    def has_documents(self, obj):
        """Show document availability icons"""
        docs = []
        if obj.proforma_pdf:
            docs.append("P")
        if obj.invoice_pdf:
            docs.append("I")
        if obj.receipt_pdf:
            docs.append("R")
        if obj.credit_note_pdf:
            docs.append("C")
        if obj.voucher_pdf:
            docs.append("V")
        if obj.other_documents:
            docs.append(f"+{len(obj.other_documents)}")
        return " | ".join(docs) if docs else "-"
    has_documents.short_description = "Docs"


# Flight Booking Admin Configurations
class FlightPassengerInline(admin.TabularInline):
    model = FlightPassenger
    extra = 0
    fields = (
        "passenger_reference",
        "passenger_type",
        "title",
        "first_name",
        "last_name",
        "date_of_birth",
        "gender",
        "passport_number",
        "infant_with_passenger",
    )
    readonly_fields = (
        "passenger_reference",
        "passenger_type",
        "title",
        "first_name",
        "last_name",
        "date_of_birth",
        "gender",
        "passport_number",
        "infant_with_passenger",
    )
    can_delete = False


class FlightAncillaryServiceInline(admin.TabularInline):
    model = FlightAncillaryService
    extra = 0
    fields = (
        "passenger",
        "service_type",
        "service_code",
        "service_description",
        "service_price",
    )
    readonly_fields = (
        "passenger",
        "service_type",
        "service_code",
        "service_description",
        "service_price",
    )
    can_delete = False


class FlightBookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking_reference",
        "airiq_pnr",
        "airline_pnr",
        "status",
        "flying_from",
        "flying_to",
        "departure_date",
        "flight_trip",
        "related_booking_link",
    )
    list_filter = ("status", "flight_trip", "departure_date")
    search_fields = ("booking_reference", "airiq_pnr", "airline_pnr", "airiq_track_id")
    readonly_fields = (
        "id",
        "booking_reference",
        "airiq_pnr",
        "airline_pnr",
        "airiq_track_id",
    )

    fieldsets = (
        ("Basic Information", {"fields": ("id", "booking_reference", "status")}),
        (
            "AirIQ Integration",
            {
                "fields": (
                    "airiq_pnr",
                    "airline_pnr",
                    "airiq_track_id",
                    "airiq_request_data",
                    "airiq_response_data",
                )
            },
        ),
        ("Operations", {"fields": ("cancel_remark", "reschedule_remark")}),
        (
            "Flight Details",
            {
                "fields": (
                    "flying_from",
                    "flying_to",
                    "departure_date",
                    "return_date",
                    "flight_trip",
                    "flight_no",
                    "airline_code",
                )
            },
        ),
        ("Hold Management", {"fields": ("hold_expires_at", "payment_expires_at")}),
        (
            "Session Data",
            {
                "fields": (
                    "search_session_data",
                    "selected_flight_data",
                    "pricing_validation_data",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Fare Rules", {"fields": ("fare_rules",), "classes": ("collapse",)}),
    )

    inlines = [FlightPassengerInline, FlightAncillaryServiceInline]

    def get_queryset(self, request):
        return super().get_queryset(request)

    def related_booking_link(self, obj):
        """Get the related booking for this flight booking"""
        try:
            booking = Booking.objects.get(flight_booking=obj)
            url = reverse("admin:booking_booking_change", args=[booking.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                booking.confirmation_code or f"Booking #{booking.id}",
            )
        except Booking.DoesNotExist:
            return "-"

    related_booking_link.short_description = "Related Booking"


class FlightPassengerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "passenger_reference",
        "passenger_type",
        "full_name",
        "date_of_birth",
        "gender",
        "flight_booking_link",
        "booking_link",
    )
    list_filter = ("passenger_type", "gender", "created_at")
    search_fields = (
        "first_name",
        "last_name",
        "passport_number",
        "flight_booking__booking_reference",
    )
    readonly_fields = ("id", "created_at", "updated_at")

    fieldsets = (
        (
            "Passenger Information",
            {
                "fields": (
                    "id",
                    "passenger_reference",
                    "passenger_type",
                    "title",
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "gender",
                )
            },
        ),
        (
            "Travel Documents",
            {
                "fields": (
                    "passport_number",
                    "passport_expiry",
                    "passport_issued_date",
                    "passport_country_code",
                )
            },
        ),
        (
            "Infant & Frequent Flyer",
            {
                "fields": (
                    "infant_with_passenger",
                    "frequent_flyer_number",
                    "frequent_flyer_airline",
                )
            },
        ),
        ("Ticket Information", {"fields": ("ticket_number", "seat_number")}),
        ("Relationships", {"fields": ("flight_booking", "booking")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def flight_booking_link(self, obj):
        if obj.flight_booking:
            url = reverse(
                "admin:booking_flightbooking_change", args=[obj.flight_booking.id]
            )
            return format_html(
                '<a href="{}">{}</a>', url, obj.flight_booking.booking_reference
            )
        return "-"

    flight_booking_link.short_description = "Flight Booking"

    def booking_link(self, obj):
        if obj.booking:
            url = reverse("admin:booking_booking_change", args=[obj.booking.id])
            return format_html(
                '<a href="{}">{}</a>', url, obj.booking.confirmation_code
            )
        return "-"

    booking_link.short_description = "Main Booking"


class FlightAncillaryServiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "service_type",
        "service_code",
        "service_description",
        "service_price",
        "passenger_link",
        "flight_booking_link",
    )
    list_filter = ("service_type", "created_at")
    search_fields = (
        "service_code",
        "service_description",
        "passenger__first_name",
        "passenger__last_name",
    )
    readonly_fields = ("id", "created_at", "updated_at")

    fieldsets = (
        (
            "Service Information",
            {
                "fields": (
                    "id",
                    "service_type",
                    "airiq_service_id",
                    "service_code",
                    "service_description",
                )
            },
        ),
        ("Pricing", {"fields": ("service_price",)}),
        ("Segment Details", {"fields": ("segment_reference",)}),
        ("Relationships", {"fields": ("flight_booking", "passenger")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def passenger_link(self, obj):
        if obj.passenger:
            return (
                f"{obj.passenger.full_name} (Ref: {obj.passenger.passenger_reference})"
            )
        return "-"

    passenger_link.short_description = "Passenger"

    def flight_booking_link(self, obj):
        if obj.flight_booking:
            url = reverse(
                "admin:booking_flightbooking_change", args=[obj.flight_booking.id]
            )
            return format_html(
                '<a href="{}">{}</a>', url, obj.flight_booking.booking_reference
            )
        return "-"

    flight_booking_link.short_description = "Flight Booking"


# Enhanced Booking Admin with Flight Booking Integration
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "booking_type",
        "confirmation_code",
        "invoice_id",
        "status",
        "created",
        "updated",
        "flight_booking_link",
    )
    list_filter = ("booking_type", "status", "created")
    search_fields = (
        "confirmation_code",
        "user__email",
        "user__first_name",
        "user__last_name",
    )

    def flight_booking_link(self, obj):
        if obj.booking_type == "FLIGHT" and hasattr(obj, "flight_booking"):
            url = reverse(
                "admin:booking_flightbooking_change", args=[obj.flight_booking.id]
            )
            return format_html('<a href="{}">View Flight Details</a>', url)
        return "-"

    flight_booking_link.short_description = "Flight Booking"


# Register all models with their admin configurations
admin.site.register(Invoice, InvoiceAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(HotelBooking)
admin.site.register(HolidayPackageBooking)
admin.site.register(VehicleBooking)
admin.site.register(FlightBooking, FlightBookingAdmin)
admin.site.register(FlightPassenger, FlightPassengerAdmin)
admin.site.register(FlightAncillaryService, FlightAncillaryServiceAdmin)
admin.site.register(TaxRule)
admin.site.register(BookingPaymentDetail, BookingPaymentAdmin)
admin.site.register(Review)
admin.site.register(BookingCommission)
admin.site.register(VisaBooking)
admin.site.register(EventBooking)


class QueryCommunicationInline(admin.TabularInline):
    model = QueryCommunication
    extra = 0
    fields = ("communication_type", "subject", "message", "user", "is_internal", "created")
    readonly_fields = ("created",)
    can_delete = True


class QueryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "query_reference",
        "query_type",
        "raised_by",
        "company",
        "booking_for",
        "status",
        "quote_amount",
        "invoice_link",
        "created",
    )
    list_filter = ("query_type", "status", "booking_for", "created")
    search_fields = (
        "query_reference",
        "raised_by__email",
        "company__company_name",
        "query_data",
    )
    readonly_fields = ("id", "query_reference", "created", "updated")
    inlines = [QueryCommunicationInline]
    
    fieldsets = (
        ("Basic Information", {"fields": ("id", "query_reference", "query_type", "status")}),
        ("User/Company", {"fields": ("raised_by", "company", "booking_for")}),
        ("Referral", {"fields": ("referred_by", "referral_type")}),
        ("Pricing & Invoice", {"fields": ("quote_amount", "invoice", "expires_at")}),
        ("Data", {"fields": ("query_data", "itinerary_details", "admin_notes")}),
        ("Relationships", {"fields": ("booking",)}),
        ("Timestamps", {"fields": ("created", "updated", "active")}),
    )
    
    def invoice_link(self, obj):
        if obj.invoice:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse("admin:booking_invoice_change", args=[obj.invoice.id])
            return format_html('<a href="{}">{} ({})</a>', url, obj.invoice.invoice_number, obj.invoice.invoice_type)
        return "-"
    invoice_link.short_description = "Invoice"


class QueryCommunicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "query",
        "communication_type",
        "subject",
        "user",
        "is_internal",
        "created",
    )
    list_filter = ("communication_type", "is_internal", "created")
    search_fields = ("subject", "message", "query__query_reference")
    readonly_fields = ("created",)


admin.site.register(Query, QueryAdmin)
admin.site.register(QueryCommunication, QueryCommunicationAdmin)
