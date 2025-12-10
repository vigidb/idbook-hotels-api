"""
Enhanced Flight Search ViewSet
Integrates with the comprehensive pricing service and session management
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta
import logging

from .models import FlightSearchSession, FlightOption, Airline, Airport
from .services.pricing_service import flight_pricing_service
from .services.airiq_service import airiq_service, AirIQException
from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin

logger = logging.getLogger(__name__)


class EnhancedFlightSearchViewSet(
    viewsets.ViewSet, StandardResponseMixin, LoggingMixin
):
    """
    Enhanced Flight search operations with session management and pricing cache
    Handles the complete search → pricing → booking preparation flow
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        method="get",
        operation_description="Get list of airports",
        manual_parameters=[
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Search by IATA code, name, or city",
            ),
            openapi.Parameter(
                "country",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by country",
            ),
            openapi.Parameter(
                "limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, default=50
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="airports")
    def list_airports(self, request):
        """Get list of airports with search and filtering"""
        try:
            search = request.query_params.get("search", "")
            country = request.query_params.get("country", "")
            limit = min(int(request.query_params.get("limit", 50)), 200)

            airports = Airport.objects.filter(is_active=True)

            if search:
                airports = airports.filter(
                    models.Q(iata_code__icontains=search)
                    | models.Q(name__icontains=search)
                    | models.Q(city__icontains=search)
                )

            if country:
                airports = airports.filter(country__icontains=country)

            airports = airports[:limit]

            airport_data = [
                {
                    "iata_code": airport.iata_code,
                    "name": airport.name,
                    "city": airport.city,
                    "country": airport.country,
                }
                for airport in airports
            ]

            return self.get_response(
                data=airport_data,
                message="Airports retrieved successfully",
                status="success",
                count=len(airport_data),
                status_code=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error fetching airports: {str(e)}")
            return self.get_error_response(
                message="Error retrieving airports",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        method="get",
        operation_description="Search and filter airlines (backed by OpenFlights data)",
        manual_parameters=[
            openapi.Parameter(
                "search",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Free-text search across code, ICAO, name, alias, callsign, country",
            ),
            openapi.Parameter(
                "country",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by country (case-insensitive contains)",
            ),
            openapi.Parameter(
                "iata",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by IATA code (exact match)",
            ),
            openapi.Parameter(
                "icao",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by ICAO code (exact match)",
            ),
            openapi.Parameter(
                "active",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by OpenFlights active flag (Y/N)",
            ),
            openapi.Parameter(
                "is_active",
                openapi.IN_QUERY,
                type=openapi.TYPE_BOOLEAN,
                description="Filter by internal is_active flag (true/false). Defaults to true.",
            ),
            openapi.Parameter(
                "limit",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                default=50,
                description="Maximum number of records to return (max 200)",
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="airlines")
    def list_airlines(self, request):
        """Advanced airline search API using OpenFlights-backed data.

        Examples:
        - `/api/v1/flights/search/airlines/?search=india`
        - `/api/v1/flights/search/airlines/?iata=AI`
        - `/api/v1/flights/search/airlines/?icao=AIC`
        - `/api/v1/flights/search/airlines/?country=United%20States&active=Y`
        """
        try:
            search = request.query_params.get("search", "").strip()
            country = request.query_params.get("country", "").strip()
            iata = request.query_params.get("iata", "").strip()
            icao = request.query_params.get("icao", "").strip()
            active = request.query_params.get("active", "").strip().upper()
            is_active_param = request.query_params.get("is_active", "").strip().lower()
            limit = min(int(request.query_params.get("limit", 50)), 200)

            # Default to only internally active airlines unless explicitly overridden
            qs = Airline.objects.all()
            if is_active_param in {"true", "1", "yes"} or is_active_param == "":
                qs = qs.filter(is_active=True)
            elif is_active_param in {"false", "0", "no"}:
                qs = qs.filter(is_active=False)

            if iata:
                qs = qs.filter(code__iexact=iata)
            if icao:
                qs = qs.filter(icao_code__iexact=icao)
            if country:
                qs = qs.filter(country__icontains=country)
            if active in {"Y", "N"}:
                qs = qs.filter(active=active)
            if search:
                qs = qs.filter(
                    models.Q(code__icontains=search)
                    | models.Q(icao_code__icontains=search)
                    | models.Q(name__icontains=search)
                    | models.Q(alias__icontains=search)
                    | models.Q(callsign__icontains=search)
                    | models.Q(country__icontains=search)
                )

            qs = qs.order_by("name")[:limit]

            from .serializers import AirlineSerializer

            serializer = AirlineSerializer(qs, many=True, context={"request": request})

            return self.get_response(
                data=serializer.data,
                message="Airlines retrieved successfully",
                status="success",
                count=len(serializer.data),
                status_code=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error fetching airlines: {str(e)}")
            return self.get_error_response(
                message="Error retrieving airlines",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # Below are not used yet - the frontend is using airiq proxy viewset for availability, pricing and seat map - this is for future reference only

    @swagger_auto_schema(
        method="post",
        operation_description="Search flights and create pricing session",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["origin", "destination", "departure_date", "adults"],
            properties={
                "origin": openapi.Schema(
                    type=openapi.TYPE_STRING, description="3-letter IATA origin code"
                ),
                "destination": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="3-letter IATA destination code",
                ),
                "departure_date": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Departure date (YYYY-MM-DD)"
                ),
                "return_date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Return date for round trip (YYYY-MM-DD)",
                ),
                "trip_type": openapi.Schema(
                    type=openapi.TYPE_STRING, enum=["O", "R"], default="O"
                ),
                "adults": openapi.Schema(
                    type=openapi.TYPE_INTEGER, minimum=1, maximum=9, default=1
                ),
                "children": openapi.Schema(
                    type=openapi.TYPE_INTEGER, minimum=0, maximum=8, default=0
                ),
                "infants": openapi.Schema(
                    type=openapi.TYPE_INTEGER, minimum=0, maximum=4, default=0
                ),
                "flight_class": openapi.Schema(
                    type=openapi.TYPE_STRING, enum=["E", "B", "F"], default="E"
                ),
                "direct_only": openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False),
            },
        ),
        responses={
            200: openapi.Response(
                description="Flight search results with pricing session",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        "data": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                "session_id": openapi.Schema(type=openapi.TYPE_STRING),
                                "track_id": openapi.Schema(type=openapi.TYPE_STRING),
                                "flight_options": openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Items(type=openapi.TYPE_OBJECT),
                                ),
                                "expires_at": openapi.Schema(type=openapi.TYPE_STRING),
                                "time_remaining": openapi.Schema(
                                    type=openapi.TYPE_INTEGER
                                ),
                            },
                        ),
                    },
                ),
            )
        },
    )
    @action(detail=False, methods=["post"], url_path="availability")
    def flight_availability(self, request):
        """
        Get flight availability - search for flights without creating pricing session
        """
        try:
            # Validate required fields
            required_fields = ["origin", "destination", "departure_date", "adults"]
            for field in required_fields:
                if not request.data.get(field):
                    return self.get_error_response(
                        message=f"Field '{field}' is required",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

            # Validate date format
            try:
                departure_date = datetime.strptime(
                    request.data["departure_date"], "%Y-%m-%d"
                ).date()
                if departure_date < timezone.now().date():
                    raise ValueError("Departure date cannot be in the past")
            except ValueError as e:
                return self.get_error_response(
                    message=f"Invalid departure date format or value: {str(e)}",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Validate return date for round trip
            if request.data.get("trip_type") == "R":
                if not request.data.get("return_date"):
                    return self.get_error_response(
                        message="Return date is required for round trip",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
                try:
                    return_date = datetime.strptime(
                        request.data["return_date"], "%Y-%m-%d"
                    ).date()
                    if return_date <= departure_date:
                        raise ValueError("Return date must be after departure date")
                except ValueError as e:
                    return self.get_error_response(
                        message=f"Invalid return date: {str(e)}",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

            # Validate passenger counts
            adults = request.data.get("adults", 1)
            children = request.data.get("children", 0)
            infants = request.data.get("infants", 0)

            if adults + children > 9:
                return self.get_error_response(
                    message="Total adults and children cannot exceed 9",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if infants > adults:
                return self.get_error_response(
                    message="Number of infants cannot exceed number of adults",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Convert dates to AirIQ format (YYYYMMDD)
            airiq_departure_date = departure_date.strftime("%Y%m%d")
            airiq_return_date = None
            if request.data.get("return_date"):
                try:
                    return_date_obj = datetime.strptime(
                        request.data["return_date"], "%Y-%m-%d"
                    ).date()
                    airiq_return_date = return_date_obj.strftime("%Y%m%d")
                except ValueError:
                    return self.get_error_response(
                        message="Invalid return date format. Use YYYY-MM-DD",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

            # Search flights without creating pricing session
            search_params = {
                "origin": request.data["origin"].upper(),
                "destination": request.data["destination"].upper(),
                "departure_date": airiq_departure_date,  # Convert to YYYYMMDD format
                "return_date": airiq_return_date,
                "trip_type": request.data.get("trip_type", "O"),
                "adults": adults,
                "children": children,
                "infants": infants,
                "flight_class": request.data.get("flight_class", "E"),
                "direct_only": request.data.get("direct_only", False),
            }

            # Get flight availability from AirIQ
            flight_results, track_id = airiq_service.search_flights(search_params)

            # Debug: Log the actual AirIQ response structure
            self.log_info(f"AirIQ Response Type: {type(flight_results)}")
            self.log_info(
                f"AirIQ Response Keys: {list(flight_results.keys()) if isinstance(flight_results, dict) else 'Not a dict'}"
            )

            # Check if response has Status information
            if isinstance(flight_results, dict) and "Status" in flight_results:
                status_info = flight_results["Status"]
                self.log_info(
                    f"AirIQ Status - Code: {status_info.get('ResultCode')}, Error: {status_info.get('Error')}"
                )

            # Check ItineraryFlightList
            if isinstance(flight_results, dict):
                itinerary_list = flight_results.get("ItineraryFlightList")
                self.log_info(f"ItineraryFlightList type: {type(itinerary_list)}")
                self.log_info(f"ItineraryFlightList value: {itinerary_list}")

                if itinerary_list is not None:
                    itinerary_count = (
                        len(itinerary_list) if isinstance(itinerary_list, list) else 0
                    )
                    self.log_info(
                        f"Found {itinerary_count} itineraries in AirIQ response"
                    )
                    if itinerary_count > 0:
                        # Log first itinerary structure
                        first_itinerary = itinerary_list[0]
                        self.log_info(
                            f"First itinerary keys: {list(first_itinerary.keys()) if isinstance(first_itinerary, dict) else 'Not a dict'}"
                        )
                else:
                    self.log_warning(
                        "ItineraryFlightList is None - no flights returned by AirIQ"
                    )

            # Group flights by flight number and combine fares
            grouped_flights = self._group_flights_by_number(flight_results)

            # Extract additional metadata from AirIQ response
            airiq_metadata = {
                "track_id": track_id,
                "status": flight_results.get("Status", {}),
                "sequence_id": flight_results.get("Status", {}).get("SequenceID", ""),
                "result_code": flight_results.get("Status", {}).get("ResultCode", ""),
                "error_message": flight_results.get("Status", {}).get("Error", ""),
            }

            # Create pricing session during availability (without separate pricing API call)
            pricing_session = flight_pricing_service.create_pricing_session(
                search_params=search_params,
                user=request.user if request.user.is_authenticated else None,
                track_id=track_id,
                flight_results=grouped_flights,  # Store results in session
            )

            self.log_info(
                f"Flight availability search completed - Found {len(grouped_flights)} flight groups, created session {pricing_session['session_id']}",
                extra={
                    "search_params": search_params,
                    "user_id": (
                        request.user.id if request.user.is_authenticated else None
                    ),
                    "results_count": len(grouped_flights),
                    "session_id": pricing_session["session_id"],
                    "track_id": track_id,
                },
            )

            # Add helpful message if no flights found
            response_message = "Flight availability retrieved successfully"
            if len(grouped_flights) == 0:
                response_message = "No flights found for the selected criteria. Try adjusting your search parameters (dates, direct flights setting, or different airports)."

            return self.get_response(
                data={
                    "session_id": pricing_session["session_id"],
                    "track_id": track_id,
                    "flights": grouped_flights,
                    "search_params": search_params,
                    "search_timestamp": timezone.now().isoformat(),
                    "results_count": len(grouped_flights),
                    "expires_at": pricing_session["expires_at"],
                    "time_remaining": pricing_session["time_remaining_minutes"],
                    "airiq_metadata": airiq_metadata,
                },
                message=response_message,
                status="success",
                status_code=status.HTTP_200_OK,
            )

        except AirIQException as e:
            self.log_error(f"AirIQ search error: {str(e)}")
            return self.get_error_response(
                message=f"Flight search failed: {str(e)}",
                status="error",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            self.log_error(f"Flight search error: {str(e)}")
            return self.get_error_response(
                message="An error occurred while searching flights",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _group_flights_by_number(self, flight_results):
        """
        Group flights by flight number and combine multiple fares for same flight
        """
        flight_groups = {}

        # Extract flights from AirIQ response
        itinerary_list = flight_results.get("ItineraryFlightList", [])

        # Debug logging
        logger.info(
            f"Processing {len(itinerary_list) if itinerary_list else 0} itineraries from AirIQ"
        )
        if not itinerary_list:
            logger.warning("No itineraries found in AirIQ response")
            logger.info(f"AirIQ response structure: {flight_results}")

        # Process each flight group in ItineraryFlightList
        for flight_group in itinerary_list:
            # Each group has Items array
            items = flight_group.get("Items", [])
            logger.info(f"Processing flight group with {len(items)} items")

            for item in items:
                # Each item has FlightDetails and Fares
                flight_details = item.get("FlightDetails", [])
                fares = item.get("Fares", [])

                if not flight_details:
                    logger.warning("No flight details found in item")
                    continue

                # Use first flight detail as the main flight info
                first_flight = flight_details[0]
                flight_number = first_flight.get("FlightNumber", "")

                # Create unique key based on flight number, route, and time
                flight_key = f"{flight_number}_{first_flight.get('Origin')}_{first_flight.get('Destination')}_{first_flight.get('DepartureDateTime')}"

                if flight_key not in flight_groups:
                    # Create new flight group with comprehensive flight details
                    flight_groups[flight_key] = {
                        "flight_number": flight_number,
                        "airline_code": first_flight.get("AirlineDescription", "")[:2]
                        or first_flight.get("OperatingCarrier", ""),
                        "airline_name": first_flight.get("AirlineDescription", ""),
                        "origin": first_flight.get("Origin", ""),
                        "destination": first_flight.get("Destination", ""),
                        "departure_datetime": first_flight.get("DepartureDateTime", ""),
                        "arrival_datetime": first_flight.get("ArrivalDateTime", ""),
                        "departure_terminal": first_flight.get("DepartureTerminal", ""),
                        "arrival_terminal": first_flight.get("ArrivalTerminal", ""),
                        "duration": first_flight.get("JourneyTime", ""),
                        "flying_time": first_flight.get("FlyingTime", ""),
                        "stops": int(first_flight.get("Stops", 0)),
                        "via": first_flight.get("Via", ""),
                        "flight_class": first_flight.get("Class", ""),
                        "cabin": first_flight.get("Cabin", ""),
                        "fare_basis_code": first_flight.get("FareBasisCode", ""),
                        "airline_category": first_flight.get("AirlineCategory", ""),
                        "connection_flag": first_flight.get("ConnectionFlag", ""),
                        "cnx": first_flight.get("CNX", ""),
                        "plating_carrier": first_flight.get("PlatingCarrier", ""),
                        "operating_carrier": first_flight.get("OperatingCarrier", ""),
                        "segment_details": first_flight.get("SegmentDetails", ""),
                        "multi_class": first_flight.get("MultiClass", "0"),
                        "allow_fqt": first_flight.get("AllowFQT", False),
                        "available_seats": first_flight.get("AvailSeat", ""),
                        "promo_code": first_flight.get("PromoCode", ""),
                        "promo_code_desc": first_flight.get("PromoCodeDesc", ""),
                        "fare_type_description": first_flight.get(
                            "FareTypeDescription", ""
                        ),
                        "fare_description": first_flight.get("FareDescription", ""),
                        "fare_rule_info": first_flight.get("FareRuleInfo", ""),
                        "refundable": first_flight.get("Refundable", "False").lower()
                        == "true",
                        "baggage": first_flight.get("Baggage", ""),
                        "cabin_baggage": first_flight.get("CabinBaggage", ""),
                        "reference_token": first_flight.get("ReferenceToken", ""),
                        "seg_ref": first_flight.get("SegRef", ""),
                        "itin_ref": first_flight.get("ItinRef", ""),
                        "fare_id": first_flight.get("FareId", ""),
                        "flight_details": flight_details,
                        "fare_options": [],
                        "cheapest_fare": None,
                        "refundable_fare": None,
                        "aircraft_type": (
                            first_flight.get("SegmentDetails", "").split("\r\n")[0]
                            if first_flight.get("SegmentDetails")
                            else ""
                        ),
                    }

                # Process all fares for this flight
                for fare in fares:
                    fare_info = self._extract_fare_info_from_airiq(fare)
                    if fare_info:
                        flight_groups[flight_key]["fare_options"].append(fare_info)

                        # Update cheapest fare
                        if (
                            not flight_groups[flight_key]["cheapest_fare"]
                            or fare_info["gross_amount"]
                            < flight_groups[flight_key]["cheapest_fare"]["gross_amount"]
                        ):
                            flight_groups[flight_key]["cheapest_fare"] = fare_info

                        # Update refundable fare (if this is refundable)
                        if fare_info.get("is_refundable") and (
                            not flight_groups[flight_key]["refundable_fare"]
                            or fare_info["gross_amount"]
                            < flight_groups[flight_key]["refundable_fare"][
                                "gross_amount"
                            ]
                        ):
                            flight_groups[flight_key]["refundable_fare"] = fare_info

        # Convert to list and sort by departure time
        grouped_flights = list(flight_groups.values())
        grouped_flights.sort(key=lambda x: x.get("departure_datetime", ""))

        return grouped_flights

    def _extract_fare_info(self, itinerary):
        """
        Extract fare information from itinerary (legacy format)
        """
        try:
            fare_details = itinerary.get("FareDetailsInfo", {})

            return {
                "fare_key": itinerary.get("Token", ""),
                "flight_key": itinerary.get("Token", ""),
                "fare_type": fare_details.get("FareType", "Economy"),
                "base_fare": float(fare_details.get("BasicAmount", 0)),
                "taxes": float(fare_details.get("Tax", 0)),
                "total_fare": float(fare_details.get("GrossAmount", 0)),
                "currency": fare_details.get("Currency", "INR"),
                "is_refundable": fare_details.get("IsRefundable", False),
                "baggage_info": fare_details.get("BaggageInfo", ""),
                "fare_rules": fare_details.get("FareRulesInfo", {}),
                "fare_basis": fare_details.get("FareBasis", ""),
                "booking_class": fare_details.get("BookingClass", ""),
            }
        except Exception as e:
            logger.error(f"Error extracting fare info: {e}")
            return None

    def _extract_fare_info_from_airiq(self, fare_data):
        """
        Extract fare information from actual AirIQ fare structure
        """
        try:
            logger.info(f"Processing fare data: {list(fare_data.keys())}")

            # Get fare description - should be a list
            fare_descriptions = fare_data.get("Faredescription", [])
            if not fare_descriptions:
                logger.warning("No fare descriptions found")
                return None

            # Get first fare description
            first_fare_desc = fare_descriptions[0]
            logger.info(f"First fare description keys: {list(first_fare_desc.keys())}")

            # Extract all fare amounts
            base_fare = float(first_fare_desc.get("BaseAmount", 0))
            total_tax_amount = float(first_fare_desc.get("TotalTaxAmount", 0))
            gross_amount = float(first_fare_desc.get("GrossAmount", 0))
            net_amount = float(first_fare_desc.get("NetAmount", 0))
            incentive = float(first_fare_desc.get("Incentive", 0))
            service_charge = float(first_fare_desc.get("Servicecharge", 0))
            tds = float(first_fare_desc.get("TDS", 0))
            discount = float(first_fare_desc.get("Discount", 0))
            plb_amount = float(first_fare_desc.get("PLBAmount", 0))
            sf = float(first_fare_desc.get("SF", 0))
            sfgst = float(first_fare_desc.get("SFGST", 0))

            # Extract tax breakdown
            taxes_breakdown = first_fare_desc.get("Taxes", [])
            tax_details = []
            for tax in taxes_breakdown:
                tax_details.append(
                    {"code": tax.get("Code", ""), "amount": float(tax.get("Amount", 0))}
                )

            return {
                "fare_key": fare_data.get("FlightId", ""),
                "flight_key": fare_data.get("FlightId", ""),
                "fare_type": fare_data.get("FareType", "N"),
                "base_fare": base_fare,
                "total_tax_amount": total_tax_amount,
                "gross_amount": gross_amount,
                "net_amount": net_amount,
                "incentive": incentive,
                "service_charge": service_charge,
                "tds": tds,
                "discount": discount,
                "plb_amount": plb_amount,
                "sf": sf,
                "sfgst": sfgst,
                "taxes": total_tax_amount,  # Keep for backward compatibility
                "total_fare": gross_amount,  # Keep for backward compatibility
                "currency": fare_data.get("Currency", "INR"),
                "is_refundable": True,  # AirIQ flights are generally refundable with conditions
                "baggage_info": "",  # Will be populated from FlightDetails
                "fare_rules": {},
                "fare_basis": "",
                "booking_class": "",
                "tax_breakdown": tax_details,
                "pax_type": first_fare_desc.get("Paxtype", "ADT"),
            }
        except Exception as e:
            logger.error(f"Error extracting AirIQ fare info: {e}")
            logger.error(f"Fare data: {fare_data}")
            return None

    @swagger_auto_schema(
        method="post",
        operation_description="Get detailed pricing for selected flights with ancillary services",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["search_params", "selected_flights"],
            properties={
                "search_params": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Original search parameters from availability",
                ),
                "selected_flights": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(type=openapi.TYPE_OBJECT),
                    description="Selected flight with fare option from availability results",
                ),
                "session_id": openapi.Schema(
                    type=openapi.TYPE_STRING, description="Optional existing session ID"
                ),
                "ancillary_services": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "seats": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Items(type=openapi.TYPE_OBJECT),
                        ),
                        "meals": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Items(type=openapi.TYPE_OBJECT),
                        ),
                        "baggage": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Items(type=openapi.TYPE_OBJECT),
                        ),
                        "other": openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Items(type=openapi.TYPE_OBJECT),
                        ),
                    },
                ),
            },
        ),
    )
    @action(detail=False, methods=["post"], url_path="pricing")
    def get_detailed_pricing(self, request):
        """
        Create pricing session and get comprehensive pricing breakdown.
        Also supports direct AirIQ pricing call when session_id is not provided and
        the request contains AirIQ-compatible keys: SegmentInfo, Trackid, ItineraryInfo.
        """
        try:
            # Fast-path: if no session_id provided but AirIQ payload present, proxy to AirIQ pricing
            session_id = request.data.get("session_id")
            has_airiq_payload = not session_id and (
                request.data.get("SegmentInfo") is not None
                and (request.data.get("Trackid") or request.data.get("TrackId"))
                and request.data.get("ItineraryInfo") is not None
            )
            if has_airiq_payload:
                track_id = request.data.get("Trackid") or request.data.get("TrackId")
                segment_info = request.data.get("SegmentInfo") or {}
                itinerary_info = request.data.get("ItineraryInfo") or []

                pricing_response = airiq_service.price_flight(
                    track_id=track_id,
                    segment_info=segment_info,
                    itinerary_info=itinerary_info,
                )
                # Return raw AirIQ response as requested
                return Response(pricing_response, status=status.HTTP_200_OK)

            # Default enhanced flow (requires session_id or search_params + selected_flights)
            search_params = request.data.get("search_params")
            selected_flights = request.data.get("selected_flights", [])
            ancillary_services = request.data.get("ancillary_services", {})
            session_id = request.data.get("session_id")  # Optional existing session

            if not search_params:
                return self.get_error_response(
                    message="search_params is required",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if not selected_flights:
                return self.get_error_response(
                    message="selected_flights is required",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Create or use existing pricing session
            if not session_id:
                pricing_session = flight_pricing_service.create_pricing_session(
                    search_params=search_params,
                    user=request.user if request.user.is_authenticated else None,
                )
                session_id = pricing_session["session_id"]

            # Get detailed pricing with comprehensive breakdown
            pricing_result = flight_pricing_service.get_detailed_pricing(
                session_id=session_id,
                selected_flights=selected_flights,
                ancillary_services=ancillary_services,
            )

            self.log_info(
                f"Detailed pricing calculated for session {session_id}",
                extra={
                    "session_id": session_id,
                    "user_id": (
                        request.user.id if request.user.is_authenticated else None
                    ),
                },
            )

            return self.get_response(
                data=pricing_result,
                message="Detailed pricing calculated successfully",
                status="success",
                status_code=status.HTTP_200_OK,
            )

        except ValueError as e:
            return self.get_error_response(
                message=str(e), status="error", status_code=status.HTTP_400_BAD_REQUEST
            )
        except AirIQException as e:
            self.log_error(f"AirIQ pricing error: {str(e)}")
            return self.get_error_response(
                message=f"Pricing calculation failed: {str(e)}",
                status="error",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            self.log_error(f"Pricing calculation error: {str(e)}")
            return self.get_error_response(
                message="An error occurred while calculating pricing",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        method="post",
        operation_description="Calculate final booking total with GST and all charges",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["session_id"],
            properties={
                "session_id": openapi.Schema(type=openapi.TYPE_STRING),
                "gst_info": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "gst_number": openapi.Schema(type=openapi.TYPE_STRING),
                        "company_name": openapi.Schema(type=openapi.TYPE_STRING),
                        "address": openapi.Schema(type=openapi.TYPE_STRING),
                        "email": openapi.Schema(type=openapi.TYPE_STRING),
                        "mobile": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            },
        ),
    )
    @action(detail=False, methods=["post"], url_path="booking-total")
    def calculate_booking_total(self, request):
        """
        Calculate final booking total including GST for business bookings.
        Supports two modes:
        - Session mode: provide session_id (uses cached pricing_breakdown)
        - Direct mode: provide AirIQ-compatible booking data (AdultCount, ItineraryFlightsInfo, BaseOrigin, BaseDestination, TripType, TrackId)
          In direct mode we call AirIQ pricing first (like in create-booking) and then compute totals.
        """
        try:
            session_id = request.data.get("session_id")
            gst_info = request.data.get("gst_info", {})

            # Direct mode: if no session_id, but booking payload present
            if (
                not session_id
                and request.data.get("ItineraryFlightsInfo")
                and (
                    request.data.get("TrackId")
                    or request.data.get("TrackID")
                    or request.data.get("Trackid")
                )
            ):
                try:
                    # Build SegmentInfo from booking payload
                    segment_info = {
                        "BaseOrigin": request.data.get("BaseOrigin"),
                        "BaseDestination": request.data.get("BaseDestination"),
                        "TripType": request.data.get("TripType", "O"),
                        "AdultCount": str(request.data.get("AdultCount", "1")),
                        "ChildCount": str(request.data.get("ChildCount", "0")),
                        "InfantCount": str(request.data.get("InfantCount", "0")),
                    }
                    # Build ItineraryInfo for AirIQ pricing
                    itin_list = request.data.get("ItineraryFlightsInfo") or []
                    itinerary_info = []
                    for itn in itin_list:
                        flight_details = (
                            itn.get("FlighstInfo") or itn.get("FlightsInfo") or []
                        )
                        base_amount = itn.get("PaymentInfo", [{}])[0].get(
                            "BaseAmount", itn.get("BaseAmount", 0)
                        )
                        gross_amount = itn.get("PaymentInfo", [{}])[0].get(
                            "GrossAmount", itn.get("GrossAmount", 0)
                        )
                        itinerary_info.append(
                            {
                                "FlightDetails": flight_details,
                                "BaseAmount": str(base_amount),
                                "GrossAmount": str(gross_amount),
                            }
                        )

                    track_id = (
                        request.data.get("TrackId")
                        or request.data.get("TrackID")
                        or request.data.get("Trackid")
                    )

                    # Call AirIQ pricing
                    pricing_response = airiq_service.price_flight(
                        track_id=track_id,
                        segment_info=segment_info,
                        itinerary_info=itinerary_info,
                    )

                    # Prepare inputs for comprehensive pricing breakdown
                    # Derive search_params and ancillary_services from booking payload
                    adults = int(request.data.get("AdultCount", 1) or 1)
                    children = int(request.data.get("ChildCount", 0) or 0)
                    infants = int(request.data.get("InfantCount", 0) or 0)
                    search_params = {
                        "origin": request.data.get("BaseOrigin"),
                        "destination": request.data.get("BaseDestination"),
                        "trip_type": request.data.get("TripType", "O"),
                        "adults": adults,
                        "children": children,
                        "infants": infants,
                    }
                    # Aggregate ancillary services from all itinerary items
                    seats = []
                    meals = []
                    baggage = []
                    other = []
                    for itn in itin_list:
                        seats.extend(itn.get("SeatsSSRInfo", []))
                        meals.extend(itn.get("MealsSSRInfo", []))
                        baggage.extend(itn.get("BaggSSRInfo", []))
                        other.extend(itn.get("OtherSSRInfo", []))
                    ancillary_services = {
                        "seats": seats,
                        "meals": meals,
                        "baggage": baggage,
                        "other": other,
                    }

                    # Use pricing service to compute comprehensive breakdown and totals
                    pricing_breakdown = (
                        flight_pricing_service._calculate_comprehensive_pricing(
                            pricing_response,
                            search_params,
                            ancillary_services,
                        )
                    )
                    booking_total = flight_pricing_service.calculate_booking_total(
                        pricing_breakdown=pricing_breakdown,
                        gst_info=gst_info,
                    )

                    # Extract meta (track id, token, flights) from AirIQ pricing response (robust)
                    track_id_meta = None
                    token_meta = None
                    flights_meta = []
                    try:
                        pii = (
                            pricing_response.get("PriceItenaryInfo")
                            or pricing_response.get("PriceItineraryInfo")
                            or []
                        )
                        if isinstance(pii, list) and pii:
                            pi0 = pii[0]
                            track_id_meta = (
                                pi0.get("Trackid")
                                or pi0.get("TrackId")
                                or pi0.get("TRACKID")
                            )
                            # Token might be at pi0 level or inside AvailabilityResponse
                            token_meta = pi0.get("Token")
                            ar = (
                                pi0.get("AvailabilityResponse")
                                or pi0.get("Availability")
                                or []
                            )
                            if isinstance(ar, list) and ar:
                                ar0 = ar[0]
                                token_meta = ar0.get("Token") or token_meta
                                flights_meta = (
                                    ar0.get("Flights") or ar0.get("FlightsInfo") or []
                                )
                        # Root-level fallbacks
                        track_id_meta = (
                            track_id_meta
                            or pricing_response.get("Trackid")
                            or pricing_response.get("TrackId")
                        )
                        token_meta = token_meta or pricing_response.get("Token")
                    except Exception:
                        pass
                    # Fallback meta if AirIQ didn't return structured pricing
                    if not track_id_meta:
                        track_id_meta = track_id
                    if not flights_meta:
                        # Flatten flights from provided ItineraryFlightsInfo
                        try:
                            for itn in itin_list:
                                flights_meta.extend(
                                    itn.get("FlighstInfo")
                                    or itn.get("FlightsInfo")
                                    or []
                                )
                        except Exception:
                            pass

                    return self.get_response(
                        data={
                            "pricing_breakdown": pricing_breakdown,
                            "booking_total": booking_total,
                            "airiq_pricing": pricing_response,
                            "track_id": track_id_meta,
                            "token": token_meta,
                            "flights": flights_meta,
                        },
                        message="Booking total calculated successfully",
                        status="success",
                        status_code=status.HTTP_200_OK,
                    )
                except AirIQException as e:
                    return self.get_error_response(
                        message=f"AirIQ pricing failed: {str(e)}",
                        status="error",
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                except Exception as e:
                    return self.get_error_response(
                        message=f"Failed to calculate booking total: {str(e)}",
                        status="error",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

            # Session mode (existing behaviour)
            if not session_id:
                return self.get_error_response(
                    message="session_id is required when direct booking payload is not provided",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Get session data
            session_data = flight_pricing_service.get_session_data(session_id)
            if not session_data:
                return self.get_error_response(
                    message="Invalid or expired session",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if not session_data.get("pricing_calculated"):
                return self.get_error_response(
                    message="Pricing must be calculated first",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Calculate final booking total
            pricing_breakdown = session_data["pricing_breakdown"]
            booking_total = flight_pricing_service.calculate_booking_total(
                pricing_breakdown=pricing_breakdown, gst_info=gst_info
            )

            # Extract meta from cached pricing response if available
            track_id_meta = None
            token_meta = None
            flights_meta = []
            try:
                pricing_data = session_data.get("pricing_data") or {}
                pii = (
                    pricing_data.get("PriceItenaryInfo")
                    or pricing_data.get("PriceItineraryInfo")
                    or []
                )
                if isinstance(pii, list) and pii:
                    pi0 = pii[0]
                    track_id_meta = (
                        pi0.get("Trackid")
                        or pi0.get("TrackId")
                        or session_data.get("track_id")
                    )
                    token_meta = pi0.get("Token")
                    ar = (
                        pi0.get("AvailabilityResponse") or pi0.get("Availability") or []
                    )
                    if isinstance(ar, list) and ar:
                        ar0 = ar[0]
                        token_meta = ar0.get("Token") or token_meta
                        flights_meta = (
                            ar0.get("Flights") or ar0.get("FlightsInfo") or []
                        )
                # Root-level fallbacks
                track_id_meta = (
                    track_id_meta
                    or pricing_data.get("Trackid")
                    or pricing_data.get("TrackId")
                    or session_data.get("track_id")
                )
                token_meta = token_meta or pricing_data.get("Token")
            except Exception:
                pass

            return self.get_response(
                data={
                    "pricing_breakdown": pricing_breakdown,
                    "booking_total": booking_total,
                    "track_id": track_id_meta or session_data.get("track_id"),
                    "token": token_meta,
                    "flights": flights_meta,
                },
                message="Booking total calculated successfully",
                status="success",
                status_code=status.HTTP_200_OK,
            )

        except Exception as e:
            self.log_error(f"Booking total calculation error: {str(e)}")
            return self.get_error_response(
                message="Error calculating booking total",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        method="get",
        operation_description="Get seat map for selected flights",
        manual_parameters=[
            openapi.Parameter(
                "session_id", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=True
            ),
        ],
    )
    @action(detail=False, methods=["get"], url_path="seat-map")
    def get_seat_map(self, request):
        """
        Get seat map for selected flights in pricing session
        """
        try:
            session_id = request.query_params.get("session_id")

            if not session_id:
                return self.get_error_response(
                    message="session_id is required",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Get session data
            session_data = flight_pricing_service.get_session_data(session_id)
            if not session_data or not session_data.get("selected_flights"):
                return self.get_error_response(
                    message="Invalid session or no flights selected",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            # Extract flight segments and passenger info
            selected_flights = session_data["selected_flights"]
            search_params = session_data["search_params"]

            # Format flight segments for seat map
            flight_segments = []
            for flight in selected_flights:
                flight_segments.extend(flight.get("segments", []))

            # Format passenger data
            passengers = []
            adult_count = search_params.get("adults", 1)
            child_count = search_params.get("children", 0)
            infant_count = search_params.get("infants", 0)

            pax_ref = 1
            for i in range(adult_count):
                passengers.append(
                    {
                        "reference": pax_ref,
                        "title": "MR",
                        "type": "ADT",
                        "first_name": f"PASSENGER{pax_ref}",
                        "last_name": "ADULT",
                    }
                )
                pax_ref += 1

            for i in range(child_count):
                passengers.append(
                    {
                        "reference": pax_ref,
                        "title": "MSTR",
                        "type": "CHD",
                        "first_name": f"PASSENGER{pax_ref}",
                        "last_name": "CHILD",
                    }
                )
                pax_ref += 1

            for i in range(infant_count):
                passengers.append(
                    {
                        "reference": pax_ref,
                        "title": "MISS",
                        "type": "INF",
                        "first_name": f"PASSENGER{pax_ref}",
                        "last_name": "INFANT",
                    }
                )
                pax_ref += 1

            # Get seat map from AirIQ
            seat_map_response = airiq_service.get_seat_map(
                flight_segments=flight_segments,
                passengers=passengers,
                track_id=session_data["track_id"],
            )

            return self.get_response(
                data={"seat_map": seat_map_response},
                message="Seat map retrieved successfully",
                status="success",
                status_code=status.HTTP_200_OK,
            )

        except AirIQException as e:
            self.log_error(f"AirIQ seat map error: {str(e)}")
            return self.get_error_response(
                message=f"Seat map retrieval failed: {str(e)}",
                status="error",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            self.log_error(f"Seat map error: {str(e)}")
            return self.get_error_response(
                message="Error retrieving seat map",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        method="post",
        operation_description="Extend pricing session expiry",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["session_id"],
            properties={
                "session_id": openapi.Schema(type=openapi.TYPE_STRING),
                "minutes": openapi.Schema(
                    type=openapi.TYPE_INTEGER, default=5, minimum=1, maximum=15
                ),
            },
        ),
    )
    @action(detail=False, methods=["post"], url_path="extend-session")
    def extend_session(self, request):
        """
        Extend pricing session expiry (max 15 minutes total)
        """
        try:
            session_id = request.data.get("session_id")
            minutes = request.data.get("minutes", 5)

            if not session_id:
                return self.get_error_response(
                    message="session_id is required",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if minutes < 1 or minutes > 15:
                return self.get_error_response(
                    message="Extension must be between 1 and 15 minutes",
                    status="error",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            success = flight_pricing_service.extend_session(session_id, minutes)

            if success:
                return self.get_response(
                    data={"session_id": session_id, "extended_by_minutes": minutes},
                    message=f"Session extended by {minutes} minutes",
                    status="success",
                    status_code=status.HTTP_200_OK,
                )
            else:
                return self.get_error_response(
                    message="Session not found or already expired",
                    status="error",
                    status_code=status.HTTP_404_NOT_FOUND,
                )

        except Exception as e:
            self.log_error(f"Session extension error: {str(e)}")
            return self.get_error_response(
                message="Error extending session",
                status="error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
