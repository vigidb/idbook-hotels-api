from rest_framework import serializers, status

# from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import BasePermission

# from apps.authentication.models import *
from .models import (
    Booking,
    HotelBooking,
    HolidayPackageBooking,
    VehicleBooking,
    FlightBooking,
    AppliedCoupon,
    Review,
    BookingPaymentDetail,
    BookingCommission,
    Invoice,
    FlightPassenger,
    FlightAncillaryService,
    VisaBooking,
    EventBooking,
    Query,
    QueryCommunication,
)
from apps.customer.models import Customer
from apps.hotels.utils.db_utils import get_property_gallery
from apps.booking.utils.db_utils import get_booking_commission
from apps.authentication.constants import UserGroups, CORPORATE_GROUPS
from apps.authentication.utils.token_utils import get_user_active_group
from apps.booking.utils.agent_linking_utils import get_agent_for_user

from django.conf import settings
import logging

logger = logging.getLogger(__name__)


# from booking.models import *
# from carts.models import *
# from coupons.models import *
# from customer.models import *
# from holiday_package.models import *
# from hotel_managements.models import *
# from hotels.models import *
# from org_managements.models import *
# from apps.org_resources.models import *
# from payment_gateways.models import *
# from IDBOOKAPI.utils import format_custom_id

import pytz


class BookingCommissionSerializer(serializers.ModelSerializer):
    commission = serializers.FloatField()
    tax_percentage = serializers.FloatField()
    tax_amount = serializers.FloatField()
    com_amnt = serializers.FloatField()
    com_amnt_withtax = serializers.FloatField()
    tcs = serializers.FloatField()
    tds = serializers.FloatField()
    hotelier_amount = serializers.FloatField()
    # hotelier_amount_with_tax = serializers.FloatField()
    final_payout = serializers.FloatField()

    class Meta:
        model = BookingCommission
        fields = "__all__"


class BookingPayoutSerializer(serializers.ModelSerializer):
    commission_info = BookingCommissionSerializer()

    class Meta:
        model = Booking
        fields = (
            "id",
            "confirmation_code",
            "invoice_id",
            "status",
            "is_direct_pay",
            "commission_info",
        )


class BookingSerializerBase(serializers.ModelSerializer):
    """Base BookingSerializer with just Meta - actual methods are in BookingSerializerMixin below"""
    commission_info = BookingCommissionSerializer(required=False, read_only=True)
    invoice_pdf_url = serializers.SerializerMethodField()
    receipt_pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = "__all__"


class QueryCommunicationSerializer(serializers.ModelSerializer):
    """Serializer for QueryCommunication model"""
    user_name = serializers.CharField(source="user.name", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    
    class Meta:
        model = QueryCommunication
        fields = "__all__"
        read_only_fields = ("id", "created", "query", "user")


class QuerySerializer(serializers.ModelSerializer):
    """Unified serializer for all query types"""
    communications = QueryCommunicationSerializer(many=True, read_only=True)
    raised_by_name = serializers.CharField(source="raised_by.name", read_only=True)
    raised_by_email = serializers.EmailField(source="raised_by.email", read_only=True)
    referred_by_name = serializers.CharField(source="referred_by.name", read_only=True)
    company_name = serializers.CharField(source="company.company_name", read_only=True)
    booking_details = serializers.SerializerMethodField()
    invoice_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Query
        fields = "__all__"
        read_only_fields = ("id", "query_reference", "created", "updated", "booking", "invoice")
    
    def get_booking_details(self, obj):
        """Return booking details if query has been converted"""
        if obj.booking:
            return {
                "id": obj.booking.id,
                "reference_code": obj.booking.reference_code,
                "confirmation_code": obj.booking.confirmation_code,
                "status": obj.booking.status,
                "final_amount": str(obj.booking.final_amount),
                "invoice_id": obj.booking.invoice_id,
            }
        return None
    
    def get_invoice_details(self, obj):
        """Return invoice details if invoice exists"""
        if obj.invoice:
            return {
                "id": obj.invoice.id,
                "invoice_number": obj.invoice.invoice_number,
                "invoice_type": obj.invoice.invoice_type,
                "invoice_date": str(obj.invoice.invoice_date) if obj.invoice.invoice_date else None,
                "due_date": str(obj.invoice.due_date) if obj.invoice.due_date else None,
                "total_amount": obj.invoice.total_amount,
                "status": obj.invoice.status,
                "documents": {
                    "proforma_pdf": obj.invoice.proforma_pdf.url if obj.invoice.proforma_pdf else None,
                    "invoice_pdf": obj.invoice.invoice_pdf.url if obj.invoice.invoice_pdf else None,
                    "receipt_pdf": obj.invoice.receipt_pdf.url if obj.invoice.receipt_pdf else None,
                    "credit_note_pdf": obj.invoice.credit_note_pdf.url if obj.invoice.credit_note_pdf else None,
                    "voucher_pdf": obj.invoice.voucher_pdf.url if obj.invoice.voucher_pdf else None,
                    "other_documents": obj.invoice.other_documents or [],
                },
            }
        return None
    
    def validate(self, attrs):
        """Validate query data"""
        request = self.context.get("request")
        user = request.user if request else None
        is_update = self.instance is not None

        # On create: set raised_by and auto-populate company/agent/booking_for from authenticated user.
        # On update: do not change raised_by (preserve the customer who created the query).
        if user and user.is_authenticated and not is_update:
            attrs["raised_by"] = user

            active_group = get_user_active_group(user, request) if request else None
            default_group = active_group or user.default_group

            # Corporate users → corporate booking + company
            if default_group in CORPORATE_GROUPS or getattr(user, "company_id", None):
                attrs["booking_for"] = "CORPORATE"
                # Prefer token company if not explicitly set
                if getattr(user, "company_id", None):
                    attrs["company_id"] = user.company_id

            # Agent users → agent booking + agent link + referral metadata
            elif default_group in (UserGroups.AGENT_GRP, UserGroups.AGENT_ADMIN):
                attrs["booking_for"] = "AGENT"
                agent = get_agent_for_user(user)
                if agent:
                    attrs["agent"] = agent
                    # Default referral metadata if not already provided
                    attrs.setdefault("referred_by", user)
                    attrs.setdefault("referral_type", "AGENT")

            # Everyone else → B2C
            else:
                attrs.setdefault("booking_for", "B2C")

        # On update: ensure raised_by is not in attrs so the original creator is not overwritten
        if is_update and "raised_by" in attrs:
            del attrs["raised_by"]

        # Validate query_data is a dict
        query_data = attrs.get("query_data", {})
        if not isinstance(query_data, dict):
            raise serializers.ValidationError("query_data must be a JSON object")

        return attrs

    def create(self, validated_data):
        """Create a Query object - override to avoid using BookingSerializer's create"""
        query = Query.objects.create(**validated_data)
        # Auto-generate query reference if not provided
        if not query.query_reference:
            query.query_reference = f"QRY-{query.id:06d}"
            query.save(update_fields=["query_reference"])
        return query


# BookingSerializer methods (these were incorrectly nested in QuerySerializer above)
# Keeping them here for backward compatibility - they belong to BookingSerializer

class BookingSerializerMixin:
    """Mixin containing BookingSerializer methods"""
    
    def validation_error_response(self, error_data):
        error_response = {
            "status": "error",
            "message": "Validation Error",
            "errors": [{"field": "non_field_value", "message": error_data}],
            "errorCode": "VALIDATION_ERROR",
        }
        return error_response

    def create_hotel_booking(self, data):
        room_type = data.get("room_type", "DELUXE")
        checkin_time = data.get("checkin_time", None)
        if not checkin_time:
            checkin_time = None
        checkout_time = data.get("checkout_time", None)
        if not checkout_time:
            checkout_time = None
        bed_count = data.get("bed_count", 1)

        enquired_property = data.get("enquired_property", "")
        booking_slot = data.get("booking_slot", "24 HOURS")
        requested_room_no = data.get("requested_room_no", 1)

        try:
            hotel_booking = HotelBooking.objects.create(
                room_type=room_type,
                checkin_time=checkin_time,
                checkout_time=checkout_time,
                bed_count=bed_count,
                enquired_property=enquired_property,
                booking_slot=booking_slot,
                requested_room_no=requested_room_no,
            )
        except Exception as e:
            print(e)
            error_response = self.validation_error_response(e)
            raise serializers.ValidationError(error_response)
        return hotel_booking

    def create_holidaypack_booking(self, data):
        enquired_holidaypack = data.get("enquired_holidaypack", "")
        no_days = data.get("no_days", 0)
        available_start_date = data.get("available_start_date", "")
        if not available_start_date:
            available_start_date = None
        try:
            holidaypack_booking = HolidayPackageBooking.objects.create(
                enquired_holiday_package=enquired_holidaypack,
                no_days=no_days,
                available_start_date=available_start_date,
            )
        except Exception as e:
            print(e)
            error_response = self.validation_error_response(e)
            raise serializers.ValidationError(error_response)
        return holidaypack_booking

    def create_vehicle_booking(self, data):
        pickup_addr = data.get("pickup_addr", "")
        dropoff_addr = data.get("dropoff_addr", "")
        pickup_time = data.get("pickup_time", "")
        if not pickup_time:
            pickup_time = None
        vehicle_type = data.get("vehicle_type", "CAR")

        try:
            vehicle_booking = VehicleBooking.objects.create(
                pickup_addr=pickup_addr,
                dropoff_addr=dropoff_addr,
                pickup_time=pickup_time,
                vehicle_type=vehicle_type,
            )
        except Exception as e:
            print(e)
            error_response = self.validation_error_response(e)
            raise serializers.ValidationError(error_response)

        return vehicle_booking

    def create_visa_booking(self, data):
        """Create visa booking - similar to create_hotel_booking"""
        destination_country = data.get("destination_country", "")
        travel_date = data.get("travel_date", None)
        visa_type = data.get("visa_type", "tourist")
        passport_number = data.get("passport_number", "")
        passport_expiry = data.get("passport_expiry", None)
        travel_purpose = data.get("travel_purpose", "")
        documents_uploaded = data.get("documents_uploaded", {})
        special_requirements = data.get("special_requirements", "")
        itinerary_details = data.get("itinerary_details", {})
        admin_notes = data.get("admin_notes", "")
        status = data.get("status", "pending")
        
        try:
            visa_booking = VisaBooking.objects.create(
                destination_country=destination_country,
                travel_date=travel_date,
                visa_type=visa_type,
                passport_number=passport_number,
                passport_expiry=passport_expiry,
                travel_purpose=travel_purpose,
                documents_uploaded=documents_uploaded,
                special_requirements=special_requirements,
                itinerary_details=itinerary_details,
                admin_notes=admin_notes,
                status=status,
            )
        except Exception as e:
            print(e)
            error_response = self.validation_error_response(e)
            raise serializers.ValidationError(error_response)
        return visa_booking

    def create_event_booking(self, data):
        """Create event booking - similar to create_hotel_booking"""
        event_name = data.get("event_name", "")
        event_type = data.get("event_type", "other")
        event_date = data.get("event_date", None)
        event_end_date = data.get("event_end_date", None)
        location = data.get("location", "")
        attendee_count = data.get("attendee_count", 1)
        budget_range = data.get("budget_range", None)
        special_requirements = data.get("special_requirements", "")
        itinerary_details = data.get("itinerary_details", {})
        admin_notes = data.get("admin_notes", "")
        status = data.get("status", "pending")
        
        try:
            event_booking = EventBooking.objects.create(
                event_name=event_name,
                event_type=event_type,
                event_date=event_date,
                event_end_date=event_end_date,
                location=location,
                attendee_count=attendee_count,
                budget_range=budget_range,
                special_requirements=special_requirements,
                itinerary_details=itinerary_details,
                admin_notes=admin_notes,
                status=status,
            )
        except Exception as e:
            print(e)
            error_response = self.validation_error_response(e)
            raise serializers.ValidationError(error_response)
        return event_booking

    def get_invoice_pdf_url(self, obj):
        if not obj.invoice_id:
            return None
        invoice = Invoice.objects.filter(invoice_number=obj.invoice_id).first()
        if invoice and invoice.invoice_pdf:
            return invoice.invoice_pdf.url
        return None

    def get_receipt_pdf_url(self, obj):
        # Hotel bookings have a dedicated receipt PDF
        if (
            obj.booking_type == "HOTEL"
            and obj.hotel_booking
            and obj.hotel_booking.hotelier_receipt_pdf
        ):
            return obj.hotel_booking.hotelier_receipt_pdf.url

        invoice_url = self.get_invoice_pdf_url(obj)
        if not invoice_url:
            return None

        try:
            total_paid = float(obj.total_payment_made or 0)
            final_amount = float(obj.final_amount or 0)
        except (TypeError, ValueError):
            total_paid = 0
            final_amount = 0

        if final_amount and total_paid >= final_amount:
            return invoice_url

        return None

    def create_flight_booking(self, data):
        """Enhanced flight booking creation with AirIQ integration"""
        from apps.booking.utils.flight_booking_utils import (
            FlightBookingProcessor,
            FlightBookingAuthManager,
        )
        from apps.flights.services.airiq_service import airiq_service, AirIQException

        # === VALIDATION: Only check truly essential data ===

        # REQUIRED USER DATA (cannot be retrieved from session):
        required_user_data = ["passengers", "contact"]
        for field in required_user_data:
            if not data.get(field):
                raise serializers.ValidationError(
                    {
                        "message": f'Required field "{field}" is missing',
                        "error_code": "MISSING_REQUIRED_DATA",
                    }
                )

        # REQUIRED SESSION LINK (must come from search session):
        if not data.get("session_id") and not (
            data.get("pricing_token") and data.get("track_id")
        ):
            raise serializers.ValidationError(
                {
                    "message": "Either session_id or (pricing_token + track_id) is required.",
                    "error_code": "MISSING_SESSION_LINK",
                }
            )

        # If user only provides track_id, we can retrieve pricing_token from session
        # If user only provides pricing_token, that's also acceptable

        # Extract flight booking data - smart prefilling with user override capability
        flight_data = {
            # === REQUIRED USER DATA (Must be provided) ===
            "passengers": data["passengers"],  # User MUST provide passenger details
            "contact": data["contact"],  # User MUST provide contact info
            "block_pnr": data.get("block_pnr", False),  # User choice: hold vs immediate
            # === SMART PREFILLING (Use stored data as defaults, allow user overrides) ===
            # Session linking (user provides at least one)
            "pricing_token": data.get("pricing_token", ""),
            "track_id": data.get("track_id", ""),
            # Flight segments (usually from pricing, allow user override for flexibility)
            "flight_segments": data.get("flight_segments", []),
            # Trip details (usually from search, allow user override)
            "base_origin": data.get("base_origin", data.get("flying_from", "")),
            "base_destination": data.get("base_destination", data.get("flying_to", "")),
            "trip_type": data.get("trip_type", "O"),
            # Passenger counts (usually from search, allow user override)
            "adult_count": data.get("adult_count", 1),
            "child_count": data.get("child_count", 0),
            "infant_count": data.get("infant_count", 0),
            # Pricing info (usually from pricing response, allow user override)
            "total_amount": data.get("total_amount", 0),
            # === OPTIONAL USER SELECTIONS ===
            "gst_info": data.get("gst_info", {}),  # Optional: GST invoice details
            "seats": data.get("seats", []),  # Optional: seat preferences
            "baggage": data.get("baggage", []),  # Optional: extra baggage
            "meals": data.get("meals", []),  # Optional: meal preferences
            "other_services": data.get("other_services", []),  # Optional: other SSR
            "frequent_flyer": data.get("frequent_flyer", []),  # Optional: FF numbers
            # === LEGACY COMPATIBILITY FIELDS ===
            "flight_trip": data.get("flight_trip", "ROUND"),
            "flight_class": data.get("flight_class", "ECONOMY"),
            "departure_date": data.get("departure_date"),
            "return_date": data.get("return_date"),
            "flying_from": data.get("flying_from", ""),
            "flying_to": data.get("flying_to", ""),
            "flight_no": data.get("flight_no", ""),
            "airline_code": data.get("airline_code", ""),
        }

        try:
            # For basic flight booking (legacy compatibility)
            if not flight_data.get("pricing_token"):
                # Simple flight booking without AirIQ
                flight_booking = FlightBooking.objects.create(
                    flight_trip=flight_data["flight_trip"],
                    flight_class=flight_data["flight_class"],
                    departure_date=flight_data["departure_date"],
                    return_date=flight_data["return_date"],
                    flying_from=flight_data["flying_from"],
                    flying_to=flight_data["flying_to"],
                    flight_no=flight_data["flight_no"],
                    airline_code=flight_data["airline_code"],
                    status="INITIATED",
                )
                return flight_booking

            # Enhanced flight booking with AirIQ integration
            request = self.context.get("request")
            user = request.user if request else None

            # Handle authentication (authenticated vs guest)
            auth_manager = FlightBookingAuthManager(flight_data, user)
            is_eligible, message, validated_user = (
                auth_manager.validate_user_eligibility()
            )

            if not is_eligible and "email verification required" in message:
                # For guest bookings, we'll create a basic flight booking first
                # The complete processing will happen after OTP verification
                flight_booking = FlightBooking.objects.create(
                    flight_trip=flight_data["flight_trip"],
                    flight_class=flight_data["flight_class"],
                    departure_date=flight_data["departure_date"],
                    return_date=flight_data["return_date"],
                    flying_from=flight_data["flying_from"],
                    flying_to=flight_data["flying_to"],
                    flight_no=flight_data["flight_no"],
                    airline_code=flight_data["airline_code"],
                    status="VERIFICATION_PENDING",
                    selected_flight_data={
                        "segments": flight_data["flight_segments"],
                        "pricing_token": flight_data["pricing_token"],
                        "requires_verification": True,
                    },
                    search_session_data={
                        "track_id": flight_data["track_id"],
                        "trip_type": flight_data["trip_type"],
                        "guest_booking_data": flight_data,
                    },
                )

                # Store verification requirement info
                flight_booking.booking_reference = f"TEMP_{flight_booking.id}"
                flight_booking.save()

                return flight_booking

            elif not is_eligible:
                raise serializers.ValidationError(
                    {"message": message, "error_code": "AUTHENTICATION_ERROR"}
                )

            # Process full flight booking for authenticated users
            processor = FlightBookingProcessor(validated_user, flight_data)

            # Validate booking data
            if not processor.validate_booking_data():
                raise serializers.ValidationError(
                    {
                        "message": "Flight booking validation failed",
                        "errors": processor.errors,
                        "error_code": "FLIGHT_VALIDATION_ERROR",
                    }
                )

            # Use session-stored data for security and performance
            session_id = flight_data.get("session_id")

            if session_id:
                # Preferred approach: Use session-stored data
                try:
                    from apps.flights.models import FlightSearchSession

                    session = FlightSearchSession.objects.get(
                        session_id=session_id, expires_at__gt=timezone.now()
                    )

                    # Validate session has required data
                    if not session.selected_flight_data:
                        raise ValueError(
                            "No flight selected in session. Please select a flight first."
                        )

                    if not session.pricing_data:
                        raise ValueError(
                            "No pricing data in session. Please get pricing first."
                        )

                    # Check if pricing is expired (AirIQ pricing typically expires quickly)
                    if (
                        session.pricing_expires_at
                        and timezone.now() > session.pricing_expires_at
                    ):
                        raise ValueError(
                            "Pricing data expired. Please refresh pricing."
                        )

                    # Use session data
                    flight_data["flight_segments"] = session.selected_flight_data.get(
                        "segments", []
                    )
                    flight_data["total_amount"] = float(
                        session.pricing_data.get("total_amount", 0)
                    )
                    flight_data["base_amount"] = float(
                        session.pricing_data.get("base_amount", 0)
                    )
                    flight_data["pricing_token"] = session.pricing_token
                    flight_data["track_id"] = session.airiq_track_id

                    # Add ancillary services from session
                    flight_data["seats"] = session.selected_seats
                    flight_data["meals"] = session.selected_meals
                    flight_data["baggage"] = session.selected_baggage
                    flight_data["other_services"] = session.selected_other_services

                    # Calculate final amount including ancillary services
                    ancillary_cost = 0
                    for seat in session.selected_seats:
                        ancillary_cost += float(seat.get("amount", 0))
                    for meal in session.selected_meals:
                        ancillary_cost += float(meal.get("amount", 0))
                    for baggage in session.selected_baggage:
                        ancillary_cost += float(baggage.get("amount", 0))
                    for service in session.selected_other_services:
                        ancillary_cost += float(service.get("amount", 0))

                    flight_data["total_amount"] += ancillary_cost

                    logger.info(
                        f"Using session data for booking - Base: {session.pricing_data.get('total_amount', 0)}, Ancillary: {ancillary_cost}, Total: {flight_data['total_amount']}"
                    )

                except FlightSearchSession.DoesNotExist:
                    raise serializers.ValidationError(
                        {
                            "message": "Invalid or expired session_id. Please search for flights again.",
                            "error_code": "INVALID_SESSION",
                        }
                    )
                except Exception as e:
                    logger.error(f"Error using session data: {str(e)}")
                    raise serializers.ValidationError(
                        {
                            "message": f"Unable to use session data. Error: {str(e)}",
                            "error_code": "SESSION_DATA_ERROR",
                        }
                    )
            else:
                # Fallback: Manual data entry (less secure, requires validation)
                flight_segments = flight_data.get("flight_segments", [])
                total_amount = flight_data.get("total_amount", 0)

                if not flight_segments or not total_amount:
                    raise serializers.ValidationError(
                        {
                            "message": "When not using session_id, you must provide complete flight_segments and total_amount data.",
                            "error_code": "MISSING_MANUAL_DATA",
                        }
                    )

                # Validate flight segments structure
                for i, segment in enumerate(flight_segments):
                    required_fields = [
                        "FlightID",
                        "FlightNumber",
                        "Origin",
                        "Destination",
                        "DepartureDateTime",
                        "ArrivalDateTime",
                    ]
                    missing_fields = [
                        field for field in required_fields if not segment.get(field)
                    ]
                    if missing_fields:
                        raise ValueError(
                            f"Segment {i+1} missing required fields: {', '.join(missing_fields)}"
                        )

                flight_data["total_amount"] = float(total_amount)
                logger.warning(
                    f"Using manual flight data for booking - Total: {flight_data['total_amount']}"
                )

            # Create AirIQ booking if needed
            airiq_response = None
            if flight_data.get("pricing_token") and flight_data.get("track_id"):
                try:
                    # Smart prefilling: Use stored data as defaults, allow user overrides
                    airiq_booking_data = {
                        # === PASSENGER COUNTS (prefill from stored data if not provided) ===
                        "adults": flight_data.get("adult_count", 1),
                        "children": flight_data.get("child_count", 0),
                        "infants": flight_data.get("infant_count", 0),
                        # === REQUIRED USER DATA (must be provided) ===
                        "passengers": flight_data["passengers"],
                        "contact": flight_data["contact"],
                        # === FLIGHT DATA (prefill from stored session/pricing) ===
                        "token": flight_data.get("pricing_token", ""),
                        "flight_segments": flight_data.get("flight_segments", []),
                        "trip_type": flight_data.get("trip_type", "O"),
                        "origin": flight_data.get(
                            "base_origin", flight_data.get("flying_from", "")
                        ),
                        "destination": flight_data.get(
                            "base_destination", flight_data.get("flying_to", "")
                        ),
                        "total_amount": flight_data.get("total_amount", 0),
                        # === OPTIONAL USER SELECTIONS ===
                        "gst": flight_data.get("gst_info", {}),
                        "seats": flight_data.get("seats", []),
                        "baggage": flight_data.get("baggage", []),
                        "meals": flight_data.get("meals", []),
                        "other_services": flight_data.get("other_services", []),
                        "frequent_flyer": flight_data.get("frequent_flyer", []),
                    }

                    # Call existing AirIQ service method
                    airiq_response = airiq_service.create_booking(
                        booking_data=airiq_booking_data,
                        track_id=flight_data["track_id"],
                        block_pnr=flight_data["block_pnr"],
                    )

                except AirIQException as e:
                    # If AirIQ fails, create local booking without AirIQ data
                    print(f"AirIQ booking failed: {e}")
                    airiq_response = None

            # Determine correct booking status based on block_pnr and AirIQ response
            if flight_data["block_pnr"]:
                # Block PNR = true: Create held booking, allow delayed payment
                booking_status = "HELD"
            else:
                # Block PNR = false: Create pending payment booking, require immediate payment
                booking_status = "PENDING_PAYMENT"

            # Only set to CONFIRMED if AirIQ returned success and we have PNR data
            if (
                airiq_response
                and airiq_response.get("AirIqPNR")
                and not flight_data["block_pnr"]
            ):
                # For immediate bookings, if AirIQ succeeded, we still need payment before confirmation
                booking_status = "PENDING_PAYMENT"

            # Create comprehensive flight booking
            flight_booking_data = {
                "flight_trip": flight_data["flight_trip"],
                "flight_class": flight_data["flight_class"],
                "departure_date": flight_data["departure_date"],
                "return_date": flight_data["return_date"],
                "flying_from": flight_data["flying_from"],
                "flying_to": flight_data["flying_to"],
                "flight_no": flight_data["flight_no"],
                "airline_code": flight_data["airline_code"],
                "booking_reference": processor.generate_confirmation_code(),
                "status": booking_status,
                "booking_mode": "REALTIME",
                "selected_flight_data": {
                    "segments": flight_data["flight_segments"],
                    "pricing_token": flight_data["pricing_token"],
                },
                "search_session_data": {
                    "track_id": flight_data["track_id"],
                    "trip_type": flight_data["trip_type"],
                    "passenger_counts": {
                        "adults": flight_data["adult_count"],
                        "children": flight_data["child_count"],
                        "infants": flight_data["infant_count"],
                    },
                },
            }

            # Handle AirIQ response based on all documented response types
            if airiq_response:
                # Extract status information
                status_info = airiq_response.get("Status", {})
                result_code = status_info.get("ResultCode", "-1")
                error_message = status_info.get("Error", "")
                booking_response = airiq_response.get("Bookingresponse", {})
                itinerary_details = booking_response.get("ItinearyDetails")

                # Handle different response types according to AirIQ docs
                if result_code == "1":  # Success
                    if itinerary_details:
                        # Extract booking details from successful response
                        flight_booking_data.update(
                            {
                                "airiq_pnr": itinerary_details.get("AirIqPNR", ""),
                                "airline_pnr": itinerary_details.get("AirlinePNR", ""),
                                "airiq_track_id": airiq_response.get(
                                    "TrackId", flight_data["track_id"]
                                ),
                            }
                        )

                        # Set hold expiry if booking is blocked
                        if flight_data["block_pnr"] and itinerary_details.get(
                            "HoldExpiry"
                        ):
                            from dateutil import parser

                            try:
                                flight_booking_data["hold_expires_at"] = parser.parse(
                                    itinerary_details["HoldExpiry"]
                                )
                            except (ValueError, TypeError):
                                from datetime import datetime, timedelta
                                from django.utils import timezone

                                flight_booking_data["hold_expires_at"] = (
                                    timezone.now() + timedelta(minutes=30)
                                )

                        logger.info(
                            f"AirIQ booking successful - PNR: {flight_booking_data.get('airiq_pnr')}"
                        )

                elif (
                    result_code == "2"
                ):  # Pending - "The booking might be confirmed. Please check customer care."
                    flight_booking_data.update(
                        {
                            "airiq_track_id": airiq_response.get(
                                "TrackId", flight_data["track_id"]
                            ),
                            "status": "PENDING_CONFIRMATION",  # Special status for pending bookings
                        }
                    )
                    logger.warning(
                        f"AirIQ booking pending - TrackId: {flight_booking_data['airiq_track_id']}, Message: {error_message}"
                    )

                elif (
                    result_code == "0"
                ):  # Failure (e.g., "The requested token was timed out")
                    flight_booking_data.update(
                        {
                            "airiq_track_id": airiq_response.get(
                                "TrackId", flight_data["track_id"]
                            ),
                            "status": "FAILED",
                        }
                    )
                    logger.error(f"AirIQ booking failed - Error: {error_message}")
                    # Still create local booking for user reference, but mark as failed

                elif (
                    result_code == "-1"
                ):  # Exception (e.g., "EX-Unable to book for the requested segments")
                    flight_booking_data.update(
                        {
                            "airiq_track_id": airiq_response.get(
                                "TrackId", flight_data["track_id"]
                            ),
                            "status": "FAILED",
                        }
                    )
                    logger.error(f"AirIQ booking exception - Error: {error_message}")
                    # Still create local booking for user reference, but mark as failed

                # Store the full AirIQ response for debugging
                if "selected_flight_data" not in flight_booking_data:
                    flight_booking_data["selected_flight_data"] = {}
                flight_booking_data["selected_flight_data"][
                    "airiq_response"
                ] = airiq_response

            else:
                # Even without AirIQ response, save the track_id for later use
                flight_booking_data["airiq_track_id"] = flight_data["track_id"]
                logger.warning(
                    "No AirIQ response received - booking created locally only"
                )

            flight_booking = FlightBooking.objects.create(**flight_booking_data)

            # Store additional data for later processing
            flight_booking._passenger_data = flight_data["passengers"]
            flight_booking._ancillary_data = {
                "seats": flight_data["seats"],
                "baggage": flight_data["baggage"],
                "meals": flight_data["meals"],
                "other_services": flight_data["other_services"],
            }

            return flight_booking

        except Exception as e:
            print(f"Flight booking creation error: {e}")
            error_response = self.validation_error_response(str(e))
            raise serializers.ValidationError(error_response)

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user

        hotel_booking, holidaypack_booking = None, None
        vehicle_booking, flight_booking = None, None
        visa_booking, event_booking = None, None
        company = None

        booking_type = validated_data.get("booking_type", "HOTEL")
        adult_count = validated_data.get("adult_count", 1)
        child_count = validated_data.get("child_count", 0)
        infant_count = validated_data.get("infant_count", 0)
        company = validated_data.get("company", None)
        child_age_list = validated_data.get("child_age_list", [])

        if not isinstance(child_age_list, list):
            child_age_list = []

        if booking_type == "HOTEL":
            hotel_booking = self.create_hotel_booking(request.data)

        elif booking_type == "HOLIDAYPACK":
            holidaypack_booking = self.create_holidaypack_booking(request.data)

        elif booking_type == "VEHICLE":
            vehicle_booking = self.create_vehicle_booking(request.data)

        elif booking_type == "FLIGHT":
            flight_booking = self.create_flight_booking(request.data)

        elif booking_type == "VISA":
            visa_booking = self.create_visa_booking(request.data)

        elif booking_type == "EVENT":
            event_booking = self.create_event_booking(request.data)

        company_detail = Booking(
            user=user,
            booking_type=booking_type,
            hotel_booking=hotel_booking,
            holiday_package_booking=holidaypack_booking,
            vehicle_booking=vehicle_booking,
            flight_booking=flight_booking,
            visa_booking=visa_booking,
            event_booking=event_booking,
            adult_count=adult_count,
            child_count=child_count,
            infant_count=infant_count,
            company=company,
            child_age_list=child_age_list,
        )

        # Calculate pricing for flight bookings
        if booking_type == "FLIGHT" and flight_booking:
            from apps.booking.utils.flight_booking_utils import FlightBookingProcessor

            # Calculate comprehensive pricing using current request data
            try:
                processor = FlightBookingProcessor(user, request.data)
                pricing = processor.calculate_pricing()

                # Update booking with calculated pricing
                company_detail.subtotal = pricing["subtotal"]
                company_detail.gst_amount = pricing["gst_amount"]
                company_detail.gst_percentage = pricing["gst_percentage"]
                company_detail.gst_type = pricing["gst_type"]
                company_detail.service_tax = pricing["service_tax"]
                company_detail.final_amount = pricing["final_amount"]

            except Exception as e:
                print(f"Error calculating flight booking pricing: {e}")
                # Set minimal pricing data if calculation fails
                company_detail.final_amount = float(request.data.get("total_amount", 0))
                company_detail.subtotal = company_detail.final_amount

            # Set booking status based on flight booking status and payment requirement
            if flight_booking.status in ["CONFIRMED", "TICKETED"]:
                company_detail.status = "confirmed"
            elif flight_booking.status == "HELD":
                company_detail.status = "pending"  # Held booking awaiting payment
            elif flight_booking.status == "PENDING_PAYMENT":
                company_detail.status = "pending"  # Immediate booking awaiting payment
            elif flight_booking.status == "PENDING_CONFIRMATION":
                company_detail.status = "pending"  # AirIQ booking pending confirmation
            elif flight_booking.status == "FAILED":
                company_detail.status = "canceled"  # AirIQ booking failed
            elif flight_booking.status == "VERIFICATION_PENDING":
                company_detail.status = (
                    "pending"  # Guest booking awaiting OTP verification
                )

            # Set confirmation code
            if (
                flight_booking.booking_reference
                and not flight_booking.booking_reference.startswith("TEMP_")
            ):
                company_detail.confirmation_code = flight_booking.booking_reference

        # Determine booking_source before saving
        from apps.booking.utils.booking_source_utils import determine_booking_source
        company_id = company.id if company else (user.company_id if user else None)
        booking_source = determine_booking_source(
            user=user,
            agent=None,  # Agent will be detected from user if applicable
            company_id=company_id,
            request=request
        )
        company_detail.booking_source = booking_source
        
        # Handle agent linking if booking_source is AGENT
        if booking_source == 'AGENT' and user:
            from apps.booking.utils.agent_linking_utils import get_agent_for_user
            agent_detail = get_agent_for_user(user)
            if agent_detail:
                company_detail.agent = agent_detail

        # Validate company_id requirement for corporate users before saving
        if user:
            from apps.booking.utils.booking_utils import (
                validate_company_id_for_corporate_user,
            )

            # Pass request to get active_group from token
            is_valid, error_message = validate_company_id_for_corporate_user(
                user, company, request=request
            )
            if not is_valid:
                raise serializers.ValidationError(
                    {"company": error_message, "error_code": "COMPANY_ID_REQUIRED"}
                )

        company_detail.save()
        
        # Link customer to agent if booking_source is AGENT
        if booking_source == 'AGENT' and company_detail.user and company_detail.agent:
            from apps.booking.utils.agent_linking_utils import link_customer_to_agent_on_booking
            link_customer_to_agent_on_booking(company_detail, company_detail.agent)

        # Generate access token for all bookings (includes user group info)
        if company_detail.user:
            from apps.booking.utils.booking_utils import generate_guest_access_token

            # Generate token with user information (includes group info)
            if not company_detail.guest_access_token:
                max_attempts = 10
                for attempt in range(max_attempts):
                    guest_token = generate_guest_access_token(
                        company_detail.id, user=company_detail.user
                    )
                    # Check if token already exists (very unlikely but handle it)
                    if not Booking.objects.filter(
                        guest_access_token=guest_token
                    ).exists():
                        company_detail.guest_access_token = guest_token
                        company_detail.save(update_fields=["guest_access_token"])
                        break

        # Calculate and save commission for flight bookings
        if booking_type == "FLIGHT" and company_detail.subtotal:
            from apps.booking.utils.booking_utils import commission_calculation
            from apps.booking.utils.db_utils import add_or_update_booking_commission

            try:
                # For flight bookings, we use None as property_id since it's not property-based
                # You can add flight-specific commission logic here if needed
                commission_details = commission_calculation(
                    property_id=None,  # Flight bookings don't have property_id
                    subtotal=company_detail.subtotal or 0,
                    total_discount=0,  # Apply any flight-specific discount logic here
                    final_amount=company_detail.final_amount or 0,
                    final_tax_amount=company_detail.gst_amount or 0,
                    pay_at_hotel=False,  # Flight bookings are pre-paid
                )

                if commission_details:
                    add_or_update_booking_commission(
                        company_detail.id, commission_details
                    )
                    print(
                        f"Commission calculated and saved for flight booking {company_detail.id}"
                    )

            except Exception as e:
                print(
                    f"Error calculating commission for flight booking {company_detail.id}: {e}"
                )
                # Continue even if commission calculation fails

        # Process flight booking passengers and services after main booking is saved
        if (
            booking_type == "FLIGHT"
            and flight_booking
            and hasattr(flight_booking, "_passenger_data")
        ):
            try:
                self._process_flight_booking_details(company_detail, flight_booking)
            except Exception as e:
                print(f"Error processing flight booking details: {e}")
                # Continue even if passenger processing fails

        # Handle payment redirect for block_pnr=false bookings
        if (
            booking_type == "FLIGHT"
            and flight_booking
            and flight_booking.status == "PENDING_PAYMENT"
            and not request.data.get("block_pnr", False)
        ):

            # Return payment redirect information
            payment_redirect_data = {
                "booking_id": company_detail.id,
                "amount": float(company_detail.final_amount),
                "payment_required": True,
                "redirect_to_payment": True,
                "message": "Payment is required to confirm this booking",
            }

            # Attach payment redirect info to the booking object for response handling
            company_detail._payment_redirect_required = True
            company_detail._payment_redirect_data = payment_redirect_data

        return company_detail

    def _process_flight_booking_details(self, booking, flight_booking):
        """Process flight booking passengers and ancillary services"""
        from apps.booking.utils.flight_booking_utils import FlightBookingProcessor

        # Get stored passenger data
        passenger_data = getattr(flight_booking, "_passenger_data", [])
        ancillary_data = getattr(flight_booking, "_ancillary_data", {})

        if not passenger_data:
            return

        # Create processor to handle passengers and services
        flight_data = flight_booking.search_session_data.get("guest_booking_data", {})
        if flight_data:
            flight_data["passengers"] = passenger_data
            flight_data.update(ancillary_data)

            processor = FlightBookingProcessor(booking.user, flight_data)

            # Create passengers
            try:
                passengers = processor.create_passengers(booking, flight_booking)
                print(f"Created {len(passengers)} passengers for booking {booking.id}")
            except Exception as e:
                print(f"Error creating passengers: {e}")
                passengers = []

            # Create ancillary services
            try:
                services = processor.create_ancillary_services(
                    flight_booking, passengers
                )
                print(
                    f"Created {len(services)} ancillary services for booking {booking.id}"
                )
            except Exception as e:
                print(f"Error creating ancillary services: {e}")

            # Send notifications for confirmed bookings
            if booking.status == "confirmed":
                try:
                    from apps.booking.tasks import (
                        send_booking_email_task,
                        send_flight_booking_task,
                    )

                    send_booking_email_task.delay(
                        booking.id, "flight-booking-confirmation"
                    )
                    send_flight_booking_task.delay(booking.id, "confirmed")
                except Exception as e:
                    print(f"Error sending notifications: {e}")

        # raise serializers.ValidationError({'message': 'Internal Server Error'})

    def holiday_package_representation(self, holidaypack_booking):
        holiday_package_json = {}
        confirmed_hpackage_json = {}
        no_days = holidaypack_booking.no_days
        available_start_date = holidaypack_booking.available_start_date
        enquired_holiday_package = holidaypack_booking.enquired_holiday_package
        confirmed_hpackage = holidaypack_booking.confirmed_holiday_package
        if confirmed_hpackage:
            id = confirmed_hpackage.id
            trip_id = confirmed_hpackage.trip_id
            trip_name = confirmed_hpackage.trip_name
            tour_duration = confirmed_hpackage.tour_duration
            total_booking_amount = confirmed_hpackage.total_booking_amount
            confirmed_hpackage_json = {
                "trip_id": trip_id,
                "trip_name": trip_name,
                "tour_duration": tour_duration,
                "total_booking_amount": total_booking_amount,
            }

        holiday_package_json = {
            "id": holidaypack_booking.id,
            "no_days": no_days,
            "available_start_date": available_start_date,
            "enquired_holiday_package": enquired_holiday_package,
            "confirmed_holiday_package": confirmed_hpackage_json,
        }

        return holiday_package_json

    def flight_representation(self, flight_booking):
        """Create flight booking representation for API response"""
        flight_json = {}

        # Basic flight details
        flight_no = flight_booking.flight_no
        airline_code = flight_booking.airline_code
        flight_trip = flight_booking.flight_trip
        flight_class = flight_booking.flight_class
        departure_date = flight_booking.departure_date
        arrival_date = flight_booking.arrival_date
        return_date = flight_booking.return_date
        return_arrival_date = flight_booking.return_arrival_date
        flying_from = flight_booking.flying_from
        flying_to = flight_booking.flying_to
        return_from = flight_booking.return_from
        return_to = flight_booking.return_to

        # AirIQ details
        booking_reference = flight_booking.booking_reference
        airiq_pnr = flight_booking.airiq_pnr
        airline_pnr = flight_booking.airline_pnr
        airiq_track_id = flight_booking.airiq_track_id
        status = flight_booking.status
        booking_mode = flight_booking.booking_mode

        # Flight data
        selected_flight_data = flight_booking.selected_flight_data or {}
        search_session_data = flight_booking.search_session_data or {}

        # Ticket details
        ticket_numbers = flight_booking.ticket_numbers or []
        flight_ticket = (
            flight_booking.flight_ticket.url if flight_booking.flight_ticket else None
        )

        # Expiry and timestamps
        hold_expires_at = flight_booking.hold_expires_at
        confirmed_at = flight_booking.confirmed_at
        cancelled_at = flight_booking.cancelled_at

        # Passengers
        passengers = []
        if hasattr(flight_booking, "passengers"):
            for passenger in flight_booking.passengers.all():
                passenger_info = {
                    "id": passenger.id,
                    "passenger_reference": passenger.passenger_reference,
                    "passenger_type": passenger.passenger_type,
                    "title": passenger.title,
                    "first_name": passenger.first_name,
                    "last_name": passenger.last_name,
                    "full_name": passenger.full_name,
                    "date_of_birth": (
                        passenger.date_of_birth.isoformat()
                        if passenger.date_of_birth
                        else None
                    ),
                    "gender": passenger.gender,
                    "passport_number": passenger.passport_number,
                    "ticket_number": passenger.ticket_number,
                    "seat_number": passenger.seat_number,
                }
                passengers.append(passenger_info)

        # Ancillary services
        ancillary_services = []
        if hasattr(flight_booking, "ancillary_services"):
            for service in flight_booking.ancillary_services.all():
                service_info = {
                    "id": service.id,
                    "service_type": service.service_type,
                    "service_code": service.service_code,
                    "service_description": service.service_description,
                    "service_price": float(service.service_price),
                    "passenger_name": (
                        service.passenger.full_name if service.passenger else None
                    ),
                }
                ancillary_services.append(service_info)

        flight_json = {
            "id": flight_booking.id,
            "flight_no": flight_no,
            "airline_code": airline_code,
            "flight_trip": flight_trip,
            "flight_class": flight_class,
            "departure_date": departure_date.isoformat() if departure_date else None,
            "arrival_date": arrival_date.isoformat() if arrival_date else None,
            "return_date": return_date.isoformat() if return_date else None,
            "return_arrival_date": (
                return_arrival_date.isoformat() if return_arrival_date else None
            ),
            "flying_from": flying_from,
            "flying_to": flying_to,
            "return_from": return_from,
            "return_to": return_to,
            "booking_reference": booking_reference,
            "airiq_pnr": airiq_pnr,
            "airline_pnr": airline_pnr,
            "airiq_track_id": airiq_track_id,
            "status": status,
            "booking_mode": booking_mode,
            "selected_flight_data": selected_flight_data,
            "search_session_data": search_session_data,
            "ticket_numbers": ticket_numbers,
            "flight_ticket": flight_ticket,
            "hold_expires_at": hold_expires_at.isoformat() if hold_expires_at else None,
            "confirmed_at": confirmed_at.isoformat() if confirmed_at else None,
            "cancelled_at": cancelled_at.isoformat() if cancelled_at else None,
            "is_expired": (
                flight_booking.is_expired
                if hasattr(flight_booking, "is_expired")
                else False
            ),
            "passengers": passengers,
            "ancillary_services": ancillary_services,
            "passenger_count": len(passengers),
            "total_ancillary_cost": sum(
                service["service_price"] for service in ancillary_services
            ),
            # New multi-itinerary/PNR fields
            "airiq_pnrs": getattr(flight_booking, "airiq_pnrs", []) or [],
            "airline_pnrs": getattr(flight_booking, "airline_pnrs", []) or [],
            "airiq_track_ids": getattr(flight_booking, "airiq_track_ids", []) or [],
            "booked_itineraries": getattr(flight_booking, "booked_itineraries", [])
            or [],
            # AirIQ booking response
            # 'airiq_booking_response': self._get_airiq_booking_response(flight_booking),
            "airiq_raw_response": getattr(flight_booking, "airiq_response_data", {})
            or {},
        }

        return flight_json

    def _get_airiq_booking_response(self, flight_booking):
        """Extract AirIQ Bookingresponse from airiq_response_data"""
        airiq_raw = getattr(flight_booking, "airiq_response_data", {}) or {}
        if isinstance(airiq_raw, dict):
            return airiq_raw.get("Bookingresponse", {}) or {}
        return {}

    def hotel_representation(self, hotel_booking):
        hotel_json = {}
        confirmed_property_json = {}
        room_json = {}

        enquired_property = hotel_booking.enquired_property
        booking_slot = hotel_booking.booking_slot
        room_type = hotel_booking.room_type
        checkin_time = hotel_booking.checkin_time
        checkout_time = hotel_booking.checkout_time
        bed_count = hotel_booking.bed_count
        requested_room_no = hotel_booking.requested_room_no
        cancellation_details = hotel_booking.cancellation_details
        confirmed_property = hotel_booking.confirmed_property
        hotelier_receipt_pdf = hotel_booking.hotelier_receipt_pdf
        if confirmed_property:
            service_category = confirmed_property.service_category
            address = confirmed_property.address
            name = confirmed_property.name
            title = confirmed_property.title
            area_name = confirmed_property.area_name
            city_name = confirmed_property.city_name
            state = confirmed_property.state
            country = confirmed_property.country
            slug = confirmed_property.slug

            policies = getattr(confirmed_property, "policies", None)
            phone_no = getattr(confirmed_property, "phone_no", None)
            email = getattr(confirmed_property, "email", None)

            # get property gallery
            gallery_property = get_property_gallery(confirmed_property.id)
            gallery_list = []
            if gallery_property:
                property_gallery = list(
                    gallery_property.filter(active=True).values("id", "media")
                )
                for gallery in property_gallery:
                    media_gallery = f"{settings.CDN}{settings.PUBLIC_MEDIA_LOCATION}/{str(gallery.get('media', ''))}"
                    gallery_list.append(media_gallery)

            confirmed_property_json = {
                "id": confirmed_property.id,
                "service_category": service_category,
                "address": address,
                "area_name": area_name,
                "city_name": city_name,
                "state": state,
                "country": country,
                "name": name,
                "title": title,
                "gallery": gallery_list,
                "slug": slug,
                "policies": policies,
                "hotelier_phone_no": phone_no,
                "hotelier_email": email,
            }

        ##        room = hotel_booking.room
        ##        if room:
        ##            room_type = room.room_type
        ##            room_view = room.room_view
        ##            bed_type = room.bed_type
        ##            room_json = {'id':room.id, 'room_type':room_type, 'room_view':room_view,
        ##                         'bed_type':bed_type}

        room_json = hotel_booking.confirmed_room_details
        confirmed_checkin_time = hotel_booking.confirmed_checkin_time
        confirmed_checkout_time = hotel_booking.confirmed_checkout_time
        try:
            booking = Booking.objects.get(hotel_booking=hotel_booking)
        except Booking.DoesNotExist:
            booking = None

        invoice_details = {}
        if booking and booking.invoice_id:
            try:
                invoice = Invoice.objects.get(invoice_number=booking.invoice_id)
                invoice_details = InvoiceSerializer(invoice).data
            except Invoice.DoesNotExist:
                invoice_details = {"error": "Invoice not found"}
        hotel_json = {
            "enquired_property": enquired_property,
            "booking_slot": booking_slot,
            "room_type": room_type,
            "checkin_time": checkin_time,
            "checkout_time": checkout_time,
            "bed_count": bed_count,
            "confirmed_property": confirmed_property_json,
            "room": room_json,
            "confirmed_checkin_time": confirmed_checkin_time,
            "confirmed_checkout_time": confirmed_checkout_time,
            "requested_room_no": requested_room_no,
            "hotelier_receipt_pdf": (
                hotelier_receipt_pdf.url if hotelier_receipt_pdf else None
            ),
            "cancellation_details": cancellation_details,
            "invoice_details": invoice_details,
        }

        return hotel_json

    def vehicle_representation(self, vehicle_booking):
        pickup_addr = vehicle_booking.pickup_addr
        dropoff_addr = vehicle_booking.dropoff_addr
        pickup_time = vehicle_booking.pickup_time
        vehicle_type = vehicle_booking.vehicle_type

        vehicle_json = {
            "pickup_addr": pickup_addr,
            "dropoff_addr": dropoff_addr,
            "pickup_time": pickup_time,
            "vehicle_type": vehicle_type,
        }
        return vehicle_json

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        booking_type = instance.booking_type

        if instance:
            payment_details = instance.booking_payment.values(
                "transaction_id",
                "merchant_transaction_id",
                "code",
                "payment_type",
                "payment_medium",
                "amount",
                "is_transaction_success",
                "transaction_for",
            )

            representation["payment_details"] = list(payment_details)
            booking_payment = list(
                instance.booking_payment.values_list(
                    "merchant_transaction_id", flat=True
                )
            )
            representation["merchant_transaction_ids"] = booking_payment

            representation["final_amount"] = instance.final_amount
            representation["total_payment_made"] = instance.total_payment_made
            if instance.user:
                representation["user"] = {
                    "user_id": instance.user_id,
                    "name": instance.user.name,
                    "email": instance.user.email,
                    "mobile_number": instance.user.mobile_number,
                }
            if booking_type == "HOLIDAYPACK":
                holidaypack_booking = instance.holiday_package_booking
                if holidaypack_booking:
                    holiday_package_json = self.holiday_package_representation(
                        holidaypack_booking
                    )
                    representation["holiday_package_booking"] = holiday_package_json
            elif booking_type == "HOTEL":
                hotel_booking = instance.hotel_booking
                if hotel_booking:
                    hotel_json = self.hotel_representation(hotel_booking)
                    representation["hotel_booking"] = hotel_json
            elif booking_type == "VEHICLE":
                vehicle_booking = instance.vehicle_booking
                if vehicle_booking:
                    vehicle_json = self.vehicle_representation(vehicle_booking)
                    representation["vehicle_booking"] = vehicle_json

            elif booking_type == "FLIGHT":
                flight_booking = instance.flight_booking
                if flight_booking:
                    flight_json = self.flight_representation(flight_booking)
                    representation["flight_booking"] = flight_json

        return representation


# Final BookingSerializer combining base and mixin
class BookingSerializer(BookingSerializerMixin, BookingSerializerBase):
    """Complete BookingSerializer with all methods"""
    pass


class HotelBookingSerializer(serializers.ModelSerializer):

    class Meta:
        model = HotelBooking
        fields = (
            "confirmed_room_details",
            "confirmed_checkin_time",
            "confirmed_checkout_time",
        )


class PreConfirmHotelBookingSerializer(serializers.ModelSerializer):
    hotel_booking = HotelBookingSerializer()
    commission_info = BookingCommissionSerializer()

    class Meta:
        model = Booking
        fields = (
            "id",
            "booking_type",
            "hotel_booking",
            "final_amount",
            "total_discount",
            "gst_amount",
            "discount",
            "pro_member_discount_percent",
            "pro_member_discount_value",
            "subtotal",
            "status",
            "commission_info",
            "agent_markup_percent",
            "agent_markup_amount",
            "final_price_with_markup",
            "pay_with_commission",
        )


class QueryFilterBookingSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    offset = serializers.IntegerField(required=False)
    limit = serializers.IntegerField(required=False)
    search = serializers.CharField(
        required=False, help_text="Available columns: confirmation_code"
    )

    class Meta:
        model = Booking
        fields = (
            "booking_type",
            "status",
            "company_id",
            "user_id",
            "offset",
            "limit",
            "search",
        )


##        extra_kwargs = {
##            'company_id': {
##                'help_text': 'Corporate Id'
##            }
##        }


class QueryFilterUserBookingSerializer(serializers.ModelSerializer):
    offset = serializers.IntegerField(required=False)
    limit = serializers.IntegerField(required=False)
    search = serializers.CharField(
        required=False, help_text="Available columns: confirmation_code"
    )

    class Meta:
        model = Booking
        fields = ("booking_type", "status", "offset", "limit", "search")


##        extra_kwargs = {
##            'company_id': {
##                'help_text': 'Corporate Id'
##            }
##        }


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = "__all__"

    def create(self, validated_data):
        user = self.context["request"].user
        review_instance = Review(**validated_data)
        review_instance.user = user
        review_instance.save()
        return review_instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user = instance.user
        if user:
            name = user.name
            profile_picture = ""
            customer = (
                Customer.objects.filter(user=user).values("profile_picture").first()
            )
            if customer:
                profile_picture = customer.get("profile_picture", "")
            if profile_picture:
                profile_picture = f"{settings.CDN}{settings.PUBLIC_MEDIA_LOCATION}/{str(profile_picture)}"
            representation["user"] = {
                "id": user.id,
                "name": name,
                "profile_picture": profile_picture,
            }
        else:
            representation["user"] = {}
        return representation


class AppliedCouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppliedCoupon
        fields = "__all__"


class BookingPaymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingPaymentDetail
        fields = "__all__"


class PropertyPaymentBookingSerializer(serializers.ModelSerializer):
    confirmed_checkin_time = serializers.DateTimeField(
        source="hotel_booking__confirmed_checkin_time", allow_null=True
    )
    confirmed_checkout_time = serializers.DateTimeField(
        source="hotel_booking__confirmed_checkout_time", allow_null=True
    )
    merchant_transaction_id = serializers.CharField(
        source="booking_payment__merchant_transaction_id", allow_null=True
    )
    payment_type = serializers.CharField(
        source="booking_payment__payment_type", allow_null=True
    )
    payment_medium = serializers.CharField(
        source="booking_payment__payment_medium", allow_null=True
    )
    payment_amount = serializers.DecimalField(
        source="booking_payment__amount",
        allow_null=True,
        max_digits=15,
        decimal_places=6,
    )
    is_transaction_success = serializers.BooleanField(
        source="booking_payment__is_transaction_success", allow_null=True
    )

    class Meta:
        model = Booking
        fields = (
            "id",
            "reference_code",
            "confirmation_code",
            "final_amount",
            "total_payment_made",
            "invoice_id",
            "confirmed_checkin_time",
            "confirmed_checkout_time",
            "merchant_transaction_id",
            "payment_type",
            "payment_medium",
            "payment_amount",
            "is_transaction_success",
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["commission_info"] = None
        booking_id = instance.get("id")  # Get booking ID from the instance
        if booking_id:
            try:
                booking_instance = Booking.objects.get(id=booking_id)
                representation["booking_status"] = booking_instance.status
            except Booking.DoesNotExist:
                representation["booking_status"] = None

        representation["user"] = {
            "id": instance.get("user_id"),
            "email": instance.get("user__email"),
            "mobile_number": instance.get("user__mobile_number"),
            "name": instance.get("user__name"),
        }
        if instance:
            booking_id = instance.get("id", None)
            booking_commission = get_booking_commission(booking_id)
            if booking_commission:
                comm_serailizer = BookingCommissionSerializer(booking_commission)
                representation["commission_info"] = comm_serailizer.data

        return representation


class PaymentMediumSerializer(serializers.Serializer):
    payment_type = serializers.CharField(
        source="booking_payment__payment_type", allow_null=True
    )
    payment_medium = serializers.CharField(
        source="booking_payment__payment_medium", allow_null=True
    )
    total_payment = serializers.DecimalField(
        allow_null=True, max_digits=15, decimal_places=6
    )


class BookingCheckInOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ["is_checkin", "is_checkout"]


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = "__all__"

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        # Set created_by field if user is available
        if user and user.is_authenticated:
            validated_data["created_by"] = str(user.id)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        # Set updated_by field if user is available
        if user and user.is_authenticated:
            validated_data["updated_by"] = str(user.id)

        return super().update(instance, validated_data)

    def transform_items(self, items):
        """Transform items list to change 'price' key to 'rate'"""
        if not items:
            return items

        transformed_items = []
        for item in items:
            if isinstance(item, dict):
                # Create a copy of the item
                transformed_item = item.copy()

                # Change 'price' key to 'rate' if it exists
                if "price" in transformed_item:
                    transformed_item["rate"] = transformed_item.pop("price")

                transformed_items.append(transformed_item)
            else:
                transformed_items.append(item)

        return transformed_items

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # Transform items if they exist in the representation
        if "items" in representation:
            representation["items"] = self.transform_items(representation["items"])

        # Get associated booking details
        bookings = Booking.objects.filter(invoice_id=instance.invoice_number)

        if bookings.exists():
            booking = bookings.first()
            representation["booking"] = {
                "id": booking.id,
                "booking_type": (
                    booking.booking_type if hasattr(booking, "booking_type") else ""
                ),
            }
        # Get associated payment details
        payment_details = BookingPaymentDetail.objects.filter(invoice=instance)
        if payment_details.exists():
            representation["payment_details"] = []
            for payment in payment_details:
                payment_data = {
                    "id": payment.id,
                    "merchant_transaction_id": payment.merchant_transaction_id,
                    "transaction_id": payment.transaction_id,
                    "amount": float(payment.amount) if payment.amount else 0,
                    "payment_type": payment.payment_type,
                    "payment_medium": payment.payment_medium,
                    "is_transaction_success": payment.is_transaction_success,
                    "reference": payment.reference,
                    "created": payment.created.strftime("%Y-%m-%d %H:%M:%S"),
                }
                representation["payment_details"].append(payment_data)

        return representation

    def validate(self, data):
        if self.instance is None and not data.get("invoice_number"):
            raise serializers.ValidationError(
                {"invoice_number": "Invoice number is required"}
            )

        if not self.instance and not data.get("invoice_date"):
            raise serializers.ValidationError(
                {"invoice_date": "Invoice date is required"}
            )

        if not self.instance and not data.get("billed_by"):
            raise serializers.ValidationError({"billed_by": "Billed by is required"})

        # Validate that billed_by exists if provided
        if "billed_by" in data and data["billed_by"] is not None:
            from apps.org_managements.models import BusinessDetail

            billed_by_id = (
                data["billed_by"].id
                if hasattr(data["billed_by"], "id")
                else data["billed_by"]
            )
            if not BusinessDetail.objects.filter(id=billed_by_id).exists():
                raise serializers.ValidationError(
                    {
                        "billed_by": f"BusinessDetail with id {billed_by_id} does not exist. Please ensure an active business is configured."
                    }
                )

        # if not self.instance and not data.get('billed_to'):
        #     raise serializers.ValidationError({"billed_to": "Billed to is required"})

        return data


class FlightPassengerSerializer(serializers.ModelSerializer):
    """Serializer for flight passenger details"""

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = FlightPassenger
        fields = "__all__"

    def validate_date_of_birth(self, value):
        """Validate passenger date of birth"""
        from datetime import date

        if value is not None and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future")
        return value

    def validate_passenger_type(self, value):
        """Validate passenger type based on age"""
        if hasattr(self, "initial_data") and "date_of_birth" in self.initial_data:
            from datetime import date
            from dateutil.relativedelta import relativedelta

            dob = self.initial_data.get("date_of_birth")
            if isinstance(dob, str):
                from datetime import datetime

                try:
                    dob = datetime.strptime(dob, "%Y-%m-%d").date()
                except ValueError:
                    # If date parsing fails, skip age validation
                    return value

            if isinstance(dob, date):
                age = relativedelta(date.today(), dob).years

                if value == "ADT" and age < 12:
                    raise serializers.ValidationError(
                        "Adult passengers must be 12+ years old"
                    )
                elif value == "CHD" and (age < 2 or age >= 12):
                    raise serializers.ValidationError(
                        "Child passengers must be 2-11 years old"
                    )
                elif value == "INF" and age >= 2:
                    raise serializers.ValidationError(
                        "Infant passengers must be under 2 years old"
                    )

        return value


class FlightAncillaryServiceSerializer(serializers.ModelSerializer):
    """Serializer for flight ancillary services"""

    passenger_full_name = serializers.CharField(
        source="passenger.full_name", read_only=True
    )

    class Meta:
        model = FlightAncillaryService
        fields = "__all__"

    def validate_service_price(self, value):
        """Validate service price is positive"""
        if value < 0:
            raise serializers.ValidationError("Service price cannot be negative")
        return value


class FlightBookingDetailSerializer(serializers.ModelSerializer):
    """Enhanced FlightBooking serializer with passenger and service details"""

    passengers = FlightPassengerSerializer(many=True, read_only=True)
    ancillary_services = FlightAncillaryServiceSerializer(many=True, read_only=True)
    is_expired = serializers.ReadOnlyField()

    class Meta:
        model = FlightBooking
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Add computed fields
        representation["passenger_count"] = instance.passengers.count()
        representation["total_ancillary_cost"] = sum(
            service.service_price for service in instance.ancillary_services.all()
        )

        return representation


class VisaBookingSerializer(serializers.ModelSerializer):
    """Serializer for VisaBooking model"""
    
    class Meta:
        model = VisaBooking
        fields = "__all__"
        read_only_fields = ("id", "created", "updated")


class EventBookingSerializer(serializers.ModelSerializer):
    """Serializer for EventBooking model"""
    
    class Meta:
        model = EventBooking
        fields = "__all__"
        read_only_fields = ("id", "created", "updated")
