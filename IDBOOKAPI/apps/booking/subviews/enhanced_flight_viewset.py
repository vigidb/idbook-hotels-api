"""
Enhanced Flight Booking ViewSet
Implements comprehensive flight booking flow with pricing sessions and AirIQ integration
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from django.conf import settings
import logging
import uuid
from decimal import Decimal

from ..models import Booking, FlightBooking, FlightPassenger, FlightAncillaryService
from ..serializers import BookingSerializer
from ..utils.flight_booking_utils import FlightBookingProcessor, FlightBookingAuthManager
from apps.flights.services.pricing_service import flight_pricing_service
from apps.flights.services.airiq_service import airiq_service, AirIQException
from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
from apps.booking.utils.db_utils import (
    create_booking_payment_details,
    update_booking_payment_details,
    get_booking_from_payment,
)
from apps.customer.utils.db_utils import (
    get_wallet_balance,
    get_company_wallet_balance,
    deduct_wallet_balance,
    deduct_company_wallet_balance,
    add_user_wallet_amount,
    add_company_wallet_amount,
)
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin

logger = logging.getLogger(__name__)


class EnhancedFlightBookingViewSet(viewsets.ViewSet, StandardResponseMixin, LoggingMixin):
    """
    Enhanced Flight Booking API with comprehensive pricing flow
    
    Flow:
    1. Search flights → Create pricing session (5-minute cache)
    2. Get detailed pricing → Calculate comprehensive breakdown
    3. Select ancillary services → Update pricing
    4. Create booking → Process payment → Confirm with AirIQ
    5. Issue ticket → Complete booking
    """
    permission_classes = [AllowAny]  # Handle auth in individual methods

    def get_flight_booking(self, booking_id, guest_token=None):
        """Helper to fetch booking and attached flight booking with access validation.
        Supports both authenticated users and guest token access.
        """
        from apps.booking.utils.booking_utils import validate_guest_access_token
        
        # Check if guest_token is provided (from request data or query params)
        if not guest_token and hasattr(self, 'request'):
            guest_token = self.request.data.get('guest_token') or self.request.query_params.get('guest_token')
        
        # If guest_token is provided, validate it and get booking
        if guest_token:
            booking = validate_guest_access_token(guest_token)
            if not booking:
                raise ValueError("Invalid guest token")
            if booking.booking_type != 'FLIGHT':
                raise ValueError("Booking is not a flight booking")
            # If booking_id is provided, verify it matches the booking from token
            if booking_id and booking.id != int(booking_id):
                raise ValueError("Booking ID does not match guest token")
            if not booking.flight_booking:
                raise ValueError("Flight booking details not found")
            return booking, booking.flight_booking
        
        # Standard authenticated user path
        booking = get_object_or_404(
            Booking.objects.select_related('flight_booking'),
            id=booking_id,
            booking_type='FLIGHT'
        )
        # If the requester is authenticated, enforce ownership (non-auth users allowed for now for status webhooks/guest flows)
        if hasattr(self, 'request') and getattr(self.request, 'user', None) and self.request.user.is_authenticated:
            if (booking.user and booking.user_id != self.request.user.id) and not self.request.user.is_staff:
                raise ValueError("Booking not found")
        if not booking.flight_booking:
            raise ValueError("Flight booking details not found")
        return booking, booking.flight_booking

    @swagger_auto_schema(
        method='post',
        operation_description="Create flight booking with automatic pricing validation",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['TrackId', 'PaxDetailsInfo', 'AddressDetails'],
            properties={
                'session_id': openapi.Schema(type=openapi.TYPE_STRING, description='Optional: Pricing session ID from search'),
                'TrackId': openapi.Schema(type=openapi.TYPE_STRING, description='AirIQ Track ID for pricing'),
                'AdultCount': openapi.Schema(type=openapi.TYPE_INTEGER, default=1),
                'ChildCount': openapi.Schema(type=openapi.TYPE_INTEGER, default=0),
                'InfantCount': openapi.Schema(type=openapi.TYPE_INTEGER, default=0),
                'TripType': openapi.Schema(type=openapi.TYPE_STRING, enum=['O', 'R'], default='O'),
                'BaseOrigin': openapi.Schema(type=openapi.TYPE_STRING, description='Origin airport code'),
                'BaseDestination': openapi.Schema(type=openapi.TYPE_STRING, description='Destination airport code'),
                'ItineraryFlightsInfo': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'Token': openapi.Schema(type=openapi.TYPE_STRING),
                            'PaymentInfo': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Items(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        'TotalAmount': openapi.Schema(type=openapi.TYPE_STRING)
                                    }
                                )
                            )
                        }
                    )
                ),
                'PaxDetailsInfo': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'PaxRefNumber': openapi.Schema(type=openapi.TYPE_STRING),
                            'Title': openapi.Schema(type=openapi.TYPE_STRING, enum=['MR', 'MRS', 'MISS', 'MS', 'MSTR', 'DR']),
                            'FirstName': openapi.Schema(type=openapi.TYPE_STRING),
                            'LastName': openapi.Schema(type=openapi.TYPE_STRING),
                            'DOB': openapi.Schema(type=openapi.TYPE_STRING),
                            'Gender': openapi.Schema(type=openapi.TYPE_STRING, enum=['Male', 'Female']),
                            'PaxType': openapi.Schema(type=openapi.TYPE_STRING, enum=['ADT', 'CHD', 'INF']),
                            'PassportNo': openapi.Schema(type=openapi.TYPE_STRING),
                            'PassportExpiry': openapi.Schema(type=openapi.TYPE_STRING),
                            'InfantRef': openapi.Schema(type=openapi.TYPE_STRING)
                        }
                    )
                ),
                'AddressDetails': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'CountryCode': openapi.Schema(type=openapi.TYPE_STRING, default='91'),
                        'ContactNumber': openapi.Schema(type=openapi.TYPE_STRING),
                        'EmailID': openapi.Schema(type=openapi.TYPE_STRING, format='email')
                    }
                ),
                'GSTInfo': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'GSTNumber': openapi.Schema(type=openapi.TYPE_STRING),
                        'GSTCompanyName': openapi.Schema(type=openapi.TYPE_STRING),
                        'GSTAddress': openapi.Schema(type=openapi.TYPE_STRING),
                        'GSTEmailID': openapi.Schema(type=openapi.TYPE_STRING),
                        'GSTMobileNumber': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                ),
                'BlockPNR': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False),
                'guest_booking': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False),
                'otp': openapi.Schema(type=openapi.TYPE_STRING, description='OTP for guest booking verification'),
                'company_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Company ID (required for corporate users)')
            }
        ),
        responses={
            201: openapi.Response(
                description="Booking created successfully - payment required",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'booking_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'booking_reference': openapi.Schema(type=openapi.TYPE_STRING),
                                'status': openapi.Schema(type=openapi.TYPE_STRING),
                                'total_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'payment_expires_at': openapi.Schema(type=openapi.TYPE_STRING, format='datetime'),
                                'payment_lock_duration': openapi.Schema(type=openapi.TYPE_INTEGER, description='Minutes')
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description="Invalid request data or insufficient balance"),
            402: openapi.Response(description="Payment required"),
            500: openapi.Response(description="Booking creation failed")
        }
    )
    @action(detail=False, methods=['post'], url_path='create-booking')
    def create_booking(self, request):
        """
        Create flight booking with automatic pricing validation and agent balance check
        Supports both session-based and direct booking requests
        """
        try:
            # Validate required fields for direct booking
            track_id = request.data.get('TrackId')
            if not track_id:
                return self.get_error_response(
                    message="TrackId is required",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            
            # Handle authentication / guest OTP flow
            auth_manager = FlightBookingAuthManager(request.data, request.user)
            is_eligible, auth_message, auth_user = auth_manager.validate_user_eligibility()

            # Resolve booking_user
            if request.user and request.user.is_authenticated:
                # Authenticated user path
                booking_user = request.user
            else:
                # Unauthenticated → treat as guest flow by default
                # If validation failed (e.g., missing email), return an error
                if not is_eligible and not auth_user:
                    return self.get_error_response(
                        message=auth_message or "Email is required for guest bookings",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                # Allow guest booking even if email belongs to an existing account (hotel parity)
                # If OTP not provided, initiate email verification for the provided contact email
                if not request.data.get('otp'):
                    success, message, verification_data = auth_manager.initiate_guest_booking()
                    if success:
                        return self.get_response(
                            data=verification_data,
                            message=message,
                            status="verification_required",
                            status_code=status.HTTP_202_ACCEPTED
                        )
                    return self.get_error_response(
                        message=message,
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                # Verify OTP and create a guest user
                success, message, guest_user = auth_manager.verify_guest_booking_otp(request.data['otp'])
                if not success:
                    return self.get_error_response(
                        message=message,
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                booking_user = guest_user
            # Get or create session data from request
            session_data = self._get_or_create_session_data(request.data)
            # print("session_data", session_data)
            if not session_data:
                return self.get_error_response(
                    message="Failed to create pricing session",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Fetch fare rules before pricing validation (non-blocking)
            fare_rules_resp = self._get_fare_rules_response(request.data)

            # Extract pricing directly from request without API recalculation
            pricing_validation = self._extract_pricing_from_request(request.data)
            print("pricing_validation", pricing_validation)
            if not pricing_validation['success']:
                return self.get_error_response(
                    message=pricing_validation['message'],
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Check agent balance using AirIQ service on payable amount (includes SSR when provided)
            # chk_amount = pricing_validation.get('payable_amount', pricing_validation.get('final_amount', 0))
            # agent_balance_check = self._check_agent_balance(chk_amount)
            # if not agent_balance_check['success']:
            #     return self.get_error_response(
            #         message="We're unable to process your booking at this time. Please try again later or contact support for assistance.",
            #         status="error",
            #         status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            #     )
            
            # Prepare booking data
            booking_data = self._prepare_booking_data_from_request(request.data, pricing_validation)
            
            # Validate booking data
            processor = FlightBookingProcessor(booking_user, booking_data)
            if not processor.validate_booking_data():
                return self.get_error_response(
                    message="Booking validation failed",
                    status="error",
                    errors=processor.errors,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate company_id requirement for corporate users
            company_id = None
            company = None
            if booking_user:
                from apps.authentication.utils.token_utils import get_user_active_group
                from apps.authentication.utils.group_utils import is_corporate_user
                from apps.org_resources.models import CompanyDetail
                
                # Get active group from token to determine if user is corporate
                active_group = get_user_active_group(booking_user, request)
                is_corporate = is_corporate_user(active_group)
                
                if is_corporate:
                    # For corporate users, company_id MUST be provided in the request
                    company_id = request.data.get('company_id')
                    if not company_id:
                        return self.get_error_response(
                            message="Company ID is required for corporate users",
                            status="error",
                            errors=[{'field': 'company_id', 'message': 'Company ID is required for corporate users'}],
                            error_code='COMPANY_ID_REQUIRED',
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Validate that the company exists
                    try:
                        company = CompanyDetail.objects.get(id=company_id)
                        # Validate that the company_id matches user's company_id (if user has one)
                        if booking_user.company_id and booking_user.company_id != int(company_id):
                            return self.get_error_response(
                                message="Company ID does not match your assigned company",
                                status="error",
                                errors=[{'field': 'company_id', 'message': 'Company ID does not match your assigned company'}],
                                error_code='INVALID_COMPANY_ID',
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                    except CompanyDetail.DoesNotExist:
                        return self.get_error_response(
                            message="Invalid Company ID",
                            status="error",
                            errors=[{'field': 'company_id', 'message': 'Company ID does not exist'}],
                            error_code='INVALID_COMPANY_ID',
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    # For non-corporate users, allow optional company_id from request
                    company_id = request.data.get('company_id')
                    if company_id:
                        try:
                            company = CompanyDetail.objects.get(id=company_id)
                        except CompanyDetail.DoesNotExist:
                            return self.get_error_response(
                                message="Invalid Company ID",
                                status="error",
                                errors=[{'field': 'company_id', 'message': 'Company ID does not exist'}],
                                error_code='INVALID_COMPANY_ID',
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
            
            # Check if BlockPNR is true - if so, call AirIQ directly and skip payment flow
            block_pnr = bool(request.data.get('BlockPNR', False))
            
            if block_pnr:
                # BlockPNR flow: Call AirIQ directly, save response, and return
                return self._handle_block_pnr_booking(
                    request, booking_user, processor, pricing_validation, company, fare_rules_resp
                )
            
            # Create booking WITHOUT AirIQ integration (payment pending)
            with transaction.atomic():
                booking, flight_booking = self._create_booking_local_only(
                    processor, request.data, pricing_validation, company=company
                )
                
                # Create 5-minute payment lock
                payment_expires_at = timezone.now() + timedelta(minutes=5)
                flight_booking.payment_expires_at = payment_expires_at
                flight_booking.status = 'PENDING_PAYMENT'
                if 'fare_rules_resp' in locals() and fare_rules_resp:
                    flight_booking.fare_rules = fare_rules_resp
                flight_booking.save()
            
            # Prepare response data
            response_data = {
                'booking_id': booking.id,
                'booking_reference': flight_booking.booking_reference,
                'status': flight_booking.status,
                'total_amount': float(booking.final_amount),
                'payment_expires_at': payment_expires_at.isoformat(),
                'payment_lock_duration': 5,  # minutes
                'guest_token': booking.guest_access_token,  # Include guest token for guest bookings
                'booking_details': {
                    'flying_from': flight_booking.flying_from,
                    'flying_to': flight_booking.flying_to,
                    'departure_date': flight_booking.departure_date.isoformat() if flight_booking.departure_date else None,
                    'flight_trip': flight_booking.flight_trip,
                    'passenger_count': booking.adult_count + booking.child_count + booking.infant_count
                },
                'pnrs': {
                    'airiq_pnr_primary': flight_booking.airiq_pnr,
                    'airline_pnr_primary': flight_booking.airline_pnr,
                    'airiq_pnrs': flight_booking.airiq_pnrs,
                    'airline_pnrs': flight_booking.airline_pnrs,
                    'airiq_track_ids': flight_booking.airiq_track_ids,
                },
                'booked_itineraries': flight_booking.booked_itineraries,
                'amount_breakdown': {
                    'currency': pricing_validation.get('currency', 'INR'),
                    'basic_amount': float(pricing_validation.get('basic_amount', 0)),
                    'gross_amount': float(pricing_validation.get('gross_amount', booking.final_amount)),
                    'taxes': pricing_validation.get('tax_breakdown', {}),
                    'gst': pricing_validation.get('gst_breakdown', {}),
                    'ssr': pricing_validation.get('ssr_breakdown', {}),
                    'total_discount': float(pricing_validation.get('total_discount', 0)),
                    'final_amount': float(pricing_validation.get('final_amount', booking.final_amount)),
                    'payable_amount': float(pricing_validation.get('payable_amount', booking.final_amount)),
                }
            }
            
            self.log_info(
                f"Flight booking created - payment pending: {flight_booking.booking_reference}",
                extra={
                    'booking_id': booking.id,
                    'track_id': track_id,
                    'user_id': booking_user.id,
                    'amount': float(booking.final_amount)
                }
            )
            
            return self.get_response(
                data=response_data,
                message="Booking created successfully - payment required within 5 minutes",
                status="payment_required",
                status_code=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            # Improved diagnostics: log traceback and return a trace_id in errors for quick look-up
            import traceback, uuid
            trace_id = uuid.uuid4().hex[:8]
            tb = traceback.format_exc()
            try:
                self.log_error(f"[create_booking][{trace_id}] {str(e)}\n{tb}")
            except Exception:
                pass
            try:
                print(f"[create_booking][{trace_id}] {str(e)}")
            except Exception:
                pass
            return self.get_error_response(
                message="An error occurred while creating the booking",
                status="error",
                errors=[{"trace_id": trace_id, "error": str(e)}],
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='get',
        operation_description="Retrieve booking details from AirIQ and update local records (missing fields only)",
        manual_parameters=[
            openapi.Parameter('booking_id', openapi.IN_PATH, description="Flight booking ID", type=openapi.TYPE_INTEGER, required=True)
        ]
    )
    @action(detail=False, methods=['get'], url_path=r'(?P<booking_id>\d+)/airiq/retrieve')
    def airiq_retrieve_booking(self, request, booking_id=None):
        try:
            booking, flight_booking = self.get_flight_booking(booking_id)
            if not flight_booking.airiq_pnr:
                return self.get_error_response(
                    message="AirIQ PNR missing on booking",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            resp = airiq_service.get_booking_details(airiq_pnr=flight_booking.airiq_pnr)
            # Update local entities with any missing info from response
            self._update_booking_from_retrieve_response(booking, flight_booking, resp)
            # Normalize success payload shape
            body = {
                'Retrieveresponse': resp.get('Retrieveresponse') or resp.get('Retriveresponse') or resp.get('Bookingresponse') or resp,
                'Status': resp.get('Status') or resp.get('ResponseStatus') or {'ResultCode': '1', 'Error': ''}
            }
            return self.get_response(
                data=body,
                message="Booking retrieved successfully",
                status="success",
                status_code=status.HTTP_200_OK
            )
        except ValueError as e:
            return self.get_error_response(
                message=str(e),
                status="error",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except AirIQException as e:
            self.log_error(f"AirIQ retrieve error for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message=f"Unable to retrieve booking: {str(e)}",
                status="error",
                status_code=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            self.log_error(f"Unexpected error in AirIQ retrieve for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message="An unexpected error occurred",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='get',
        operation_description="Track booking status from AirIQ and update local records (missing fields only)",
        manual_parameters=[
            openapi.Parameter('booking_id', openapi.IN_PATH, description="Flight booking ID", type=openapi.TYPE_INTEGER, required=True)
        ]
    )
    @action(detail=False, methods=['get'], url_path=r'(?P<booking_id>\d+)/airiq/track-status')
    def airiq_track_status(self, request, booking_id=None):
        try:
            booking, flight_booking = self.get_flight_booking(booking_id)
            if not flight_booking.airiq_track_id:
                return self.get_error_response(
                    message="AirIQ Track ID missing on booking",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            resp = airiq_service.track_booking_status(booking_track_id=flight_booking.airiq_track_id)
            # Attempt to enrich local data: if track response contains PNR or we can subsequently retrieve
            try:
                # If we don't have PNR yet, try to pull via retrieve when track returns it
                retr_needed = False
                retr_pnr = None
                # Try to dig common places for AirIQ PNR in track response
                if isinstance(resp, dict):
                    ar = resp.get('Retrieveresponse') or resp.get('Retriveresponse') or resp.get('TrackStatusResponse') or {}
                    itins = ar.get('ItinearyDetails') or ar.get('ItineraryDetails') or []
                    if isinstance(itins, list) and itins:
                        items = (itins[0].get('Item') or [])
                        if items:
                            retr_pnr = items[0].get('AirIqPNR') or items[0].get('AiriqPNR')
                if retr_pnr and not flight_booking.airiq_pnr:
                    flight_booking.airiq_pnr = retr_pnr
                    flight_booking.save()
                    retr_needed = True
                # If we have (or just obtained) PNR, fetch full retrieve to update any missing fields
                if retr_needed or not flight_booking.ticket_numbers:
                    if flight_booking.airiq_pnr:
                        retr_resp = airiq_service.get_booking_details(airiq_pnr=flight_booking.airiq_pnr)
                        self._update_booking_from_retrieve_response(booking, flight_booking, retr_resp)
            except Exception as e:
                logger.warning(f"Track-status enrichment failed for booking {booking_id}: {e}")
            # Build response to match desired TrackStatus format
            status_block = resp.get('Status') or resp.get('ResponseStatus') or {}
            result_code = str(status_block.get('ResultCode', '1'))
            final_status = {
                'Error': status_block.get('Error', ''),
                'ResultCode': result_code,
                'SequenceID': status_block.get('SequenceID', ''),
                'Track_Status': 'SUCCESS' if result_code == '1' else 'FAILED'
            }
            # Extract ItinearyDetails and wrap under TrackStatusresponse
            track_block = resp.get('TrackStatusresponse')
            if not track_block:
                possible_blocks = [resp.get('TrackStatusresponse'), resp.get('Retrieveresponse'), resp.get('Retriveresponse'), resp]
                itins = []
                for blk in possible_blocks:
                    if isinstance(blk, dict):
                        itins = blk.get('ItinearyDetails') or blk.get('ItineraryDetails') or []
                        if itins:
                            break
                track_block = {'ItinearyDetails': itins}
            body = {
                'Status': final_status,
                'TrackStatusresponse': track_block
            }
            return self.get_response(
                data=body,
                message="Booking status tracked successfully",
                status="success",
                status_code=status.HTTP_200_OK
            )
        except ValueError as e:
            return self.get_error_response(
                message=str(e),
                status="error",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except AirIQException as e:
            self.log_error(f"AirIQ track-status error for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message=f"Unable to track booking status: {str(e)}",
                status="error",
                status_code=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            self.log_error(f"Unexpected error in AirIQ track-status for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message="An unexpected error occurred",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='post',
        operation_description='Get available SSR (ancillary) options for a confirmed/held booking',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'AirIqPNR': openapi.Schema(type=openapi.TYPE_STRING, description='Override AirIQ PNR (optional)'),
                'AirlinePNR': openapi.Schema(type=openapi.TYPE_STRING, description='Override Airline PNR (optional)')
            }
        ),
        responses={200: openapi.Response(description='SSR options with TrackId and price data')}
    )
    @action(detail=True, methods=['post'], url_path='ancillary/get-ssr', permission_classes=[IsAuthenticated])
    def get_ssr_options(self, request, pk=None):
        try:
            booking, flight_booking = self.get_flight_booking(pk)
            if flight_booking.status not in ['HELD', 'CONFIRMED', 'TICKETED']:
                return self.get_error_response(
                    message='SSR options are available only after hold/confirm',
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            airiq_pnr = request.data.get('AirIqPNR') or flight_booking.airiq_pnr
            airline_pnr = request.data.get('AirlinePNR') or flight_booking.airline_pnr
            if not airiq_pnr or not airline_pnr:
                return self.get_error_response(
                    message='Missing PNRs to fetch SSR options',
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            ssr_resp = airiq_service.get_ssr_services(airiq_pnr=airiq_pnr, airline_pnr=airline_pnr)

            # Persist TrackId for subsequent AddSSR
            track_id = ssr_resp.get('TrackId') or ssr_resp.get('TrackID') or ''
            if track_id:
                flight_booking.airiq_track_id = track_id
                flight_booking.save(update_fields=['airiq_track_id'])

            return Response(ssr_resp, status=status.HTTP_200_OK)
        except AirIQException as e:
            return self.get_error_response(
                message=f'GetSSR failed: {str(e)}',
                status='error',
                status_code=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            return self.get_error_response(
                message=f'Unexpected error fetching SSR: {str(e)}',
                status='error',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        method='post',
        operation_description='Add SSR (ancillary) selections to an existing booking. Supports WALLET and PHONE PAY payment methods.',
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['TracKID'],
            properties={
                'TracKID': openapi.Schema(type=openapi.TYPE_STRING, description='TrackId from GetSSR response'),
                'AirIqPNR': openapi.Schema(type=openapi.TYPE_STRING, description='Override AirIQ PNR (optional)'),
                'AirlinePNR': openapi.Schema(type=openapi.TYPE_STRING, description='Override Airline PNR (optional)'),
                'Remarks': openapi.Schema(type=openapi.TYPE_STRING),
                'MealsSSR': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)),
                'BaggSSR': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)),
                'SeatsSSR': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)),
                'OtherSSR': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)),
                'Payment': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_OBJECT, properties={
                        'PaymentMode': openapi.Schema(type=openapi.TYPE_STRING, default='T'),
                        'Amount': openapi.Schema(type=openapi.TYPE_STRING)
                    })
                ),
                'payment_channel': openapi.Schema(type=openapi.TYPE_STRING, enum=['WALLET', 'PHONE PAY'], description='Payment method'),
                'redirect_url': openapi.Schema(type=openapi.TYPE_STRING, description='Redirect URL for PhonePe payment')
            }
        ),
        responses={200: openapi.Response(description='Updated booking snapshot and AirIQ response')}
    )
    @action(detail=True, methods=['post'], url_path='ancillary/add-ssr', permission_classes=[IsAuthenticated])
    def add_ssr(self, request, pk=None):
        try:
            booking, flight_booking = self.get_flight_booking(pk)

            airiq_pnr = request.data.get('AirIqPNR') or flight_booking.airiq_pnr
            airline_pnr = request.data.get('AirlinePNR') or flight_booking.airline_pnr
            track_id = request.data.get('TracKID') or request.data.get('TrackId') or request.data.get('TrackID') or flight_booking.airiq_track_id
            if not all([airiq_pnr, airline_pnr, track_id]):
                return self.get_error_response(
                    message='AirIqPNR, AirlinePNR and TracKID/TrackId are required',
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            meals = request.data.get('MealsSSR') or []
            baggage = request.data.get('BaggSSR') or []
            seats = request.data.get('SeatsSSR') or []
            other = request.data.get('OtherSSR') or []
            remarks = request.data.get('Remarks') or ''
            payment_arr = request.data.get('Payment') or []
            payment_amount = Decimal('0')
            try:
                if payment_arr and isinstance(payment_arr, list):
                    payment_amount = Decimal(str((payment_arr[0] or {}).get('Amount') or 0))
            except Exception:
                payment_amount = Decimal('0')

            # Prepare ancillary request data
            ancillary_request = {
                'AirIqPNR': airiq_pnr,
                'AirlinePNR': airline_pnr,
                'TracKID': track_id,
                'Remarks': remarks,
                'MealsSSR': meals,
                'BaggSSR': baggage,
                'SeatsSSR': seats,
                'OtherSSR': other,
            }

            # If no payment required, directly call AirIQ and update
            if payment_amount <= 0:
                airiq_resp = airiq_service.add_ssr_services(
                    airiq_pnr=airiq_pnr,
                    airline_pnr=airline_pnr,
                    track_id=track_id,
                    meals_ssr=meals,
                    baggage_ssr=baggage,
                    seats_ssr=seats,
                    other_ssr=other,
                    payment_amount=0.0,
                    remarks=remarks,
                )
                from apps.booking.utils.flight_booking_utils import process_ssr_success
                result = process_ssr_success(booking, flight_booking, airiq_resp, meals, baggage, seats, other, payment_amount)
                return self.get_response(
                    data=result,
                    message='Ancillary services added successfully',
                    status='success',
                    status_code=status.HTTP_200_OK,
                )

            # Payment required - determine payment channel
            payment_channel = (request.data.get('payment_channel') or 'WALLET').upper()
            if payment_channel not in ('WALLET', 'PHONE PAY'):
                return self.get_error_response(
                    message='Unsupported payment_channel. Use WALLET or PHONE PAY',
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # WALLET payment flow: deduct -> call AirIQ -> update or refund
            if payment_channel == 'WALLET':
                return self._handle_ssr_wallet_payment(
                    booking, flight_booking, ancillary_request, payment_amount, meals, baggage, seats, other, request
                )

            # PHONE PAY flow: save request data -> initiate payment -> handle in callback
            if payment_channel == 'PHONE PAY':
                return self._handle_ssr_phonepe_payment(
                    booking, flight_booking, ancillary_request, payment_amount, request
                )
        except AirIQException as e:
            return self.get_error_response(
                message=f'AddSSR failed: {str(e)}',
                status='error',
                status_code=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as e:
            return self.get_error_response(
                message=str(e),
                status='error',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return self.get_error_response(
                message=f'Unexpected error adding SSR: {str(e)}',
                status='error',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _handle_ssr_wallet_payment(self, booking, flight_booking, ancillary_request, payment_amount, meals, baggage, seats, other, request):
        """Handle wallet payment for SSR: deduct -> call AirIQ -> update or refund"""
        try:
            from apps.booking.utils.booking_utils import check_wallet_balance_for_booking, deduct_booking_amount, refund_wallet_payment
            from apps.booking.utils.db_utils import create_booking_payment_details, update_booking_payment_details
            
            user = request.user
            company_id = None
            if user:
                user_default_group = getattr(user, 'default_group', '') or ''
                if user_default_group in ('CORP-ADMIN', 'CORP-EMP', 'CORPORATE-GRP'):
                    company_id = getattr(user, 'company_id', None)
            
            # Check wallet balance
            can_pay, balance_info = check_wallet_balance_for_booking(booking, user, company_id=company_id)
            if not can_pay:
                return self.get_error_response(
                    message='Insufficient wallet balance',
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            # Create payment detail record
            append_id = f"SSR{user.id}" if user else "SSRGUEST"
            payment_detail = create_booking_payment_details(booking.id, append_id)
            payment_detail.amount = float(payment_amount)
            payment_detail.transaction_for = "others"
            payment_detail.transaction_details = {
                'ssr_type': 'ancillary_services',
                'ancillary_request': ancillary_request
            }
            payment_detail.save()
            
            # Deduct wallet
            deduct_success = deduct_booking_amount(booking, company_id=company_id, request=request)
            if not deduct_success:
                return self.get_error_response(
                    message='Wallet deduction failed',
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            # Update payment detail as paid
            update_booking_payment_details(payment_detail.merchant_transaction_id, {
                'code': 'PAYMENT_SUCCESS',
                'message': 'Payment successful via wallet',
                'payment_type': 'WALLET',
                'payment_medium': 'Idbook',
                'is_transaction_success': True,
                'transaction_id': payment_detail.merchant_transaction_id
            })
            
            # Call AirIQ AddSSR
            try:
                airiq_resp = airiq_service.add_ssr_services(
                    airiq_pnr=ancillary_request['AirIqPNR'],
                    airline_pnr=ancillary_request['AirlinePNR'],
                    track_id=ancillary_request['TracKID'],
                    meals_ssr=ancillary_request['MealsSSR'],
                    baggage_ssr=ancillary_request['BaggSSR'],
                    seats_ssr=ancillary_request['SeatsSSR'],
                    other_ssr=ancillary_request['OtherSSR'],
                    payment_amount=float(payment_amount),
                    remarks=ancillary_request['Remarks'],
                )
                
                # Process success
                from apps.booking.utils.flight_booking_utils import process_ssr_success
                result = process_ssr_success(booking, flight_booking, airiq_resp, meals, baggage, seats, other, payment_amount)
                return self.get_response(
                    data=result,
                    message='Ancillary services added successfully',
                    status='success',
                    status_code=status.HTTP_200_OK,
                )
                
            except AirIQException as e:
                # AirIQ failed - refund wallet
                refund_details = {
                    'reason': f'AirIQ AddSSR failed: {str(e)}',
                    'timestamp': timezone.now().isoformat(),
                    'airiq_error': str(e)
                }
                refund_ok, refund_status, refund_data = refund_wallet_payment(booking, payment_amount, refund_details)
                
                update_booking_payment_details(payment_detail.merchant_transaction_id, {
                    'code': 'SSR_FAILED_REFUNDED',
                    'message': f'AddSSR failed; wallet refunded: {str(e)}',
                    'is_transaction_success': False,
                    'transaction_details': {
                        'refund_status': refund_status,
                        'refund_data': refund_data,
                        'airiq_error': str(e)
                    }
                })
                
                return self.get_error_response(
                    message=f'AddSSR failed; wallet refunded: {str(e)}',
                    status='error',
                    status_code=status.HTTP_502_BAD_GATEWAY,
                )
            except Exception as e:
                # Unexpected error - refund wallet
                refund_details = {
                    'reason': f'Unexpected error: {str(e)}',
                    'timestamp': timezone.now().isoformat(),
                }
                refund_ok, refund_status, refund_data = refund_wallet_payment(booking, payment_amount, refund_details)
                
                update_booking_payment_details(payment_detail.merchant_transaction_id, {
                    'code': 'SSR_ERROR_REFUNDED',
                    'message': f'Unexpected error; wallet refunded: {str(e)}',
                    'is_transaction_success': False,
                })
                
                return self.get_error_response(
                    message=f'Unexpected error; wallet refunded: {str(e)}',
                    status='error',
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        except Exception as e:
            self.log_error(f"SSR wallet payment error: {str(e)}")
            return self.get_error_response(
                message=f'Wallet payment processing failed: {str(e)}',
                status='error',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    def _handle_ssr_phonepe_payment(self, booking, flight_booking, ancillary_request, payment_amount, request):
        """Handle PhonePe payment for SSR: save request data -> initiate payment -> handle in callback"""
        try:
            from apps.booking.utils.db_utils import create_booking_payment_details, update_booking_payment_details
            from django.conf import settings
            
            user = request.user
            append_id = f"SSR{user.id}" if user else "SSRGUEST"
            payment_detail = create_booking_payment_details(booking.id, append_id)
            payment_detail.amount = float(payment_amount)
            payment_detail.transaction_for = "others"
            payment_detail.transaction_details = {
                'ssr_type': 'ancillary_services',
                'ancillary_request': ancillary_request
            }
            payment_detail.save()
            
            # Initiate PhonePe payment
            phonepe = PhonePayMixin()
            payload = {
                'merchantId': settings.MERCHANT_ID,
                'merchantTransactionId': payment_detail.merchant_transaction_id,
                'merchantUserId': str(user.id) if user and user.is_authenticated else 'guest',
                'amount': int(payment_amount * 100),
                'redirectUrl': request.data.get('redirect_url') or getattr(settings, 'FRONTEND_URL', ''),
                'redirectMode': 'REDIRECT',
                'callbackUrl': f"{settings.CALLBACK_URL}/api/v1/booking/flight-bookings/ancillary/phonepe-callback/",
                'paymentInstrument': {'type': 'PAY_PAGE'}
            }
            
            req, headers = phonepe.get_encrypted_header_and_payload(payload)
            resp = phonepe.post_pay_page(req, headers)
            
            if resp.status_code != 200:
                return self.get_error_response(
                    message='Failed to initiate PhonePe payment',
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            
            data_json = resp.json()
            pay_url = data_json.get('data', {}).get('instrumentResponse', {}).get('redirectInfo', {}).get('url', '')
            
            update_booking_payment_details(payment_detail.merchant_transaction_id, {
                'code': 'PAYMENT_INITIATED',
                'message': 'Payment initiated via PhonePe',
                'payment_type': 'PAYMENT GATEWAY',
                'payment_medium': 'PHONE PAY',
            })
            
            return self.get_response(
                data={
                    'payment_method': 'phonepe',
                    'payment_url': pay_url,
                    'transaction_id': payment_detail.merchant_transaction_id,
                },
                message='Ancillary payment initiated',
                status='success',
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            self.log_error(f"SSR PhonePe payment initiation error: {str(e)}")
            return self.get_error_response(
                message=f'Failed to initiate PhonePe payment: {str(e)}',
                status='error',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'], url_path='ancillary/phonepe-callback', permission_classes=[])
    def ancillary_phonepe_callback(self, request):
        """Handle PhonePe callback for SSR payment"""
        try:
            from apps.booking.utils.flight_payment_utils import process_ssr_phonepe_callback
            
            result = process_ssr_phonepe_callback(request.data)
            
            if not result.get('success'):
                return self.get_error_response(
                    message=result.get('error', 'Callback processing failed'),
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST if result.get('error_code') == 'INVALID_CALLBACK' else status.HTTP_502_BAD_GATEWAY,
                )
            
            if result.get('ssr_processed'):
                return self.get_response(
                    data=result,
                    message='Ancillary services added successfully',
                    status='success',
                    status_code=status.HTTP_200_OK,
                )
            
            return self.get_response(
                data={'payment_success': result.get('payment_success', False)},
                message=result.get('message', 'Callback processed'),
                status='success',
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            self.log_error(f"SSR PhonePe callback error: {str(e)}")
            return self.get_error_response(
                message=f'Callback processing failed: {str(e)}',
                status='error',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'], url_path='reschedule/phonepe-callback', permission_classes=[])
    def reschedule_phonepe_callback(self, request):
        """Handle PhonePe callback for reschedule payment"""
        try:
            from apps.booking.utils.flight_payment_utils import process_reschedule_phonepe_callback
            
            result = process_reschedule_phonepe_callback(request.data)
            
            if not result.get('success'):
                return self.get_error_response(
                    message=result.get('error', 'Callback processing failed'),
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST if result.get('error_code') == 'INVALID_CALLBACK' else status.HTTP_502_BAD_GATEWAY,
                )
            
            if result.get('reschedule_processed'):
                return self.get_response(
                    data=result,
                    message='Reschedule processed successfully',
                    status='success',
                    status_code=status.HTTP_200_OK,
                )
            
            return self.get_response(
                data={'payment_success': result.get('payment_success', False)},
                message=result.get('message', 'Callback processed'),
                status='success',
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            self.log_error(f"Reschedule PhonePe callback error: {str(e)}")
            return self.get_error_response(
                message=f'Callback processing failed: {str(e)}',
                status='error',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=['post'], url_path='ticket/phonepe-callback', permission_classes=[])
    def ticket_phonepe_callback(self, request):
        """Handle PhonePe callback for ticket issuance payment"""
        try:
            from apps.booking.utils.flight_payment_utils import process_ticket_issuance_phonepe_callback
            
            result = process_ticket_issuance_phonepe_callback(request.data)
            
            if not result.get('success'):
                return self.get_error_response(
                    message=result.get('error', 'Callback processing failed'),
                    status='error',
                    status_code=status.HTTP_400_BAD_REQUEST if result.get('error_code') == 'INVALID_CALLBACK' else status.HTTP_502_BAD_GATEWAY,
                )
            
            if result.get('ticket_issued'):
                return self.get_response(
                    data=result,
                    message='Ticket issued successfully',
                    status='success',
                    status_code=status.HTTP_200_OK,
                )
            
            return self.get_response(
                data={'payment_success': result.get('payment_success', False)},
                message=result.get('message', 'Callback processed'),
                status='success',
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            self.log_error(f"Ticket issuance PhonePe callback error: {str(e)}")
            return self.get_error_response(
                message=f'Callback processing failed: {str(e)}',
                status='error',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _handle_ssr_wallet_payment(self, booking, flight_booking, ancillary_request, payment_amount, meals, baggage, seats, other, request):
        """Handle wallet payment for SSR: deduct -> call AirIQ -> update or refund"""
        from apps.booking.utils.booking_utils import (
            check_wallet_balance_for_booking, deduct_booking_amount, refund_wallet_payment
        )
        
        user = request.user
        company_id = None
        if user:
            user_default_group = getattr(user, 'default_group', '') or ''
            if user_default_group in ('CORP-ADMIN', 'CORP-EMP', 'CORPORATE-GRP'):
                company_id = getattr(user, 'company_id', None)

        # Check wallet balance
        can_pay, balance_info = check_wallet_balance_for_booking(booking, user, company_id=company_id)
        if not can_pay:
            return self.get_error_response(
                message='Insufficient wallet balance',
                status='error',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Deduct from wallet
        deduct_success = deduct_booking_amount(booking, company_id=company_id, request=request)
        if not deduct_success:
            return self.get_error_response(
                message='Wallet deduction failed',
                status='error',
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Create payment detail record
        append_id = f"SSR{user.id}" if user else "SSRGUEST"
        payment_detail = create_booking_payment_details(booking.id, append_id)
        update_booking_payment_details(payment_detail.merchant_transaction_id, {
            'amount': float(payment_amount),
            'transaction_for': 'others',
            'payment_type': 'WALLET',
            'payment_medium': 'Idbook',
            'code': 'PAYMENT_SUCCESS',
            'message': 'SSR payment successful via wallet',
            'is_transaction_success': True,
            'transaction_id': payment_detail.merchant_transaction_id,
            'transaction_details': {
                'ssr_type': 'ancillary_services',
                'ancillary_request': ancillary_request,
            }
        })

        # Call AirIQ AddSSR
        try:
            airiq_resp = airiq_service.add_ssr_services(
                airiq_pnr=ancillary_request['AirIqPNR'],
                airline_pnr=ancillary_request['AirlinePNR'],
                track_id=ancillary_request['TracKID'],
                meals_ssr=ancillary_request['MealsSSR'],
                baggage_ssr=ancillary_request['BaggSSR'],
                seats_ssr=ancillary_request['SeatsSSR'],
                other_ssr=ancillary_request['OtherSSR'],
                payment_amount=float(payment_amount),
                remarks=ancillary_request['Remarks'],
            )
            
            # Process success
            from apps.booking.utils.flight_booking_utils import process_ssr_success
            result = process_ssr_success(booking, flight_booking, airiq_resp, meals, baggage, seats, other, payment_amount)
            return self.get_response(
                data=result,
                message='Ancillary services added successfully',
                status='success',
                status_code=status.HTTP_200_OK,
            )
            
        except AirIQException as e:
            # Refund wallet on AirIQ failure
            refund_details = {
                'reason': 'AirIQ AddSSR failed after wallet deduction',
                'timestamp': timezone.now().isoformat(),
                'airiq_error': str(e)
            }
            refund_ok, refund_status, refund_data = refund_wallet_payment(booking, payment_amount, refund_details)
            
            update_booking_payment_details(payment_detail.merchant_transaction_id, {
                'code': 'SSR_FAILED_REFUNDED',
                'message': f'AddSSR failed; wallet refunded: {str(e)}',
                'is_transaction_success': False,
                'transaction_details': {
                    'refund_status': refund_status,
                    'refund_data': refund_data,
                    'airiq_error': str(e)
                }
            })
            
            return self.get_error_response(
                message=f'AddSSR failed after wallet payment; wallet refunded: {str(e)}',
                status='error',
                status_code=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            # Refund wallet on unexpected error
            refund_details = {
                'reason': 'Unexpected error during AddSSR',
                'timestamp': timezone.now().isoformat(),
                'error': str(e)
            }
            refund_ok, refund_status, refund_data = refund_wallet_payment(booking, payment_amount, refund_details)
            
            update_booking_payment_details(payment_detail.merchant_transaction_id, {
                'code': 'SSR_ERROR_REFUNDED',
                'message': f'Unexpected error; wallet refunded: {str(e)}',
                'is_transaction_success': False,
            })
            
            return self.get_error_response(
                message=f'Unexpected error adding SSR; wallet refunded: {str(e)}',
                status='error',
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _handle_ssr_phonepe_payment(self, booking, flight_booking, ancillary_request, payment_amount, request):
        """Handle PhonePe payment for SSR: save request data -> initiate payment -> handle in callback"""
        from apps.payment_gateways.mixins.phonepay_mixins import PhonePayMixin
        
        # Create payment detail and save ancillary request data
        append_id = f"SSR{request.user.id}" if request.user and request.user.is_authenticated else "SSRGUEST"
        payment_detail = create_booking_payment_details(booking.id, append_id)
        update_booking_payment_details(payment_detail.merchant_transaction_id, {
            'amount': float(payment_amount),
            'transaction_for': 'others',
            'payment_type': 'PAYMENT GATEWAY',
            'payment_medium': 'PHONE PAY',
            'code': 'PAYMENT_INITIATED',
            'message': 'SSR payment initiated via PhonePe',
            'transaction_details': {
                'ssr_type': 'ancillary_services',
                'ancillary_request': ancillary_request,
            }
        })

        # Initiate PhonePe payment
        phonepe = PhonePayMixin()
        payload = {
            'merchantId': settings.MERCHANT_ID,
            'merchantTransactionId': payment_detail.merchant_transaction_id,
            'merchantUserId': str(request.user.id) if request.user and request.user.is_authenticated else 'guest',
            'amount': int(payment_amount * 100),
            'redirectUrl': request.data.get('redirect_url') or getattr(settings, 'FRONTEND_URL', ''),
            'redirectMode': 'REDIRECT',
            'callbackUrl': f"{settings.CALLBACK_URL}/api/v1/booking/flight-bookings/ancillary/phonepe-callback/",
            'paymentInstrument': {'type': 'PAY_PAGE'}
        }
        
        req, headers = phonepe.get_encrypted_header_and_payload(payload)
        resp = phonepe.post_pay_page(req, headers)
        
        if resp.status_code != 200:
            return self.get_error_response(
                message='Failed to initiate PhonePe payment',
                status='error',
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        
        data_json = resp.json()
        pay_url = data_json.get('data', {}).get('instrumentResponse', {}).get('redirectInfo', {}).get('url', '')
        
        return self.get_response(
            data={
                'payment_method': 'phonepe',
                'payment_url': pay_url,
                'transaction_id': payment_detail.merchant_transaction_id,
            },
            message='SSR payment initiated via PhonePe',
            status='success',
            status_code=status.HTTP_200_OK,
        )

    def _get_or_create_session_data(self, request_data: dict) -> dict:
        """Get existing session data or create new session from request data"""
        session_id = request_data.get('session_id')
        
        if session_id:
            # Try to get existing session
            session_data = flight_pricing_service.get_session_data(session_id)
            if session_data and session_data.get('pricing_calculated'):
                return session_data
        
        # Create new session from request data
        track_id = request_data.get('TrackId')
        if not track_id:
            return None
            
        # Extract search parameters from request
        search_params = {
            'track_id': track_id,
            'trip_type': request_data.get('TripType', 'O'),
            'origin': request_data.get('BaseOrigin'),
            'destination': request_data.get('BaseDestination'),
            'adults': request_data.get('AdultCount', 1),
            'children': request_data.get('ChildCount', 0),
            'infants': request_data.get('InfantCount', 0)
        }
        
        # Create session data structure
        session_data = {
            'search_params': search_params,
            'track_id': track_id,
            'itinerary_flights': request_data.get('ItineraryFlightsInfo', []),
            'passengers': request_data.get('PaxDetailsInfo', []),
            'contact': request_data.get('AddressDetails', {}),
            'gst_info': request_data.get('GSTInfo', {}),
            'created_at': timezone.now().isoformat()
        }
        
        return session_data
    
    def _normalize_itinerary_flights(self, itin_list: list, default_token: str = None, flights_override: dict = None) -> list:
        """Normalize itinerary list to expected AirIQ booking request structure.
        - Preserve PaymentInfo and SSR blocks exactly as provided
        - Normalize flights key to 'FlighstInfo'
        - Inject pricing token into each item's 'Token' only if missing
        - If flights_override is provided as a dict of {itin_ref: [segments]}, assign per index
        """
        norm = []
        for idx, item in enumerate(itin_list or []):
            new_item = {}
            token_val = item.get('Token') or default_token
            if token_val:
                new_item['Token'] = token_val
            # Preserve original multi-segment flights per itinerary item unless explicit override provided for this leg
            if isinstance(flights_override, dict) and (idx in flights_override):
                flights = flights_override.get(idx) or []
            else:
                flights = item.get('FlighstInfo') or item.get('FlightsInfo') or []
            new_item['FlighstInfo'] = flights
            # Copy through mode and SSR arrays as-is
            new_item['PaymentMode'] = item.get('PaymentMode', 'T')
            new_item['SeatsSSRInfo'] = item.get('SeatsSSRInfo', [])
            new_item['BaggSSRInfo'] = item.get('BaggSSRInfo', [])
            new_item['MealsSSRInfo'] = item.get('MealsSSRInfo', [])
            new_item['OtherSSRInfo'] = item.get('OtherSSRInfo', [])
            new_item['PaymentInfo'] = item.get('PaymentInfo', [])
            norm.append(new_item)
        return norm
    
    def _build_airiq_booking_request(self, request_data: dict, pricing_validation: dict = None) -> dict:
        """Build exact AirIQ booking request structure (excluding AgentInfo).
        Uses flights (itinerary), fares metadata, TrackId and Token from latest pricing response.
        """
        pricing_token = None
        price_resp = None
        if pricing_validation and isinstance(pricing_validation, dict):
            pricing_token = pricing_validation.get('pricing_token')
            price_resp = pricing_validation.get('pricing_response')
        
        # Extract TrackId and group Flights per itinerary leg if present
        track_from_price = None
        flights_grouped = None  # dict: {itin_index: [segments]}
        if isinstance(price_resp, dict):
            pi = (price_resp.get('PriceItenaryInfo') or [])
            if pi:
                track_from_price = pi[0].get('Trackid') or pi[0].get('TrackId')
                ar = pi[0].get('AvailabilityResponse') or []
                if ar:
                    flights_all = ar[0].get('Flights') or []
                    # Group by ItinRef (0 onward, 1 return), preserve full segment dicts
                    flights_grouped = {}
                    for seg in flights_all:
                        try:
                            itin_ref = int(seg.get('ItinRef') or 0)
                        except Exception:
                            itin_ref = 0
                        flights_grouped.setdefault(itin_ref, []).append(seg)
        
        # Counts as integers
        adult = int(request_data.get('AdultCount', 1) or 0)
        child = int(request_data.get('ChildCount', 0) or 0)
        infant = int(request_data.get('InfantCount', 0) or 0)
        
        # Normalize itinerary list and inject per-item tokens; keep original multi-segment flights.
        # If pricing provided grouped flights, apply per itinerary index; otherwise preserve request flights.
        itin_list = request_data.get('ItineraryFlightsInfo') or []
        itin_norm = self._normalize_itinerary_flights(itin_list, default_token=pricing_token, flights_override=flights_grouped if flights_grouped else None)
        
        # Passengers list as-is
        pax_list = request_data.get('PaxDetailsInfo') or []
        
        # Contacts and GST as-is with defaults
        address = request_data.get('AddressDetails') or {}
        gst = request_data.get('GSTInfo') or {}
        
        airiq_struct = {
            "AdultCount": adult,
            "ChildCount": child,
            "InfantCount": infant,
            "ItineraryFlightsInfo": itin_norm,
            "PaxDetailsInfo": pax_list,
            "AddressDetails": {
                "CountryCode": address.get('CountryCode', '91'),
                "ContactNumber": address.get('ContactNumber', ''),
                "EmailID": address.get('EmailID', '')
            },
            "GSTInfo": {
                "GSTNumber": gst.get('GSTNumber', ''),
                "GSTCompanyName": gst.get('GSTCompanyName', ''),
                "GSTAddress": gst.get('GSTAddress', ''),
                "GSTEmailID": gst.get('GSTEmailID', ''),
                "GSTMobileNumber": gst.get('GSTMobileNumber', '')
            },
            "TripType": request_data.get('TripType', 'O'),
            "BlockPNR": bool(request_data.get('BlockPNR', False)),
            "BaseOrigin": request_data.get('BaseOrigin'),
            "BaseDestination": request_data.get('BaseDestination'),
            "TrackId": track_from_price or request_data.get('TrackId') or request_data.get('TrackID') or ''
        }
        return airiq_struct
    
    def _extract_amounts_from_pricing_response(self, pricing_response: dict, request_data: dict) -> dict:
        """Parse AirIQ pricing response (V2.0) to compute base/gross/taxes per pax type.
        Falls back safely if the expected structure is missing.
        """
        try:
            pi = (pricing_response or {}).get('PriceItenaryInfo') or []
            if not pi:
                return {}
            ar = (pi[0] or {}).get('AvailabilityResponse') or []
            if not ar:
                return {}
            fares = (ar[0] or {}).get('Fares') or []
            if not fares:
                return {}
            fdesc = (fares[0] or {}).get('Faredescription') or []
            if not fdesc:
                return {}
            # Pax counts from request
            adt = int(request_data.get('AdultCount', 0) or 0)
            chd = int(request_data.get('ChildCount', 0) or 0)
            inf = int(request_data.get('InfantCount', 0) or 0)
            pax_map = {'ADT': adt, 'CHD': chd, 'INF': inf}
            gross_total = 0.0
            base_total = 0.0
            tax_breakdown = {}
            currency = 'INR'
            for row in fdesc:
                ptype = (row.get('Paxtype') or '').upper()
                pax_count = pax_map.get(ptype, 0)
                # Prefer per-pax amounts; multiply by pax count
                g = float(row.get('GrossAmount', 0) or 0)
                b = float(row.get('BaseAmount', 0) or 0)
                gross_total += g * (pax_count if pax_count > 0 else 1)
                base_total += b * (pax_count if pax_count > 0 else 1)
                taxes = row.get('Taxes') or []
                for tx in taxes:
                    code = tx.get('Code', '')
                    amt = float(tx.get('Amount', 0) or 0)
                    tax_breakdown[code] = tax_breakdown.get(code, 0.0) + (amt * (pax_count if pax_count > 0 else 1))
                currency = row.get('CurrencyCode') or currency
            return {
                'currency': currency,
                'gross_total': gross_total,
                'base_total': base_total,
                'tax_breakdown': tax_breakdown
            }
        except Exception:
            return {}

    def _build_seat_price_map(self, seatmap_resp: dict) -> dict:
        """Build a mapping of seat identifier -> price from AvailSeat response.
        Tries common keys heuristically (SeatID/SeatId/SeatCode/SeatNo with Amount/SeatAmount/Price).
        """
        price_map = {}
        try:
            def visit(node):
                if isinstance(node, dict):
                    keys = {k.lower(): k for k in node.keys()}
                    # Identify seat id
                    sid = None
                    for k in ('seatid','seat_id','seatcode','seat_no','seatno','code'):
                        if k in keys:
                            sid = str(node[keys[k]]).strip()
                            break
                    # Identify price
                    amt = None
                    for k in ('amount','seatamount','price'):
                        if k in keys and node[keys[k]] not in (None,''):
                            try:
                                amt = float(node[keys[k]])
                            except Exception:
                                amt = None
                            break
                    if sid and (amt is not None):
                        price_map[sid] = amt
                    for v in node.values():
                        visit(v)
                elif isinstance(node, list):
                    for it in node:
                        visit(it)
            visit(seatmap_resp)
        except Exception:
            return price_map
        return price_map

    def _extract_pricing_from_request(self, request_data: dict) -> dict:
        """Extract pricing from request data using only the provided ItineraryFlightsInfo.
        - Do not require pricing_response or seatmap response
        - Do not add SSR on top of TotalAmount
        - Sum TotalAmount across all itinerary items
        - Derive basic/gross/taxes when available; otherwise, fall back safely
        """
        try:
            itinerary_flights = request_data.get('ItineraryFlightsInfo') or []
            if not itinerary_flights:
                return {'success': False, 'message': 'Flight itinerary information is required'}

            pricing_token = itinerary_flights[0].get('Token', '') if itinerary_flights else ''

            total_amount = 0.0
            base_amount = 0.0
            gross_amount = 0.0
            total_discount = 0.0
            net_amount = 0.0
            total_tax_amount = 0.0
            currency = 'INR'
            tax_breakdown = {}

            for flight_info in itinerary_flights:
                payment_info = (flight_info.get('PaymentInfo') or [{}])
                p = payment_info[0] if payment_info else {}
                # Prefer TotalAmount; fallback to Gross/Basic as needed
                ta = p.get('TotalAmount')
                ga = p.get('GrossAmount')
                ba = p.get('BaseAmount')
                try:
                    total_amount += float(ta if ta not in (None, '') else (ga if ga not in (None, '') else (ba or 0)))
                except Exception:
                    pass
                try:
                    base_amount += float(ba or 0)
                except Exception:
                    pass
                try:
                    gross_amount += float(ga if ga not in (None, '') else (ta or 0))
                except Exception:
                    pass
                try:
                    total_discount += float(p.get('totalDiscount', 0) or 0)
                    net_amount += float(p.get('netamount', 0) or 0)
                    total_tax_amount += float(p.get('TotalTaxAmount', 0) or 0)
                except Exception:
                    pass
                if p.get('CurrencyCode'):
                    currency = p.get('CurrencyCode')
                # Taxes array (new structure)
                for tax in (p.get('Taxes') or []):
                    code = tax.get('Code') or ''
                    amt = tax.get('Amount')
                    try:
                        tax_breakdown[code] = tax_breakdown.get(code, 0.0) + float(amt or 0)
                    except Exception:
                        pass

            if total_amount <= 0:
                return {'success': False, 'message': 'TotalAmount must be greater than zero'}

            # Do not add SSR/seatmap amounts on top; TotalAmount is treated as final
            final_amount = float(total_amount)
            payable_amount = final_amount

            # Fallbacks
            if base_amount <= 0:
                base_amount = final_amount
            if gross_amount <= 0:
                gross_amount = final_amount

            gst_breakdown = self._extract_gst_from_new_response_structure(base_amount, final_amount, tax_breakdown)

            return {
                'success': True,
                'currency': currency,
                'final_amount': final_amount,
                'payable_amount': payable_amount,
                'pricing_response': request_data,  # echo request context for traceability
                'gst_breakdown': gst_breakdown,
                'basic_amount': base_amount,
                'gross_amount': gross_amount,
                'tax_breakdown': tax_breakdown,
                'pricing_token': pricing_token,
                'total_discount': total_discount,
                'net_amount': net_amount,
                'total_tax_amount': total_tax_amount,
                'ssr_breakdown': {}
            }
        except Exception as e:
            logger.error(f"Pricing extraction error: {str(e)}")
            return {'success': False, 'message': 'Failed to extract pricing from request'}
        
    
    def _get_fare_rules_response(self, request_data: dict) -> dict:
        """Call AirIQ GetFareRule and return response if successful; else None."""
        try:
            track_id = request_data.get('TrackId') or request_data.get('TrackID')
            if not track_id:
                return None
            itin_list = request_data.get('ItineraryFlightsInfo') or []
            if not itin_list:
                return None
            first_itin = itin_list[0] or {}
            flights_info = first_itin.get('FlighstInfo') or first_itin.get('FlightsInfo') or []
            flight_ids = []
            for seg in flights_info:
                fid = seg.get('FlightID') or seg.get('FlightId') or seg.get('Flightid')
                if fid:
                    flight_ids.append(str(fid))
            if not flight_ids:
                return None
            resp = airiq_service.get_fare_rules(flight_ids=flight_ids, track_id=track_id)
            status_block = resp.get('Status') or resp.get('ResponseStatus') or {}
            if status_block.get('ResultCode') == '1' or not status_block:
                return resp
            return None
        except AirIQException as e:
            logger.warning(f"AirIQ GetFareRule failed: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error fetching fare rules: {e}")
            return None
    
    def _validate_current_pricing(self, request_data: dict, session_data: dict) -> dict:
        """Validate current pricing using AirIQ pricing API"""
        try:
            track_id = request_data.get('TrackId')
            itinerary_flights = request_data.get('ItineraryFlightsInfo', [])
            
            if not itinerary_flights:
                return {
                    'success': False,
                    'message': 'Flight itinerary information is required'
                }
            
            # Extract flight details from request
            flight_details = itinerary_flights[0].get('FlighstInfo', []) if itinerary_flights else []
            base_amount = itinerary_flights[0].get('PaymentInfo')[0].get('BaseAmount', 0) if itinerary_flights else 0
            gross_amount = itinerary_flights[0].get('PaymentInfo')[0].get('GrossAmount', 0) if itinerary_flights else 0
            
            # Prepare itinerary info for AirIQ pricing call
            itinerary_info = [
                {
                    "FlightDetails": flight_details,
                    "BaseAmount": base_amount,
                    "GrossAmount": gross_amount
                }
            ]
            
            # Prepare segment info for AirIQ pricing call
            segment_info = {
                "BaseOrigin": request_data.get("BaseOrigin"),
                "BaseDestination": request_data.get("BaseDestination"),
                "TripType": request_data.get("TripType", "O"),
                "AdultCount": str(request_data.get("AdultCount", "1")),
                "ChildCount": str(request_data.get("ChildCount", "0")),
                "InfantCount": str(request_data.get("InfantCount", "0"))
            }
            
            try:
                # Call AirIQ pricing service with correct method signature
                pricing_response = airiq_service.price_flight(
                    track_id=track_id,
                    segment_info=segment_info,
                    itinerary_info=itinerary_info
                )
                
                # Extract pricing details from new AirIQ response structure
                current_total = 0
                basic_amount = 0
                tax_breakdown = {}
                
                # Check ResponseStatus first
                response_status = pricing_response.get('ResponseStatus', {})
                if response_status.get('ResultCode') != '1':
                    error_msg = response_status.get('Error', 'Pricing validation failed')
                    return {
                        'success': False,
                        'message': f'Pricing validation failed: {error_msg}'
                    }
                
                # Extract pricing from new structure: PriceItenaryInfo -> AvailabilityResponse -> Fares
                pricing_token = ''
                price_itinerary_info = pricing_response.get('PriceItenaryInfo', [])
                if price_itinerary_info:
                    availability_response = price_itinerary_info[0].get('AvailabilityResponse', [])
                    if availability_response:
                        # Extract pricing token from AvailabilityResponse
                        pricing_token = availability_response[0].get('Token', '')
                        
                        fares = availability_response[0].get('Fares', [])
                        if fares:
                            # Get fare details for adult passengers
                            fare_details = fares[0].get('Faredescription', [])
                            for fare_desc in fare_details:
                                if fare_desc.get('Paxtype') == 'ADT':
                                    current_total = float(fare_desc.get('GrossAmount', 0))
                                    basic_amount = float(fare_desc.get('BaseAmount', 0))
                                    
                                    # Extract tax breakdown
                                    taxes = fare_desc.get('Taxes', [])
                                    for tax in taxes:
                                        tax_code = tax.get('Code', '')
                                        tax_amount = float(tax.get('Amount', 0))
                                        tax_breakdown[tax_code] = tax_amount
                                    break
                
                # If no pricing found in new structure, try fallback
                if current_total == 0:
                    # Fallback to old structure if available
                    if 'ItinearyDetails' in pricing_response:
                        for itinerary in pricing_response['ItinearyDetails']:
                            if 'PassengerDetails' in itinerary:
                                for passenger in itinerary['PassengerDetails']:
                                    if 'SegmentInformation' in passenger:
                                        segment_info = passenger['SegmentInformation']
                                        if 'MonetaryDetail' in segment_info:
                                            monetary_detail = segment_info['MonetaryDetail']
                                            current_total = float(monetary_detail.get('GrossAmount', 0))
                                            basic_amount = float(monetary_detail.get('BasicAmount', 0))
                                            break
                                if current_total > 0:
                                    break
                    
                    # Last resort: check for direct total amount
                    if current_total == 0 and 'TotalAmount' in pricing_response:
                        current_total = float(pricing_response['TotalAmount'])
                
                # Extract requested amount from frontend
                requested_total = 0
                for flight_info in itinerary_flights:
                    payment_info = flight_info.get('PaymentInfo', [])
                    if payment_info:
                        requested_total += float(payment_info[0].get('TotalAmount', 0))
                
                # Validate amounts match (allow small variance for rounding)
                amount_difference = abs(current_total - requested_total)
                if amount_difference > 1:  # Allow 1 unit difference for rounding
                    return {
                        'success': False,
                        'message': f'Price has changed. Current price is {current_total}, but requested {requested_total}'
                    }
                
                # Extract GST and tax details from AirIQ response
                gst_breakdown = self._extract_gst_from_new_response_structure(
                    basic_amount, current_total, tax_breakdown
                )
                
                return {
                    'success': True,
                    'final_amount': current_total,
                    'pricing_response': pricing_response,
                    'gst_breakdown': gst_breakdown,
                    'basic_amount': basic_amount,
                    'tax_breakdown': tax_breakdown,
                    'pricing_token': pricing_token
                }
                
            except AirIQException as e:
                logger.error(f"AirIQ pricing validation failed: {str(e)}")
                return {
                    'success': False,
                    'message': 'Unable to validate current pricing. Please try again.'
                }
                
        except Exception as e:
            logger.error(f"Pricing validation error: {str(e)}")
            return {
                'success': False,
                'message': 'Pricing validation failed'
            }
    
    def _check_agent_balance(self, booking_amount: float) -> dict:
        """Check agent balance using AirIQ service"""
        try:
            # Get agent balance from AirIQ using the enhanced service method
            balance_response = airiq_service.get_agent_balance()
            
            if not balance_response or 'success' not in balance_response:
                logger.error("Failed to retrieve agent balance from AirIQ")
                return {
                    'success': False,
                    'message': 'Unable to verify account balance'
                }
            
            if not balance_response['success']:
                logger.error(f"AirIQ balance check failed: {balance_response.get('message', 'Unknown error')}")
                return {
                    'success': False,
                    'message': balance_response.get('message', 'Unable to verify account balance')
                }
            
            # Use the primary balance (TopupBalance) for validation
            available_balance = float(balance_response.get('balance', 0))
            topup_balance = float(balance_response.get('topup_balance', 0))
            credit_balance = float(balance_response.get('credit_balance', 0))
            
            # Log balance details for debugging
            logger.info(f"Agent balance details - Topup: {topup_balance}, Credit: {credit_balance}, Total: {available_balance}")
            
            # Check if we have sufficient balance (with small buffer)
            required_amount = booking_amount * 1.1  # 10% buffer for fees
            
            if available_balance < required_amount and topup_balance < required_amount and credit_balance < required_amount:
                logger.warning(f"Insufficient agent balance: {available_balance} < {required_amount}")
                return {
                    'success': False,
                    'message': f'Insufficient balance. Available: {available_balance}, Required: {required_amount}'
                }
            
            return {
                'success': True,
                'balance': available_balance,
                'topup_balance': topup_balance,
                'credit_balance': credit_balance
            }
            
        except Exception as e:
            logger.error(f"Agent balance check error: {str(e)}")
            return {
                'success': False,
                'message': 'Unable to verify account balance'
            }
    
    def _extract_gst_from_airiq_response(self, monetary_detail: dict) -> dict:
        """Extract GST breakdown from AirIQ monetary detail response (legacy method)"""
        gst_breakdown = {
            'cgst_amount': 0,
            'sgst_amount': 0,
            'igst_amount': 0,
            'total_gst': 0,
            'gst_type': '',
            'basic_amount': float(monetary_detail.get('BasicAmount', 0)),
            'gross_amount': float(monetary_detail.get('GrossAmount', 0)),
            'service_tax_amount': float(monetary_detail.get('ServiceTaxAmount', 0))
        }
        
        # Extract tax details from AirIQ response
        if 'TaxDetails' in monetary_detail and 'item' in monetary_detail['TaxDetails']:
            for tax_item in monetary_detail['TaxDetails']['item']:
                tax_code = tax_item.get('TaxCode', '')
                tax_amount = float(tax_item.get('Amount', 0))
                
                if 'CGST' in tax_code:
                    gst_breakdown['cgst_amount'] += tax_amount
                elif 'SGST' in tax_code:
                    gst_breakdown['sgst_amount'] += tax_amount
                elif 'IGST' in tax_code:
                    gst_breakdown['igst_amount'] += tax_amount
        
        # Calculate totals and determine GST type
        total_gst = gst_breakdown['cgst_amount'] + gst_breakdown['sgst_amount'] + gst_breakdown['igst_amount']
        gst_breakdown['total_gst'] = total_gst
        
        if gst_breakdown['cgst_amount'] > 0 and gst_breakdown['sgst_amount'] > 0:
            gst_breakdown['gst_type'] = 'CGST/SGST'
        elif gst_breakdown['igst_amount'] > 0:
            gst_breakdown['gst_type'] = 'IGST'
        
        # Calculate GST percentage if basic amount is available
        basic_amount = gst_breakdown['basic_amount']
        if basic_amount > 0 and total_gst > 0:
            gst_breakdown['gst_percentage'] = (total_gst / basic_amount) * 100
        else:
            gst_breakdown['gst_percentage'] = 0
        
        return gst_breakdown
    
    def _extract_gst_from_new_response_structure(self, basic_amount: float, gross_amount: float, tax_breakdown: dict) -> dict:
        """Extract GST breakdown from new AirIQ response structure"""
        gst_breakdown = {
            'cgst_amount': 0,
            'sgst_amount': 0,
            'igst_amount': 0,
            'total_gst': 0,
            'gst_type': '',
            'basic_amount': basic_amount,
            'gross_amount': gross_amount,
            'service_tax_amount': 0
        }
        
        # Map tax codes to GST types based on common AirIQ tax codes
        # K3, P2, YR, IN are common tax codes in the sample data
        for tax_code, tax_amount in tax_breakdown.items():
            if 'CGST' in tax_code.upper():
                gst_breakdown['cgst_amount'] += tax_amount
            elif 'SGST' in tax_code.upper():
                gst_breakdown['sgst_amount'] += tax_amount
            elif 'IGST' in tax_code.upper():
                gst_breakdown['igst_amount'] += tax_amount
            elif tax_code in ['K3', 'P2', 'YR', 'IN']:  # Common AirIQ tax codes
                # These are typically service taxes or other fees
                gst_breakdown['service_tax_amount'] += tax_amount
        
        # Calculate total GST
        total_gst = gst_breakdown['cgst_amount'] + gst_breakdown['sgst_amount'] + gst_breakdown['igst_amount']
        gst_breakdown['total_gst'] = total_gst
        
        # Determine GST type
        if gst_breakdown['cgst_amount'] > 0 and gst_breakdown['sgst_amount'] > 0:
            gst_breakdown['gst_type'] = 'CGST/SGST'
        elif gst_breakdown['igst_amount'] > 0:
            gst_breakdown['gst_type'] = 'IGST'
        elif total_gst > 0:
            gst_breakdown['gst_type'] = 'OTHER'
        
        # Calculate GST percentage if basic amount is available
        if basic_amount > 0 and total_gst > 0:
            gst_breakdown['gst_percentage'] = (total_gst / basic_amount) * 100
        else:
            gst_breakdown['gst_percentage'] = 0
        
        return gst_breakdown
    
    def _prepare_booking_data_from_request(self, request_data: dict, pricing_validation: dict) -> dict:
        """Prepare booking data from direct request with AirIQ pricing data"""
        passengers_info = request_data.get('PaxDetailsInfo', [])
        address_details = request_data.get('AddressDetails', {})
        gst_info = request_data.get('GSTInfo', {})
        itinerary_flights = request_data.get('ItineraryFlightsInfo', [])
        
        # Convert passenger data format
        passengers = []
        for pax in passengers_info:
            passengers.append({
                'passenger_ref': pax.get('PaxRefNumber', '1'),
                'passenger_type': pax.get('PaxType', 'ADT'),
                'title': pax.get('Title', 'MR'),
                'first_name': pax.get('FirstName', ''),
                'last_name': pax.get('LastName', ''),
                'date_of_birth': pax.get('DOB', ''),
                'gender': pax.get('Gender', 'Male').lower(),
                'passport_number': pax.get('PassportNo', ''),
                'passport_expiry': pax.get('PassportExpiry', ''),
                'infant_ref': pax.get('InfantRef', '')
            })
        
        # Extract pricing details from validation response
        gst_breakdown = pricing_validation.get('gst_breakdown', {})
        basic_amount = pricing_validation.get('basic_amount', pricing_validation['final_amount'])
        pricing_token = pricing_validation.get('pricing_token', '')
        
        booking_data = {
            'booking_type': 'FLIGHT',
            'trip_type': request_data.get('TripType', 'O'),
            'base_origin': request_data.get('BaseOrigin'),
            'base_destination': request_data.get('BaseDestination'),
            'adults': request_data.get('AdultCount', 1),
            'children': request_data.get('ChildCount', 0),
            'infants': request_data.get('InfantCount', 0),
            'adult_count': request_data.get('AdultCount', 1),
            'child_count': request_data.get('ChildCount', 0),
            'infant_count': request_data.get('InfantCount', 0),
            'total_amount': pricing_validation['final_amount'],
            'basic_amount': basic_amount,
            'track_id': request_data.get('TrackId'),
            'pricing_token': pricing_token,
            'flight_segments': itinerary_flights,
            'passengers': passengers,
            'contact': {
                'country_code': address_details.get('CountryCode', '91'),
                'phone': address_details.get('ContactNumber', ''),
                'email': address_details.get('EmailID', '')
            },
            'gst_info': {
                'gst_number': gst_info.get('GSTNumber', ''),
                'company_name': gst_info.get('GSTCompanyName', ''),
                'address': gst_info.get('GSTAddress', ''),
                'email': gst_info.get('GSTEmailID', ''),
                'mobile': gst_info.get('GSTMobileNumber', '')
            },
            # GST data from AirIQ response
            'gst_breakdown': gst_breakdown,
            'seats': [],
            'meals': [],
            'baggage': [],
            'other_services': [],
            # Store original pricing validation for reference
            'pricing_validation': pricing_validation
        }
        
        # Extract ancillary services if present
        for flight_info in itinerary_flights:
            if 'SeatsSSRInfo' in flight_info:
                booking_data['seats'].extend(flight_info['SeatsSSRInfo'])
            if 'MealsSSRInfo' in flight_info:
                booking_data['meals'].extend(flight_info['MealsSSRInfo'])
            if 'BaggSSRInfo' in flight_info:
                booking_data['baggage'].extend(flight_info['BaggSSRInfo'])
            if 'OtherSSRInfo' in flight_info:
                booking_data['other_services'].extend(flight_info['OtherSSRInfo'])
        
        return booking_data
    
    def _handle_block_pnr_booking(self, request, booking_user, processor, pricing_validation, company, fare_rules_resp):
        """Handle BlockPNR booking: Call AirIQ directly, save response, and return"""
        try:
            # Build AirIQ booking request
            airiq_request = self._build_airiq_booking_request(request.data, pricing_validation)
            
            # Convert AirIQ request format to format expected by airiq_service.create_booking
            booking_data = self._convert_airiq_request_to_booking_data(airiq_request, request.data, pricing_validation)
            
            # Get track_id
            track_id = airiq_request.get('TrackId') or request.data.get('TrackId')
            if not track_id:
                return self.get_error_response(
                    message="TrackId is required for BlockPNR booking",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Call AirIQ create_booking with block_pnr=True
            try:
                airiq_response = airiq_service.create_booking(
                    booking_data=booking_data,
                    track_id=track_id,
                    block_pnr=True
                )
            except AirIQException as e:
                self.log_error(f"AirIQ BlockPNR booking failed: {str(e)}")
                return self.get_error_response(
                    message=f"Failed to create BlockPNR booking: {str(e)}",
                    status="error",
                    status_code=status.HTTP_502_BAD_GATEWAY
                )
            
            # Check if booking was successful
            status_block = airiq_response.get('Status', {})
            if status_block.get('ResultCode') != '1':
                error_msg = status_block.get('Error', 'Booking failed')
                return self.get_error_response(
                    message=f"BlockPNR booking failed: {error_msg}",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Create local booking records
            with transaction.atomic():
                booking, flight_booking = self._create_booking_local_only(
                    processor, request.data, pricing_validation, company=company
                )
                
                # Extract booking details from AirIQ response
                booking_details = self._extract_airiq_booking_details(airiq_response)
                
                # Update flight booking with AirIQ response data
                flight_booking.airiq_pnr = booking_details.get('airiq_pnr', '')
                flight_booking.airline_pnr = booking_details.get('airline_pnr', '')
                flight_booking.airiq_track_id = booking_details.get('track_id', track_id)
                flight_booking.status = 'HELD'  # BlockPNR creates a held booking
                flight_booking.hold_expires_at = timezone.now() + timedelta(hours=24)
                
                # Save the complete AirIQ response
                flight_booking.airiq_response_data = airiq_response
                flight_booking.airiq_request_data = airiq_request
                flight_booking.pricing_validation_data = pricing_validation
                
                # Update booking from AirIQ response (extract PNRs, amounts, etc.)
                self._update_booking_from_airiq_response(booking, flight_booking, airiq_response)
                
                # Ensure HELD status is preserved for BlockPNR bookings (in case update method changed it)
                flight_booking.status = 'HELD'
                
                if fare_rules_resp:
                    flight_booking.fare_rules = fare_rules_resp
                
                # Save flight_booking (already saved in _update_booking_from_airiq_response, but save again to ensure all updates are persisted)
                flight_booking.save()
                
                # Update main booking status
                booking.status = 'pending'  # Held booking is pending until payment
                booking.save()
            
            # Prepare response data
            response_data = {
                'booking_id': booking.id,
                'booking_reference': flight_booking.booking_reference,
                'status': flight_booking.status,
                'total_amount': float(booking.final_amount),
                'hold_expires_at': flight_booking.hold_expires_at.isoformat() if flight_booking.hold_expires_at else None,
                'guest_token': booking.guest_access_token,
                'booking_details': {
                    'flying_from': flight_booking.flying_from,
                    'flying_to': flight_booking.flying_to,
                    'departure_date': flight_booking.departure_date.isoformat() if flight_booking.departure_date else None,
                    'flight_trip': flight_booking.flight_trip,
                    'passenger_count': booking.adult_count + booking.child_count + booking.infant_count
                },
                'pnrs': {
                    'airiq_pnr_primary': flight_booking.airiq_pnr,
                    'airline_pnr_primary': flight_booking.airline_pnr,
                    'airiq_pnrs': flight_booking.airiq_pnrs or [],
                    'airline_pnrs': flight_booking.airline_pnrs or [],
                    'airiq_track_ids': flight_booking.airiq_track_ids or [],
                },
                'booked_itineraries': flight_booking.booked_itineraries or [],
                'amount_breakdown': {
                    'currency': pricing_validation.get('currency', 'INR'),
                    'basic_amount': float(pricing_validation.get('basic_amount', 0)),
                    'gross_amount': float(pricing_validation.get('gross_amount', booking.final_amount)),
                    'taxes': pricing_validation.get('tax_breakdown', {}),
                    'gst': pricing_validation.get('gst_breakdown', {}),
                    'ssr': pricing_validation.get('ssr_breakdown', {}),
                    'total_discount': float(pricing_validation.get('total_discount', 0)),
                    'final_amount': float(pricing_validation.get('final_amount', booking.final_amount)),
                    'payable_amount': float(pricing_validation.get('payable_amount', booking.final_amount)),
                },
                'airiq_response': airiq_response  # Include full AirIQ response
            }
            
            self.log_info(
                f"BlockPNR booking created: {flight_booking.booking_reference}",
                extra={
                    'booking_id': booking.id,
                    'track_id': track_id,
                    'user_id': booking_user.id if booking_user else None,
                    'airiq_pnr': flight_booking.airiq_pnr,
                    'amount': float(booking.final_amount)
                }
            )
            
            return self.get_response(
                data=response_data,
                message="BlockPNR booking created successfully",
                status="held",
                status_code=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            import traceback
            trace_id = uuid.uuid4().hex[:8]
            tb = traceback.format_exc()
            self.log_error(f"[_handle_block_pnr_booking][{trace_id}] {str(e)}\n{tb}")
            return self.get_error_response(
                message="An error occurred while creating BlockPNR booking",
                status="error",
                errors=[{"trace_id": trace_id, "error": str(e)}],
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _convert_airiq_request_to_booking_data(self, airiq_request: dict, request_data: dict, pricing_validation: dict) -> dict:
        """Convert AirIQ request format to format expected by airiq_service.create_booking"""
        # Extract passengers from PaxDetailsInfo
        passengers = []
        for pax in airiq_request.get('PaxDetailsInfo', []):
            passengers.append({
                'passenger_ref': pax.get('PaxRefNumber', '1'),
                'title': pax.get('Title', 'MR'),
                'first_name': pax.get('FirstName', ''),
                'last_name': pax.get('LastName', ''),
                'date_of_birth': pax.get('DOB', ''),
                'gender': pax.get('Gender', 'Male'),
                'pax_type': pax.get('PaxType', 'ADT'),
                'passport_number': pax.get('PassportNo', ''),
                'passport_expiry': pax.get('PassportExpiry', ''),
                'passport_issued_date': pax.get('PassportIssuedDate', ''),
                'passport_country_code': pax.get('PassportCountryCode', ''),
                'infant_ref': pax.get('InfantRef', '')
            })
        
        # Extract token from ItineraryFlightsInfo (use first itinerary's token)
        token = ''
        itinerary_flights_info = airiq_request.get('ItineraryFlightsInfo', [])
        if itinerary_flights_info:
            # Get token from first itinerary item
            token = itinerary_flights_info[0].get('Token', '')
            # Fallback to pricing_validation token if not found
            if not token and pricing_validation:
                token = pricing_validation.get('pricing_token', '')
        
        # Extract flight segments from ItineraryFlightsInfo
        flight_segments = []
        for itin in itinerary_flights_info:
            flights = itin.get('FlighstInfo', []) or itin.get('FlightsInfo', [])
            flight_segments.extend(flights)
        
        # Extract GST info
        gst_info = airiq_request.get('GSTInfo', {})
        gst = {}
        if gst_info.get('GSTNumber'):
            gst = {
                'number': gst_info.get('GSTNumber', ''),
                'company_name': gst_info.get('GSTCompanyName', ''),
                'address': gst_info.get('GSTAddress', ''),
                'email': gst_info.get('GSTEmailID', ''),
                'mobile': gst_info.get('GSTMobileNumber', '')
            }
        
        # Extract contact info
        address = airiq_request.get('AddressDetails', {})
        contact = {
            'country_code': address.get('CountryCode', '91'),
            'phone': address.get('ContactNumber', ''),
            'email': address.get('EmailID', '')
        }
        
        # Extract ancillary services
        seats = []
        meals = []
        baggage = []
        other_services = []
        for itin in itinerary_flights_info:
            seats.extend(itin.get('SeatsSSRInfo', []))
            meals.extend(itin.get('MealsSSRInfo', []))
            baggage.extend(itin.get('BaggSSRInfo', []))
            other_services.extend(itin.get('OtherSSRInfo', []))
        
        return {
            'token': token,  # Include token for airiq_service.create_booking
            'passengers': passengers,
            'flight_segments': flight_segments,
            'gst': gst,
            'contact': contact,
            'adults': airiq_request.get('AdultCount', 1),
            'children': airiq_request.get('ChildCount', 0),
            'infants': airiq_request.get('InfantCount', 0),
            'origin': airiq_request.get('BaseOrigin', ''),
            'destination': airiq_request.get('BaseDestination', ''),
            'trip_type': airiq_request.get('TripType', 'O'),
            'total_amount': pricing_validation.get('final_amount', 0) if pricing_validation else 0,
            'seats': seats,
            'meals': meals,
            'baggage': baggage,
            'other_services': other_services
        }
    
    def _update_booking_from_airiq_response(self, booking: Booking, flight_booking: FlightBooking, airiq_response: dict):
        """Update booking and flight_booking from AirIQ BlockPNR response"""
        try:
            # Extract additional details from Bookingresponse before calling update method
            booking_response = airiq_response.get('Bookingresponse', {})
            itinerary_details = booking_response.get('ItinearyDetails', [])
            
            # Extract ticketing time limit and store in airiq_response_data
            ticketing_time_limit = None
            if itinerary_details:
                itin = itinerary_details[0]
                items = itin.get('Item', [])
                if items:
                    item = items[0]
                    ticketing_time_limit = item.get('TicketingTimeLimit', '')
                    
                    # Extract total amount from response if available
                    total_amount = itin.get('TotalAmount', '')
                    if total_amount:
                        try:
                            booking.final_amount = Decimal(str(total_amount))
                        except Exception:
                            pass
                    
                    # Extract payment details
                    payment_details = item.get('PaymentDetails', {})
                    payment_items = payment_details.get('Item', [])
                    if payment_items:
                        payment_item = payment_items[0]
                        amount = payment_item.get('Amount', '')
                        if amount:
                            try:
                                booking.final_amount = Decimal(str(amount))
                            except Exception:
                                pass
            
            # Use the existing method to update from response (this saves the flight_booking)
            self._update_booking_from_retrieve_response(booking, flight_booking, airiq_response)
            
            # Store ticketing time limit in airiq_response_data after update
            if ticketing_time_limit:
                if not flight_booking.airiq_response_data:
                    flight_booking.airiq_response_data = {}
                if isinstance(flight_booking.airiq_response_data, dict):
                    flight_booking.airiq_response_data['ticketing_time_limit'] = ticketing_time_limit
                    flight_booking.save(update_fields=['airiq_response_data'])
        except Exception as e:
            logger.warning(f"Error updating booking from AirIQ response: {e}")
    
    def _save_ticket_response(self, booking: Booking, flight_booking: FlightBooking, ticket_response: dict):
        """Save ticket response data from AirIQ IssueTicket API"""
        try:
            from apps.booking.utils.flight_payment_utils import FlightPaymentProcessor
            
            # Update flight booking with ticket response using FlightPaymentProcessor
            # This will properly extract ticket numbers, PNRs, and other details
            processor = FlightPaymentProcessor(booking, booking.user, {})
            processor.flight_booking = flight_booking
            
            # Use the existing method to update from AirIQ response
            # The ticket response has the same structure as booking response
            processor._update_flight_booking_from_airiq_response(ticket_response)
            
            # Update status to TICKETED
            flight_booking.status = 'TICKETED'
            flight_booking.ticketed_at = timezone.now()
            
            # Persist ticket response in airiq_response_data
            blob = flight_booking.airiq_response_data or {}
            blob['ticket_response'] = ticket_response
            flight_booking.airiq_response_data = blob
            
            # Save all updates
            flight_booking.save()
            
            # Update main booking status
            booking.status = 'confirmed'
            booking.save()
            
        except Exception as e:
            logger.error(f"Error saving ticket response for booking {booking.id}: {str(e)}")
            # Still try to save basic info even if full update fails
            try:
                flight_booking.status = 'TICKETED'
                blob = flight_booking.airiq_response_data or {}
                blob['ticket_response'] = ticket_response
                flight_booking.airiq_response_data = blob
                flight_booking.save()
                booking.status = 'confirmed'
                booking.save()
            except Exception:
                pass
    
    def _create_booking_local_only(self, processor: FlightBookingProcessor, 
                                 request_data: dict, pricing_validation: dict, company=None) -> tuple:
        """Create booking locally without AirIQ integration"""
        
        # Create local booking records only
        booking, flight_booking = processor.create_booking_without_airiq()
        
        # Set company if provided
        if company:
            booking.company = company
            booking.save(update_fields=['company'])
        
        # Store normalized AirIQ request data (without AgentInfo)
        airiq_req_struct = self._build_airiq_booking_request(request_data, pricing_validation)
        flight_booking.airiq_request_data = airiq_req_struct
        flight_booking.pricing_validation_data = pricing_validation
        # Persist raw pricing and optional seatmap responses if provided
        try:
            raw_price = request_data.get('pricing_response') or request_data.get('pricing_info') or {}
            raw_seatmap = request_data.get('avail_seat_map_response') or request_data.get('SeatMapResponse') or {}
            if raw_price:
                flight_booking.pricing_response_data = raw_price
            if raw_seatmap:
                flight_booking.seatmap_response_data = raw_seatmap
        except Exception:
            pass
        
        # Set initial status
        flight_booking.status = 'PENDING_PAYMENT'
        flight_booking.booking_reference = processor.generate_confirmation_code()
        
        # Extract flight details from request
        itinerary_flights = request_data.get('ItineraryFlightsInfo', [])
        if itinerary_flights and 'FlighstInfo' in itinerary_flights[0]:
            flight_info = itinerary_flights[0]['FlighstInfo'][0]
            # Always use BaseOrigin/BaseDestination for primary route, not first segment
            flight_booking.flying_from = request_data.get('BaseOrigin', '')
            flight_booking.flying_to = request_data.get('BaseDestination', '')
            flight_booking.flight_no = flight_info.get('FlightNumber', '')
            
            # Parse departure date from first segment for schedule reference
            departure_str = flight_info.get('DepartureDateTime', '')
            if departure_str:
                try:
                    flight_booking.departure_date = datetime.strptime(departure_str, '%d %b %Y %H:%M')
                except ValueError:
                    pass
        
        # For round-trip, capture return leg primary details from second itinerary item if present
        if request_data.get('TripType', 'O') == 'R' and len(itinerary_flights) > 1 and 'FlighstInfo' in itinerary_flights[1] and itinerary_flights[1]['FlighstInfo']:
            ret_info = itinerary_flights[1]['FlighstInfo'][0]
            flight_booking.return_from = ret_info.get('Origin', '')
            flight_booking.return_to = ret_info.get('Destination', '')
            ret_dep = ret_info.get('DepartureDateTime', '')
            if ret_dep:
                try:
                    flight_booking.return_date = datetime.strptime(ret_dep, '%d %b %Y %H:%M')
                except ValueError:
                    pass
        
        flight_booking.flight_trip = request_data.get('TripType', 'O')
        flight_booking.save()
        
        # Update main booking
        booking.confirmation_code = flight_booking.booking_reference
        # Save the payable amount (what user will actually pay) as booking.final_amount
        try:
            booking.final_amount = Decimal(str(pricing_validation.get('payable_amount', pricing_validation['final_amount'])))
        except Exception:
            booking.final_amount = pricing_validation['final_amount']
        
        # Save total_discount if available
        if 'total_discount' in pricing_validation and pricing_validation['total_discount'] > 0:
            booking.total_discount = pricing_validation['total_discount']
        
        booking.status = 'pending'
        booking.save()
        
        # Create passenger records
        self._create_passenger_records(booking, flight_booking, processor.booking_data['passengers'])
        
        return booking, flight_booking
    
    def _prepare_booking_data(self, request_data: dict, session_data: dict) -> dict:
        """Prepare comprehensive booking data from session and request (legacy method)"""
        search_params = session_data['search_params']
        pricing_breakdown = session_data.get('pricing_breakdown', {})
        booking_total = session_data.get('booking_total', {})
        
        # Extract flight segments from selected flights
        selected_flights = session_data.get('selected_flights', [])
        flight_segments = []
        for flight in selected_flights:
            flight_segments.extend(flight.get('segments', []))
        
        booking_data = {
            # Basic trip info
            'booking_type': 'FLIGHT',
            'trip_type': search_params['trip_type'],
            'base_origin': search_params['origin'],
            'base_destination': search_params['destination'],
            'departure_date': search_params['departure_date'],
            'return_date': search_params.get('return_date'),
            
            # Passenger counts
            'adults': search_params['adults'],
            'children': search_params['children'],
            'infants': search_params['infants'],
            'adult_count': search_params['adults'],
            'child_count': search_params['children'],
            'infant_count': search_params['infants'],
            
            # Pricing data
            'total_amount': booking_total.get('final_total', pricing_breakdown.get('gross_amount', 0)),
            'pricing_token': session_data.get('pricing_data', {}).get('Token', ''),
            'track_id': session_data['track_id'],
            
            # Flight details
            'flight_segments': flight_segments,
            'selected_flight_data': session_data.get('selected_flights', []),
            
            # Passenger details
            'passengers': request_data.get('passengers', []),
            
            # Contact information
            'contact': request_data.get('contact', {}),
            
            # GST information
            'gst_info': request_data.get('gst_info', {}),
            
            # Ancillary services
            'seats': session_data.get('ancillary_services', {}).get('seats', []),
            'meals': session_data.get('ancillary_services', {}).get('meals', []),
            'baggage': session_data.get('ancillary_services', {}).get('baggage', []),
            'other_services': session_data.get('ancillary_services', {}).get('other', [])
        }
        
        return booking_data

    def _create_booking_with_airiq(self, processor: FlightBookingProcessor, 
                                 session_data: dict, block_pnr: bool) -> tuple:
        """Create booking with AirIQ integration"""
        
        # Prepare AirIQ booking data
        airiq_booking_data = {
            'token': session_data.get('pricing_data', {}).get('Token', ''),
            'flight_segments': processor.booking_data['flight_segments'],
            'passengers': processor.booking_data['passengers'],
            'contact': processor.booking_data['contact'],
            'gst': processor.booking_data.get('gst_info', {}),
            'adults': processor.booking_data['adults'],
            'children': processor.booking_data['children'],
            'infants': processor.booking_data['infants'],
            'origin': processor.booking_data['base_origin'],
            'destination': processor.booking_data['base_destination'],
            'trip_type': processor.booking_data['trip_type'],
            'total_amount': processor.booking_data['total_amount'],
            'seats': processor.booking_data.get('seats', []),
            'meals': processor.booking_data.get('meals', []),
            'baggage': processor.booking_data.get('baggage', []),
            'other_services': processor.booking_data.get('other_services', [])
        }
        
        # Create AirIQ booking
        airiq_response = airiq_service.create_booking(
            booking_data=airiq_booking_data,
            track_id=session_data['track_id'],
            block_pnr=block_pnr
        )
        
        # Extract booking details from AirIQ response
        booking_details = self._extract_airiq_booking_details(airiq_response)
        
        # Create local booking records
        booking, flight_booking = processor.create_booking(airiq_response=airiq_response)
        
        # Update flight booking with AirIQ details
        flight_booking.airiq_pnr = booking_details.get('airiq_pnr', '')
        flight_booking.airline_pnr = booking_details.get('airline_pnr', '')
        flight_booking.airiq_track_id = booking_details.get('track_id', session_data['track_id'])
        flight_booking.status = 'CONFIRMED' if not block_pnr else 'HELD'
        
        # Store complete pricing and flight data
        flight_booking.selected_flight_data = processor.booking_data['selected_flight_data']
        flight_booking.search_session_data = session_data['search_params']
        
        if block_pnr:
            flight_booking.hold_expires_at = timezone.now() + timedelta(hours=24)
            flight_booking.save()
            # Send hold booking SMS notification
            try:
                from apps.booking.tasks import send_booking_sms_task
                hold_expiry_str = flight_booking.hold_expires_at.strftime('%B %d, %Y %I:%M %p')
                send_booking_sms_task.delay(
                    notification_type='FLIGHT_HOLD_REQUESTED',
                    params={
                        'booking_id': booking.id,
                        'hold_expiry': hold_expiry_str
                    }
                )
                self.log_info(f"Hold booking SMS notification queued for booking {booking.id}")
            except Exception as e:
                self.log_error(f"Error queuing hold booking SMS: {str(e)}")
        else:
            flight_booking.save()
        
        # Create passenger records
        self._create_passenger_records(booking, flight_booking, processor.booking_data['passengers'])
        
        return booking, flight_booking

    def _extract_airiq_booking_details(self, airiq_response: dict) -> dict:
        """Extract booking details from AirIQ response"""
        booking_response = airiq_response.get('Bookingresponse', {})
        itinerary_details = booking_response.get('ItinearyDetails', [])
        
        if itinerary_details:
            details = itinerary_details[0]
            # Prefer nested AirlinePNR under TravellerInfo -> SegmentInformation -> Item[0]
            airline_pnr = ''
            try:
                trav = (details.get('TravellerInfo') or {}).get('Item') or []
                if trav:
                    seginfo = trav[0].get('SegmentInformation') or {}
                    seg_items = seginfo.get('Item') or []
                    if seg_items:
                        airline_pnr = seg_items[0].get('AirlinePNR') or ''
            except Exception:
                pass
            # Fallback to top-level keys
            airline_pnr = airline_pnr or details.get('AirlinePNR', '') or details.get('CRSPNR', '')
            # Normalize NA values
            if isinstance(airline_pnr, str) and airline_pnr.strip().upper() in ('N/A', 'NA', 'NULL'):
                airline_pnr = ''
            airiq_pnr = details.get('AirIqPNR') or details.get('AiriqPNR') or ''
            return {
                'airiq_pnr': airiq_pnr,
                'airline_pnr': airline_pnr,
                'track_id': details.get('TrackId', '') or details.get('BookingTrackId', ''),
                'booking_status': details.get('BookingStatus', ''),
                'total_amount': details.get('TotalAmount', '0')
            }
        
        return {
            'airiq_pnr': '',
            'airline_pnr': '',
            'track_id': '',
            'booking_status': 'PENDING',
            'total_amount': '0'
        }

    def _create_passenger_records(self, booking: Booking, flight_booking: FlightBooking, passengers: list):
        """Create passenger records for flight booking"""
        passenger_records = []
        
        for passenger in passengers:
            # Convert date strings to proper date objects
            date_of_birth = self._convert_date_string(passenger.get('date_of_birth'))
            passport_expiry = self._convert_date_string(passenger.get('passport_expiry'))
            passport_issued_date = self._convert_date_string(passenger.get('passport_issued_date'))
            
            passenger_record = FlightPassenger(
                flight_booking=flight_booking,
                booking=booking,
                passenger_reference=passenger.get('passenger_ref', 1),
                passenger_type=passenger.get('passenger_type', 'ADT'),
                title=passenger.get('title', 'MR'),
                first_name=passenger.get('first_name', ''),
                last_name=passenger.get('last_name', ''),
                date_of_birth=date_of_birth,
                gender=passenger.get('gender', 'male'),
                passport_number=passenger.get('passport_number', ''),
                passport_expiry=passport_expiry,
                passport_issued_date=passport_issued_date,
                passport_country_code=passenger.get('passport_country_code', ''),
                infant_with_passenger=self._convert_infant_ref(passenger.get('infant_ref'))
            )
            passenger_records.append(passenger_record)
        
        FlightPassenger.objects.bulk_create(passenger_records)
    
    def _convert_date_string(self, date_string):
        """Convert date string to date object, handling multiple formats"""
        if not date_string:
            return None
            
        if isinstance(date_string, str):
            from datetime import datetime
            
            # Try different input formats
            formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%m/%d/%Y']
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_string, fmt)
                    return dt.date()
                except ValueError:
                    continue
            
            # If no format matched, raise an error
            raise ValueError(f"Unable to parse date: {date_string}. Expected formats: DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY, YYYY/MM/DD, MM/DD/YYYY")
        
        return date_string
    
    def _convert_infant_ref(self, infant_ref):
        """Convert infant reference to integer or None"""
        if not infant_ref or infant_ref == '':
            return None
        
        try:
            return int(infant_ref)
        except (ValueError, TypeError):
            return None

    @swagger_auto_schema(
        method='get',
        operation_description="Get booking status and details",
        manual_parameters=[
            openapi.Parameter('booking_id', openapi.IN_PATH, type=openapi.TYPE_INTEGER, required=True)
        ]
    )
    @action(detail=True, methods=['get'], url_path='status')
    def get_booking_status(self, request, pk=None):
        """Get comprehensive booking status"""
        try:
            booking = get_object_or_404(
                Booking.objects.select_related('flight_booking'),
                id=pk,
                booking_type='FLIGHT'
            )
            
            if request.user.is_authenticated and booking.user != request.user:
                return self.get_error_response(
                    message="Booking not found",
                    status="error",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            flight_booking = booking.flight_booking
            if not flight_booking:
                return self.get_error_response(
                    message="Flight booking details not found",
                    status="error",
                    status_code=status.HTTP_404_NOT_FOUND
                )
            
            # Get latest status from AirIQ if we have PNRs
            airiq_status = None
            if flight_booking.airiq_track_id:
                try:
                    airiq_status = airiq_service.track_booking_status(flight_booking.airiq_track_id)
                except AirIQException as e:
                    logger.warning(f"Failed to get AirIQ status for booking {pk}: {str(e)}")
            
            # Get passengers
            passengers = FlightPassenger.objects.filter(flight_booking=flight_booking)
            passenger_data = [
                {
                    'passenger_ref': p.passenger_reference,
                    'name': f"{p.title} {p.first_name} {p.last_name}",
                    'type': p.passenger_type,
                    'date_of_birth': p.date_of_birth.isoformat() if p.date_of_birth else None
                }
                for p in passengers
            ]
            
            # Include full raw AirIQ booking response and request for complete traceability
            airiq_raw = getattr(flight_booking, 'airiq_response_data', {}) or {}
            airiq_booking = (airiq_raw.get('Bookingresponse') if isinstance(airiq_raw, dict) else {}) or {}

            response_data = {
                'booking_id': booking.id,
                'booking_reference': flight_booking.booking_reference,
                'status': flight_booking.status,
                'airiq_pnr': flight_booking.airiq_pnr,
                'airline_pnr': flight_booking.airline_pnr,
                'pnrs': {
                    'airiq_pnrs': getattr(flight_booking, 'airiq_pnrs', []) or [],
                    'airline_pnrs': getattr(flight_booking, 'airline_pnrs', []) or [],
                    'airiq_track_ids': getattr(flight_booking, 'airiq_track_ids', []) or []
                },
                'booked_itineraries': getattr(flight_booking, 'booked_itineraries', []) or [],
                'flight_details': {
                    'flying_from': flight_booking.flying_from,
                    'flying_to': flight_booking.flying_to,
                    'departure_date': flight_booking.departure_date.isoformat() if flight_booking.departure_date else None,
                    'flight_trip': flight_booking.flight_trip,
                    'flight_number': flight_booking.flight_no
                },
                'passengers': passenger_data,
                'amount_details': {
                    'final_amount': float(booking.final_amount),
                    'total_payment_made': float(booking.total_payment_made),
                    'balance_due': float(booking.final_amount - booking.total_payment_made)
                },
                'created_at': booking.created.isoformat(),
                'airiq_status': airiq_status,
                'airiq_booking': airiq_booking,
                'airiq_raw': airiq_raw,
                'airiq_request': getattr(flight_booking, 'airiq_request_data', {}) or {}
            }
            
            return self.get_response(
                data=response_data,
                message="Booking status retrieved successfully",
                status="success",
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            self.log_error(f"Error getting booking status {pk}: {str(e)}")
            return self.get_error_response(
                message="Error retrieving booking status",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _update_booking_from_retrieve_response(self, booking: Booking, flight_booking: FlightBooking, retrieve_resp: dict) -> None:
        """Update local booking records from AirIQ RetrieveBooking response (only missing/empty fields)."""
        try:
            retr = retrieve_resp.get('Retrieveresponse') or retrieve_resp.get('Retriveresponse') or retrieve_resp.get('Bookingresponse') or {}
            itins = retr.get('ItinearyDetails') or retr.get('ItineraryDetails') or []
            if not isinstance(itins, list) or not itins:
                return
            # Collections
            airiq_pnrs = set(flight_booking.airiq_pnrs or [])
            airline_pnrs = set(flight_booking.airline_pnrs or [])
            track_ids = set(flight_booking.airiq_track_ids or [])
            booked_list = flight_booking.booked_itineraries or []
            gross_amount_primary = None
            # Iterate each itinerary block
            for itin in itins:
                items = itin.get('Item') or []
                if not items:
                    continue
                hdr = items[0]
                # Track ID & PNR
                track_id = hdr.get('BookingTrackId') or hdr.get('TrackId') or ''
                if track_id:
                    track_ids.add(track_id)
                airiq_pnr = hdr.get('AirIqPNR') or hdr.get('AiriqPNR') or ''
                if airiq_pnr:
                    airiq_pnrs.add(airiq_pnr)
                # Amount at itinerary level
                pay = (hdr.get('PaymentDetails') or {}).get('Item') or []
                itin_amount = None
                if pay:
                    try:
                        itin_amount = float(pay[0].get('Amount', 0))
                    except Exception:
                        itin_amount = None
                # Traveller/Segments
                trav = (hdr.get('TravellerInfo') or {}).get('Item') or []
                airline_pnr_nested = ''
                ticket_numbers = []
                segs = []
                if trav:
                    seginfo = (trav[0].get('SegmentInformation') or {})
                    seg_items = seginfo.get('Item') or []
                    if seg_items:
                        airline_pnr_nested = seg_items[0].get('AirlinePNR', '') or ''
                    for t in trav:
                        tn = t.get('TicketNumber') or t.get('TicketNo')
                        if tn:
                            ticket_numbers.append(tn)
                        sgi = t.get('SegmentInformation') or {}
                        for s in (sgi.get('Item') or []):
                            segs.append({
                                'AirlinePNR': s.get('AirlinePNR'),
                                'FlightNumber': s.get('FlightNumber'),
                                'Origin': s.get('Origin'),
                                'Destination': s.get('Destination'),
                                'DepartureDateTime': s.get('DepartureDateTime'),
                                'ArrivalDateTime': s.get('ArrivalDateTime'),
                                'CarrierCode': s.get('CarrierCode'),
                                'ClassCode': s.get('ClassCode'),
                                'FareBasis': s.get('FareBasis'),
                                'SeatPreference': s.get('SeatPreference'),
                                'SeatAmount': s.get('SeatAmount'),
                                'MealsPreference': s.get('MealsPreference'),
                                'MealsAmount': s.get('MealsAmount'),
                                'BaggagePreference': s.get('BaggagePreference'),
                                'BaggageAmount': s.get('BaggageAmount'),
                            })
                if airline_pnr_nested:
                    airline_pnrs.add(airline_pnr_nested)
                # Set primary gross amount if missing
                if gross_amount_primary is None and trav:
                    mon = (trav[0].get('SegmentInformation') or {}).get('MonetaryDetail') or {}
                    try:
                        gross_amount_primary = float(mon.get('GrossAmount', 0))
                    except Exception:
                        pass
                # Append itinerary record
                booked_list.append({
                    'booking_track_id': track_id,
                    'airiq_pnr': airiq_pnr,
                    'amount': itin_amount,
                    'segments': segs,
                })
            # Save collections back
            # Set single fields if empty for backward compatibility
            if not flight_booking.airiq_pnr and airiq_pnrs:
                flight_booking.airiq_pnr = list(airiq_pnrs)[0]
            if not flight_booking.airiq_track_id and track_ids:
                flight_booking.airiq_track_id = list(track_ids)[0]
            if not flight_booking.ticket_numbers and 'ticket_numbers' in locals() and ticket_numbers:
                flight_booking.ticket_numbers = ticket_numbers
            # Save lists
            flight_booking.airiq_pnrs = list(airiq_pnrs)
            flight_booking.airline_pnrs = list(airline_pnrs)
            flight_booking.airiq_track_ids = list(track_ids)
            flight_booking.booked_itineraries = booked_list
            
            # Infer status - preserve HELD status for BlockPNR bookings
            if not flight_booking.status or flight_booking.status in ['INITIATED', 'PENDING_PAYMENT']:
                if flight_booking.ticket_numbers:
                    flight_booking.status = 'TICKETED'
                elif airiq_pnrs:
                    flight_booking.status = 'CONFIRMED'
            # Only update to CONFIRMED if currently HELD and we have ticket numbers (ticketed)
            elif flight_booking.status == 'HELD':
                if flight_booking.ticket_numbers:
                    flight_booking.status = 'TICKETED'
                # Keep HELD status if not ticketed yet
            # Persist amounts on main booking if missing
            if gross_amount_primary is not None and float(booking.final_amount or 0) == 0.0:
                from decimal import Decimal
                booking.final_amount = Decimal(str(gross_amount_primary))
            # Sync parent booking status - only for CONFIRMED/TICKETED, not HELD
            if flight_booking.status in ['CONFIRMED', 'TICKETED'] and booking.status != 'confirmed':
                booking.status = 'confirmed'
                flight_booking.save()
                booking.save()
            elif flight_booking.status == 'HELD' and booking.status != 'pending':
                booking.status = 'pending'
                flight_booking.save()
                booking.save()
                pay = (hdr.get('PaymentDetails') or {}).get('Item') or []
                gross_amount = None
                if pay:
                    try:
                        gross_amount = float(pay[0].get('Amount', 0))
                    except Exception:
                        gross_amount = None
                # Try monetary detail too
                trav = (hdr.get('TravellerInfo') or {}).get('Item') or []
                airline_pnr = ''
                ticket_numbers = []
                if trav:
                    seginfo = (trav[0].get('SegmentInformation') or {})
                    seg_items = seginfo.get('Item') or []
                    if seg_items:
                        airline_pnr = seg_items[0].get('AirlinePNR', '') or airline_pnr
                        mon = seginfo.get('MonetaryDetail') or {}
                        if not gross_amount:
                            try:
                                gross_amount = float(mon.get('GrossAmount', 0))
                            except Exception:
                                pass
                    # Collect ticket numbers from all pax
                    for t in trav:
                        tn = t.get('TicketNumber') or t.get('TicketNo')
                        if tn:
                            ticket_numbers.append(tn)
                # Treat existing value 'N/A'/'NA'/empty as missing and update from nested AirlinePNR
                def _is_na(val):
                    try:
                        s = (val or '').strip()
                        return s == '' or s.upper() in ('N/A', 'NA', 'NULL')
                    except Exception:
                        return True
                if airline_pnr and _is_na(flight_booking.airline_pnr):
                    flight_booking.airline_pnr = airline_pnr
                if ticket_numbers and not flight_booking.ticket_numbers:
                    flight_booking.ticket_numbers = ticket_numbers
                # Also persist per-passenger seat/meals/baggage if available
                try:
                    pax_qs = { (p.title.upper(), p.first_name.strip().upper(), p.last_name.strip().upper(), str(p.date_of_birth) if p.date_of_birth else None): p for p in flight_booking.passengers.all() }
                    for t in trav:
                        key = ((t.get('Title') or '').upper(), (t.get('FirstName') or '').strip().upper(), (t.get('LastName') or '').strip().upper(), None)
                        passenger = pax_qs.get(key)
                        if not passenger:
                            continue
                        # Ticket number
                        tn = t.get('TicketNumber') or t.get('TicketNo')
                        if tn and not passenger.ticket_number:
                            passenger.ticket_number = tn
                        seginfo = t.get('SegmentInformation') or {}
                        seg_items = seginfo.get('Item') or []
                        if seg_items:
                            s = seg_items[0]
                            seat_pref = (s.get('SeatPreference') or '').strip()
                            meal_pref = (s.get('MealsPreference') or '').strip()
                            bag_pref = (s.get('BaggagePreference') or '').strip()
                            seat_amt = s.get('SeatAmount') or '0'
                            meal_amt = s.get('MealsAmount') or '0'
                            bag_amt = s.get('BaggageAmount') or '0'
                            if seat_pref and not passenger.seat_number:
                                passenger.seat_number = seat_pref
                            passenger.save(update_fields=['ticket_number','seat_number'])
                            from decimal import Decimal as _D
                            from apps.booking.models import FlightAncillaryService as _FAS
                            def ensure_service(stype, code, desc, amt):
                                if not desc and not code:
                                    return
                                try:
                                    price = _D(str(amt or 0))
                                except Exception:
                                    price = _D('0')
                                exists = _FAS.objects.filter(
                                    flight_booking=flight_booking,
                                    passenger=passenger,
                                    service_type=stype,
                                    service_description=desc[:200] if desc else code,
                                ).exists()
                                if not exists:
                                    _FAS.objects.create(
                                        flight_booking=flight_booking,
                                        passenger=passenger,
                                        service_type=stype,
                                        airiq_service_id=str(code or ''),
                                        service_code=str(code or ''),
                                        service_description=(desc or str(code))[:200],
                                        segment_reference=1,
                                        service_price=price,
                                    )
                            if seat_pref:
                                ensure_service('SEAT', seat_pref, f"Seat {seat_pref}", seat_amt)
                            if meal_pref:
                                ensure_service('MEAL', '', meal_pref, meal_amt)
                            if bag_pref:
                                ensure_service('BAGGAGE', '', bag_pref, bag_amt)
                except Exception:
                    pass
                # Infer status - preserve HELD status for BlockPNR bookings
                ticket_status = (hdr.get('TicketStatus') or '').upper()
                if not flight_booking.status or flight_booking.status in ['INITIATED', 'PENDING_PAYMENT']:
                    if ticket_numbers:
                        flight_booking.status = 'TICKETED'
                    elif ticket_status == 'CONFIRMED':
                        flight_booking.status = 'CONFIRMED'
                # Only update HELD status if ticketed
                elif flight_booking.status == 'HELD':
                    if ticket_numbers:
                        flight_booking.status = 'TICKETED'
                    # Keep HELD status if not ticketed yet
                # Persist amounts if missing on main booking
                if gross_amount is not None and float(booking.final_amount or 0) == 0.0:
                    from decimal import Decimal
                    booking.final_amount = Decimal(str(gross_amount))
                # Sync parent booking status - only for CONFIRMED/TICKETED, not HELD
                if flight_booking.status in ['CONFIRMED', 'TICKETED'] and booking.status != 'confirmed':
                    booking.status = 'confirmed'
                elif flight_booking.status == 'HELD' and booking.status != 'pending':
                    booking.status = 'pending'
            flight_booking.save()
            booking.save()
        except Exception as e:
            logger.warning(f"Failed to update local booking from retrieve response: {e}")

    
    @swagger_auto_schema(
        method='post',
        operation_description="Issue ticket for confirmed flight booking",
        manual_parameters=[
            openapi.Parameter(
                'booking_id',
                openapi.IN_PATH,
                description="Flight booking ID",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="Ticket issued successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'ticket_response': openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    description="Ticketing response from AirIQ"
                                ),
                                'booking_status': openapi.Schema(type=openapi.TYPE_STRING)
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description="Bad request"),
            404: openapi.Response(description="Booking not found"),
            500: openapi.Response(description="AirIQ service error")
        }
    )
    @action(detail=False, methods=['post'], url_path=r'(?P<booking_id>\d+)/ticket')
    def issue_ticket(self, request, booking_id=None):
        """
        Issue ticket for confirmed flight booking
        
        This endpoint issues tickets for a confirmed flight booking via AirIQ.
        For HELD bookings (BlockPNR=true), it will:
        1. Check payment status
        2. If not paid, require payment
        3. After payment, confirm the booking with AirIQ (convert HELD to CONFIRMED)
        4. Then issue the ticket
        
        For CONFIRMED bookings, it directly issues the ticket.
        """
        try:
            print("issue_ticket")
            booking, flight_booking = self.get_flight_booking(booking_id)
            
            # Check if already ticketed
            if flight_booking.status == 'TICKETED':
                return self.get_error_response(
                    message="Booking is already ticketed",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Handle HELD bookings (BlockPNR=true) - need payment and confirmation first
            if flight_booking.status == 'HELD':
                # Check if payment is done
                from django.db.models import Sum
                total_paid = booking.booking_payment.filter(is_transaction_success=True).aggregate(total=Sum('amount'))['total'] or 0
                try:
                    total_paid_float = float(total_paid)
                except Exception:
                    total_paid_float = 0.0
                
                balance_due = float(booking.final_amount) - total_paid_float
                
                # If payment not complete, require payment
                if balance_due > 0.01:  # Allow small rounding differences
                    # Get payment method and redirect URL from request
                    payment_method = (request.data.get('payment_method') or '').strip().upper()
                    redirect_url = request.data.get('redirect_url', '')
                    
                    # If no payment method provided, try to default to wallet if user is authenticated
                    if not payment_method and request.user and request.user.is_authenticated:
                        # Check if user has sufficient wallet balance
                        try:
                            from apps.booking.utils.booking_utils import check_wallet_balance_for_booking
                            company_id = None
                            if hasattr(request.user, 'default_group') and request.user.default_group in ('CORP-ADMIN', 'CORP-EMP', 'CORPORATE-GRP'):
                                company_id = getattr(request.user, 'company_id', None)
                            
                            can_pay, balance_info = check_wallet_balance_for_booking(booking, request.user, company_id=company_id)
                            if can_pay:
                                payment_method = 'WALLET'
                        except Exception as e:
                            self.log_error(f"Error checking wallet balance for default payment: {str(e)}")
                    
                    # Handle wallet payment
                    if payment_method == 'WALLET':
                        from apps.booking.utils.flight_payment_utils import FlightPaymentProcessor
                        from decimal import Decimal
                        
                        # Create payment processor for wallet payment
                        processor = FlightPaymentProcessor(booking, request.user, {
                            'payment_channel': 'WALLET',
                            'amount': str(balance_due),
                            'transaction_type': 'ticket_issuance_payment'
                        }, request=request)
                        
                        # Process wallet payment
                        payment_result = processor.initiate_payment(allow_confirmed=True)
                        
                        if not payment_result.get('success'):
                            return self.get_error_response(
                                message=f"Wallet payment failed: {payment_result.get('error', 'Unknown error')}",
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                        
                        # Wallet payment successful - proceed directly to ticket issuance
                        # For HELD bookings, we don't need to call Book API again
                        # We'll directly call IssueTicket API after payment
                        booking.refresh_from_db()
                        flight_booking.refresh_from_db()
                        
                        # Recalculate balance_due after payment
                        from django.db.models import Sum
                        total_paid_after = booking.booking_payment.filter(is_transaction_success=True).aggregate(total=Sum('amount'))['total'] or 0
                        try:
                            total_paid_float_after = float(total_paid_after)
                        except Exception:
                            total_paid_float_after = 0.0
                        
                        balance_due_after = float(booking.final_amount) - total_paid_float_after
                        
                        # Update status if still PENDING_PAYMENT (wallet payment for ticket issuance may not update status)
                        if flight_booking.status == 'PENDING_PAYMENT' and balance_due_after <= 0.01:
                            # Payment is complete, so update status to HELD (for BlockPNR bookings) or CONFIRMED
                            # Check if this was a BlockPNR booking
                            airiq_request = flight_booking.airiq_request_data or {}
                            if airiq_request.get('BlockPNR', False):
                                flight_booking.status = 'HELD'
                            else:
                                flight_booking.status = 'CONFIRMED'
                            flight_booking.save(update_fields=['status'])
                        
                        # Skip to ticket issuance section below (no need to confirm via Book API)
                        # Payment is complete, so we'll skip the status check for PENDING_PAYMENT
                    
                    # Handle PhonePe payment
                    elif payment_method in ['PHONEPE', 'PHONE_PAY', 'PHONE PAY']:
                        from apps.booking.utils.flight_payment_utils import FlightPaymentProcessor
                        from decimal import Decimal
                        from apps.booking.utils.db_utils import create_booking_payment_details
                        from IDBOOKAPI.utils import get_unique_id_from_time
                        
                        # Create payment detail with metadata for ticket issuance callback
                        append_id = get_unique_id_from_time()
                        payment_detail = create_booking_payment_details(booking.id, append_id)
                        
                        # Store metadata for callback to know this is for ticket issuance
                        update_booking_payment_details(payment_detail.merchant_transaction_id, {
                            'transaction_type': 'ticket_issuance_payment',
                            'booking_id': booking_id,
                            'flight_booking_id': flight_booking.id
                        })
                        
                        # Create payment processor with ticket issuance transaction type
                        # redirect_url is optional - FlightPaymentProcessor will use default callback URL based on transaction_type
                        payment_data = {
                            'payment_channel': 'PHONE PAY',
                            'amount': str(balance_due),
                            'transaction_type': 'ticket_issuance_payment'
                        }
                        if redirect_url:
                            payment_data['redirect_url'] = redirect_url
                        
                        processor = FlightPaymentProcessor(booking, request.user, payment_data, request=request)
                        
                        # Initiate PhonePe payment
                        payment_result = processor.initiate_payment(allow_confirmed=True)
                        
                        if payment_result.get('success'):
                            return self.get_response(
                                data={
                                    'payment_url': payment_result.get('payment_url'),
                                    'transaction_id': payment_result.get('transaction_id'),
                                    'payment_method': payment_method,
                                    'amount': float(balance_due),
                                    'message': 'Please complete payment to proceed with ticket issuance'
                                },
                                message="Payment gateway initiated. Complete payment to issue ticket.",
                                status="payment_required",
                                status_code=status.HTTP_200_OK
                            )
                        else:
                            return self.get_error_response(
                                message=f"Failed to initiate payment: {payment_result.get('error', 'Unknown error')}",
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                    
                    # Otherwise, return payment required error (no payment method provided or unsupported method)
                    else:
                        error_message = "Payment is required before ticket issuance"
                        if payment_method:
                            error_message += f". Unsupported payment method: {payment_method}. Supported methods: WALLET, PHONEPE, PHONE_PAY"
                        else:
                            error_message += ". Please provide payment_method (WALLET, PHONEPE, or PHONE_PAY) in the request"
                        
                        return self.get_error_response(
                            message=error_message,
                            status="error", 
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            errors=[{
                                "action": "redirect_to_payment",
                                "booking_id": booking_id,
                                "amount": str(balance_due),
                                "total_amount": str(booking.final_amount),
                                "paid_amount": str(total_paid_float),
                                "payment_method": payment_method if payment_method else None,
                                "redirect_url": redirect_url if redirect_url else None,
                                "supported_payment_methods": ["WALLET", "PHONEPE", "PHONE_PAY"]
                            }]
                        )
                
                # Payment is complete - for HELD bookings, we proceed directly to ticket issuance
                # No need to call Book API again - IssueTicket API will handle the ticket issuance
                # The booking status can remain HELD until ticket is issued
            
            # Validate booking status - allow HELD or CONFIRMED bookings for ticket issuance
            # HELD bookings with payment complete can proceed to ticket issuance
            # Also check if payment is complete even if status is still PENDING_PAYMENT (e.g., after wallet payment)
            if flight_booking.status == 'PENDING_PAYMENT':
                # Recalculate balance to check if payment was just completed
                from django.db.models import Sum
                total_paid_check = booking.booking_payment.filter(is_transaction_success=True).aggregate(total=Sum('amount'))['total'] or 0
                try:
                    total_paid_float_check = float(total_paid_check)
                except Exception:
                    total_paid_float_check = 0.0
                
                balance_due_check = float(booking.final_amount) - total_paid_float_check
                
                # If payment is still due, return error
                if balance_due_check > 0.01:
                    return self.get_error_response(
                        message="Payment is required before ticket issuance",
                        status="error", 
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        errors=[{
                            "action": "redirect_to_payment",
                            "booking_id": booking_id,
                            "amount": str(balance_due_check)
                        }]
                    )
                # Payment is complete, update status and continue
                else:
                    # Update status to HELD (for BlockPNR) or CONFIRMED
                    airiq_request = flight_booking.airiq_request_data or {}
                    if airiq_request.get('BlockPNR', False):
                        flight_booking.status = 'HELD'
                    else:
                        flight_booking.status = 'CONFIRMED'
                    flight_booking.save(update_fields=['status'])
            elif flight_booking.status not in ['HELD', 'CONFIRMED']:
                return self.get_error_response(
                    message=f"Tickets can only be issued for HELD or CONFIRMED bookings. Current status: {flight_booking.status}",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Get PNRs and track IDs - support both single fields and arrays
            airiq_pnr = flight_booking.airiq_pnr
            airline_pnr = flight_booking.airline_pnr
            airiq_track_id = flight_booking.airiq_track_id
            
            # Fallback to arrays if single fields are empty
            if not airiq_pnr:
                airiq_pnrs_list = flight_booking.airiq_pnrs or []
                if airiq_pnrs_list:
                    airiq_pnr = airiq_pnrs_list[0] if isinstance(airiq_pnrs_list, list) else str(airiq_pnrs_list)
            
            if not airline_pnr:
                airline_pnrs_list = flight_booking.airline_pnrs or []
                if airline_pnrs_list:
                    airline_pnr = airline_pnrs_list[0] if isinstance(airline_pnrs_list, list) else str(airline_pnrs_list)
            
            if not airiq_track_id:
                airiq_track_ids_list = flight_booking.airiq_track_ids or []
                if airiq_track_ids_list:
                    airiq_track_id = airiq_track_ids_list[0] if isinstance(airiq_track_ids_list, list) else str(airiq_track_ids_list)
            
            # Validate required AirIQ data
            if not all([airiq_track_id, airiq_pnr, airline_pnr]):
                return self.get_error_response(
                    message="Flight booking missing required PNR or track ID",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Get payment method from request (default to "T" for Agent Deposit)
            payment_method = request.data.get('payment_method', 'T').upper()
            redirect_url = request.data.get('redirect_url', '')
            
            # Validate payment method for AirIQ IssueTicket API
            # PaymentMode should be "T" for Agent Deposit
            payment_mode = 'T'  # Always use "T" for AirIQ IssueTicket API
            
            # Call AirIQ service to issue ticket
            ticket_response = airiq_service.issue_ticket(
                booking_track_id=airiq_track_id,
                airiq_pnr=airiq_pnr,
                airline_pnr=airline_pnr,
                booking_amount=float(booking.final_amount),
                payment_mode=payment_mode
            )
            
            # Save ticket response data properly
            self._save_ticket_response(booking, flight_booking, ticket_response)
            
            self.log_info(
                f"Ticket issued for booking {booking_id}",
                extra={
                    'booking_id': booking_id,
                    'flight_booking_id': flight_booking.id,
                    'airiq_pnr': flight_booking.airiq_pnr,
                    'user_id': request.user.id if request.user.is_authenticated else None
                }
            )
            
            return self.get_response(
                data={
                    'ticket_response': ticket_response,
                    'booking_status': flight_booking.status
                },
                message="Ticket issued successfully",
                status="success",
                status_code=status.HTTP_200_OK
            )
            
        except ValueError as e:
            return self.get_error_response(
                message=str(e),
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except AirIQException as e:
            self.log_error(f"AirIQ error issuing ticket for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message=f"Unable to issue ticket: {str(e)}",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            self.log_error(f"Error issuing ticket for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message="An unexpected error occurred",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='post',
        operation_description="Cancel flight booking",
        manual_parameters=[
            openapi.Parameter(
                'booking_id',
                openapi.IN_PATH,
                description="Flight booking ID",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'flag': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['PENALTY', 'CANCEL'],
                    default='CANCEL',
                    description="PENALTY to check cancellation penalty, CANCEL to cancel booking"
                ),
                'remarks': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Cancellation remarks (optional)"
                ),
                'guest_token': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Guest access token (required for guest bookings, optional for authenticated users)"
                )
            }
        ),
        responses={
            200: openapi.Response(
                description="Cancellation processed successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'cancellation_response': openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    description="Cancellation response from AirIQ"
                                ),
                                'booking_status': openapi.Schema(type=openapi.TYPE_STRING)
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description="Bad request"),
            404: openapi.Response(description="Booking not found"),
            500: openapi.Response(description="AirIQ service error")
        }
    )
    @action(detail=False, methods=['post'], url_path=r'(?P<booking_id>\d+)/cancel')
    def cancel_booking(self, request, booking_id=None):
        """
        Cancel flight booking or check cancellation penalty
        
        This endpoint cancels a flight booking via AirIQ or checks cancellation penalty.
        Supports multiple itineraries (round-trip, connecting flights) - cancels all flights
        and sums up penalties/refunds.
        
        Supports both authenticated users and guest bookings:
        - Authenticated users: Use JWT token in Authorization header
        - Guest users: Provide guest_token in request body or query params
        
        Important: Refunds are only processed if at least one cancellation succeeds.
        If all cancellations fail, booking status remains unchanged and no refund is processed.
        """
        try:
            # Support guest_token for guest bookings
            guest_token = request.data.get('guest_token') or request.query_params.get('guest_token')
            booking, flight_booking = self.get_flight_booking(booking_id, guest_token=guest_token)
            
            # Validate booking status
            if flight_booking.status in ['CANCELLED']:
                return self.get_error_response(
                    message="Booking is already cancelled",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Get request parameters
            flag = request.data.get('flag', 'CANCEL')
            remarks = request.data.get('remarks', f'Cancellation requested by user {request.user.id}')
            
            # Validate flag parameter
            if flag not in ['PENALTY', 'CANCEL']:
                return self.get_error_response(
                    message="Invalid flag. Must be 'PENALTY' or 'CANCEL'",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Persist cancel remark if provided
            if remarks:
                try:
                    flight_booking.cancel_remark = str(remarks)[:255]
                    flight_booking.save(update_fields=['cancel_remark'])
                except Exception:
                    pass
            
            # Determine all PNRs to cancel - support multiple itineraries
            pnrs_to_cancel = []
            
            # Check if we have multiple itineraries in booked_itineraries
            booked_itineraries = flight_booking.booked_itineraries or []
            if booked_itineraries:
                # Extract PNRs from booked_itineraries
                for itin in booked_itineraries:
                    airiq_pnr = itin.get('airiq_pnr', '').strip()
                    if airiq_pnr and airiq_pnr.upper() not in ('N/A', 'NA', 'NULL', ''):
                        pnrs_to_cancel.append({
                            'airiq_pnr': airiq_pnr,
                            'amount': itin.get('amount', '0'),
                            'track_id': itin.get('track_id', '')
                        })
            
            # Fallback to airiq_pnrs list if booked_itineraries is empty
            if not pnrs_to_cancel:
                airiq_pnrs_list = flight_booking.airiq_pnrs or []
                if airiq_pnrs_list:
                    for pnr in airiq_pnrs_list:
                        if pnr and str(pnr).strip().upper() not in ('N/A', 'NA', 'NULL', ''):
                            pnrs_to_cancel.append({
                                'airiq_pnr': str(pnr).strip(),
                                'amount': '0',  # Amount not available in airiq_pnrs
                                'track_id': ''
                            })
            
            # Final fallback to single airiq_pnr field
            if not pnrs_to_cancel:
                if flight_booking.airiq_pnr and flight_booking.airiq_pnr.strip().upper() not in ('N/A', 'NA', 'NULL', ''):
                    pnrs_to_cancel.append({
                        'airiq_pnr': flight_booking.airiq_pnr.strip(),
                        'amount': '0',
                        'track_id': flight_booking.airiq_track_id or ''
                    })
            
            # Validate that we have at least one PNR
            if not pnrs_to_cancel:
                return self.get_error_response(
                    message="Flight booking missing AirIQ PNR(s)",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Cancel all itineraries and collect responses/penalties
            all_cancellation_responses = []
            total_penalty_amount = 0.0
            cancellation_errors = []
            
            for pnr_info in pnrs_to_cancel:
                airiq_pnr = pnr_info['airiq_pnr']
                try:
                    cancellation_response = airiq_service.cancel_booking(
                        airiq_pnr=airiq_pnr,
                        flag=flag,
                        remarks=remarks
                    )
                    
                    # Extract penalty if present
                    penalty_amount_str = (cancellation_response or {}).get('PenalityAmount') or '0'
                    try:
                        penalty_amount = float(penalty_amount_str)
                        total_penalty_amount += penalty_amount
                    except Exception:
                        penalty_amount = 0.0
                    
                    all_cancellation_responses.append({
                        'airiq_pnr': airiq_pnr,
                        'response': cancellation_response,
                        'penalty_amount': penalty_amount,
                        'success': True
                    })
                    
                except Exception as e:
                    error_msg = str(e)
                    cancellation_errors.append({
                        'airiq_pnr': airiq_pnr,
                        'error': error_msg
                    })
                    all_cancellation_responses.append({
                        'airiq_pnr': airiq_pnr,
                        'response': None,
                        'penalty_amount': 0.0,
                        'success': False,
                        'error': error_msg
                    })
                    logger.error(f"Error cancelling PNR {airiq_pnr}: {error_msg}")
            
            # If checking penalty only, return aggregated penalty info
            if flag == 'PENALTY':
                # Persist last known penalty on the flight booking JSON field
                pv = flight_booking.pricing_validation_data or {}
                pv['cancel_penalty'] = {
                    'amount': total_penalty_amount,
                    'retrieved_at': str(timezone.now()),
                    'per_itinerary': [
                        {
                            'airiq_pnr': resp['airiq_pnr'],
                            'penalty_amount': resp['penalty_amount']
                        }
                        for resp in all_cancellation_responses
                    ]
                }
                flight_booking.pricing_validation_data = pv
                flight_booking.save(update_fields=['pricing_validation_data'])
                
                self.log_info(
                    f"Cancellation penalty checked for booking {booking_id} ({len(pnrs_to_cancel)} itineraries)",
                    extra={
                        'booking_id': booking_id,
                        'flight_booking_id': flight_booking.id,
                        'user_id': request.user.id,
                        'total_penalty': total_penalty_amount,
                        'itinerary_count': len(pnrs_to_cancel)
                    }
                )
                
                message = f"Cancellation penalty retrieved successfully for {len(pnrs_to_cancel)} itinerary(ies)"
                if cancellation_errors:
                    message += f". {len(cancellation_errors)} error(s) occurred."
                
                return self.get_response(
                    data={
                        'cancellation_responses': all_cancellation_responses,
                        'total_penalty_amount': total_penalty_amount,
                        'booking_status': flight_booking.status,
                        'errors': cancellation_errors if cancellation_errors else None
                    },
                    message=message,
                    status="success",
                    status_code=status.HTTP_200_OK
                )
            
            # Actual cancellation path - check if all cancellations succeeded
            successful_cancellations = [r for r in all_cancellation_responses if r.get('success')]
            
            # CRITICAL: If ALL cancellations failed, do NOT process refunds or update status
            if not successful_cancellations:
                # All cancellations failed - return error response
                error_messages = [err['error'] for err in cancellation_errors]
                combined_error = "; ".join(error_messages[:3])  # Limit to first 3 errors
                
                self.log_error(
                    f"All cancellations failed for booking {booking_id}. No refund processed.",
                    extra={
                        'booking_id': booking_id,
                        'flight_booking_id': flight_booking.id,
                        'airiq_pnrs': [p['airiq_pnr'] for p in pnrs_to_cancel],
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'cancellation_errors': cancellation_errors
                    }
                )
                
                return self.get_response(
                    data={
                        'cancellation_responses': all_cancellation_responses,
                        'booking_status': flight_booking.status,
                        'errors': cancellation_errors
                    },
                    message=f"Cancellation failed for all itineraries. {combined_error}",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    is_error=True
                )
            
            # At least one cancellation succeeded - proceed with status update and refund
            # Update booking status only if at least one cancellation succeeded
            flight_booking.status = 'CANCELLED'
            flight_booking.cancelled_at = timezone.now()
            flight_booking.save(update_fields=['status', 'cancelled_at'])
            
            # Update main booking status
            booking.status = 'canceled'
            booking.save(update_fields=['status'])
            
            # Compute refund = total_paid - total_penalty (sum of all penalties from successful cancellations)
            from django.db.models import Sum
            total_paid = booking.booking_payment.filter(is_transaction_success=True).aggregate(total=Sum('amount'))['total'] or 0
            try:
                total_paid_float = float(total_paid)
            except Exception:
                total_paid_float = 0.0
            
            # Only sum penalties from successful cancellations
            successful_penalty_total = sum(
                resp.get('penalty_amount', 0.0) 
                for resp in successful_cancellations
            )
            
            net_refund = max(total_paid_float - successful_penalty_total, 0.0)
            
            # Process refund using existing manager
            refund_summary = {
                'penalty_amount': successful_penalty_total,
                'total_paid': total_paid_float,
                'refund_amount': net_refund,
                'itineraries_cancelled': len(successful_cancellations),
                'total_itineraries': len(pnrs_to_cancel),
                'cancellation_details': [
                    {
                        'airiq_pnr': resp['airiq_pnr'],
                        'penalty_amount': resp['penalty_amount'],
                        'success': resp.get('success', False)
                    }
                    for resp in all_cancellation_responses
                ]
            }
            
            if net_refund > 0:
                from apps.booking.utils.flight_booking_utils import FlightCancellationManager
                cancel_mgr = FlightCancellationManager(booking)
                cancellation_details = {
                    'airiq_responses': all_cancellation_responses,
                    'total_penalty_amount': successful_penalty_total,
                    'total_paid': total_paid_float,
                    'itinerary_count': len(pnrs_to_cancel),
                    'successful_cancellations': len(successful_cancellations)
                }
                success, refund_status, refund_data = cancel_mgr.process_refund(
                    Decimal(str(net_refund)), 
                    cancellation_details
                )
                refund_summary['refund_status'] = refund_status
                # refund_data may contain Decimals; ensure primitive types
                try:
                    if isinstance(refund_data, dict) and 'refund_amount' in refund_data:
                        refund_summary['refund_merchant_transaction_id'] = refund_data.get('merchant_refund_id')
                except Exception:
                    pass
            else:
                refund_summary['refund_status'] = 'no_refund'
            
            # Log warning if some cancellations failed
            if cancellation_errors:
                logger.warning(
                    f"Partial cancellation for booking {booking_id}: "
                    f"{len(successful_cancellations)}/{len(pnrs_to_cancel)} succeeded. "
                    f"Errors: {cancellation_errors}"
                )
            
            self.log_info(
                f"Booking {booking_id} cancelled successfully ({len(successful_cancellations)}/{len(pnrs_to_cancel)} itineraries)",
                extra={
                    'booking_id': booking_id,
                    'flight_booking_id': flight_booking.id,
                    'airiq_pnrs': [p['airiq_pnr'] for p in pnrs_to_cancel],
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'refund_summary': refund_summary,
                    'cancellation_errors': cancellation_errors if cancellation_errors else None
                }
            )
            
            message = f"Booking cancelled successfully ({len(successful_cancellations)}/{len(pnrs_to_cancel)} itineraries)"
            if cancellation_errors:
                message += f". {len(cancellation_errors)} cancellation(s) had errors."
            
            return self.get_response(
                data={
                    'cancellation_responses': all_cancellation_responses,
                    'booking_status': flight_booking.status,
                    'refund': refund_summary,
                    'errors': cancellation_errors if cancellation_errors else None
                },
                message=message,
                status="success",
                status_code=status.HTTP_200_OK
            )
            
        except ValueError as e:
            return self.get_error_response(
                message=str(e),
                status="error",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except AirIQException as e:
            self.log_error(f"AirIQ error cancelling booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message=f"Unable to process cancellation: {str(e)}",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            self.log_error(f"Error cancelling booking {booking_id}: {str(e)}")
            print("Error cancelling booking:", str(e))
            return self.get_error_response(
                message="An unexpected error occurred",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='post',
        operation_description="Cancel held booking (BlockPNR). This endpoint is specifically for cancelling bookings that are in HELD status before ticket issuance.",
        manual_parameters=[
            openapi.Parameter(
                'booking_id',
                openapi.IN_PATH,
                description="Flight booking ID",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'airiq_pnr': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="AirIQ PNR (optional, will use booking's PNR if not provided)"
                ),
                'airline_pnr': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Airline PNR (optional, will use booking's PNR if not provided)"
                ),
                'guest_token': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Guest access token (required for guest bookings, optional for authenticated users)"
                )
            }
        ),
        responses={
            200: openapi.Response(
                description="Hold cancellation processed successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'cancel_status': openapi.Schema(type=openapi.TYPE_STRING),
                                'remarks': openapi.Schema(type=openapi.TYPE_STRING),
                                'booking_status': openapi.Schema(type=openapi.TYPE_STRING),
                                'airiq_response': openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    description="Hold cancel response from AirIQ"
                                )
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(description="Bad request - booking not in HELD status or missing PNRs"),
            404: openapi.Response(description="Booking not found"),
            500: openapi.Response(description="AirIQ service error")
        }
    )
    @action(detail=False, methods=['post'], url_path=r'(?P<booking_id>\d+)/cancel-hold')
    def cancel_hold(self, request, booking_id=None):
        """
        Cancel held booking (BlockPNR)
        This endpoint cancels bookings that are in HELD status (BlockPNR=true bookings)
        """
        try:
            booking, flight_booking = self.get_flight_booking(booking_id)
            
            # Validate booking is in HELD status
            if flight_booking.status != 'HELD':
                return self.get_error_response(
                    message=f"Hold cancellation is only available for HELD bookings. Current status: {flight_booking.status}",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Get PNRs from request or use booking's PNRs
            airiq_pnr = request.data.get('airiq_pnr') or flight_booking.airiq_pnr
            airline_pnr = request.data.get('airline_pnr') or flight_booking.airline_pnr
            
            if not airiq_pnr:
                return self.get_error_response(
                    message="AirIQ PNR is required for hold cancellation",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            if not airline_pnr:
                return self.get_error_response(
                    message="Airline PNR is required for hold cancellation",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Call AirIQ hold cancel API
            try:
                cancel_response = airiq_service.hold_cancel(
                    airiq_pnr=airiq_pnr,
                    airline_pnr=airline_pnr
                )
            except AirIQException as e:
                self.log_error(f"AirIQ hold cancel failed for booking {booking_id}: {str(e)}")
                return self.get_error_response(
                    message=f"Failed to cancel hold: {str(e)}",
                    status="error",
                    status_code=status.HTTP_502_BAD_GATEWAY
                )
            
            # Check response status
            cancel_status = cancel_response.get('CancelStatus', '').upper()
            status_info = cancel_response.get('Status', {})
            result_code = status_info.get('ResultCode', '0')
            remarks = cancel_response.get('Remarks', '')
            
            # Update booking status based on response
            if cancel_status == 'SUCCESS' and result_code == '1':
                # Successfully cancelled
                flight_booking.status = 'CANCELLED'
                flight_booking.cancelled_at = timezone.now()
                
                # Save hold cancel response
                blob = flight_booking.airiq_response_data or {}
                blob['hold_cancel_response'] = cancel_response
                flight_booking.airiq_response_data = blob
                
                flight_booking.save(update_fields=['status', 'cancelled_at', 'airiq_response_data'])
                
                # Update main booking status
                booking.status = 'canceled'
                booking.save(update_fields=['status'])
                
                self.log_info(
                    f"Hold cancelled successfully for booking {booking_id}",
                    extra={
                        'booking_id': booking.id,
                        'flight_booking_id': flight_booking.id,
                        'airiq_pnr': airiq_pnr,
                        'airline_pnr': airline_pnr,
                        'user_id': request.user.id if request.user.is_authenticated else None
                    }
                )
                
                return self.get_response(
                    data={
                        'cancel_status': cancel_status,
                        'remarks': remarks,
                        'booking_status': flight_booking.status,
                        'airiq_response': cancel_response
                    },
                    message=remarks or "Hold cancelled successfully",
                    status="success",
                    status_code=status.HTTP_200_OK
                )
            else:
                # Cancellation failed or pending
                error_msg = status_info.get('Error', '') or remarks or 'Hold cancellation failed'
                
                # Save response even if failed
                blob = flight_booking.airiq_response_data or {}
                blob['hold_cancel_response'] = cancel_response
                flight_booking.airiq_response_data = blob
                flight_booking.save(update_fields=['airiq_response_data'])
                
                self.log_error(
                    f"Hold cancel failed for booking {booking_id}: {error_msg}",
                    extra={
                        'booking_id': booking.id,
                        'flight_booking_id': flight_booking.id,
                        'airiq_pnr': airiq_pnr,
                        'airline_pnr': airline_pnr,
                        'cancel_status': cancel_status,
                        'result_code': result_code
                    }
                )
                
                return self.get_error_response(
                    message=error_msg,
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    data={
                        'cancel_status': cancel_status,
                        'remarks': remarks,
                        'booking_status': flight_booking.status,
                        'airiq_response': cancel_response
                    }
                )
                
        except ValueError as e:
            return self.get_error_response(
                message=str(e),
                status="error",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except AirIQException as e:
            self.log_error(f"AirIQ error cancelling hold for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message=f"Unable to process hold cancellation: {str(e)}",
                status="error",
                status_code=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            self.log_error(f"Unexpected error cancelling hold for booking {booking_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            return self.get_error_response(
                message="An unexpected error occurred while cancelling hold",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='post',
        operation_description="Get reschedule availability for a booking. For round-trip, provide flights array with onward and return details.",
        manual_parameters=[
            openapi.Parameter('booking_id', openapi.IN_PATH, description="Flight booking ID", type=openapi.TYPE_INTEGER, required=True)
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'flights': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description='Array of flight segments to reschedule (for round-trip, include both onward and return)',
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'flight_date': openapi.Schema(type=openapi.TYPE_STRING, description='YYYY-MM-DD'),
                            'departure_station': openapi.Schema(type=openapi.TYPE_STRING, description='3-letter IATA code'),
                            'arrival_station': openapi.Schema(type=openapi.TYPE_STRING, description='3-letter IATA code')
                        }
                    )
                ),
                'flight_date': openapi.Schema(type=openapi.TYPE_STRING, description='YYYY-MM-DD (for single flight/backward compatibility)'),
                'departure_station': openapi.Schema(type=openapi.TYPE_STRING, description='IATA origin (backward compatibility)'),
                'arrival_station': openapi.Schema(type=openapi.TYPE_STRING, description='IATA destination (backward compatibility)'),
                'remarks': openapi.Schema(type=openapi.TYPE_STRING)
            }
        )
    )
    @action(detail=False, methods=['post'], url_path=r'(?P<booking_id>\d+)/reschedule/availability')
    def reschedule_availability(self, request, booking_id=None):
        try:
            booking, flight_booking = self.get_flight_booking(booking_id)

            if not flight_booking.airiq_pnr:
                return self.get_error_response(
                    message="AirIQ PNR missing on booking",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Derive trip type
            trip_type = flight_booking.search_session_data.get('trip_type') or 'O'
            if trip_type not in ['O', 'R', 'Y']:
                mapping = {'ONE-WAY': 'O', 'ROUND': 'R', 'ROUND-TRIP': 'R'}
                trip_type = mapping.get(flight_booking.flight_trip, 'O')

            remarks = request.data.get('remarks', '')
            # Save reschedule remark if provided
            if remarks:
                try:
                    flight_booking.reschedule_remark = str(remarks)[:255]
                    flight_booking.save(update_fields=['reschedule_remark'])
                except Exception:
                    pass
            
            # Build flight segments for reschedule
            flight_segments = []
            
            # Check if flights array is provided (new format)
            if 'flights' in request.data and isinstance(request.data['flights'], list):
                for idx, flight in enumerate(request.data['flights'], 1):
                    if not all([flight.get('flight_date'), flight.get('departure_station'), flight.get('arrival_station')]):
                        return self.get_error_response(
                            message=f"Flight #{idx}: flight_date, departure_station, and arrival_station are all required",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    
                    try:
                        flight_date_str = str(flight['flight_date']).strip()
                        
                        # Log for debugging
                        self.log_info(f"Flight #{idx} date parsing: '{flight_date_str}' (len={len(flight_date_str)})")
                        
                        if not flight_date_str:
                            return self.get_error_response(
                                message=f"Flight #{idx}: flight_date cannot be empty",
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                        
                        # Try to parse the date - support both YYYY-MM-DD and YYYYMMDD
                        dt = None
                        if '-' in flight_date_str:
                            dt = datetime.strptime(flight_date_str, '%Y-%m-%d')
                        elif len(flight_date_str) == 8 and flight_date_str.isdigit():
                            dt = datetime.strptime(flight_date_str, '%Y%m%d')
                        else:
                            return self.get_error_response(
                                message=f"Flight #{idx}: Invalid date format '{flight_date_str}'. Use YYYY-MM-DD or YYYYMMDD",
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                        
                        # Validate date is not in the past
                        today = datetime.now().date()
                        if dt.date() < today:
                            return self.get_error_response(
                                message=f"Flight #{idx}: Date cannot be in the past (received: {flight_date_str})",
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                        
                        flight_date_fmt = dt.strftime('%Y%m%d')
                        self.log_info(f"Flight #{idx} date converted: {flight_date_str} -> {flight_date_fmt}")
                        
                    except ValueError as e:
                        self.log_error(f"Flight #{idx} date parsing error: {str(e)} | Input: '{flight.get('flight_date')}'")
                        return self.get_error_response(
                            message=f"Flight #{idx}: Invalid date format. Use YYYY-MM-DD (e.g., 2025-12-25) | Received: '{flight.get('flight_date')}'",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    except Exception as e:
                        self.log_error(f"Flight #{idx} unexpected error: {type(e).__name__}: {str(e)} | Input: '{flight.get('flight_date')}'")
                        return self.get_error_response(
                            message=f"Flight #{idx}: Unexpected error processing date '{flight.get('flight_date')}': {str(e)}",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    
                    flight_segments.append({
                        'departure_station': str(flight['departure_station']).strip().upper(),
                        'arrival_station': str(flight['arrival_station']).strip().upper(),
                        'flight_date': flight_date_fmt
                    })
            else:
                # Backward compatibility: single flight date format
                flight_date = request.data.get('flight_date')
                if not flight_date:
                    return self.get_error_response(
                        message="flight_date is required (or use 'flights' array for multiple segments)",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                
                dep = request.data.get('departure_station') or flight_booking.flying_from or ''
                arr = request.data.get('arrival_station') or flight_booking.flying_to or ''
                
                # Clean and validate flight_date
                flight_date_str = str(flight_date).strip() if flight_date else ''
                
                # Debug logging
                self.log_info(f"Single flight reschedule: date='{flight_date_str}' | type={type(flight_date).__name__} | len={len(flight_date_str)} | dep={dep} | arr={arr}")
                
                if not flight_date_str:
                    return self.get_error_response(
                        message="flight_date cannot be empty",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                
                if not dep or not arr:
                    return self.get_error_response(
                        message="departure_station and arrival_station are required",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                
                try:
                    # Try to parse the date - support both YYYY-MM-DD and YYYYMMDD
                    dt = None
                    if '-' in flight_date_str:
                        dt = datetime.strptime(flight_date_str, '%Y-%m-%d')
                    elif len(flight_date_str) == 8 and flight_date_str.isdigit():
                        dt = datetime.strptime(flight_date_str, '%Y%m%d')
                    else:
                        return self.get_error_response(
                            message=f"Invalid date format '{flight_date_str}'. Use YYYY-MM-DD (e.g., 2025-11-21) or YYYYMMDD (e.g., 20251121)",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Validate date is not in the past
                    today = datetime.now().date()
                    if dt.date() < today:
                        return self.get_error_response(
                            message=f"Date cannot be in the past. Today: {today}, Received: {dt.date()} ('{flight_date_str}')",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Convert to YYYYMMDD format for AirIQ API
                    flight_date_fmt = dt.strftime('%Y%m%d')
                    self.log_info(f"Date parsed successfully: '{flight_date_str}' -> '{flight_date_fmt}'")
                    
                except ValueError as e:
                    self.log_error(f"Date parsing ValueError: {str(e)} | Input: '{flight_date_str}'")
                    return self.get_error_response(
                        message=f"Invalid date format. Expected YYYY-MM-DD (e.g., 2025-11-21), got '{flight_date_str}' | Error: {str(e)}",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                except Exception as e:
                    self.log_error(f"Unexpected date parsing error: {type(e).__name__}: {str(e)} | Input: '{flight_date_str}' | Raw: {repr(flight_date)}")
                    return self.get_error_response(
                        message=f"Unexpected error processing date '{flight_date_str}': {type(e).__name__}: {str(e)}",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                
                flight_segments.append({
                    'departure_station': str(dep).strip().upper(),
                    'arrival_station': str(arr).strip().upper(),
                    'flight_date': flight_date_fmt
                })

            # Validate flight_segments before API call
            if not flight_segments:
                return self.get_error_response(
                    message="No valid flight segments to reschedule",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if multiple PNRs exist (roundtrip with separate PNRs)
            airline_pnrs = flight_booking.airline_pnrs or []
            airiq_pnrs = flight_booking.airiq_pnrs or []
            
            # Use single PNR fields if lists are empty (backward compatibility)
            if not airline_pnrs and flight_booking.airline_pnr:
                airline_pnrs = [flight_booking.airline_pnr]
            if not airiq_pnrs and flight_booking.airiq_pnr:
                airiq_pnrs = [flight_booking.airiq_pnr]
            
            # Check if user wants to reschedule specific PNR(s) only
            pnr_index = request.data.get('pnr_index')  # 0-based index
            specific_airiq_pnr = request.data.get('airiq_pnr')  # Specific PNR to reschedule
            
            # Determine if we need to handle multiple PNRs
            has_multiple_pnrs = len(airline_pnrs) > 1 or len(airiq_pnrs) > 1
            is_roundtrip = flight_booking.flight_trip == 'ROUND'
            
            # Filter PNRs if specific one requested
            if pnr_index is not None:
                try:
                    pnr_idx = int(pnr_index)
                    if 0 <= pnr_idx < len(airiq_pnrs):
                        airiq_pnrs = [airiq_pnrs[pnr_idx]]
                        airline_pnrs = [airline_pnrs[pnr_idx]] if pnr_idx < len(airline_pnrs) else []
                        has_multiple_pnrs = False  # Treat as single for this request
                    else:
                        return self.get_error_response(
                            message=f"Invalid pnr_index {pnr_idx}. Valid range: 0-{len(airiq_pnrs)-1}",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                except (ValueError, TypeError):
                    return self.get_error_response(
                        message="pnr_index must be a valid integer",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            elif specific_airiq_pnr:
                # Find PNR by value
                try:
                    pnr_idx = airiq_pnrs.index(specific_airiq_pnr)
                    airiq_pnrs = [airiq_pnrs[pnr_idx]]
                    airline_pnrs = [airline_pnrs[pnr_idx]] if pnr_idx < len(airline_pnrs) else []
                    has_multiple_pnrs = False
                except ValueError:
                    return self.get_error_response(
                        message=f"AirIQ PNR '{specific_airiq_pnr}' not found in booking",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            if has_multiple_pnrs and is_roundtrip:
                # Handle multiple PNRs: call API for each segment separately
                from apps.booking.utils.flight_booking_utils import process_multi_pnr_reschedule_availability
                
                # Prepare reschedule requests for each PNR
                reschedule_requests = []
                
                # Check if segments are provided grouped by PNR
                segments_by_pnr = request.data.get('segments_by_pnr') or []
                
                if segments_by_pnr and len(segments_by_pnr) == len(airiq_pnrs):
                    # Segments are explicitly grouped by PNR
                    for idx, airiq_pnr in enumerate(airiq_pnrs):
                        segment_trip_type = 'O' if idx == 0 else 'R'
                        pnr_segments = segments_by_pnr[idx] or []
                        
                        # Convert to flight_segments format
                        segment_flights = []
                        for seg in pnr_segments:
                            segment_flights.append({
                                'departure_station': str(seg.get('departure_station', '')).strip().upper(),
                                'arrival_station': str(seg.get('arrival_station', '')).strip().upper(),
                                'flight_date': str(seg.get('flight_date', '')).strip()
                            })
                        
                        if not segment_flights:
                            return self.get_error_response(
                                message=f"No flight segments provided for {segment_trip_type} journey (PNR {idx + 1})",
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                        
                        reschedule_requests.append({
                            'airiq_pnr': airiq_pnr,
                            'airline_pnr': airline_pnrs[idx] if idx < len(airline_pnrs) else '',
                            'trip_type': segment_trip_type,
                            'flight_segments': segment_flights,
                            'remarks': remarks
                        })
                else:
                    # Auto-separate segments based on route matching
                    # Extract route info from AirIQ booking response
                    from apps.booking.utils.flight_booking_utils import extract_route_info_from_airiq_response
                    route_info = extract_route_info_from_airiq_response(flight_booking)
                    
                    onward_origin = route_info.get('onward_origin', '').strip().upper() or (flight_booking.flying_from or '').strip().upper()
                    onward_dest = route_info.get('onward_destination', '').strip().upper() or (flight_booking.flying_to or '').strip().upper()
                    return_origin = route_info.get('return_origin', '').strip().upper() or (flight_booking.return_from or '').strip().upper()
                    return_dest = route_info.get('return_destination', '').strip().upper() or (flight_booking.return_to or '').strip().upper()
                    
                    # Log extracted route info for debugging
                    self.log_info(f"Extracted route info: onward={onward_origin}-{onward_dest}, return={return_origin}-{return_dest}")
                    self.log_info(f"Route info from AirIQ: {route_info.get('itineraries', [])}")
                    
                    # Get itinerary info from route_info for better matching
                    itineraries = route_info.get('itineraries', [])
                    
                    # For roundtrip, first PNR is onward (O), second is return (R)
                    for idx, airiq_pnr in enumerate(airiq_pnrs):
                        segment_trip_type = 'O' if idx == 0 else 'R'
                        segment_flights = []
                        
                        # Try to match using itinerary info from AirIQ response
                        if idx < len(itineraries):
                            itin_info = itineraries[idx]
                            itin_segments = itin_info.get('segments', [])
                            
                            # Match segments by origin-destination pairs
                            for req_seg in flight_segments:
                                req_dep = req_seg.get('departure_station', '').strip().upper()
                                req_arr = req_seg.get('arrival_station', '').strip().upper()
                                
                                # Check if this segment matches any segment in the itinerary
                                for itin_seg in itin_segments:
                                    itin_origin = (itin_seg.get('origin', '') or '').strip().upper()
                                    itin_dest = (itin_seg.get('destination', '') or '').strip().upper()
                                    
                                    # Match by origin (and optionally destination)
                                    if req_dep == itin_origin:
                                        segment_flights.append(req_seg)
                                        break
                        
                        # Fallback: match by route origin if itinerary matching didn't work
                        if not segment_flights:
                            if idx == 0:
                                # Onward segment: match by origin
                                for seg in flight_segments:
                                    dep = seg.get('departure_station', '').strip().upper()
                                    if dep == onward_origin:
                                        segment_flights.append(seg)
                                    # Also check if it's the first segment chronologically
                                    elif not segment_flights and onward_origin:
                                        segment_flights.append(seg)
                                        break
                                
                                # If still empty, take first half of segments
                                if not segment_flights:
                                    mid_point = len(flight_segments) // 2
                                    segment_flights = flight_segments[:mid_point] if mid_point > 0 else flight_segments
                            else:
                                # Return segment: match by return origin
                                for seg in flight_segments:
                                    dep = seg.get('departure_station', '').strip().upper()
                                    if dep == return_origin:
                                        segment_flights.append(seg)
                                
                                # If still empty, take second half of segments
                                if not segment_flights:
                                    mid_point = len(flight_segments) // 2
                                    segment_flights = flight_segments[mid_point:] if mid_point > 0 else []
                        
                        # Validate we have segments for this PNR
                        if not segment_flights:
                            return self.get_error_response(
                                message=f"No flight segments found for {segment_trip_type} journey (PNR {idx + 1}). Please provide 'segments_by_pnr' array with segments for each PNR, or ensure segments are in correct order.",
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                        
                        seg_routes = [f"{s.get('departure_station')}-{s.get('arrival_station')}" for s in segment_flights]
                        self.log_info(f"PNR {idx + 1} ({segment_trip_type}): {len(segment_flights)} segments - {seg_routes}")
                        
                        reschedule_requests.append({
                            'airiq_pnr': airiq_pnr,
                            'airline_pnr': airline_pnrs[idx] if idx < len(airline_pnrs) else '',
                            'trip_type': segment_trip_type,
                            'flight_segments': segment_flights,
                            'remarks': remarks
                        })
                
                # Log all requests before processing
                self.log_info(f"Processing {len(reschedule_requests)} reschedule requests for {len(airiq_pnrs)} PNRs")
                
                # Process all segments
                result = process_multi_pnr_reschedule_availability(
                    flight_booking=flight_booking,
                    reschedule_requests=reschedule_requests,
                    airiq_service=airiq_service
                )
                
                if not result.get('success'):
                    return self.get_error_response(
                        message=f"Failed to fetch reschedule availability for some segments: {result.get('errors', [])}",
                        status="error",
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        data=result
                    )
                
                return self.get_response(
                    data={'reschedule_availability': result},
                    message='Reschedule availability retrieved for all segments',
                    status="success",
                    status_code=status.HTTP_200_OK
                )
            else:
                # Single PNR case (backward compatibility)
                self.log_info(f"Calling AirIQ reschedule_availability with: trip_type={trip_type}, airiq_pnr={airiq_pnrs[0] if airiq_pnrs else flight_booking.airiq_pnr}, segments={flight_segments}")
                
                resp = airiq_service.reschedule_availability(
                    trip_type=trip_type,
                    flight_segments=flight_segments,
                    airiq_pnr=airiq_pnrs[0] if airiq_pnrs else flight_booking.airiq_pnr,
                    remarks=remarks
                )

                return self.get_response(
                    data={'reschedule_availability': resp},
                    message='Reschedule availability retrieved',
                    status="success",
                    status_code=status.HTTP_200_OK
                )
        except AirIQException as e:
            self.log_error(f"AirIQ reschedule availability error for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message=f"Unable to fetch reschedule availability: {str(e)}",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            self.log_error(f"Error in reschedule availability for booking {booking_id}: {str(e)}")
            print("Error in reschedule availability:", str(e))
            return self.get_error_response(
                message="An unexpected error occurred",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @swagger_auto_schema(
        method='post',
        operation_description="Confirm reschedule for a booking",
        manual_parameters=[
            openapi.Parameter('booking_id', openapi.IN_PATH, description="Flight booking ID", type=openapi.TYPE_INTEGER, required=True)
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['track_id', 'flight_details', 'contact_no'],
            properties={
                'track_id': openapi.Schema(type=openapi.TYPE_STRING),
                'contact_no': openapi.Schema(type=openapi.TYPE_STRING),
                'remarks': openapi.Schema(type=openapi.TYPE_STRING),
                'flag': openapi.Schema(type=openapi.TYPE_STRING, enum=['CHECKFARE', 'CONFIRM'], default='CONFIRM'),
                'flight_details': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'origin': openapi.Schema(type=openapi.TYPE_STRING),
                        'destination': openapi.Schema(type=openapi.TYPE_STRING),
                        'trip_type': openapi.Schema(type=openapi.TYPE_STRING, enum=['O','R','Y']),
                        'segments': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_OBJECT)),
                        'base_amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'gross_amount': openapi.Schema(type=openapi.TYPE_NUMBER)
                    }
                )
            }
        )
    )
    @action(detail=False, methods=['post'], url_path=r'(?P<booking_id>\d+)/reschedule/confirm')
    def reschedule_confirm(self, request, booking_id=None):
        try:
            booking, flight_booking = self.get_flight_booking(booking_id)
            
            # Check for PNRs (support both single and multiple)
            airline_pnrs = flight_booking.airline_pnrs or []
            airiq_pnrs = flight_booking.airiq_pnrs or []
            
            # Use single PNR fields if lists are empty (backward compatibility)
            if not airline_pnrs and flight_booking.airline_pnr:
                airline_pnrs = [flight_booking.airline_pnr]
            if not airiq_pnrs and flight_booking.airiq_pnr:
                airiq_pnrs = [flight_booking.airiq_pnr]
            
            if not airiq_pnrs:
                return self.get_error_response(
                    message="PNRs missing on booking",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            contact_no = request.data.get('contact_no')
            remarks = request.data.get('remarks', '')
            flag = request.data.get('flag', 'CONFIRM')
            
            # Support both single flight_details and multiple segments
            flight_details_list = request.data.get('flight_details_list') or []
            flight_details = request.data.get('flight_details') or {}
            
            # If flight_details_list is provided, use it; otherwise use single flight_details
            if flight_details_list:
                # Multiple segments (onward and return)
                if len(flight_details_list) != len(airiq_pnrs):
                    return self.get_error_response(
                        message=f"Number of flight_details ({len(flight_details_list)}) must match number of PNRs ({len(airiq_pnrs)})",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            elif flight_details:
                # Single segment (backward compatibility)
                flight_details_list = [flight_details]
            else:
                return self.get_error_response(
                    message="flight_details or flight_details_list is required",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            if not contact_no:
                return self.get_error_response(
                    message="contact_no is required",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Check if user wants to reschedule specific PNR(s) only
            pnr_index = request.data.get('pnr_index')  # 0-based index
            specific_airiq_pnr = request.data.get('airiq_pnr')  # Specific PNR to reschedule
            
            # Filter PNRs if specific one requested
            original_airiq_pnrs = airiq_pnrs.copy() if isinstance(airiq_pnrs, list) else list(airiq_pnrs)
            original_airline_pnrs = airline_pnrs.copy() if isinstance(airline_pnrs, list) else list(airline_pnrs)
            
            if pnr_index is not None:
                try:
                    pnr_idx = int(pnr_index)
                    if 0 <= pnr_idx < len(airiq_pnrs):
                        airiq_pnrs = [airiq_pnrs[pnr_idx]]
                        airline_pnrs = [airline_pnrs[pnr_idx]] if pnr_idx < len(airline_pnrs) else []
                    else:
                        return self.get_error_response(
                            message=f"Invalid pnr_index {pnr_idx}. Valid range: 0-{len(original_airiq_pnrs)-1}",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                except (ValueError, TypeError):
                    return self.get_error_response(
                        message="pnr_index must be a valid integer",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            elif specific_airiq_pnr:
                # Find PNR by value
                try:
                    pnr_idx = original_airiq_pnrs.index(specific_airiq_pnr)
                    airiq_pnrs = [original_airiq_pnrs[pnr_idx]]
                    airline_pnrs = [original_airline_pnrs[pnr_idx]] if pnr_idx < len(original_airline_pnrs) else []
                except ValueError:
                    return self.get_error_response(
                        message=f"AirIQ PNR '{specific_airiq_pnr}' not found in booking",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            
            # Check if multiple PNRs exist (roundtrip with separate PNRs)
            has_multiple_pnrs = len(original_airiq_pnrs) > 1
            is_roundtrip = flight_booking.flight_trip == 'ROUND'

            if has_multiple_pnrs and is_roundtrip:
                # Handle multiple PNRs: call API for each segment separately
                from apps.booking.utils.flight_booking_utils import process_multi_pnr_reschedule_confirm
                
                # Prepare reschedule requests for each PNR
                reschedule_requests = []
                track_ids = request.data.get('track_ids') or []
                
                # If single track_id provided, use it for all segments
                if not track_ids:
                    track_id = request.data.get('track_id')
                    if track_id:
                        track_ids = [track_id] * len(airiq_pnrs)
                    else:
                        return self.get_error_response(
                            message="track_id or track_ids is required",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                
                if len(track_ids) != len(airiq_pnrs):
                    return self.get_error_response(
                        message=f"Number of track_ids ({len(track_ids)}) must match number of PNRs ({len(airiq_pnrs)})",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                
                for idx, airiq_pnr in enumerate(airiq_pnrs):
                    # Determine trip type: first is onward (O), rest are return (R)
                    segment_trip_type = 'O' if idx == 0 else 'R'
                    
                    reschedule_requests.append({
                        'airiq_pnr': airiq_pnr,
                        'track_id': track_ids[idx],
                        'trip_type': segment_trip_type,
                        'flight_details': flight_details_list[idx],
                        'contact_no': contact_no,
                        'remarks': remarks
                    })
                
                # First check fare if flag is CHECKFARE
                if flag == 'CHECKFARE':
                    result = process_multi_pnr_reschedule_confirm(
                        flight_booking=flight_booking,
                        reschedule_requests=reschedule_requests,
                        airiq_service=airiq_service,
                        flag='CHECKFARE'
                    )
                    
                    successful_checks = result.get('responses', [])
                    failed_checks = result.get('errors', [])
                    
                    if not successful_checks:
                        # All failed
                        return self.get_error_response(
                            message=f"Failed to check fare for all segments: {failed_checks}",
                            status="error",
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            data=result
                        )
                    
                    # Partial or full success
                    if failed_checks:
                        return self.get_response(
                            data={'reschedule_response': result},
                            message=f'Reschedule fare checked for {len(successful_checks)} of {len(successful_checks) + len(failed_checks)} segments. Some segments failed.',
                            status="partial_success",
                            status_code=status.HTTP_207_MULTI_STATUS
                        )
                    
                    return self.get_response(
                        data={'reschedule_response': result},
                        message='Reschedule fare checked for all segments',
                        status="success",
                        status_code=status.HTTP_200_OK
                    )
                
                # For CONFIRM, first check fare to get penalty/fare difference
                check_fare_result = process_multi_pnr_reschedule_confirm(
                    flight_booking=flight_booking,
                    reschedule_requests=reschedule_requests,
                    airiq_service=airiq_service,
                    flag='CHECKFARE'
                )
                
                # Handle partial success in fare check
                successful_fare_checks = check_fare_result.get('responses', [])
                failed_fare_checks = check_fare_result.get('errors', [])
                
                if not successful_fare_checks:
                    # All failed
                    return self.get_error_response(
                        message=f"Failed to check fare for all segments: {failed_fare_checks}",
                        status="error",
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        data=check_fare_result
                    )
                
                # Aggregate penalties and fare differences from successful checks only
                total_penalty = Decimal('0')
                total_fare_difference = Decimal('0')
                for resp_item in successful_fare_checks:
                    total_penalty += Decimal(str(resp_item.get('penalty', 0)))
                    total_fare_difference += Decimal(str(resp_item.get('fare_difference', 0)))
                
                total_payment = total_penalty + total_fare_difference
                
                response_data = {
                    'reschedule_response': check_fare_result,
                    'partial_success': len(failed_fare_checks) > 0,
                    'successful_segments': len(successful_fare_checks),
                    'failed_segments': len(failed_fare_checks)
                }
                
                # Prepare reschedule request data for payment handlers
                reschedule_request = {
                    'reschedule_requests': reschedule_requests,
                    'multi_pnr': True
                }
                
                # Process payment if required (total_payment > 0)
                if total_payment > 0:
                    payment_channel = (request.data.get('payment_channel') or 'WALLET').upper()
                    if payment_channel not in ('WALLET', 'PHONE PAY'):
                        return self.get_error_response(
                            message='Unsupported payment_channel. Use WALLET or PHONE PAY',
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )

                    from apps.booking.utils.flight_payment_utils import (
                        handle_reschedule_wallet_payment, handle_reschedule_phonepe_payment
                    )

                    if payment_channel == 'WALLET':
                        # Wallet payment: deduct -> call AirIQ -> update or refund
                        payment_result = handle_reschedule_wallet_payment(
                            booking=booking,
                            flight_booking=flight_booking,
                            user=request.user,
                            reschedule_request=reschedule_request,
                            reschedule_response=check_fare_result,
                            payment_amount=total_payment,
                            request=request
                        )

                        if not payment_result.get('success'):
                            return self.get_error_response(
                                message=f"Reschedule payment failed: {payment_result.get('error', 'Unknown error')}",
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST,
                                data=response_data
                            )

                        response_data['payment'] = {
                            'success': True,
                            'transaction_id': payment_result.get('transaction_id'),
                            'payment_method': payment_result.get('payment_method'),
                            'amount': float(total_payment)
                        }
                    else:
                        # PhonePe payment: save request data -> initiate payment -> handle in callback
                        payment_result = handle_reschedule_phonepe_payment(
                            booking=booking,
                            flight_booking=flight_booking,
                            user=request.user,
                            reschedule_request=reschedule_request,
                            reschedule_response=check_fare_result,
                            payment_amount=total_payment,
                            request=request
                        )

                        if not payment_result.get('success'):
                            return self.get_error_response(
                                message=f"Failed to initiate reschedule payment: {payment_result.get('error', 'Unknown error')}",
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST,
                                data=response_data
                            )

                        response_data['payment'] = {
                            'success': True,
                            'payment_method': payment_result.get('payment_method'),
                            'payment_url': payment_result.get('payment_url'),
                            'transaction_id': payment_result.get('transaction_id'),
                            'amount': float(total_payment)
                        }
                elif total_payment < 0:
                    # Refund case: new fare is less than old fare
                    # Confirm reschedule only for segments that passed fare check
                    successful_requests = []
                    for resp_item in successful_fare_checks:
                        pnr_idx = resp_item.get('pnr_index')
                        if pnr_idx is not None and pnr_idx < len(reschedule_requests):
                            successful_requests.append(reschedule_requests[pnr_idx])
                    
                    if not successful_requests:
                        return self.get_error_response(
                            message="No segments available for reschedule confirmation",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST,
                            data=response_data
                        )
                    
                    confirm_result = process_multi_pnr_reschedule_confirm(
                        flight_booking=flight_booking,
                        reschedule_requests=successful_requests,
                        airiq_service=airiq_service,
                        flag='CONFIRM'
                    )
                    
                    # Handle partial success in confirmation
                    successful_confirmations = confirm_result.get('responses', [])
                    failed_confirmations = confirm_result.get('errors', [])
                    
                    if not successful_confirmations:
                        return self.get_error_response(
                            message=f"Failed to confirm reschedule for all segments: {failed_confirmations}",
                            status="error",
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            data=confirm_result
                        )
                    
                    response_data['reschedule_response'] = confirm_result
                    response_data['partial_success'] = len(failed_confirmations) > 0
                    
                    # Process reschedule success for each successful confirmation
                    from apps.booking.utils.flight_booking_utils import (
                        process_reschedule_success, process_reschedule_refund, record_reschedule_failure
                    )
                    
                    # Update booking for each successful reschedule
                    all_new_pnrs = original_airiq_pnrs.copy() if isinstance(original_airiq_pnrs, list) else list(original_airiq_pnrs)
                    successful_pnr_indices = []
                    
                    for resp_item in successful_confirmations:
                        pnr_idx = resp_item.get('pnr_index')
                        old_pnr = resp_item.get('old_airiq_pnr') or resp_item.get('airiq_pnr')
                        airiq_resp = resp_item.get('response', {})
                        new_pnr = airiq_resp.get('New_PNR', '')
                        
                        if new_pnr and pnr_idx is not None:
                            # Update PNR at specific index
                            if pnr_idx < len(all_new_pnrs):
                                all_new_pnrs[pnr_idx] = new_pnr
                            successful_pnr_indices.append(pnr_idx)
                            
                            # Process success for this PNR
                            process_reschedule_success(
                                booking, flight_booking, airiq_resp, remarks,
                                pnr_index=pnr_idx, old_airiq_pnr=old_pnr
                            )
                    
                    # Record failures
                    for err_item in failed_confirmations:
                        pnr_idx = err_item.get('pnr_index')
                        old_pnr = err_item.get('airiq_pnr')
                        error_msg = err_item.get('error', 'Unknown error')
                        if pnr_idx is not None and old_pnr:
                            record_reschedule_failure(flight_booking, old_pnr, error_msg, pnr_index=pnr_idx)
                    
                    # Update PNRs list
                    if all_new_pnrs:
                        flight_booking.airiq_pnrs = all_new_pnrs
                        flight_booking.save(update_fields=['airiq_pnrs'])
                    
                    # Process refund
                    refund_amount = abs(total_payment)
                    reschedule_details = {
                        'penalty': float(total_penalty),
                        'fare_difference': float(total_fare_difference),
                        'total_segments': len(successful_confirmations),
                        'responses': successful_confirmations
                    }
                    
                    refund_result = process_reschedule_refund(booking, refund_amount, reschedule_details)
                    
                    if refund_result.get('success'):
                        response_data['refund'] = {
                            'success': True,
                            'refund_amount': refund_result.get('refund_amount'),
                            'refund_method': refund_result.get('refund_method'),
                            'refund_status': refund_result.get('refund_status'),
                            'transaction_id': refund_result.get('transaction_id'),
                            'message': refund_result.get('message')
                        }
                    else:
                        self.log_error(f"Reschedule successful but refund failed for booking {booking_id}: {refund_result.get('error')}")
                        response_data['refund'] = {
                            'success': False,
                            'error': refund_result.get('error'),
                            'refund_amount': float(refund_amount),
                            'note': 'Reschedule completed but refund processing failed. Please contact support.'
                        }
                else:
                    # No payment or refund required (total_payment == 0)
                    # Confirm reschedule only for segments that passed fare check
                    successful_requests = []
                    for resp_item in successful_fare_checks:
                        pnr_idx = resp_item.get('pnr_index')
                        if pnr_idx is not None and pnr_idx < len(reschedule_requests):
                            successful_requests.append(reschedule_requests[pnr_idx])
                    
                    if not successful_requests:
                        return self.get_error_response(
                            message="No segments available for reschedule confirmation",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST,
                            data=response_data
                        )
                    
                    confirm_result = process_multi_pnr_reschedule_confirm(
                        flight_booking=flight_booking,
                        reschedule_requests=successful_requests,
                        airiq_service=airiq_service,
                        flag='CONFIRM'
                    )
                    
                    # Handle partial success
                    successful_confirmations = confirm_result.get('responses', [])
                    failed_confirmations = confirm_result.get('errors', [])
                    
                    if not successful_confirmations:
                        return self.get_error_response(
                            message=f"Failed to confirm reschedule for all segments: {failed_confirmations}",
                            status="error",
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            data=confirm_result
                        )
                    
                    response_data['reschedule_response'] = confirm_result
                    response_data['partial_success'] = len(failed_confirmations) > 0
                    
                    # Process reschedule success for each successful confirmation
                    from apps.booking.utils.flight_booking_utils import (
                        process_reschedule_success, record_reschedule_failure
                    )
                    
                    all_new_pnrs = original_airiq_pnrs.copy() if isinstance(original_airiq_pnrs, list) else list(original_airiq_pnrs)
                    
                    for resp_item in successful_confirmations:
                        pnr_idx = resp_item.get('pnr_index')
                        old_pnr = resp_item.get('old_airiq_pnr') or resp_item.get('airiq_pnr')
                        airiq_resp = resp_item.get('response', {})
                        new_pnr = airiq_resp.get('New_PNR', '')
                        
                        if new_pnr and pnr_idx is not None:
                            if pnr_idx < len(all_new_pnrs):
                                all_new_pnrs[pnr_idx] = new_pnr
                            
                            process_reschedule_success(
                                booking, flight_booking, airiq_resp, remarks,
                                pnr_index=pnr_idx, old_airiq_pnr=old_pnr
                            )
                    
                    # Record failures
                    for err_item in failed_confirmations:
                        pnr_idx = err_item.get('pnr_index')
                        old_pnr = err_item.get('airiq_pnr')
                        error_msg = err_item.get('error', 'Unknown error')
                        if pnr_idx is not None and old_pnr:
                            record_reschedule_failure(flight_booking, old_pnr, error_msg, pnr_index=pnr_idx)
                    
                    if all_new_pnrs:
                        flight_booking.airiq_pnrs = all_new_pnrs
                        flight_booking.save(update_fields=['airiq_pnrs'])
            else:
                # Single PNR case (backward compatibility)
                track_id = request.data.get('track_id')
                if not track_id:
                    return self.get_error_response(
                        message="track_id is required",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
                
                flight_details = flight_details_list[0] if flight_details_list else {}
                
                # First check fare if flag is CHECKFARE
                if flag == 'CHECKFARE':
                    resp = airiq_service.reschedule_booking(
                        airiq_pnr=airiq_pnrs[0],
                        track_id=track_id,
                        flight_details=flight_details,
                        contact_no=contact_no,
                        remarks=remarks,
                        flag='CHECKFARE'
                    )
                    return self.get_response(
                        data={'reschedule_response': resp},
                        message='Reschedule fare checked',
                        status="success",
                        status_code=status.HTTP_200_OK
                    )

                # For CONFIRM, first check fare to get penalty/fare difference
                check_fare_resp = airiq_service.reschedule_booking(
                    airiq_pnr=airiq_pnrs[0],
                    track_id=track_id,
                    flight_details=flight_details,
                    contact_no=contact_no,
                    remarks=remarks,
                    flag='CHECKFARE'
                )

                # Check if payment is required or refund is due
                penalty = Decimal(str(check_fare_resp.get('Penalty', 0) or 0))
                fare_difference = Decimal(str(check_fare_resp.get('FareDifference', 0) or 0))
                total_payment = penalty + fare_difference

                response_data = {'reschedule_response': check_fare_resp}

                # Prepare reschedule request data
                reschedule_request = {
                    'airiq_pnr': airiq_pnrs[0],
                    'track_id': track_id,
                    'flight_details': flight_details,
                    'contact_no': contact_no,
                    'remarks': remarks,
                }

            # Process payment if required (total_payment > 0)
            if total_payment > 0:
                payment_channel = (request.data.get('payment_channel') or 'WALLET').upper()
                if payment_channel not in ('WALLET', 'PHONE PAY'):
                    return self.get_error_response(
                        message='Unsupported payment_channel. Use WALLET or PHONE PAY',
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

                from apps.booking.utils.flight_payment_utils import (
                    handle_reschedule_wallet_payment, handle_reschedule_phonepe_payment
                )

                if payment_channel == 'WALLET':
                    # Wallet payment: deduct -> call AirIQ -> update or refund
                    payment_result = handle_reschedule_wallet_payment(
                        booking=booking,
                        flight_booking=flight_booking,
                        user=request.user,
                        reschedule_request=reschedule_request,
                        reschedule_response=check_fare_resp,
                        payment_amount=total_payment,
                        request=request
                    )

                    if not payment_result.get('success'):
                        return self.get_error_response(
                            message=f"Reschedule payment failed: {payment_result.get('error', 'Unknown error')}",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST,
                            data=response_data
                        )

                    response_data['payment'] = {
                        'success': True,
                        'transaction_id': payment_result.get('transaction_id'),
                        'payment_method': payment_result.get('payment_method'),
                        'amount': float(total_payment)
                    }
                else:
                    # PhonePe payment: save request data -> initiate payment -> handle in callback
                    payment_result = handle_reschedule_phonepe_payment(
                        booking=booking,
                        flight_booking=flight_booking,
                        user=request.user,
                        reschedule_request=reschedule_request,
                        reschedule_response=check_fare_resp,
                        payment_amount=total_payment,
                        request=request
                    )

                    if not payment_result.get('success'):
                        return self.get_error_response(
                            message=f"Failed to initiate reschedule payment: {payment_result.get('error', 'Unknown error')}",
                            status="error",
                            status_code=status.HTTP_400_BAD_REQUEST,
                            data=response_data
                        )

                    response_data['payment'] = {
                        'success': True,
                        'payment_method': payment_result.get('payment_method'),
                        'payment_url': payment_result.get('payment_url'),
                        'transaction_id': payment_result.get('transaction_id'),
                        'amount': float(total_payment)
                    }
            elif total_payment < 0:
                # Refund case: new fare is less than old fare
                # First confirm reschedule, then process refund
                resp = airiq_service.reschedule_booking(
                    airiq_pnr=flight_booking.airiq_pnr,
                    track_id=track_id,
                    flight_details=flight_details,
                    contact_no=contact_no,
                    remarks=remarks,
                    flag='CONFIRM'
                )
                response_data['reschedule_response'] = resp
                
                # Process reschedule success (update booking details)
                from apps.booking.utils.flight_booking_utils import process_reschedule_success, process_reschedule_refund
                process_reschedule_success(booking, flight_booking, resp, remarks)
                
                # Process refund (refund_amount is positive, so negate total_payment)
                refund_amount = abs(total_payment)
                reschedule_details = {
                    'penalty': float(penalty),
                    'fare_difference': float(fare_difference),
                    'old_booking_amount': float(check_fare_resp.get('OldBookingAmount', 0) or 0),
                    'new_booking_amount': float(check_fare_resp.get('NewBookingAmount', 0) or 0),
                    'new_pnr': check_fare_resp.get('New_PNR', ''),
                }
                
                refund_result = process_reschedule_refund(booking, refund_amount, reschedule_details)
                
                if refund_result.get('success'):
                    response_data['refund'] = {
                        'success': True,
                        'refund_amount': refund_result.get('refund_amount'),
                        'refund_method': refund_result.get('refund_method'),
                        'refund_status': refund_result.get('refund_status'),
                        'transaction_id': refund_result.get('transaction_id'),
                        'message': refund_result.get('message')
                    }
                else:
                    # Log refund failure but don't fail the reschedule
                    self.log_error(f"Reschedule successful but refund failed for booking {booking_id}: {refund_result.get('error')}")
                    response_data['refund'] = {
                        'success': False,
                        'error': refund_result.get('error'),
                        'refund_amount': float(refund_amount),
                        'note': 'Reschedule completed but refund processing failed. Please contact support.'
                    }
            else:
                # No payment or refund required (total_payment == 0)
                resp = airiq_service.reschedule_booking(
                    airiq_pnr=flight_booking.airiq_pnr,
                    track_id=track_id,
                    flight_details=flight_details,
                    contact_no=contact_no,
                    remarks=remarks,
                    flag='CONFIRM'
                )
                response_data['reschedule_response'] = resp
                
                from apps.booking.utils.flight_booking_utils import process_reschedule_success
                process_reschedule_success(booking, flight_booking, resp, remarks)

            self.log_info(f"Reschedule confirmed for booking {booking_id}")
            return self.get_response(
                data=response_data,
                message='Reschedule processed successfully',
                status="success",
                status_code=status.HTTP_200_OK
            )
        except AirIQException as e:
            self.log_error(f"AirIQ reschedule error for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message=f"Unable to process reschedule: {str(e)}",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            self.log_error(f"Error in reschedule confirm for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message="An unexpected error occurred",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
