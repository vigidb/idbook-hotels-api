## Below are not used. Invventory ticket are not possible to book. Only AirIQ block PNRs are possible to book.
## Multiple class and fare are not supported by AirIQ in Live mode yet.
## We can remove below if not needed. For future reference only.
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta
import logging

from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.utils import paginate_queryset
from .models import (
    Airline, Airport, FlightRoute, FlightInventory, FlightSearchSession,
    FlightOption
)
from .serializers import (
    FlightSearchSerializer, FlightOptionSerializer,
    FlightSearchResultSerializer, FlightPricingSerializer
)
from .services.airiq_service import airiq_service, AirIQException
from .services.inventory_service import inventory_service

logger = logging.getLogger(__name__)


class FlightSearchViewSet(viewsets.ViewSet, StandardResponseMixin, LoggingMixin):
    """
    Flight search and availability API endpoints
    Supports both real-time AirIQ search and inventory-based search
    """
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], url_path='search')
    def search_flights(self, request):
        """
        Search for available flights
        POST /api/v1/flights/search/
        
        Body: {
            "origin": "DEL",
            "destination": "BOM",
            "departure_date": "2023-12-01",
            "return_date": "2023-12-05",  # Optional for round trip
            "trip_type": "O",  # O=One-way, R=Round-trip, Y=Round-trip Special
            "flight_class": "E",  # E=Economy, P=Premium, B=Business, F=First
            "adults": 1,
            "children": 0,
            "infants": 0,
            "search_mode": "BOTH",  # REALTIME, INVENTORY, BOTH
            "direct_only": false,
            "sort_by": "price",  # price, duration, departure_time
            "airline_id": "",  # Optional filter
            "fare_type": "N"  # N=Normal, C=Corporate, R=Retail
        }
        """
        serializer = FlightSearchSerializer(data=request.data)
        if not serializer.is_valid():
            return self.get_error_response(
                message="Invalid search parameters",
                status="error",
                errors=self.custom_serializer_error(serializer.errors),
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        search_data = serializer.validated_data
        search_mode = search_data.get('search_mode', 'BOTH')
        
        try:
            all_flight_options = []
            
            # Search inventory if requested
            if search_mode in ['INVENTORY', 'BOTH']:
                inventory_options = self._search_inventory(search_data)
                all_flight_options.extend(inventory_options)
            
            # Search real-time via AirIQ if requested
            if search_mode in ['REALTIME', 'BOTH']:
                try:
                    realtime_options = self._search_realtime(search_data)
                    all_flight_options.extend(realtime_options)
                except AirIQException as e:
                    logger.error(f"AirIQ search failed: {e}")
                    # Continue with inventory results if AirIQ fails
                    if search_mode == 'REALTIME':
                        return self.get_error_response(
                            message=f"Flight search failed: {e}",
                            status="error",
                            error_code="AIRIQ_ERROR",
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
            
            # Sort and paginate results
            sorted_options = self._sort_flight_options(all_flight_options, search_data.get('sort_by', 'price'))
            
            # Apply pagination
            page_size = int(request.query_params.get('page_size', 50))
            page_number = int(request.query_params.get('page', 1))
            
            start_idx = (page_number - 1) * page_size
            end_idx = start_idx + page_size
            paginated_options = sorted_options[start_idx:end_idx]
            
            # Serialize results
            serializer = FlightOptionSerializer(paginated_options, many=True)
            
            response_data = {
                'search_results': serializer.data,
                'total_results': len(sorted_options),
                'page': page_number,
                'page_size': page_size,
                'has_next': end_idx < len(sorted_options),
                'search_mode': search_mode,
                'search_timestamp': timezone.now().isoformat()
            }
            
            return self.get_response(
                data=response_data,
                message="Flights retrieved successfully",
                status="success",
                count=len(sorted_options),
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Flight search error: {e}")
            return self.get_error_response(
                message="Failed to search flights",
                status="error",
                error_code="SEARCH_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _search_inventory(self, search_data):
        """Search in pre-booked inventory"""
        try:
            # Convert date string to date object if needed
            if isinstance(search_data['departure_date'], str):
                search_data['departure_date'] = datetime.strptime(search_data['departure_date'], '%Y-%m-%d').date()
            
            inventory_options = inventory_service.search_inventory_flights(search_data)
            return inventory_options
        except Exception as e:
            logger.error(f"Inventory search error: {e}")
            return []

    def _search_realtime(self, search_data):
        """Search via AirIQ real-time API"""
        try:
            # Convert date format for AirIQ (YYYYMMDD)
            departure_date = search_data['departure_date']
            if isinstance(departure_date, str):
                departure_date = datetime.strptime(departure_date, '%Y-%m-%d').date()
            
            airiq_search_params = {
                'origin': search_data['origin'],
                'destination': search_data['destination'],
                'departure_date': departure_date.strftime('%Y%m%d'),
                'trip_type': search_data.get('trip_type', 'O'),
                'flight_class': search_data.get('flight_class', 'E'),
                'adults': search_data.get('adults', 1),
                'children': search_data.get('children', 0),
                'infants': search_data.get('infants', 0),
                'airline_id': search_data.get('airline_id', ''),
                'fare_type': search_data.get('fare_type', 'N'),
                'direct_only': search_data.get('direct_only', False)
            }
            
            # Add return date for round trip
            if search_data.get('return_date') and search_data.get('trip_type') in ['R', 'Y']:
                return_date = search_data['return_date']
                if isinstance(return_date, str):
                    return_date = datetime.strptime(return_date, '%Y-%m-%d').date()
                airiq_search_params['return_date'] = return_date.strftime('%Y%m%d')
            
            # Call AirIQ API
            response_data, track_id = airiq_service.search_flights(airiq_search_params)
            
            # Convert AirIQ response to FlightOption objects
            realtime_options = self._parse_airiq_results(response_data, track_id, search_data)
            return realtime_options
            
        except AirIQException:
            raise
        except Exception as e:
            logger.error(f"Real-time search error: {e}")
            return []

    def _parse_airiq_results(self, response_data, track_id, search_data):
        """Parse AirIQ API response into FlightOption objects"""
        flight_options = []
        
        logger.info(f"Parsing AirIQ response with track_id: {track_id}")
        
        # Check if we have the correct response structure
        if not response_data.get('ItineraryFlightList'):
            logger.warning(f"No ItineraryFlightList found in response: {response_data.keys()}")
            return flight_options
        
        logger.info(f"Found {len(response_data['ItineraryFlightList'])} flight groups")
        
        # Create search session for tracking
        import uuid
        session_id = f"search_{uuid.uuid4().hex[:12]}"
        
        search_session = FlightSearchSession.objects.create(
            session_id=session_id,
            origin=search_data['origin'],
            destination=search_data['destination'],
            departure_date=search_data['departure_date'],
            return_date=search_data.get('return_date'),
            trip_type=search_data.get('trip_type', 'O'),
            flight_class=search_data.get('flight_class', 'E'),
            adults=search_data.get('adults', 1),
            children=search_data.get('children', 0),
            infants=search_data.get('infants', 0),
            search_mode='REALTIME',
            airiq_track_id=track_id,
            expires_at=timezone.now() + timedelta(hours=2)
        )
        
        # Parse each flight result
        for flight_group_idx, flight_group in enumerate(response_data['ItineraryFlightList']):
            logger.info(f"Processing flight group {flight_group_idx + 1}")
            
            if not flight_group.get('Items'):
                logger.warning(f"Flight group {flight_group_idx + 1} has no Items")
                continue
                
            logger.info(f"Flight group {flight_group_idx + 1} has {len(flight_group['Items'])} items")
                
            for item_idx, flight_item in enumerate(flight_group['Items']):
                logger.info(f"Processing flight item {item_idx + 1} in group {flight_group_idx + 1}")
                
                flight_details = flight_item.get('FlightDetails', [])
                if not flight_details:
                    logger.warning(f"Flight item {item_idx + 1} has no FlightDetails")
                    continue
                
                logger.info(f"Flight item has {len(flight_details)} segments")
                
                # Use first segment for main details (may need enhancement for multi-segment)
                first_segment = flight_details[0]
                logger.info(f"First segment keys: {list(first_segment.keys())}")
                
                # Parse fare information - Updated based on actual AirIQ response structure
                fares = flight_item.get('Fares', [])
                base_fare = 0
                taxes = 0
                total_fare = 0
                
                if fares:
                    logger.info(f"Found {len(fares)} fare options")
                    # Get first fare option
                    first_fare = fares[0]
                    logger.info(f"First fare keys: {list(first_fare.keys())}")
                    
                    fare_desc = first_fare.get('Faredescription', [])
                    if fare_desc:
                        logger.info(f"Found {len(fare_desc)} fare descriptions")
                        first_fare_desc = fare_desc[0]
                        logger.info(f"First fare description keys: {list(first_fare_desc.keys())}")
                        
                        base_fare = float(first_fare_desc.get('BaseAmount', 0))
                        taxes = float(first_fare_desc.get('TotalTaxAmount', 0))
                        total_fare = float(first_fare_desc.get('GrossAmount', 0))
                        
                        logger.info(f"Parsed fare - Base: {base_fare}, Taxes: {taxes}, Total: {total_fare}")
                else:
                    logger.warning("No fare information found")
                
                # Extract airline code correctly - it should be airline code, not description
                airline_code = first_segment.get('AirlineCode', first_segment.get('AirlineDescription', ''))[:3]
                flight_number = first_segment.get('FlightNumber', '')
                
                # If flight number already includes airline code, extract just the number part
                if flight_number.startswith(airline_code):
                    flight_number = flight_number[len(airline_code):].strip()
                
                # Create FlightOption with corrected field mappings
                try:
                    flight_option = FlightOption.objects.create(
                        search_session=search_session,
                        airiq_flight_id=first_segment.get('FlightID', ''),
                        airline_code=airline_code,
                        flight_number=flight_number,
                        origin=first_segment.get('Origin', ''),
                        destination=first_segment.get('Destination', ''),
                        departure_datetime=self._parse_airiq_datetime(first_segment.get('DepartureDateTime', '')),
                        arrival_datetime=self._parse_airiq_datetime(first_segment.get('ArrivalDateTime', '')),
                        flight_class=first_segment.get('Class', 'E'),
                        fare_basis=first_segment.get('FareBasisCode', ''),
                        airline_category=first_segment.get('AirlineCategory', 'LCC'),
                        stops=int(first_segment.get('Stops', 0)),
                        duration_minutes=self._parse_duration(first_segment.get('JourneyTime', '')),
                        aircraft_type=first_segment.get('AirCraftType', ''),
                        base_fare=base_fare,
                        taxes=taxes,
                        total_fare=total_fare,
                        available_seats=int(first_segment.get('AvailSeat', 9)),
                        baggage_info={'checked': first_segment.get('Baggage', '15kg')},
                        is_refundable=first_segment.get('Refundable', 'False').lower() == 'true',
                        can_hold=True  # AirIQ supports holding bookings
                    )
                    
                    flight_options.append(flight_option)
                    logger.info(f"Created FlightOption {flight_option.id}: {flight_option.airline_code} {flight_option.flight_number}")
                    
                except Exception as e:
                    logger.error(f"Failed to create FlightOption: {e}")
                    logger.error(f"First segment data: {first_segment}")
                    continue
        
        logger.info(f"Successfully parsed {len(flight_options)} flight options")
        return flight_options

    def _parse_airiq_datetime(self, datetime_str):
        """Parse AirIQ datetime format: '14 Nov 2023 14:20'"""
        from django.utils import timezone as tz_utils
        
        if not datetime_str:
            logger.warning("Empty datetime string provided")
            return tz_utils.now()
            
        try:
            # Try the main AirIQ format first
            parsed_dt = datetime.strptime(datetime_str.strip(), '%d %b %Y %H:%M')
            # Make timezone aware using Django's default timezone
            parsed_dt = tz_utils.make_aware(parsed_dt, tz_utils.get_default_timezone())
            logger.debug(f"Successfully parsed datetime: {datetime_str} -> {parsed_dt}")
            return parsed_dt
        except ValueError as e:
            logger.warning(f"Failed to parse datetime '{datetime_str}' with format '%d %b %Y %H:%M': {e}")
            
            # Try alternative formats commonly used in APIs
            alternative_formats = [
                '%Y-%m-%d %H:%M:%S',  # ISO format with seconds
                '%Y-%m-%d %H:%M',     # ISO format without seconds
                '%d/%m/%Y %H:%M',     # DD/MM/YYYY HH:MM
                '%Y-%m-%dT%H:%M:%S',  # ISO format with T separator
                '%Y-%m-%dT%H:%M:%SZ', # ISO format with Z
            ]
            
            for fmt in alternative_formats:
                try:
                    parsed_dt = datetime.strptime(datetime_str.strip(), fmt)
                    # Make timezone aware using Django's default timezone
                    parsed_dt = tz_utils.make_aware(parsed_dt, tz_utils.get_default_timezone())
                    logger.info(f"Successfully parsed datetime '{datetime_str}' with alternative format '{fmt}'")
                    return parsed_dt
                except ValueError:
                    continue
            
            logger.error(f"Could not parse datetime '{datetime_str}' with any known format")
            return tz_utils.now()

    def _parse_duration(self, duration_str):
        """Parse duration string to minutes"""
        try:
            # Duration might be in format like "140" (minutes) or "-140"
            return abs(int(duration_str)) if duration_str else 0
        except:
            return 0

    def _sort_flight_options(self, flight_options, sort_by):
        """Sort flight options based on criteria"""
        if sort_by == 'price':
            return sorted(flight_options, key=lambda x: x.total_fare)
        elif sort_by == 'duration':
            return sorted(flight_options, key=lambda x: x.duration_minutes)
        elif sort_by == 'departure_time':
            return sorted(flight_options, key=lambda x: x.departure_datetime)
        else:
            return flight_options

    @action(detail=False, methods=['get'], url_path='airports')
    def list_airports(self, request):
        """List all active airports"""
        airports = Airport.objects.filter(is_active=True).order_by('city', 'name')
        
        # Apply search filter if provided
        search = request.query_params.get('search', '')
        if search:
            airports = airports.filter(
                models.Q(iata_code__icontains=search) |
                models.Q(name__icontains=search) |
                models.Q(city__icontains=search)
            )
        
        airport_data = [
            {
                'iata_code': airport.iata_code,
                'name': airport.name,
                'city': airport.city,
                'country': airport.country
            }
            for airport in airports[:100]  # Limit to 100 results
        ]
        
        return self.get_response(
            data=airport_data,
            message="Airports retrieved successfully",
            status="success",
            count=len(airport_data),
            status_code=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='airlines')
    def list_airlines(self, request):
        """List all active airlines"""
        airlines = Airline.objects.filter(is_active=True).order_by('name')
        
        airline_data = [
            {
                'code': airline.code,
                'name': airline.name,
                'category': airline.category
            }
            for airline in airlines
        ]
        
        return self.get_response(
            data=airline_data,
            message="Airlines retrieved successfully",
            status="success",
            count=len(airline_data),
            status_code=status.HTTP_200_OK
        )


class FlightPricingViewSet(viewsets.ViewSet, StandardResponseMixin, LoggingMixin):
    """Flight pricing and fare details endpoints"""
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], url_path='price')
    def price_flight(self, request):
        """
        Get detailed pricing for selected flight
        POST /api/v1/flights/pricing/price/
        
        Body: {
            "flight_option_id": 123,
            "passenger_count": {
                "adults": 1,
                "children": 0,
                "infants": 0
            }
        }
        """
        serializer = FlightPricingSerializer(data=request.data)
        if not serializer.is_valid():
            return self.get_error_response(
                message="Invalid pricing parameters",
                status="error",
                errors=self.custom_serializer_error(serializer.errors),
                error_code="VALIDATION_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            flight_option = FlightOption.objects.select_related(
                'search_session', 'inventory_flight'
            ).get(id=serializer.validated_data['flight_option_id'])
            
            # Check if this is inventory or real-time
            if flight_option.inventory_flight:
                # Inventory pricing
                pricing_data = self._get_inventory_pricing(flight_option, serializer.validated_data)
            else:
                # Real-time AirIQ pricing
                pricing_data = self._get_realtime_pricing(flight_option, serializer.validated_data)
            
            return self.get_response(
                data=pricing_data,
                message="Pricing retrieved successfully",
                status="success",
                count=1,
                status_code=status.HTTP_200_OK
            )
            
        except FlightOption.DoesNotExist:
            return self.get_error_response(
                message="Flight option not found",
                status="error",
                error_code="NOT_FOUND",
                status_code=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Pricing error: {e}")
            return self.get_error_response(
                message="Failed to get pricing",
                status="error",
                error_code="PRICING_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_inventory_pricing(self, flight_option, pricing_data):
        """Get pricing for inventory flights"""
        passenger_count = pricing_data['passenger_count']
        adults = passenger_count.get('adults', 1)
        children = passenger_count.get('children', 0)
        infants = passenger_count.get('infants', 0)
        
        # Calculate pricing based on inventory
        base_fare_per_person = flight_option.base_fare
        taxes_per_person = flight_option.taxes
        
        # Children typically get discounted fares (80% of adult fare)
        adult_fare = base_fare_per_person * adults
        child_fare = base_fare_per_person * children * 0.8
        infant_fare = base_fare_per_person * infants * 0.1  # Infants get 10% of adult fare
        
        total_base_fare = adult_fare + child_fare + infant_fare
        total_taxes = taxes_per_person * (adults + children + infants * 0.1)
        total_amount = total_base_fare + total_taxes
        
        return {
            'flight_option_id': flight_option.id,
            'pricing_breakdown': {
                'adult_fare': adult_fare,
                'child_fare': child_fare,
                'infant_fare': infant_fare,
                'total_base_fare': total_base_fare,
                'total_taxes': total_taxes,
                'total_amount': total_amount
            },
            'passenger_breakdown': [
                {
                    'type': 'Adult',
                    'count': adults,
                    'fare_per_person': base_fare_per_person,
                    'taxes_per_person': taxes_per_person,
                    'total_per_person': base_fare_per_person + taxes_per_person
                },
                {
                    'type': 'Child',
                    'count': children,
                    'fare_per_person': base_fare_per_person * 0.8,
                    'taxes_per_person': taxes_per_person,
                    'total_per_person': (base_fare_per_person * 0.8) + taxes_per_person
                },
                {
                    'type': 'Infant',
                    'count': infants,
                    'fare_per_person': base_fare_per_person * 0.1,
                    'taxes_per_person': taxes_per_person * 0.1,
                    'total_per_person': (base_fare_per_person * 0.1) + (taxes_per_person * 0.1)
                }
            ],
            'baggage_info': flight_option.baggage_info,
            'fare_rules': flight_option.fare_rules,
            'is_refundable': flight_option.is_refundable,
            'booking_mode': 'INVENTORY'
        }

    def _get_realtime_pricing(self, flight_option, pricing_data):
        """Get pricing from AirIQ real-time API"""
        try:
            # Prepare flight details for AirIQ pricing API
            flight_details = {
                'origin': flight_option.origin,
                'destination': flight_option.destination,
                'trip_type': flight_option.search_session.trip_type,
                'adults': pricing_data['passenger_count'].get('adults', 1),
                'children': pricing_data['passenger_count'].get('children', 0),
                'infants': pricing_data['passenger_count'].get('infants', 0),
                'segments': [
                    {
                        'FlightID': flight_option.airiq_flight_id,
                        'FlightNumber': flight_option.flight_number,
                        'Origin': flight_option.origin,
                        'Destination': flight_option.destination,
                        'DepartureDateTime': flight_option.departure_datetime.strftime('%d %b %Y %H:%M'),
                        'ArrivalDateTime': flight_option.arrival_datetime.strftime('%d %b %Y %H:%M')
                    }
                ],
                'base_amount': flight_option.base_fare,
                'gross_amount': flight_option.total_fare
            }
            
            # Call AirIQ pricing API
            pricing_response = airiq_service.price_flight(
                flight_details,
                flight_option.search_session.airiq_track_id
            )
            
            # Parse AirIQ pricing response
            return self._parse_airiq_pricing(pricing_response, flight_option)
            
        except AirIQException as e:
            logger.error(f"AirIQ pricing failed: {e}")
            # Fallback to estimated pricing
            return self._get_inventory_pricing(flight_option, pricing_data)

    def _parse_airiq_pricing(self, pricing_response, flight_option):
        """Parse AirIQ pricing response"""
        # This would parse the actual AirIQ pricing response
        # For now, returning a simplified structure
        return {
            'flight_option_id': flight_option.id,
            'pricing_breakdown': pricing_response.get('PriceItenaryInfo', {}),
            'booking_mode': 'REALTIME',
            'airiq_response': pricing_response
        }

    @action(detail=False, methods=['post'], url_path='fare-rules')
    def get_fare_rules(self, request):
        """Get fare rules for specific flights"""
        flight_option_ids = request.data.get('flight_option_ids', [])
        
        if not flight_option_ids:
            return self.get_error_response(
                message="flight_option_ids required",
                status="error",
                error_code="MISSING_PARAMETER",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            flight_options = FlightOption.objects.filter(id__in=flight_option_ids)
            fare_rules_data = []
            
            for flight_option in flight_options:
                if flight_option.airiq_flight_id:
                    # Get fare rules from AirIQ
                    try:
                        fare_rules = airiq_service.get_fare_rules(
                            [flight_option.airiq_flight_id],
                            flight_option.search_session.airiq_track_id
                        )
                        fare_rules_data.append({
                            'flight_option_id': flight_option.id,
                            'fare_rules': fare_rules
                        })
                    except AirIQException:
                        # Use default fare rules for inventory
                        fare_rules_data.append({
                            'flight_option_id': flight_option.id,
                            'fare_rules': flight_option.fare_rules or {}
                        })
                else:
                    # Inventory flight - use stored fare rules
                    fare_rules_data.append({
                        'flight_option_id': flight_option.id,
                        'fare_rules': flight_option.fare_rules or {}
                    })
            
            return self.get_response(
                data=fare_rules_data,
                message="Fare rules retrieved successfully",
                status="success",
                count=len(fare_rules_data),
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Fare rules error: {e}")
            return self.get_error_response(
                message="Failed to get fare rules",
                status="error",
                error_code="FARE_RULES_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='multi-class')
    def get_multi_class(self, request):
        """
        Get available classes for flights
        POST /api/v1/flights/pricing/multi-class/
        
        Body: {
            "flight_ids": ["9603"],
            "adults": 1,
            "children": 0,
            "infants": 0,
            "trip_type": "O",
            "track_id": "<Trackid from Availability>"
        }
        """
        missing = []
        if not request.data.get('flight_ids'):
            missing.append('flight_ids')
        if not request.data.get('track_id'):
            missing.append('track_id')
        if missing:
            return self.get_error_response(
                message=f"Missing required fields: {', '.join(missing)}",
                status="error",
                error_code="MISSING_FIELDS",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            response_data = airiq_service.get_multi_class(
                flight_ids=[str(fid) for fid in request.data['flight_ids']],
                adults=int(request.data.get('adults', 1)),
                children=int(request.data.get('children', 0)),
                infants=int(request.data.get('infants', 0)),
                trip_type=request.data.get('trip_type', 'O'),
                track_id=request.data['track_id']
            )
            
            return self.get_response(
                data=response_data,
                message="Multi-class availability retrieved successfully",
                status="success",
                status_code=status.HTTP_200_OK
            )
            
        except AirIQException as e:
            return self.get_error_response(
                message=f"Multi-class request failed: {e}",
                status="error",
                error_code="AIRIQ_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Multi-class error: {e}")
            return self.get_error_response(
                message="Failed to get multi-class availability",
                status="error",
                error_code="MULTI_CLASS_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='multi-class-fare')
    def get_multi_class_fare(self, request):
        """
        Get fare for specific class
        POST /api/v1/flights/pricing/multi-class-fare/
        
        Body: {
            "flight_ids": ["9603"],
            "class_fare": [{"AirlineClass": "B", "SeatAvailFlag": "9"}],
            "adults": 1,
            "children": 0,
            "infants": 0,
            "trip_type": "O",
            "track_id": "<Trackid from Availability>"
        }
        """
        required_fields = ['flight_ids', 'class_fare', 'track_id']
        missing_fields = [field for field in required_fields if not request.data.get(field)]
        if missing_fields:
            return self.get_error_response(
                message=f"Missing required fields: {', '.join(missing_fields)}",
                status="error",
                error_code="MISSING_FIELDS",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate counts for roundtrip: ClassFare length should match FlightIDs length
        if len(request.data['class_fare']) != len(request.data['flight_ids']):
            return self.get_error_response(
                message="class_fare count must match flight_ids count (one class per segment)",
                status="error",
                error_code="INVALID_CLASS_FARE",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            response_data = airiq_service.get_multi_class_fare(
                flight_ids=[str(fid) for fid in request.data['flight_ids']],
                class_fare=request.data['class_fare'],
                adults=int(request.data.get('adults', 1)),
                children=int(request.data.get('children', 0)),
                infants=int(request.data.get('infants', 0)),
                trip_type=request.data.get('trip_type', 'O'),
                track_id=request.data['track_id']
            )
            
            return self.get_response(
                data=response_data,
                message="Multi-class fare retrieved successfully",
                status="success",
                status_code=status.HTTP_200_OK
            )
            
        except AirIQException as e:
            return self.get_error_response(
                message=f"Multi-class fare request failed: {e}",
                status="error",
                error_code="AIRIQ_ERROR",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Multi-class fare error: {e}")
            return self.get_error_response(
                message="Failed to get multi-class fare",
                status="error",
                error_code="MULTI_CLASS_FARE_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='seatmap')
    def get_seat_map(self, request):
        """
        Get seat map for selected flight segments
        POST /api/v1/flights/pricing/seatmap/
        
        Body: {
            "flight_segments": [
                {
                    "FlightID": "7368",
                    "FlightNumber": "6E 292",
                    "Origin": "IXB",
                    "Destination": "CCU",
                    "DepartureDateTime": "14 Nov 2023 14:20",
                    "ArrivalDateTime": "14 Nov 2023 15:25"
                }
            ],
            "passengers": [
                {
                    "reference": 1,
                    "title": "Mr",
                    "type": "ADT",
                    "first_name": "TESTA",
                    "last_name": "TEST"
                }
            ],
            "track_id": "<TrackId from Pricing response>"
        }
        """
        required_fields = ['flight_segments', 'passengers', 'track_id']
        missing_fields = [field for field in required_fields if not request.data.get(field)]
        if missing_fields:
            return self.get_error_response(
                message=f"Missing required fields: {', '.join(missing_fields)}",
                status="error",
                error_code="MISSING_FIELDS",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            response_data = airiq_service.get_seat_map(
                flight_segments=request.data['flight_segments'],
                passengers=request.data['passengers'],
                track_id=request.data['track_id']
            )
            
            return self.get_response(
                data=response_data,
                message="Seat map retrieved successfully",
                status="success",
                status_code=status.HTTP_200_OK
            )
        except AirIQException as e:
            return self.get_error_response(
                message=f"Seat map request failed: {e}",
                status="error",
                error_code="AIRIQ_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Seat map error: {e}")
            return self.get_error_response(
                message="Failed to get seat map",
                status="error",
                error_code="SEATMAP_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='account-balance')
    def get_account_balance(self, request):
        """
        Get agent account balance from AirIQ
        GET /api/v1/flights/pricing/account-balance/
        """
        try:
            response_data = airiq_service.get_account_balance()
            
            return self.get_response(
                data=response_data,
                message="Account balance retrieved successfully",
                status="success",
                status_code=status.HTTP_200_OK
            )
            
        except AirIQException as e:
            return self.get_error_response(
                message=f"Account balance request failed: {e}",
                status="error",
                error_code="AIRIQ_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Account balance error: {e}")
            return self.get_error_response(
                message="Failed to get account balance",
                status="error",
                error_code="BALANCE_ERROR",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


