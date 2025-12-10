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
            Booking.objects.select_related("flight_booking"),
            id=booking_id,
            booking_type="FLIGHT",
            user=self.request.user,
        )

        if not booking.flight_booking:
            raise ValueError("Flight booking details not found")

        return booking, booking.flight_booking

    @swagger_auto_schema(
        method="get",
        operation_description="Get seat map for flight booking",
        manual_parameters=[
            openapi.Parameter(
                "booking_id",
                openapi.IN_PATH,
                description="Flight booking ID",
                type=openapi.TYPE_INTEGER,
                required=True,
            )
        ],
        responses={
            200: openapi.Response(
                description="Seat map retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "seat_map": openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    description="Seat map data from AirIQ",
                                )
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Bad request"),
            404: openapi.Response(description="Booking not found"),
            500: openapi.Response(description="AirIQ service error"),
        },
    )
    @action(detail=False, methods=["get"], url_path=r"(?P<booking_id>\d+)/seatmap")
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
            if flight_booking.status in ["CANCELLED", "FAILED"]:
                return self.get_error_response(
                    message=f"Seat map is not available for {flight_booking.status.lower()} bookings",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Validate required AirIQ data
            if (
                not flight_booking.airiq_track_id
                or not flight_booking.selected_flight_data
            ):
                return self.get_error_response(
                    message="Flight booking missing required AirIQ data",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Get passengers for the booking
            passengers = FlightPassenger.objects.filter(flight_booking=flight_booking)
            if not passengers.exists():
                return self.get_error_response(
                    message="No passengers found for this booking",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Format passenger data for AirIQ
            passenger_data = []
            for passenger in passengers:
                passenger_data.append(
                    {
                        "reference": passenger.passenger_reference,
                        "title": passenger.title,
                        "type": passenger.passenger_type,
                        "first_name": passenger.first_name,
                        "last_name": passenger.last_name,
                    }
                )

            # Extract flight segments from selected flight data
            flight_segments = flight_booking.selected_flight_data.get("segments", [])
            if not flight_segments:
                return self.get_error_response(
                    message="Flight segments data not found",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Call AirIQ service to get seat map
            seat_map_response = airiq_service.get_seat_map(
                flight_segments=flight_segments,
                passengers=passenger_data,
                track_id=flight_booking.airiq_track_id,
            )

            self.log_info(
                f"Seat map retrieved for booking {booking_id}",
                extra={
                    "booking_id": booking_id,
                    "flight_booking_id": flight_booking.id,
                    "user_id": request.user.id,
                },
            )

            return self.get_response(
                data={"seat_map": seat_map_response},
                message="Seat map retrieved successfully",
                status="success",
                status_code=status.HTTP_200_OK,
            )

        except ValueError as e:
            return self.get_error_response(
                message=str(e), status="error", status_code=status.HTTP_400_BAD_REQUEST
            )
        except AirIQException as e:
            self.log_error(
                f"AirIQ error getting seat map for booking {booking_id}: {str(e)}"
            )
            return self.get_error_response(
                message=f"Unable to retrieve seat map: {str(e)}",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            self.log_error(f"Error getting seat map for booking {booking_id}: {str(e)}")
            return self.get_error_response(
                message="An unexpected error occurred",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
