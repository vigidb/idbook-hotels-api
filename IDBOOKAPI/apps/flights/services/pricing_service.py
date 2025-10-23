"""
Comprehensive Flight Pricing Service
Handles session-based pricing cache, total calculations, and AirIQ integration
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
import logging
import uuid
import json

from ..models import FlightSearchSession, FlightOption, AirIQApiLog
from .airiq_service import airiq_service, AirIQException

logger = logging.getLogger(__name__)


class FlightPricingService:
    """
    Comprehensive service for flight pricing with session-based caching
    Handles the complete flow: search → pricing → cache → booking
    """
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.search_cache_timeout = 1800  # 30 minutes
    
    def create_pricing_session(self, search_params: dict, user=None, track_id: str = None, flight_results: List[Dict] = None) -> Dict:
        """
        Create a new pricing session with comprehensive pricing data
        
        Args:
            search_params: {
                'origin': 'DEL',
                'destination': 'BOM',
                'departure_date': '2025-11-20',
                'return_date': '2025-11-25',  # Optional for round trip
                'trip_type': 'O',  # O=One-way, R=Round-trip
                'adults': 1,
                'children': 0,
                'infants': 0,
                'flight_class': 'E'  # E=Economy, B=Business, F=First
            }
        
        Returns:
            {
                'session_id': 'fps_abc123',
                'track_id': 'AirIQ_Track_ID',
                'pricing_data': {...},
                'expires_at': '2025-11-20T10:05:00Z',
                'time_remaining': 300
            }
        """
        try:
            # If track_id and flight_results are provided, skip AirIQ search
            if track_id and flight_results is not None:
                search_response = {'ItineraryFlightList': flight_results}
                flight_options = flight_results  # Use pre-fetched results directly
            else:
                # Format dates for AirIQ
                departure_date_airiq = datetime.strptime(search_params['departure_date'], '%Y-%m-%d').strftime('%Y%m%d')
                return_date_airiq = None
                if search_params.get('return_date'):
                    return_date_airiq = datetime.strptime(search_params['return_date'], '%Y-%m-%d').strftime('%Y%m%d')
                
                # Search flights via AirIQ
                airiq_search_params = {
                    'origin': search_params['origin'],
                    'destination': search_params['destination'],
                    'departure_date': departure_date_airiq,
                    'return_date': return_date_airiq,
                    'trip_type': search_params.get('trip_type', 'O'),
                    'flight_class': search_params.get('flight_class', 'E'),
                    'adults': search_params.get('adults', 1),
                    'children': search_params.get('children', 0),
                    'infants': search_params.get('infants', 0),
                    'direct_only': search_params.get('direct_only', False)
                }
                
                search_response, track_id = airiq_service.search_flights(airiq_search_params)
                
                if not track_id:
                    raise ValueError("No track ID received from AirIQ search")
                
                flight_options = self._extract_flight_options(search_response)
            
            # Generate session ID
            session_id = f"fps_{uuid.uuid4().hex[:12]}"
            expires_at = timezone.now() + timedelta(minutes=5)
            
            # Create pricing session data
            pricing_session = {
                'session_id': session_id,
                'user_id': user.id if user else None,
                'search_params': search_params,
                'track_id': track_id,
                'search_response': search_response,
                'flight_options': flight_options,
                'expires_at': expires_at,
                'created_at': timezone.now(),
                'pricing_calculated': False
            }
            
            # Cache the session
            cache.set(f"flight_pricing_session:{session_id}", pricing_session, timeout=self.cache_timeout)
            
            logger.info(f"Created flight pricing session {session_id} with track_id {track_id}")
            
            return {
                'session_id': session_id,
                'track_id': track_id,
                'flight_options': flight_options,
                'expires_at': expires_at.isoformat(),
                'time_remaining_minutes': 5
            }
            
        except AirIQException as e:
            logger.error(f"AirIQ error creating pricing session: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating pricing session: {str(e)}")
            raise ValueError(f"Failed to create pricing session: {str(e)}")
    
    def get_detailed_pricing(self, session_id: str, selected_flights: List[dict], 
                           ancillary_services: Dict = None) -> Dict:
        """
        Get detailed pricing for selected flights with ancillary services
        
        Args:
            session_id: Pricing session ID
            selected_flights: List of selected flight details
            ancillary_services: {
                'seats': [{'passenger_ref': 1, 'seat_id': '12A', 'price': 500}],
                'meals': [{'passenger_ref': 1, 'meal_id': 'VEG', 'price': 300}],
                'baggage': [{'passenger_ref': 1, 'baggage_id': 'BG15', 'price': 1500}],
                'other': [{'passenger_ref': 1, 'service_id': 'WIFI', 'price': 200}]
            }
        
        Returns:
            Complete pricing breakdown with all components
        """
        try:
            # Get session from cache
            pricing_session = cache.get(f"flight_pricing_session:{session_id}")
            if not pricing_session:
                raise ValueError("Pricing session expired or not found")
            
            # Check if session is expired
            if timezone.now() > pricing_session['expires_at']:
                raise ValueError("Pricing session has expired")
            
            # Get detailed pricing from AirIQ
            pricing_response = self._get_airiq_pricing(
                pricing_session['track_id'], 
                selected_flights, 
                pricing_session['search_params']
            )
            
            # Calculate comprehensive pricing
            pricing_breakdown = self._calculate_comprehensive_pricing(
                pricing_response, 
                pricing_session['search_params'],
                ancillary_services or {}
            )
            
            # Update session with pricing data
            pricing_session['pricing_data'] = pricing_response
            pricing_session['pricing_breakdown'] = pricing_breakdown
            pricing_session['selected_flights'] = selected_flights
            pricing_session['ancillary_services'] = ancillary_services or {}
            pricing_session['pricing_calculated'] = True
            
            # Update cache
            cache.set(f"flight_pricing_session:{session_id}", pricing_session, timeout=self.cache_timeout)
            
            logger.info(f"Calculated detailed pricing for session {session_id}")
            
            return {
                'session_id': session_id,
                'pricing_breakdown': pricing_breakdown,
                'pricing_token': pricing_response.get('Token', ''),
                'expires_at': pricing_session['expires_at'].isoformat(),
                'time_remaining': max(0, int((pricing_session['expires_at'] - timezone.now()).total_seconds()))
            }
            
        except AirIQException as e:
            logger.error(f"AirIQ pricing error for session {session_id}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error calculating pricing for session {session_id}: {str(e)}")
            raise ValueError(f"Failed to calculate pricing: {str(e)}")
    
    def get_session_data(self, session_id: str) -> Optional[Dict]:
        """Get pricing session data"""
        return cache.get(f"flight_pricing_session:{session_id}")
    
    def extend_session(self, session_id: str, minutes: int = 5) -> bool:
        """Extend pricing session expiry"""
        try:
            pricing_session = cache.get(f"flight_pricing_session:{session_id}")
            if not pricing_session:
                return False
            
            new_expiry = timezone.now() + timedelta(minutes=minutes)
            pricing_session['expires_at'] = new_expiry
            
            cache.set(f"flight_pricing_session:{session_id}", pricing_session, timeout=minutes * 60)
            
            logger.info(f"Extended session {session_id} by {minutes} minutes")
            return True
            
        except Exception as e:
            logger.error(f"Error extending session {session_id}: {str(e)}")
            return False
    
    def calculate_booking_total(self, pricing_breakdown: Dict, gst_info: Dict = None) -> Dict:
        """
        Calculate final booking total including GST and all charges
        
        Args:
            pricing_breakdown: Pricing breakdown from get_detailed_pricing
            gst_info: GST information if business booking
        
        Returns:
            Final pricing with GST calculations
        """
        try:
            # Base amounts
            base_fare = Decimal(str(pricing_breakdown['base_fare']))
            taxes = Decimal(str(pricing_breakdown['taxes']))
            ancillary_total = Decimal(str(pricing_breakdown['ancillary_total']))
            
            # Subtotal before GST
            subtotal = base_fare + taxes + ancillary_total
            
            # Calculate GST
            gst_calculation = self._calculate_gst(subtotal, gst_info)
            
            # Final total
            final_total = subtotal + gst_calculation['total_gst']
            
            return {
                'base_fare': float(base_fare),
                'taxes': float(taxes),
                'ancillary_total': float(ancillary_total),
                'subtotal': float(subtotal),
                'gst_breakdown': gst_calculation,
                'final_total': float(final_total),
                'currency': 'INR'
            }
            
        except Exception as e:
            logger.error(f"Error calculating booking total: {str(e)}")
            raise ValueError(f"Failed to calculate booking total: {str(e)}")
    
    def mark_session_as_booked(self, session_id: str, booking_reference: str) -> bool:
        """Mark pricing session as successfully booked"""
        try:
            pricing_session = cache.get(f"flight_pricing_session:{session_id}")
            if not pricing_session:
                return False
            
            pricing_session['is_booked'] = True
            pricing_session['booking_reference'] = booking_reference
            pricing_session['booked_at'] = timezone.now()
            
            # Extend cache for audit purposes
            cache.set(f"flight_pricing_session:{session_id}", pricing_session, timeout=86400)  # 24 hours
            
            logger.info(f"Marked session {session_id} as booked with reference {booking_reference}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking session {session_id} as booked: {str(e)}")
            return False
    
    def _extract_flight_options(self, search_response: Dict) -> List[Dict]:
        """Extract and format flight options from AirIQ search response"""
        options = []
        
        try:
            itinerary_list = search_response.get('ItineraryFlightList', [])
            
            for itinerary in itinerary_list:
                items = itinerary.get('Items', [])
                
                for item in items:
                    flight_details = item.get('FlightDetails', [])
                    fares = item.get('Fares', [])
                    
                    if flight_details and fares:
                        option = {
                            'flight_id': flight_details[0].get('FlightID'),
                            'airline_code': flight_details[0].get('AirlineDescription'),
                            'flight_number': flight_details[0].get('FlightNumber'),
                            'origin': flight_details[0].get('Origin'),
                            'destination': flight_details[-1].get('Destination'),  # Last segment destination
                            'departure_time': flight_details[0].get('DepartureDateTime'),
                            'arrival_time': flight_details[-1].get('ArrivalDateTime'),
                            'stops': len(flight_details) - 1,
                            'duration': flight_details[0].get('FlyingTime', ''),
                            'segments': flight_details,
                            'fares': fares,
                            'base_amount': fares[0].get('Faredescription', [{}])[0].get('BaseAmount', '0'),
                            'gross_amount': fares[0].get('Faredescription', [{}])[0].get('GrossAmount', '0'),
                            'airline_category': flight_details[0].get('AirlineCategory', 'LCC'),
                            'refundable': flight_details[0].get('Refundable', 'False') == 'True',
                            'baggage': flight_details[0].get('Baggage', ''),
                            'flight_data': item  # Store complete data for booking
                        }
                        options.append(option)
            
            return options
            
        except Exception as e:
            logger.error(f"Error extracting flight options: {str(e)}")
            return []
    
    def _get_airiq_pricing(self, track_id: str, selected_flights: List[Dict], search_params: Dict) -> Dict:
        """Get detailed pricing from AirIQ"""
        try:
            # Validate inputs
            if not track_id:
                logger.error("No track_id provided for pricing")
                return None
            
            if not selected_flights:
                logger.error("No selected flights provided for pricing")
                return None
            
            # Format flight details for AirIQ pricing call
            flight_details = {
                'origin': search_params['origin'],
                'destination': search_params['destination'],
                'trip_type': search_params.get('trip_type', 'O'),
                'adults': search_params.get('adults', 1),
                'children': search_params.get('children', 0),
                'infants': search_params.get('infants', 0),
                'segments': [],
                'base_amount': '0',
                'gross_amount': '0'
            }
            
            # Extract segment details
            total_base = Decimal('0')
            total_gross = Decimal('0')
            
            for flight in selected_flights:
                segments = flight.get('segments', [])
                if segments:
                    flight_details['segments'].extend(segments)
                
                # Handle different amount field names
                base_amount = flight.get('base_amount', flight.get('BaseAmount', flight.get('baseAmount', '0')))
                gross_amount = flight.get('gross_amount', flight.get('GrossAmount', flight.get('grossAmount', '0')))
                
                total_base += Decimal(str(base_amount))
                total_gross += Decimal(str(gross_amount))
            
            flight_details['base_amount'] = str(total_base)
            flight_details['gross_amount'] = str(total_gross)
            
            # Log the pricing request for debugging
            logger.info(f"Requesting AirIQ pricing for track_id: {track_id}, segments: {len(flight_details['segments'])}, base: {total_base}, gross: {total_gross}")
            
            # Call AirIQ pricing API
            pricing_response = airiq_service.price_flight(flight_details, track_id)
            
            # Log response structure for debugging
            if pricing_response:
                logger.info(f"AirIQ pricing response keys: {list(pricing_response.keys())}")
            else:
                logger.warning("AirIQ pricing returned None response")
            
            return pricing_response
            
        except AirIQException as e:
            logger.error(f"AirIQ service error getting pricing: {str(e)}")
            return None  # Return None to trigger fallback pricing
        except Exception as e:
            logger.error(f"Unexpected error getting AirIQ pricing: {str(e)}")
            return None  # Return None to trigger fallback pricing
    
    def _calculate_comprehensive_pricing(self, pricing_response: Dict, 
                                       search_params: Dict, ancillary_services: Dict) -> Dict:
        """Calculate comprehensive pricing breakdown"""
        try:
            # Log the pricing response structure for debugging
            logger.debug(f"Pricing response structure: {list(pricing_response.keys()) if pricing_response else 'None'}")
            
            # Validate pricing response
            if not pricing_response or not isinstance(pricing_response, dict):
                logger.warning("Pricing response is None or invalid, using fallback pricing")
                return self._create_fallback_pricing(search_params, ancillary_services)
            
            # Extract base pricing from AirIQ response with multiple fallbacks
            price_itinerary_info = None
            fare_breakdown = None
            
            # Try different response structures
            if 'PriceItenaryInfo' in pricing_response:
                price_info_list = pricing_response['PriceItenaryInfo']
                if price_info_list and isinstance(price_info_list, list):
                    price_itinerary_info = price_info_list[0]
            elif 'PriceItineraryInfo' in pricing_response:  # Alternative spelling
                price_info_list = pricing_response['PriceItineraryInfo']
                if price_info_list and isinstance(price_info_list, list):
                    price_itinerary_info = price_info_list[0]
            elif 'ItineraryInfo' in pricing_response:
                price_info_list = pricing_response['ItineraryInfo']
                if price_info_list and isinstance(price_info_list, list):
                    price_itinerary_info = price_info_list[0]
            
            if not price_itinerary_info:
                logger.warning("No price itinerary info found in response, using fallback")
                return self._create_fallback_pricing(search_params, ancillary_services)
            
            # Extract fare breakdown
            if 'FareBreakdown' in price_itinerary_info:
                fare_breakdown_list = price_itinerary_info['FareBreakdown']
                if fare_breakdown_list and isinstance(fare_breakdown_list, list):
                    fare_breakdown = fare_breakdown_list[0]
            elif 'Fare' in price_itinerary_info:
                fare_breakdown = price_itinerary_info['Fare']
            elif 'FareInfo' in price_itinerary_info:
                fare_breakdown = price_itinerary_info['FareInfo']
            
            if not fare_breakdown:
                logger.warning("No fare breakdown found in response, using fallback")
                return self._create_fallback_pricing(search_params, ancillary_services)
            
            # Base fare and taxes with fallbacks
            base_fare = Decimal(str(fare_breakdown.get('BaseAmount', '0')))
            taxes = Decimal(str(fare_breakdown.get('TotalTaxAmount', fare_breakdown.get('TaxAmount', '0'))))
            gross_amount = Decimal(str(fare_breakdown.get('GrossAmount', fare_breakdown.get('TotalAmount', '0'))))
            
            # If gross_amount is 0, try to calculate from base + tax
            if gross_amount == Decimal('0') and (base_fare > 0 or taxes > 0):
                gross_amount = base_fare + taxes
            
            # Ancillary services pricing (fix the mapping error)
            seats_total = self._calculate_ancillary_total(ancillary_services.get('seats', []))
            meals_total = self._calculate_ancillary_total(ancillary_services.get('meals', []))
            baggage_total = self._calculate_ancillary_total(ancillary_services.get('baggage', []))
            other_total = self._calculate_ancillary_total(ancillary_services.get('other', []))
            
            ancillary_total = meals_total + seats_total + baggage_total + other_total
            
            # Per passenger breakdown
            adults = search_params.get('adults', 1)
            children = search_params.get('children', 0)
            infants = search_params.get('infants', 0)
            
            passenger_breakdown = self._calculate_passenger_breakdown(
                fare_breakdown, adults, children, infants
            )
            
            result = {
                'base_fare': float(base_fare),
                'taxes': float(taxes),
                'gross_amount': float(gross_amount),
                'ancillary_services': {
                    'meals': float(meals_total),
                    'seats': float(seats_total),
                    'baggage': float(baggage_total),
                    'other': float(other_total),
                    'total': float(ancillary_total)
                },
                'ancillary_total': float(ancillary_total),
                'passenger_breakdown': passenger_breakdown,
                'fare_rules': price_itinerary_info.get('FareRules', {}),
                'baggage_info': price_itinerary_info.get('BaggageInfo', {}),
                'meal_info': price_itinerary_info.get('MealInfo', []),
                'seat_info': price_itinerary_info.get('SeatInfo', [])
            }
            
            logger.info(f"Calculated pricing breakdown: base={base_fare}, taxes={taxes}, gross={gross_amount}, ancillary={ancillary_total}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating comprehensive pricing: {str(e)}")
            raise
    
    def _calculate_ancillary_total(self, services: List[Dict]) -> Decimal:
        """Calculate total for ancillary services"""
        total = Decimal('0')
        for service in services:
            # Handle both 'price' and 'amount' fields
            price = service.get('amount', service.get('price', 0))
            total += Decimal(str(price))
        return total
    
    def _create_fallback_pricing(self, search_params: Dict, ancillary_services: Dict) -> Dict:
        """Create fallback pricing when AirIQ response is unavailable"""
        logger.info("Creating fallback pricing due to invalid AirIQ response")
        
        # Basic fallback pricing based on route and passengers
        adults = search_params.get('adults', 1)
        children = search_params.get('children', 0)
        infants = search_params.get('infants', 0)
        
        # Estimate base fare (this would normally come from AirIQ)
        base_fare_per_adult = Decimal('5000')  # Default INR 5000 per adult
        base_fare = base_fare_per_adult * adults
        base_fare += base_fare_per_adult * Decimal('0.75') * children  # 75% for children
        base_fare += base_fare_per_adult * Decimal('0.1') * infants   # 10% for infants
        
        # Estimate taxes (typically 20-30% of base fare)
        taxes = base_fare * Decimal('0.25')
        gross_amount = base_fare + taxes
        
        # Calculate ancillary services
        seats_total = self._calculate_ancillary_total(ancillary_services.get('seats', []))
        meals_total = self._calculate_ancillary_total(ancillary_services.get('meals', []))
        baggage_total = self._calculate_ancillary_total(ancillary_services.get('baggage', []))
        other_total = self._calculate_ancillary_total(ancillary_services.get('other', []))
        ancillary_total = meals_total + seats_total + baggage_total + other_total
        
        # Create passenger breakdown
        passenger_breakdown = {
            'adults': {
                'count': adults,
                'fare_per_person': float(base_fare_per_adult + (taxes / max(adults, 1))),
                'total': float(base_fare_per_adult * adults + (taxes * Decimal('0.8')))
            },
            'children': {
                'count': children,
                'fare_per_person': float(base_fare_per_adult * Decimal('0.75')),
                'total': float(base_fare_per_adult * Decimal('0.75') * children + (taxes * Decimal('0.15')))
            },
            'infants': {
                'count': infants,
                'fare_per_person': float(base_fare_per_adult * Decimal('0.1')),
                'total': float(base_fare_per_adult * Decimal('0.1') * infants + (taxes * Decimal('0.05')))
            }
        }
        
        return {
            'base_fare': float(base_fare),
            'taxes': float(taxes),
            'gross_amount': float(gross_amount),
            'ancillary_services': {
                'meals': float(meals_total),
                'seats': float(seats_total),
                'baggage': float(baggage_total),
                'other': float(other_total),
                'total': float(ancillary_total)
            },
            'ancillary_total': float(ancillary_total),
            'passenger_breakdown': passenger_breakdown,
            'fare_rules': {'note': 'Fallback pricing - contact support for fare rules'},
            'baggage_info': {'note': 'Standard baggage allowance applies'},
            'meal_info': [],
            'seat_info': [],
            'is_fallback': True
        }
    
    def _calculate_passenger_breakdown(self, fare_breakdown: Dict, adults: int, children: int, infants: int) -> Dict:
        """Calculate per passenger type pricing breakdown"""
        try:
            breakdown = {
                'adults': {'count': adults, 'fare_per_person': 0, 'total': 0},
                'children': {'count': children, 'fare_per_person': 0, 'total': 0},
                'infants': {'count': infants, 'fare_per_person': 0, 'total': 0}
            }
            
            # Extract passenger-wise pricing from fare breakdown
            passenger_fares = fare_breakdown.get('PassengerFares', [])
            
            for pax_fare in passenger_fares:
                pax_type = pax_fare.get('PaxType', 'ADT')
                base_amount = Decimal(str(pax_fare.get('BaseAmount', '0')))
                tax_amount = Decimal(str(pax_fare.get('TaxAmount', '0')))
                total_amount = base_amount + tax_amount
                
                if pax_type == 'ADT' and adults > 0:
                    breakdown['adults']['fare_per_person'] = float(total_amount)
                    breakdown['adults']['total'] = float(total_amount * adults)
                elif pax_type == 'CHD' and children > 0:
                    breakdown['children']['fare_per_person'] = float(total_amount)
                    breakdown['children']['total'] = float(total_amount * children)
                elif pax_type == 'INF' and infants > 0:
                    breakdown['infants']['fare_per_person'] = float(total_amount)
                    breakdown['infants']['total'] = float(total_amount * infants)
            
            # If no passenger-wise breakdown available, distribute equally among adults
            if not passenger_fares and adults > 0:
                total_fare = Decimal(str(fare_breakdown.get('GrossAmount', '0')))
                fare_per_adult = total_fare / adults
                breakdown['adults']['fare_per_person'] = float(fare_per_adult)
                breakdown['adults']['total'] = float(total_fare)
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error calculating passenger breakdown: {str(e)}")
            return {
                'adults': {'count': adults, 'fare_per_person': 0, 'total': 0},
                'children': {'count': children, 'fare_per_person': 0, 'total': 0},
                'infants': {'count': infants, 'fare_per_person': 0, 'total': 0}
            }
    
    def _calculate_gst(self, amount: Decimal, gst_info: Dict = None) -> Dict:
        """Calculate GST based on amount and business type"""
        try:
            gst_rate = Decimal('0.05')  # 5% GST for domestic flights
            
            # Check if it's a business booking with GST
            is_business = bool(gst_info and gst_info.get('gst_number'))
            
            if is_business:
                # Business can claim GST, so charge full GST
                cgst = sgst = (amount * gst_rate / 2).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                igst = Decimal('0.00')
                total_gst = cgst + sgst
            else:
                # Individual booking - GST included in fare
                total_gst = Decimal('0.00')
                cgst = sgst = igst = Decimal('0.00')
            
            return {
                'gst_rate': float(gst_rate),
                'cgst': float(cgst),
                'sgst': float(sgst),
                'igst': float(igst),
                'total_gst': float(total_gst),
                'gst_type': 'CGST+SGST' if is_business else 'INCLUSIVE'
            }
            
        except Exception as e:
            logger.error(f"Error calculating GST: {str(e)}")
            return {
                'gst_rate': 0.0,
                'cgst': 0.0,
                'sgst': 0.0,
                'igst': 0.0,
                'total_gst': 0.0,
                'gst_type': 'NONE'
            }


# Singleton instance
flight_pricing_service = FlightPricingService()