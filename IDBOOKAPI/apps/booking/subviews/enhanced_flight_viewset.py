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
import logging
import uuid
from decimal import Decimal

from ..models import Booking, FlightBooking, FlightPassenger
from ..serializers import BookingSerializer
from ..utils.flight_booking_utils import FlightBookingProcessor, FlightBookingAuthManager
from apps.flights.services.pricing_service import flight_pricing_service
from apps.flights.services.airiq_service import airiq_service, AirIQException
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

    def get_flight_booking(self, booking_id):
        """Helper to fetch booking and attached flight booking with access validation."""
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
                'otp': openapi.Schema(type=openapi.TYPE_STRING, description='OTP for guest booking verification')
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
            
            # Handle authentication
            auth_manager = FlightBookingAuthManager(request.data, request.user)
            is_eligible, auth_message, auth_user = auth_manager.validate_user_eligibility()
            
            if not is_eligible:
                if request.data.get('guest_booking') and not auth_user:
                    # Initiate guest booking verification
                    if not request.data.get('otp'):
                        success, message, verification_data = auth_manager.initiate_guest_booking()
                        if success:
                            return self.get_response(
                                data=verification_data,
                                message=message,
                                status="verification_required",
                                status_code=status.HTTP_202_ACCEPTED
                            )
                        else:
                            return self.get_error_response(
                                message=message,
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        # Verify OTP and create guest user
                        success, message, guest_user = auth_manager.verify_guest_booking_otp(request.data['otp'])
                        if not success:
                            return self.get_error_response(
                                message=message,
                                status="error",
                                status_code=status.HTTP_400_BAD_REQUEST
                            )
                        auth_user = guest_user
                else:
                    return self.get_error_response(
                        message=auth_message,
                        status="error",
                        status_code=status.HTTP_401_UNAUTHORIZED
                    )
            
            # Use authenticated user (either logged in or created guest user)
            booking_user = auth_user if auth_user else request.user
            
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
            
            # Check agent balance using AirIQ service
            agent_balance_check = self._check_agent_balance(pricing_validation['final_amount'])
            if not agent_balance_check['success']:
                return self.get_error_response(
                    message="We're unable to process your booking at this time. Please try again later or contact support for assistance.",
                    status="error",
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
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
            
            # Create booking WITHOUT AirIQ integration (payment pending)
            with transaction.atomic():
                booking, flight_booking = self._create_booking_local_only(
                    processor, request.data, pricing_validation
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
                'booking_details': {
                    'flying_from': flight_booking.flying_from,
                    'flying_to': flight_booking.flying_to,
                    'departure_date': flight_booking.departure_date.isoformat() if flight_booking.departure_date else None,
                    'flight_trip': flight_booking.flight_trip,
                    'passenger_count': booking.adult_count + booking.child_count + booking.infant_count
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
            self.log_error(f"Flight booking creation error: {str(e)}")
            return self.get_error_response(
                message="An error occurred while creating the booking",
                status="error",
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
    
    def _normalize_itinerary_flights(self, itin_list: list, default_token: str = None, flights_override: list = None) -> list:
        """Normalize itinerary list to expected AirIQ booking request structure.
        - Preserve PaymentInfo exactly as provided (no calculation)
        - Normalize flights key to 'FlighstInfo'
        - Inject pricing token into 'Token' when missing
        - If flights_override is provided (from pricing response), use it
        """
        norm = []
        for item in (itin_list or []):
            new_item = {}
            token_val = item.get('Token') or default_token
            if token_val:
                new_item['Token'] = token_val
            flights = flights_override if flights_override is not None else (item.get('FlighstInfo') or item.get('FlightsInfo') or [])
            new_item['FlighstInfo'] = flights
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
        
        # Extract TrackId and Flights from pricing response if available
        track_from_price = None
        flights_from_price = None
        if isinstance(price_resp, dict):
            pi = (price_resp.get('PriceItenaryInfo') or [])
            if pi:
                track_from_price = pi[0].get('Trackid') or pi[0].get('TrackId')
                ar = pi[0].get('AvailabilityResponse') or []
                if ar:
                    flights_from_price = ar[0].get('Flights') or []
        
        # Map pricing Flights to FlighstInfo structure expected in booking request
        mapped_flights = []
        if isinstance(flights_from_price, list):
            for seg in flights_from_price:
                mapped_flights.append({
                    'FlightID': seg.get('FlightID') or seg.get('FlightId') or seg.get('Flightid'),
                    'FlightNumber': seg.get('FlightNumber'),
                    'Origin': seg.get('Origin'),
                    'Destination': seg.get('Destination'),
                    'DepartureDateTime': seg.get('DepartureDateTime'),
                    'ArrivalDateTime': seg.get('ArrivalDateTime')
                })
        
        # Counts as integers
        adult = int(request_data.get('AdultCount', 1) or 0)
        child = int(request_data.get('ChildCount', 0) or 0)
        infant = int(request_data.get('InfantCount', 0) or 0)
        
        # Normalize itinerary list and inject latest pricing token; override flights with pricing Flights
        itin_list = request_data.get('ItineraryFlightsInfo') or []
        itin_norm = self._normalize_itinerary_flights(itin_list, default_token=pricing_token, flights_override=mapped_flights if mapped_flights else None)
        
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
    
    def _extract_pricing_from_request(self, request_data: dict) -> dict:
        """Extract pricing directly from request data without API recalculation"""
        try:
            itinerary_flights = request_data.get('ItineraryFlightsInfo', [])
            
            if not itinerary_flights:
                return {
                    'success': False,
                    'message': 'Flight itinerary information is required'
                }
            
            # Extract Token from ItineraryFlightsInfo[0]
            pricing_token = ''
            if itinerary_flights:
                pricing_token = itinerary_flights[0].get('Token', '')
            
            # Extract pricing_response from request if available
            pricing_response = request_data.get('pricing_response', {})
            
            # Extract TotalAmount directly from PaymentInfo (mandatory)
            # BaseAmount and GrossAmount are optional
            total_amount = 0
            base_amount = 0
            gross_amount = 0
            tax_breakdown = {}
            total_discount = 0
            net_amount = 0
            total_tax_amount = 0
            
            for flight_info in itinerary_flights:
                payment_info = flight_info.get('PaymentInfo', [])
                if payment_info:
                    payment_data = payment_info[0]
                    # TotalAmount is the final amount - directly use it
                    total_amount += float(payment_data.get('TotalAmount', 0))
                    
                    # BaseAmount and GrossAmount are optional - use if available
                    base_amount += float(payment_data.get('BaseAmount', 0))
                    gross_amount += float(payment_data.get('GrossAmount', 0))
                    
                    # Extract optional discount, net amount, and tax amount
                    total_discount += float(payment_data.get('totalDiscount', 0))
                    net_amount += float(payment_data.get('netamount', 0))
                    total_tax_amount += float(payment_data.get('TotalTaxAmount', 0))
                    
                    # Extract tax details if available
                    taxes = payment_data.get('Taxes', [])
                    for tax in taxes:
                        tax_code = tax.get('Code', '')
                        tax_amount = float(tax.get('Amount', 0))
                        if tax_code in tax_breakdown:
                            tax_breakdown[tax_code] += tax_amount
                        else:
                            tax_breakdown[tax_code] = tax_amount
            
            if total_amount <= 0:
                return {
                    'success': False,
                    'message': 'TotalAmount must be greater than zero'
                }
            
            # Use TotalAmount as the final amount (no recalculation)
            final_amount = total_amount
            
            # If base_amount not provided, use total_amount
            if base_amount <= 0:
                base_amount = total_amount
            
            # Extract GST breakdown (optional, based on available data)
            gst_breakdown = self._extract_gst_from_new_response_structure(
                base_amount, final_amount, tax_breakdown
            )
            
            return {
                'success': True,
                'final_amount': final_amount,
                'pricing_response': pricing_response if pricing_response else request_data,
                'gst_breakdown': gst_breakdown,
                'basic_amount': base_amount,
                'tax_breakdown': tax_breakdown,
                'pricing_token': pricing_token,
                'total_discount': total_discount,
                'net_amount': net_amount,
                'total_tax_amount': total_tax_amount
            }
                
        except Exception as e:
            logger.error(f"Pricing extraction error: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to extract pricing from request'
            }
    
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
    
    def _create_booking_local_only(self, processor: FlightBookingProcessor, 
                                 request_data: dict, pricing_validation: dict) -> tuple:
        """Create booking locally without AirIQ integration"""
        
        # Create local booking records only
        booking, flight_booking = processor.create_booking_without_airiq()
        
        # Store normalized AirIQ request data (without AgentInfo)
        airiq_req_struct = self._build_airiq_booking_request(request_data, pricing_validation)
        flight_booking.airiq_request_data = airiq_req_struct
        flight_booking.pricing_validation_data = pricing_validation
        
        # Set initial status
        flight_booking.status = 'PENDING_PAYMENT'
        flight_booking.booking_reference = processor.generate_confirmation_code()
        
        # Extract flight details from request
        itinerary_flights = request_data.get('ItineraryFlightsInfo', [])
        if itinerary_flights and 'FlighstInfo' in itinerary_flights[0]:
            flight_info = itinerary_flights[0]['FlighstInfo'][0]
            flight_booking.flying_from = flight_info.get('Origin', request_data.get('BaseOrigin', ''))
            flight_booking.flying_to = flight_info.get('Destination', request_data.get('BaseDestination', ''))
            flight_booking.flight_no = flight_info.get('FlightNumber', '')
            
            # Parse departure date
            departure_str = flight_info.get('DepartureDateTime', '')
            if departure_str:
                try:
                    flight_booking.departure_date = datetime.strptime(departure_str, '%d %b %Y %H:%M')
                except ValueError:
                    pass
        
        flight_booking.flight_trip = request_data.get('TripType', 'O')
        flight_booking.save()
        
        # Update main booking
        booking.confirmation_code = flight_booking.booking_reference
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
            
            response_data = {
                'booking_id': booking.id,
                'booking_reference': flight_booking.booking_reference,
                'status': flight_booking.status,
                'airiq_pnr': flight_booking.airiq_pnr,
                'airline_pnr': flight_booking.airline_pnr,
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
                'airiq_status': airiq_status
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
            first = itins[0]
            items = first.get('Item') or []
            if items:
                hdr = items[0]
                # Track ID
                track_id = hdr.get('BookingTrackId') or hdr.get('TrackId') or ''
                if track_id and not flight_booking.airiq_track_id:
                    flight_booking.airiq_track_id = track_id
                # AirIQ PNR
                airiq_pnr = hdr.get('AirIqPNR') or hdr.get('AiriqPNR') or ''
                if airiq_pnr and not flight_booking.airiq_pnr:
                    flight_booking.airiq_pnr = airiq_pnr
                # Amounts
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
                # Infer status
                ticket_status = (hdr.get('TicketStatus') or '').upper()
                if not flight_booking.status or flight_booking.status in ['INITIATED', 'PENDING_PAYMENT', 'HELD', 'CONFIRMED']:
                    if ticket_numbers:
                        flight_booking.status = 'TICKETED'
                    elif ticket_status == 'CONFIRMED':
                        flight_booking.status = 'CONFIRMED'
                # Persist amounts if missing on main booking
                if gross_amount is not None and float(booking.final_amount or 0) == 0.0:
                    from decimal import Decimal
                    booking.final_amount = Decimal(str(gross_amount))
                # Sync parent booking status
                if flight_booking.status in ['CONFIRMED', 'TICKETED'] and booking.status != 'confirmed':
                    booking.status = 'confirmed'
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
        The booking must be in 'CONFIRMED' status with valid PNRs.
        """
        try:
            booking, flight_booking = self.get_flight_booking(booking_id)
            
            # Validate booking status
            if flight_booking.status == 'PENDING_PAYMENT':
                return self.get_error_response(
                    message="Payment is required before ticket issuance",
                    status="error", 
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    errors=[{
                        "action": "redirect_to_payment",
                        "booking_id": booking_id,
                        "amount": str(booking.final_amount)
                    }]
                )
            elif flight_booking.status != 'CONFIRMED':
                return self.get_error_response(
                    message=f"Tickets can only be issued for confirmed bookings. Current status: {flight_booking.status}",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if already ticketed
            if flight_booking.status == 'TICKETED':
                return self.get_error_response(
                    message="Booking is already ticketed",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate required AirIQ data
            if not all([flight_booking.airiq_track_id, flight_booking.airiq_pnr, flight_booking.airline_pnr]):
                return self.get_error_response(
                    message="Flight booking missing required PNR or track ID",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Call AirIQ service to issue ticket
            ticket_response = airiq_service.issue_ticket(
                booking_track_id=flight_booking.airiq_track_id,
                airiq_pnr=flight_booking.airiq_pnr,
                airline_pnr=flight_booking.airline_pnr,
                booking_amount=float(booking.final_amount)
            )
            
            # Update booking status to ticketed
            flight_booking.status = 'TICKETED'
            
            # Extract ticket numbers if available in response
            if 'TicketNumbers' in ticket_response:
                flight_booking.ticket_numbers = ticket_response['TicketNumbers']
            
            flight_booking.save()
            
            # Update main booking status
            booking.status = 'confirmed'
            booking.save()
            
            self.log_info(
                f"Ticket issued for booking {booking_id}",
                extra={
                    'booking_id': booking_id,
                    'flight_booking_id': flight_booking.id,
                    'airiq_pnr': flight_booking.airiq_pnr,
                    'user_id': request.user.id
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
        The booking must have valid AirIQ PNR.
        """
        try:
            booking, flight_booking = self.get_flight_booking(booking_id)
            
            # Validate booking status
            if flight_booking.status in ['CANCELLED']:
                return self.get_error_response(
                    message="Booking is already cancelled",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate required AirIQ data
            if not flight_booking.airiq_pnr:
                return self.get_error_response(
                    message="Flight booking missing AirIQ PNR",
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
            
            # Call AirIQ service to cancel booking or check penalty
            cancellation_response = airiq_service.cancel_booking(
                airiq_pnr=flight_booking.airiq_pnr,
                flag=flag,
                remarks=remarks
            )
            
            # Extract penalty if present and persist for reference
            penalty_amount_str = (cancellation_response or {}).get('PenalityAmount') or '0'
            try:
                penalty_amount = float(penalty_amount_str)
            except Exception:
                penalty_amount = 0.0
            
            if flag == 'PENALTY':
                # Persist last known penalty on the flight booking JSON field
                pv = flight_booking.pricing_validation_data or {}
                pv['cancel_penalty'] = {
                    'amount': penalty_amount,
                    'retrieved_at': str(timezone.now())
                }
                flight_booking.pricing_validation_data = pv
                flight_booking.save(update_fields=['pricing_validation_data'])
                
                self.log_info(
                    f"Cancellation penalty checked for booking {booking_id}",
                    extra={
                        'booking_id': booking_id,
                        'flight_booking_id': flight_booking.id,
                        'user_id': request.user.id
                    }
                )
                message = "Cancellation penalty retrieved successfully"
                return self.get_response(
                    data={
                        'cancellation_response': cancellation_response,
                        'booking_status': flight_booking.status
                    },
                    message=message,
                    status="success",
                    status_code=status.HTTP_200_OK
                )
            
            # Actual cancellation path
            
            flight_booking.status = 'CANCELLED'
            flight_booking.cancelled_at = timezone.now()
            flight_booking.save(update_fields=['status', 'cancelled_at'])
            
            # Update main booking status
            booking.status = 'canceled'
            booking.save(update_fields=['status'])
            
            # Compute refund = total_paid - penalty
            from django.db.models import Sum
            total_paid = booking.booking_payment.filter(is_transaction_success=True).aggregate(total=Sum('amount'))['total'] or 0
            try:
                total_paid_float = float(total_paid)
            except Exception:
                total_paid_float = 0.0
            net_refund = max(total_paid_float - penalty_amount, 0.0)
            
            # Process refund using existing manager
            refund_summary = {
                'penalty_amount': penalty_amount,
                'total_paid': total_paid_float,
                'refund_amount': net_refund
            }
            if net_refund > 0:
                from apps.booking.utils.flight_booking_utils import FlightCancellationManager
                cancel_mgr = FlightCancellationManager(booking)
                cancellation_details = {
                    'airiq_response': cancellation_response,
                    'penalty_amount': penalty_amount,
                    'total_paid': total_paid_float
                }
                success, refund_status, refund_data = cancel_mgr.process_refund(Decimal(str(net_refund)), cancellation_details)
                refund_summary['refund_status'] = refund_status
                # refund_data may contain Decimals; ensure primitive types
                try:
                    if isinstance(refund_data, dict) and 'refund_amount' in refund_data:
                        refund_summary['refund_merchant_transaction_id'] = refund_data.get('merchant_refund_id')
                except Exception:
                    pass
            else:
                refund_summary['refund_status'] = 'no_refund'
            
            self.log_info(
                f"Booking {booking_id} cancelled successfully",
                extra={
                    'booking_id': booking_id,
                    'flight_booking_id': flight_booking.id,
                    'airiq_pnr': flight_booking.airiq_pnr,
                    'user_id': request.user.id,
                    'refund_summary': refund_summary
                }
            )
            
            return self.get_response(
                data={
                    'cancellation_response': cancellation_response,
                    'booking_status': flight_booking.status,
                    'refund': refund_summary
                },
                message="Booking cancelled successfully",
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
        operation_description="Get reschedule availability for a booking",
        manual_parameters=[
            openapi.Parameter('booking_id', openapi.IN_PATH, description="Flight booking ID", type=openapi.TYPE_INTEGER, required=True)
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['flight_date'],
            properties={
                'flight_date': openapi.Schema(type=openapi.TYPE_STRING, description='YYYY-MM-DD'),
                'departure_station': openapi.Schema(type=openapi.TYPE_STRING, description='IATA origin (optional)'),
                'arrival_station': openapi.Schema(type=openapi.TYPE_STRING, description='IATA destination (optional)'),
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
                mapping = {'ONE-WAY': 'O', 'ROUND': 'R'}
                trip_type = mapping.get(flight_booking.flight_trip, 'O')

            dep = request.data.get('departure_station') or flight_booking.flying_from or ''
            arr = request.data.get('arrival_station') or flight_booking.flying_to or ''
            flight_date = request.data.get('flight_date')
            remarks = request.data.get('remarks', '')

            try:
                dt = datetime.datetime.strptime(flight_date, '%Y-%m-%d')
                flight_date_fmt = dt.strftime('%Y%m%d')
            except Exception:
                return self.get_error_response(
                    message="Invalid flight_date format. Use YYYY-MM-DD",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            resp = airiq_service.reschedule_availability(
                trip_type=trip_type,
                departure_station=dep,
                arrival_station=arr,
                flight_date=flight_date_fmt,
                airiq_pnr=flight_booking.airiq_pnr,
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
            if not all([flight_booking.airiq_pnr, flight_booking.airline_pnr]):
                return self.get_error_response(
                    message="PNRs missing on booking",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            track_id = request.data.get('track_id')
            contact_no = request.data.get('contact_no')
            remarks = request.data.get('remarks', '')
            flag = request.data.get('flag', 'CONFIRM')
            flight_details = request.data.get('flight_details') or {}
            if not all([track_id, contact_no, flight_details]):
                return self.get_error_response(
                    message="track_id, contact_no and flight_details are required",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            resp = airiq_service.reschedule_booking(
                airiq_pnr=flight_booking.airiq_pnr,
                track_id=track_id,
                flight_details=flight_details,
                contact_no=contact_no,
                remarks=remarks,
                flag=flag
            )

            self.log_info(f"Reschedule requested for booking {booking_id}")
            return self.get_response(
                data={'reschedule_response': resp},
                message='Reschedule processed',
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
