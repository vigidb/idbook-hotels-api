"""
Flight booking viewset for IDBOOK Hotels API
Provides endpoints for flight booking operations including seatmap, ticketing, and cancellation
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging
import datetime

from ..models import Booking, FlightBooking, FlightPassenger
from ..serializers import BookingSerializer
from apps.flights.services.airiq_service import airiq_service, AirIQException
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin

logger = logging.getLogger(__name__)


class FlightBookingViewSet(viewsets.ViewSet, StandardResponseMixin, LoggingMixin):
    """
    ViewSet for flight booking operations
    Provides endpoints for:
    1. Get seat map for flight booking
    2. Issue ticket for confirmed booking
    3. Cancel flight booking
    """
    permission_classes = [IsAuthenticated]

    def get_flight_booking(self, booking_id):
        """Helper method to get flight booking with validation"""
        booking = get_object_or_404(
            Booking.objects.select_related('flight_booking'),
            id=booking_id,
            booking_type='FLIGHT',
            user=self.request.user
        )
        
        if not booking.flight_booking:
            raise ValueError("Flight booking details not found")
        
        return booking, booking.flight_booking

    @swagger_auto_schema(
        method='get',
        operation_description="Get seat map for flight booking",
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
                description="Seat map retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'seat_map': openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    description="Seat map data from AirIQ"
                                )
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
    @action(detail=False, methods=['get'], url_path=r'(?P<booking_id>\d+)/seatmap')
    def get_seat_map(self, request, booking_id=None):
        """
        Get seat map for flight booking
        
        NOTE: According to AirIQ docs, seat map should ideally be called BEFORE booking 
        using pricing data. This endpoint exists for legacy compatibility but should 
        eventually be moved to flights app search flow.
        
        This endpoint retrieves the seat map from AirIQ for a specific flight booking.
        """
        try:
            booking, flight_booking = self.get_flight_booking(booking_id)
            
            # Validate booking status - allow seat map for most statuses since it doesn't require payment
            if flight_booking.status in ['CANCELLED', 'FAILED']:
                return self.get_error_response(
                    message=f"Seat map is not available for {flight_booking.status.lower()} bookings",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate required AirIQ data
            if not flight_booking.airiq_track_id or not flight_booking.selected_flight_data:
                return self.get_error_response(
                    message="Flight booking missing required AirIQ data",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Get passengers for the booking
            passengers = FlightPassenger.objects.filter(flight_booking=flight_booking)
            if not passengers.exists():
                return self.get_error_response(
                    message="No passengers found for this booking",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Format passenger data for AirIQ
            passenger_data = []
            for passenger in passengers:
                passenger_data.append({
                    'reference': passenger.passenger_reference,
                    'title': passenger.title,
                    'type': passenger.passenger_type,
                    'first_name': passenger.first_name,
                    'last_name': passenger.last_name
                })
            
            # Extract flight segments from selected flight data
            flight_segments = flight_booking.selected_flight_data.get('segments', [])
            if not flight_segments:
                return self.get_error_response(
                    message="Flight segments data not found",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Call AirIQ service to get seat map
            seat_map_response = airiq_service.get_seat_map(
                flight_segments=flight_segments,
                passengers=passenger_data,
                track_id=flight_booking.airiq_track_id
            )
            
            self.log_info(
                f"Seat map retrieved for booking {booking_id}",
                extra={
                    'booking_id': booking_id,
                    'flight_booking_id': flight_booking.id,
                    'user_id': request.user.id
                }
            )
            
            return self.get_response(
                data={'seat_map': seat_map_response},
                message="Seat map retrieved successfully",
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
            self.log_error(f"AirIQ error getting seat map for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message=f"Unable to retrieve seat map: {str(e)}",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            self.log_error(f"Error getting seat map for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message="An unexpected error occurred",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
            
            # Update booking status if actual cancellation (not just penalty check)
            if flag == 'CANCEL':
                from django.utils import timezone
                
                flight_booking.status = 'CANCELLED'
                flight_booking.cancelled_at = timezone.now()
                flight_booking.save()
                
                # Update main booking status
                booking.status = 'canceled'
                booking.save()
                
                self.log_info(
                    f"Booking {booking_id} cancelled successfully",
                    extra={
                        'booking_id': booking_id,
                        'flight_booking_id': flight_booking.id,
                        'airiq_pnr': flight_booking.airiq_pnr,
                        'user_id': request.user.id
                    }
                )
                
                message = "Booking cancelled successfully"
            else:
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
