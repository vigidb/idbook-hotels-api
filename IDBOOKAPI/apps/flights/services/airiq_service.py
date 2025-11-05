import requests
import base64
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import logging

from ..models import AirIQApiLog, FlightSearchSession, FlightOption, AirIQTokenCache

logger = logging.getLogger(__name__)

proxies = {
    'http': 'http://localhost:8888',
    'https': 'http://localhost:8888',
} if settings.FLIGHT_API_DEBUG else None


class AirIQException(Exception):
    """Custom exception for AirIQ API errors"""
    pass


class AirIQService:
    """
    Comprehensive service for AirIQ API integration
    Handles authentication, search, pricing, booking, and all flight operations
    """
    
    def __init__(self):
        # AirIQ API Configuration from Django settings (which reads from environment)
        self.base_url = settings.AIRIQ_BASE_URL
        self.agent_id = settings.AIRIQ_AGENT_ID
        self.username = settings.AIRIQ_USERNAME
        self.password = settings.AIRIQ_PASSWORD
        self.api_version = getattr(settings, 'AIRIQ_API_VERSION', '2.0')
        
        # Current authentication token
        self._auth_token = None
        self._token_expires_at = None
        
        # API endpoints
        self.endpoints = {
            'login': f'{self.base_url}/Login',
            'availability': f'{self.base_url}/Availability',
            'fare_rules': f'{self.base_url}/GetFareRule',
            'pricing': f'{self.base_url}/Pricing',
            'seat_map': f'{self.base_url}/GetAvailSeatMap',
            'booking': f'{self.base_url}/Book',
            'ticketing': f'{self.base_url}/IssueTicket',
            'get_booking': f'{self.base_url}/RetrieveBooking',
            'balance': f'{self.base_url}/GetBalance',
            'track_status': f'{self.base_url}/TrackStatus',
            'cancel': f'{self.base_url}/Cancel',
            'reschedule_avail': f'{self.base_url}/RescheduleAvail',
            'reschedule': f'{self.base_url}/Reschedule',
            'get_ssr': f'{self.base_url}/GetSSR',
            'add_ssr': f'{self.base_url}/AddSSR',
            'hold_cancel': f'{self.base_url}/HoldCancel',
            'multi_class': f'{self.base_url}/GetMultiClass',
            'multi_class_fare': f'{self.base_url}/GetMultiClassFare',
        }

    def _create_basic_auth_header(self) -> str:
        """
        Create Base64 encoded HTTP Basic Authentication header
        Format: AgentID*Username:Password (Base64 encoded)
        """
        auth_string = f"{self.agent_id}*{self.username}:{self.password}"
        auth_bytes = auth_string.encode('ascii')
        auth_base64 = base64.b64encode(auth_bytes).decode('ascii')
        logger.debug(f"Created basic auth header for login: {auth_string[:10]}...")
        return auth_base64

    def _log_api_call(self, endpoint: str, method: str, request_data: dict, 
                     response_data: dict, result_code: str, error_message: str = '',
                     response_time_ms: int = None, booking=None):
        """Log API call for debugging and audit purposes"""
        try:
            AirIQApiLog.objects.create(
                booking=booking,
                api_endpoint=endpoint,
                http_method=method,
                request_data=request_data,
                response_data=response_data,
                result_code=result_code,
                error_message=error_message,
                response_time_ms=response_time_ms
            )
        except Exception as e:
            logger.error(f"Failed to log API call: {e}")

    def _make_request(self, endpoint: str, data: dict, method: str = 'POST',
                     booking=None) -> Tuple[dict, bool]:
        """
        Make HTTP request to AirIQ API with proper error handling
        Returns (response_data, is_success)
        """
        start_time = time.time()
        headers = {
            'Content-Type': 'application/json',
        }
        
        # Add authentication header based on endpoint type
        if 'Login' not in endpoint:
            # For regular API calls, use TOKEN authentication
            # Proactively refresh if new day or near expiry
            if self._should_refresh_token() or not self._is_token_valid():
                self.authenticate()
            headers['TOKEN'] = self._auth_token
        else:
            # For login endpoint, this should not be used anymore
            # Login is handled by dedicated _perform_login method
            logger.warning("_make_request called for login endpoint - should use _perform_login instead")
        
        try:
            # Helper to perform the HTTP request
            def _do_request():
                request_kwargs = dict(
                    method=method,
                    url=endpoint,
                    headers=headers,
                    json=data,
                    timeout=60*2,
                )
                if proxies:
                    request_kwargs['proxies'] = proxies
                return requests.request(**request_kwargs)

            # First attempt
            response = _do_request()
            
            response_time_ms = int((time.time() - start_time) * 1000)

            # Try to parse JSON response
            try:
                response_data = response.json()
            except ValueError:
                response_data = {'error': 'Invalid JSON response', 'raw': response.text}
                
            # Determine success based on AirIQ's result codes
            is_success = False
            result_code = '-1'  # Default to exception
            error_message = ''
            
            if isinstance(response_data, dict):
                # Check for status in response
                if 'Status' in response_data:
                    result_code = response_data['Status'].get('ResultCode', '-1')
                    error_message = response_data['Status'].get('Error', '')
                    is_success = result_code == '1'
                elif 'ResultCode' in response_data:
                    result_code = response_data.get('ResultCode', '-1')
                    error_message = response_data.get('Error', '')
                    is_success = result_code == '1'
                else:
                    # Some successful responses might not have explicit status
                    is_success = response.status_code == 200
                    result_code = '1' if is_success else '0'

            # If token timed out per AirIQ message, force refresh and retry once
            token_timeout = False
            if not is_success and isinstance(response_data, dict):
                err_msg = ''
                if 'Status' in response_data:
                    err_msg = (response_data.get('Status') or {}).get('Error', '') or ''
                elif 'Error' in response_data:
                    err_msg = response_data.get('Error', '') or ''
                if isinstance(err_msg, str):
                    lowered = err_msg.lower()
                    if 'token' in lowered and ('time' in lowered or 'expire' in lowered or 'timeout' in lowered or 'timed out' in lowered):
                        token_timeout = True
            if token_timeout and 'Login' not in endpoint:
                logger.warning("Detected AirIQ token timeout - refreshing token and retrying once")
                # Invalidate cached token
                try:
                    AirIQTokenCache.objects.filter(is_active=True).update(is_active=False)
                except Exception:
                    pass
                self._auth_token = None
                self._token_expires_at = None
                # Re-authenticate
                self.authenticate()
                # Update header and retry
                headers['TOKEN'] = self._auth_token
                response = _do_request()
                response_time_ms = int((time.time() - start_time) * 1000)
                try:
                    response_data = response.json()
                except ValueError:
                    response_data = {'error': 'Invalid JSON response', 'raw': response.text}
                # Re-evaluate success
                is_success = False
                result_code = '-1'
                error_message = ''
                if isinstance(response_data, dict):
                    if 'Status' in response_data:
                        result_code = response_data['Status'].get('ResultCode', '-1')
                        error_message = response_data['Status'].get('Error', '')
                        is_success = result_code == '1'
                    elif 'ResultCode' in response_data:
                        result_code = response_data.get('ResultCode', '-1')
                        error_message = response_data.get('Error', '')
                        is_success = result_code == '1'
                    else:
                        is_success = response.status_code == 200
                        result_code = '1' if is_success else '0'

            # Log the API call
            self._log_api_call(
                endpoint=endpoint.split('/')[-1],
                method=method,
                request_data=data,
                response_data=response_data,
                result_code=result_code,
                error_message=error_message,
                response_time_ms=response_time_ms,
                booking=booking
            )
            
            return response_data, is_success
            
        except requests.RequestException as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_response = {'error': str(e), 'type': 'request_error'}
            
            self._log_api_call(
                endpoint=endpoint.split('/')[-1],
                method=method,
                request_data=data,
                response_data=error_response,
                result_code='-1',
                error_message=str(e),
                response_time_ms=response_time_ms,
                booking=booking
            )
            
            return error_response, False

    def _is_token_valid(self) -> bool:
        """Check if current authentication token is valid"""
        if not self._auth_token or not self._token_expires_at:
            return False
        return timezone.now() < self._token_expires_at
    
    def _should_refresh_token(self) -> bool:
        """Check if token should be refreshed (daily refresh logic)"""
        # Check if we have a valid cached token from database
        cached_token_record = AirIQTokenCache.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        
        if not cached_token_record:
            logger.info("No valid cached token found - refresh needed")
            return True
        
        # Check if token was created yesterday or earlier
        now = timezone.now()
        token_created_date = cached_token_record.created_at.date()
        current_date = now.date()
        
        if token_created_date < current_date:
            logger.info(f"Token created on {token_created_date}, current date is {current_date} - daily refresh needed")
            return True
        
        # Check if token expires within the next 2 hours (proactive refresh)
        if cached_token_record.expires_at <= now + timedelta(hours=2):
            logger.info(f"Token expires at {cached_token_record.expires_at}, within 2 hours - proactive refresh")
            return True
        
        return False
    
    def _perform_login(self) -> Tuple[dict, bool]:
        """
        Perform login with AirIQ using HTTP Basic Authentication
        Returns (response_data, is_success)
        """
        start_time = time.time()
        
        # Create HTTP Basic Authentication header
        auth_header = self._create_basic_auth_header()
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': auth_header  # HTTP Basic Authentication
        }
        
        # Login payload (can be empty or minimal as per AirIQ docs)
        login_payload = {
            "AgentID": self.agent_id,
            "Username": self.username,
            "Password": self.password
        }
        
        try:
            logger.info(f"Attempting AirIQ login with Basic Auth for agent: {self.agent_id}")
            
            # Build request kwargs and include proxies only if configured
            request_kwargs = dict(
                url=self.endpoints['login'],
                headers=headers,
                json=login_payload,
                timeout=30,
            )
            if proxies:
                request_kwargs['proxies'] = proxies
            
            response = requests.post(**request_kwargs)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Parse JSON response
            try:
                response_data = response.json()
            except ValueError:
                response_data = {'error': 'Invalid JSON response', 'raw': response.text}
                logger.error(f"Login failed - Invalid JSON response: {response.text}")
                
            # Determine success based on AirIQ's result codes
            is_success = False
            result_code = '-1'
            error_message = ''
            
            if isinstance(response_data, dict):
                # Check for status in response
                if 'Status' in response_data:
                    result_code = response_data['Status'].get('ResultCode', '-1')
                    error_message = response_data['Status'].get('Error', '')
                    is_success = result_code == '1'
                elif 'ResultCode' in response_data:
                    result_code = response_data.get('ResultCode', '-1')
                    error_message = response_data.get('Error', '')
                    is_success = result_code == '1'
                elif response.status_code == 200 and 'Token' in response_data:
                    # Some successful responses might not have explicit status but contain Token
                    is_success = True
                    result_code = '1'
                    logger.info("Login successful - Token received")
                else:
                    logger.error(f"Login failed - No token in response: {response_data}")
            
            # Log the login attempt
            self._log_api_call(
                endpoint='Login',
                method='POST',
                request_data={
                    'AgentID': self.agent_id,
                    'Username': self.username,
                    'Password': '***HIDDEN***'  # Don't log password
                },
                response_data=response_data,
                result_code=result_code,
                error_message=error_message,
                response_time_ms=response_time_ms
            )
            
            if is_success:
                logger.info(f"AirIQ login successful (response time: {response_time_ms}ms)")
            else:
                logger.error(f"AirIQ login failed - Code: {result_code}, Error: {error_message}")
            
            return response_data, is_success
            
        except requests.RequestException as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_response = {'error': str(e), 'type': 'request_error'}
            
            logger.error(f"AirIQ login request failed: {str(e)}")
            
            # Log the failed request
            self._log_api_call(
                endpoint='Login',
                method='POST',
                request_data={
                    'AgentID': self.agent_id,
                    'Username': self.username,
                    'Password': '***HIDDEN***'
                },
                response_data=error_response,
                result_code='-1',
                error_message=str(e),
                response_time_ms=response_time_ms
            )
            
            return error_response, False

    def authenticate(self) -> bool:
        """
        Authenticate with AirIQ API and get access token
        Uses database caching with daily refresh to avoid hitting daily API limit
        Returns True if successful, False otherwise
        """
        # Check if we should refresh the token (daily refresh or expiry)
        if not self._should_refresh_token():
            # Use existing valid token
            cached_token = AirIQTokenCache.get_valid_token()
            if cached_token:
                self._auth_token = cached_token
                # Get actual expiry from database
                cached_token_record = AirIQTokenCache.objects.filter(
                    is_active=True,
                    expires_at__gt=timezone.now()
                ).first()
                if cached_token_record:
                    self._token_expires_at = cached_token_record.expires_at
                    logger.info(f"Using cached AirIQ token (expires: {self._token_expires_at})")
                    return True
        
        logger.info("Refreshing AirIQ authentication token (daily refresh or expiry)")
        
        # Authenticate with API using dedicated login method
        response_data, is_success = self._perform_login()
        
        if is_success and 'Token' in response_data:
            self._auth_token = response_data['Token']
            # Set token expiry to end of current day (AirIQ tokens expire daily)
            today_end = timezone.now().replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            self._token_expires_at = today_end
            
            # Cache the token in database with daily expiry
            token_cache = AirIQTokenCache.cache_token(self._auth_token, expires_at=today_end)
            
            logger.info(f"AirIQ authentication successful - new token cached (expires: {today_end})")
            logger.info(f"Token created on: {token_cache.created_at.date()}")
            return True
        else:
            error_msg = response_data.get('Status', {}).get('Error', 'Unknown authentication error')
            logger.error(f"AirIQ authentication failed: {error_msg}")
            raise AirIQException(f"Authentication failed: {error_msg}")
    
    def refresh_token_if_needed(self) -> bool:
        """
        Refresh token if needed (daily refresh or near expiry)
        This method can be called by scheduled tasks
        """
        try:
            if self._should_refresh_token():
                logger.info("Refreshing AirIQ token via scheduled refresh")
                return self.authenticate()
            else:
                logger.info("AirIQ token refresh not needed")
                return True
        except Exception as e:
            logger.error(f"Failed to refresh AirIQ token: {str(e)}")
            return False
    
    @classmethod
    def cleanup_expired_tokens(cls):
        """
        Clean up expired tokens from database
        """
        from django.utils import timezone
        
        expired_count = AirIQTokenCache.objects.filter(
            expires_at__lte=timezone.now()
        ).update(is_active=False)
        
        if expired_count > 0:
            logger.info(f"Deactivated {expired_count} expired AirIQ tokens")
        
        return expired_count
    
    @classmethod
    def get_token_status(cls) -> dict:
        """
        Get current token status for monitoring
        """
        from django.utils import timezone
        
        active_token = AirIQTokenCache.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        
        if active_token:
            now = timezone.now()
            hours_until_expiry = (active_token.expires_at - now).total_seconds() / 3600
            
            return {
                'has_valid_token': True,
                'created_date': active_token.created_at.date(),
                'expires_at': active_token.expires_at,
                'hours_until_expiry': round(hours_until_expiry, 2),
                'needs_refresh': active_token.created_at.date() < now.date() or hours_until_expiry < 2
            }
        else:
            return {
                'has_valid_token': False,
                'needs_refresh': True
            }

    def search_flights(self, search_params: dict) -> Tuple[dict, str]:
        """
        Search for available flights
        Args:
            search_params: {
                'origin': 'DEL',
                'destination': 'BOM', 
                'departure_date': '20231120',
                'return_date': '20231125',  # Optional for round trip
                'trip_type': 'O',  # O=One-way, R=Round-trip, Y=Round-trip Special
                'flight_class': 'E',  # E=Economy, P=Premium, B=Business, F=First
                'adults': 1,
                'children': 0,
                'infants': 0,
                'airline_id': '',  # Optional
                'fare_type': 'N',  # N=Normal, C=Corporate, R=Retail
                'direct_only': False
            }
        Returns:
            (response_data, track_id)
        """
        if not self._is_token_valid():
            self.authenticate()
        
        # Build request payload
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "TripType": search_params.get('trip_type', 'O'),
            "AirlineID": search_params.get('airline_id', ''),
            "AvailInfo": [
                {
                    "DepartureStation": search_params['origin'],
                    "ArrivalStation": search_params['destination'],
                    "FlightDate": search_params['departure_date'],
                    "FarecabinOption": search_params.get('flight_class', 'E'),
                    "FareType": search_params.get('fare_type', 'N'),
                    "OnlyDirectFlight": search_params.get('direct_only', False)
                }
            ],
            "PassengersInfo": {
                "AdultCount": str(search_params.get('adults', 1)),
                "ChildCount": str(search_params.get('children', 0)),
                "InfantCount": str(search_params.get('infants', 0))
            }
        }
        
        # Add return flight for round trip
        if search_params.get('trip_type') in ['R', 'Y'] and search_params.get('return_date'):
            payload["AvailInfo"].append({
                "DepartureStation": search_params['destination'],
                "ArrivalStation": search_params['origin'],
                "FlightDate": search_params['return_date'],
                "FarecabinOption": search_params.get('flight_class', 'E'),
                "FareType": search_params.get('fare_type', 'N'),
                "OnlyDirectFlight": search_params.get('direct_only', False)
            })
        
        response_data, is_success = self._make_request(
            self.endpoints['availability'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Flight search failed')
            raise AirIQException(f"Flight search failed: {error_msg}")
        
        track_id = response_data.get('Trackid', '')
        return response_data, track_id

    def get_fare_rules(self, flight_ids: List[str], track_id: str) -> dict:
        """
        Get fare rules for specific flights
        Args:
            flight_ids: List of flight IDs from search results
            track_id: Track ID from search response
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "FlightsInfo": [{"FlightID": flight_id} for flight_id in flight_ids],
            "Trackid": track_id
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['fare_rules'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Fare rules request failed')
            raise AirIQException(f"Fare rules request failed: {error_msg}")
        
        return response_data

    def price_flight(self, track_id: str, segment_info: dict, itinerary_info: dict) -> dict:
        """
        Get detailed pricing for selected flight
        Args:
            flight_details: Flight details from search results
            track_id: Track ID from search response
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "SegmentInfo": segment_info,
            "Trackid": track_id,
            "ItineraryInfo": itinerary_info
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['pricing'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('ResponseStatus', {}).get('Error', 'Pricing request failed')
            raise AirIQException(f"Pricing request failed: {error_msg}")
        
        return response_data

    def get_seat_map(self, flight_segments: List[dict], passengers: List[dict], track_id: str) -> dict:
        """
        Get seat map for flights
        Args:
            flight_segments: List of flight segments
            passengers: List of passenger details
            track_id: Track ID from pricing response
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "SegmentInfo": {
                "BaseOrigin": flight_segments[0]['Origin'],
                "BaseDestination": flight_segments[-1]['Destination'],
                "TripType": "O"  # Simplified for now
            },
            "FlightsInfo": [
                {
                    "FlightID": segment['FlightID'],
                    "FlightNumber": segment['FlightNumber'],
                    "Origin": segment['Origin'],
                    "Destination": segment['Destination'],
                    "DepartureDateTime": segment['DepartureDateTime'],
                    "ArrivalDateTime": segment['ArrivalDateTime']
                }
                for segment in flight_segments
            ],
            "APIPaxDetails": [
                {
                    "PaxRefNumber": str(pax['reference']),
                    "Title": pax['title'],
                    "PaxType": pax['type'],
                    "FirstName": pax['first_name'],
                    "LastName": pax['last_name']
                }
                for pax in passengers
            ],
            "TrackId": track_id
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['seat_map'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('ResponseStatus', {}).get('Error', 'Seat map request failed')
            raise AirIQException(f"Seat map request failed: {error_msg}")
        
        return response_data

    def create_booking(self, booking_data: dict, track_id: str, block_pnr: bool = False) -> dict:
        """
        Create flight booking with comprehensive validation and AirIQ API compliance
        Args:
            booking_data: Complete booking information
            track_id: Track ID from pricing response
            block_pnr: Whether to hold booking (True) or ticket immediately (False)
        """
        if not self._is_token_valid():
            self.authenticate()
        
        # Validate passenger details
        passenger_errors = self.validate_passenger_details(booking_data['passengers'])
        if passenger_errors:
            raise AirIQException(f"Passenger validation failed: {', '.join(passenger_errors)}")
        
        # Validate GST info if provided
        gst_info = booking_data.get('gst', {})
        if gst_info.get('number'):
            if not self.validate_gst_format(gst_info['number']):
                raise AirIQException("Invalid GST number format")
            
            # Check for complete GST info (all or none as per docs)
            required_gst_fields = ['number', 'company_name', 'address', 'email', 'mobile']
            if not all(gst_info.get(field) for field in required_gst_fields):
                raise AirIQException("GST information must be complete (all fields) or not provided at all")
        
        # Format passenger details for AirIQ
        formatted_passengers = [
            self.format_passenger_for_airiq(pax, i)
            for i, pax in enumerate(booking_data['passengers'], 1)
        ]
        
        # Build comprehensive booking payload (supports multiple itinerary items)
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "AdultCount": booking_data.get('adults', 1),
            "ChildCount": booking_data.get('children', 0),
            "InfantCount": booking_data.get('infants', 0),
            "ItineraryFlightsInfo": [],
            "PaxDetailsInfo": formatted_passengers,
            "AddressDetails": {
                "CountryCode": booking_data['contact']['country_code'],
                "ContactNumber": booking_data['contact']['phone'],
                "EmailID": booking_data['contact']['email']
            },
            "GSTInfo": {
                "GSTNumber": gst_info.get('number', ''),
                "GSTCompanyName": gst_info.get('company_name', ''),
                "GSTAddress": gst_info.get('address', ''),
                "GSTEmailID": gst_info.get('email', ''),
                "GSTMobileNumber": gst_info.get('mobile', '')
            },
            "FFNumberInfo": self._format_frequent_flyer(booking_data.get('frequent_flyer', [])),
            "TripType": booking_data.get('trip_type', 'O'),
            "BlockPNR": block_pnr,
            "BaseOrigin": booking_data['origin'],
            "BaseDestination": booking_data['destination'],
            "TrackId": track_id
        }
        # Fill itineraries: prefer booking_data['itineraries'] when present; else fallback to single item keys
        itins = booking_data.get('itineraries') or []
        if itins:
            for it in itins:
                payload['ItineraryFlightsInfo'].append({
                    "Token": it.get('token', ''),
                    "FlightsInfo": it.get('flight_segments', []),
                    "PaymentMode": "T",
                    "SeatsSSRInfo": self._format_seats_ssr(it.get('seats', [])),
                    "BaggSSRInfo": self._format_baggage_ssr(it.get('baggage', [])),
                    "MealsSSRInfo": self._format_meals_ssr(it.get('meals', [])),
                    "OtherSSRInfo": it.get('other_services', []),
                    "PaymentInfo": [
                        {"TotalAmount": str(it.get('payment_total') or booking_data.get('total_amount') or 0)}
                    ]
                })
        else:
            payload['ItineraryFlightsInfo'] = [
                {
                    "Token": booking_data.get('token', ''),
                    "FlightsInfo": booking_data.get('flight_segments', []),
                    "PaymentMode": "T",
                    "SeatsSSRInfo": self._format_seats_ssr(booking_data.get('seats', [])),
                    "BaggSSRInfo": self._format_baggage_ssr(booking_data.get('baggage', [])),
                    "MealsSSRInfo": self._format_meals_ssr(booking_data.get('meals', [])),
                    "OtherSSRInfo": booking_data.get('other_services', []),
                    "PaymentInfo": [
                        {"TotalAmount": str(booking_data.get('total_amount') or 0)}
                    ]
                }
            ]
        
        response_data, is_success = self._make_request(
            self.endpoints['booking'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Booking creation failed')
            raise AirIQException(f"Booking creation failed: {error_msg}")
        
        return response_data
    
    def _format_seats_ssr(self, seats: List[dict]) -> List[dict]:
        """
        Format seat selections for AirIQ API
        """
        return [
            {
                "PaxRefNumber": str(seat['passenger_ref']),
                "SeatID": seat['seat_id']
            }
            for seat in seats if seat.get('seat_id')
        ]
    
    def _format_baggage_ssr(self, baggage: List[dict]) -> List[dict]:
        """
        Format baggage selections for AirIQ API
        """
        return [
            {
                "BaggageID": str(bag['baggage_id']),
                "PaxRefNumber": str(bag['passenger_ref'])
            }
            for bag in baggage if bag.get('baggage_id')
        ]
    
    def _format_meals_ssr(self, meals: List[dict]) -> List[dict]:
        """
        Format meal selections for AirIQ API
        """
        return [
            {
                "MealID": str(meal['meal_id']),
                "PaxRefNumber": str(meal['passenger_ref'])
            }
            for meal in meals if meal.get('meal_id')
        ]
    
    def _format_frequent_flyer(self, ff_info: List[dict]) -> List[dict]:
        """
        Format frequent flyer information for AirIQ API
        """
        return [
            {
                "SegRefNumber": str(ff.get('segment_ref', '1')),
                "PaxRefNumber": str(ff['passenger_ref']),
                "AirlineCode": ff['airline_code'],
                "FlyerNumber": ff['flyer_number'],
                "Itinref": str(ff.get('itin_ref', '0'))
            }
            for ff in ff_info if ff.get('flyer_number')
        ]

    def issue_ticket(self, booking_track_id: str, airiq_pnr: str, 
                    airline_pnr: str, booking_amount: float) -> dict:
        """
        Issue ticket for held booking
        Args:
            booking_track_id: Booking track ID from booking response
            airiq_pnr: AirIQ PNR from booking response
            airline_pnr: Airline PNR from booking response
            booking_amount: Total booking amount
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "BookingTrackId": booking_track_id,
            "AirIqPNR": airiq_pnr,
            "AirlinePNR": airline_pnr,
            "BookingAmount": str(booking_amount),
            "PaymentMode": "T"
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['ticketing'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Ticket issuance failed')
            raise AirIQException(f"Ticket issuance failed: {error_msg}")
        
        return response_data

    def get_booking_details(self, airiq_pnr: str) -> dict:
        """
        Retrieve booking details
        Args:
            airiq_pnr: AirIQ PNR
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "Item": [
                {
                    "AirIqPNR": airiq_pnr
                }
            ]
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['get_booking'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Booking retrieval failed')
            raise AirIQException(f"Booking retrieval failed: {error_msg}")
        
        return response_data

    def cancel_booking(self, airiq_pnr: str, flag: str = 'CANCEL', remarks: str = '') -> dict:
        """
        Cancel or check penalty for booking
        Args:
            airiq_pnr: AirIQ PNR
            flag: 'PENALTY' to check penalty, 'CANCEL' to cancel
            remarks: Cancellation remarks
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "OnlineInfo": {
                "Flag": flag,
                "AirIqPNR": airiq_pnr,
                "Remarks": remarks
            }
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['cancel'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Cancellation request failed')
            raise AirIQException(f"Cancellation request failed: {error_msg}")
        
        return response_data

    def get_account_balance(self) -> dict:
        """Get agent account balance"""
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            }
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['balance'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Balance request failed')
            raise AirIQException(f"Balance request failed: {error_msg}")
        
        return response_data
    
    def get_agent_balance(self) -> dict:
        """Get agent balance with success/failure wrapper for enhanced flight booking"""
        try:
            response_data = self.get_account_balance()
            
            # Check if response indicates success
            status = response_data.get('Status', {})
            result_code = status.get('ResultCode', '')
            error = status.get('Error', '')
            
            # Check for success (ResultCode "1" indicates success)
            if result_code != "1" or error:
                logger.error(f"AirIQ balance check failed - ResultCode: {result_code}, Error: {error}")
                return {
                    'success': False,
                    'message': error or f"Balance check failed with ResultCode: {result_code}",
                    'balance': 0,
                    'raw_response': response_data
                }
            
            # Extract balance from AirIQ response - use TopupBalance as primary balance
            balance = 0
            if 'TopupBalance' in response_data:
                balance = float(response_data['TopupBalance'])
            elif 'CreditBalance' in response_data:
                balance = float(response_data['CreditBalance'])
            elif 'AgentDetails' in response_data:
                balance = float(response_data['AgentDetails'].get('AgentBalance', 0))
            elif 'Balance' in response_data:
                balance = float(response_data['Balance'])
            elif 'AccountBalance' in response_data:
                balance = float(response_data['AccountBalance'])
            
            return {
                'success': True,
                'balance': balance,
                'topup_balance': float(response_data.get('TopupBalance', 0)),
                'credit_balance': float(response_data.get('CreditBalance', 0)),
                'raw_response': response_data
            }
            
        except AirIQException as e:
            logger.error(f"Agent balance check failed: {str(e)}")
            return {
                'success': False,
                'message': str(e),
                'balance': 0
            }
        except Exception as e:
            logger.error(f"Unexpected error in agent balance check: {str(e)}")
            return {
                'success': False,
                'message': 'Unable to retrieve balance',
                'balance': 0
            }
    
    def get_pricing(self, pricing_data: dict) -> dict:
        """Get current pricing for flight booking validation"""
        if not self._is_token_valid():
            self.authenticate()
        
        # Build pricing request from provided data
        track_id = pricing_data.get('TrackId')
        itinerary_flights = pricing_data.get('ItineraryFlightsInfo', [])
        
        if not track_id or not itinerary_flights:
            raise AirIQException("TrackId and ItineraryFlightsInfo are required for pricing")
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "TrackId": track_id,
            "ItineraryFlightsInfo": itinerary_flights
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['pricing'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Pricing validation failed')
            raise AirIQException(f"Pricing validation failed: {error_msg}")
        
        return response_data

    def track_booking_status(self, booking_track_id: str) -> dict:
        """
        Track booking status
        Args:
            booking_track_id: Booking track ID from booking response
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "Item": [
                {
                    "BookingTrackId": booking_track_id
                }
            ]
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['track_status'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Status tracking failed')
            raise AirIQException(f"Status tracking failed: {error_msg}")
        
        return response_data

    def reschedule_availability(self, trip_type: str, departure_station: str, 
                               arrival_station: str, flight_date: str, 
                               airiq_pnr: str, remarks: str = '') -> dict:
        """
        Get reschedule availability for existing booking
        Args:
            trip_type: Trip type (O/R/Y)
            departure_station: 3-letter IATA departure code
            arrival_station: 3-letter IATA arrival code
            flight_date: Flight date in YYYYMMDD format
            airiq_pnr: AirIQ PNR
            remarks: Request remarks
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "TripType": trip_type,
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "AvailInfo": [
                {
                    "DepartureStation": departure_station,
                    "ArrivalStation": arrival_station,
                    "FlightDate": flight_date
                }
            ],
            "AirIqPNR": airiq_pnr,
            "Remarks": remarks
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['reschedule_avail'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Reschedule availability request failed')
            raise AirIQException(f"Reschedule availability failed: {error_msg}")
        
        return response_data

    def reschedule_booking(self, airiq_pnr: str, track_id: str, 
                          flight_details: dict, contact_no: str, 
                          remarks: str = '', flag: str = 'CONFIRM') -> dict:
        """
        Reschedule existing booking
        Args:
            airiq_pnr: AirIQ PNR
            track_id: Track ID from reschedule availability
            flight_details: New flight details
            contact_no: Contact number
            remarks: Request remarks
            flag: CHECKFARE or CONFIRM
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "SegmentInfo": {
                "BaseOrigin": flight_details['origin'],
                "BaseDestination": flight_details['destination'],
                "TripType": flight_details.get('trip_type', 'O')
            },
            "Trackid": track_id,
            "AirIqPNR": airiq_pnr,
            "Remarks": remarks,
            "Flag": flag,
            "ContactNo": contact_no,
            "ItineraryInfo": [
                {
                    "FlightDetails": flight_details['segments'],
                    "BaseAmount": str(flight_details['base_amount']),
                    "GrossAmount": str(flight_details['gross_amount'])
                }
            ]
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['reschedule'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Reschedule request failed')
            raise AirIQException(f"Reschedule failed: {error_msg}")
        
        return response_data

    def get_ssr_services(self, airiq_pnr: str, airline_pnr: str) -> dict:
        """
        Get available SSR services for existing booking
        Args:
            airiq_pnr: AirIQ PNR
            airline_pnr: Airline PNR
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "AirIqPNR": airiq_pnr,
            "AirlinePNR": airline_pnr
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['get_ssr'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'SSR services request failed')
            raise AirIQException(f"SSR services request failed: {error_msg}")
        
        return response_data

    def add_ssr_services(self, airiq_pnr: str, airline_pnr: str, track_id: str,
                        meals_ssr: List[dict] = None, baggage_ssr: List[dict] = None,
                        seats_ssr: List[dict] = None, other_ssr: List[dict] = None,
                        payment_amount: float = 0, remarks: str = '') -> dict:
        """
        Add SSR services to existing booking
        Args:
            airiq_pnr: AirIQ PNR
            airline_pnr: Airline PNR
            track_id: Track ID from GetSSR response
            meals_ssr: List of meal selections
            baggage_ssr: List of baggage selections
            seats_ssr: List of seat selections
            other_ssr: List of other services
            payment_amount: Total payment amount
            remarks: Request remarks
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "Remarks": remarks,
            "TracKID": track_id,
            "AirIqPNR": airiq_pnr,
            "AirlinePNR": airline_pnr,
            "MealsSSR": meals_ssr or [],
            "BaggSSR": baggage_ssr or [],
            "SeatsSSR": seats_ssr or [],
            "OtherSSR": other_ssr or [],
            "Payment": [
                {
                    "PaymentMode": "T",
                    "Amount": str(payment_amount)
                }
            ]
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['add_ssr'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Add SSR request failed')
            raise AirIQException(f"Add SSR failed: {error_msg}")
        
        return response_data

    def hold_cancel(self, airiq_pnr: str, airline_pnr: str) -> dict:
        """
        Cancel held booking
        Args:
            airiq_pnr: AirIQ PNR
            airline_pnr: Airline PNR
        """
        if not self._is_token_valid():
            self.authenticate()
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "AirIqPNR": airiq_pnr,
            "AirlinePNR": airline_pnr
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['hold_cancel'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Hold cancel request failed')
            raise AirIQException(f"Hold cancel failed: {error_msg}")
        
        return response_data

    def get_multi_class(self, flight_ids: List[str], adults: int = 1, 
                       children: int = 0, infants: int = 0, 
                       trip_type: str = 'O', track_id: str = '') -> dict:
        """
        Get available classes for flights
        Args:
            flight_ids: List of flight IDs from availability response
            adults: Number of adults
            children: Number of children
            infants: Number of infants
            trip_type: Trip type (O/R/Y)
            track_id: Track ID from availability/pricing response
        """
        if not self._is_token_valid():
            self.authenticate()
        
        if not track_id:
            raise AirIQException("Track ID is required for multi-class request")
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "FlightsInfo": [{"FlightID": flight_id} for flight_id in flight_ids],
            "PassengersInfo": {
                "AdultCount": int(adults),
                "ChildCount": int(children),
                "InfantCount": int(infants)
            },
            "TripType": trip_type,
            "Trackid": track_id
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['multi_class'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Multi class request failed')
            raise AirIQException(f"Multi class failed: {error_msg}")
        
        return response_data

    def get_multi_class_fare(self, flight_ids: List[str], class_fare: List[dict],
                            adults: int = 1, children: int = 0, infants: int = 0,
                            trip_type: str = 'O', track_id: str = '') -> dict:
        """
        Get fare for specific class
        Args:
            flight_ids: List of flight IDs from availability response (one per segment/leg)
            class_fare: List of class fare details, one per FlightID
            adults: Number of adults
            children: Number of children
            infants: Number of infants
            trip_type: Trip type
            track_id: Track ID from availability/pricing response
        """
        if not self._is_token_valid():
            self.authenticate()
        
        if not track_id:
            raise AirIQException("Track ID is required for multi-class fare request")
        if not flight_ids:
            raise AirIQException("At least one FlightID is required for multi-class fare request")
        if not class_fare:
            raise AirIQException("ClassFare is required (one item per FlightID)")
        if len(class_fare) != len(flight_ids):
            logger.warning("ClassFare count does not match FlightIDs count; proceeding but API may fail")
        
        # Normalize ClassFare items to expected schema and types
        normalized_class_fare = []
        for item in class_fare:
            airline_class = item.get('AirlineClass') or item.get('Class') or item.get('class')
            seats_flag = item.get('SeatAvailFlag') or item.get('Seats') or item.get('seats')
            if airline_class is None:
                raise AirIQException("Each ClassFare item must include AirlineClass")
            if seats_flag is None:
                seats_flag = '9'
            normalized_class_fare.append({
                "AirlineClass": str(airline_class),
                "SeatAvailFlag": str(seats_flag)
            })
        
        payload = {
            "AgentInfo": {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version)
            },
            "FlightsInfo": [{"FlightID": flight_id} for flight_id in flight_ids],
            "ClassFare": normalized_class_fare,
            "PassengersInfo": {
                "AdultCount": int(adults),
                "ChildCount": int(children),
                "InfantCount": int(infants)
            },
            "TripType": trip_type,
            "Trackid": track_id
        }
        
        response_data, is_success = self._make_request(
            self.endpoints['multi_class_fare'],
            payload
        )
        
        if not is_success:
            error_msg = response_data.get('Status', {}).get('Error', 'Multi class fare request failed')
            raise AirIQException(f"Multi class fare failed: {error_msg}")
        
        return response_data

    # ---------- Generic proxy helpers ----------
    def get_supported_endpoints(self) -> dict:
        """Return a mapping of display endpoint names to internal endpoint keys."""
        return {
            "Login": "login",
            "Availability": "availability",
            "GetFareRule": "fare_rules",
            "Pricing": "pricing",
            "GetAvailSeatMap": "seat_map",
            "Book": "booking",
            "IssueTicket": "ticketing",
            "RetrieveBooking": "get_booking",
            "GetBalance": "balance",
            "TrackStatus": "track_status",
            "Cancel": "cancel",
            "RescheduleAvail": "reschedule_avail",
            "Reschedule": "reschedule",
            "GetSSR": "get_ssr",
            "AddSSR": "add_ssr",
            "HoldCancel": "hold_cancel",
            "GetMultiClass": "multi_class",
            "GetMultiClassFare": "multi_class_fare",
        }

    def proxy_call(self, endpoint_name: str, payload: dict) -> Tuple[dict, bool]:
        """
        Generic proxy caller that:
        - ensures authentication and token header
        - injects AgentInfo if missing
        - routes to the correct AirIQ endpoint by name (case-insensitive)
        Returns (response_data, is_success)
        """
        if not isinstance(payload, dict):
            raise AirIQException("Payload must be a JSON object")

        # Normalize endpoint name (allow common misspellings/case)
        name = (endpoint_name or "").strip()
        # Fix common typo
        if name.lower() == "availabilty":
            name = "Availability"
        # Resolve display name -> key
        display_map = self.get_supported_endpoints()
        key = display_map.get(name) or display_map.get(name.title())
        if not key:
            # Try matching by internal key directly
            if name in self.endpoints:
                endpoint_url = self.endpoints[name]
            else:
                # Try lower/upper variations
                lowered = name.lower()
                reverse_map = {v: k for k, v in display_map.items()}
                if lowered in self.endpoints:
                    endpoint_url = self.endpoints[lowered]
                else:
                    raise AirIQException(f"Unsupported endpoint: {endpoint_name}")
        else:
            endpoint_url = self.endpoints[key]

        # Ensure token for non-login calls
        if 'Login' not in endpoint_url:
            if not self._is_token_valid():
                self.authenticate()

        # Inject AgentInfo if not present
        if 'AgentInfo' not in payload:
            payload['AgentInfo'] = {
                "AgentId": self.agent_id,
                "UserName": self.username,
                "AppType": "API",
                "Version": float(self.api_version),
            }

        return self._make_request(endpoint_url, payload)

    def validate_gst_format(self, gst_number: str) -> bool:
        """
        Validate GST number format according to AirIQ documentation
        GST Registration Number is 15 alpha-numeric characters with specific pattern
        Format: 2 digits + 5 letters + 4 digits + 1 letter + 3 alphanumeric
        Example: 27AAEHR8003E1ZC
        """
        import re
        if not gst_number or len(gst_number) != 15:
            return False
        
        # Pattern: 2 digits + 5 letters + 4 digits + 1 letter + 3 alphanumeric
        pattern = r'^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]{3}$'
        return bool(re.match(pattern, gst_number.upper()))

    def validate_passenger_details(self, passengers: List[dict]) -> List[str]:
        """
        Validate passenger details according to AirIQ requirements
        Returns list of validation errors
        """
        errors = []
        valid_titles = ['MR', 'MRS', 'MISS', 'MS', 'MSTR', 'DR']
        valid_pax_types = ['ADT', 'CHD', 'INF']
        
        for i, pax in enumerate(passengers, 1):
            prefix = f"Passenger {i}:"
            
            # Title validation
            if pax.get('title', '').upper() not in valid_titles:
                errors.append(f"{prefix} Invalid title. Must be one of {valid_titles}")
            
            # Passenger type validation
            if pax.get('pax_type', '').upper() not in valid_pax_types:
                errors.append(f"{prefix} Invalid passenger type. Must be ADT, CHD, or INF")
            
            # Name validation
            if not pax.get('first_name', '').strip():
                errors.append(f"{prefix} First name is required")
            if not pax.get('last_name', '').strip():
                errors.append(f"{prefix} Last name is required")
            
            # DOB validation
            if not pax.get('date_of_birth'):
                errors.append(f"{prefix} Date of birth is required")
            
            # Gender validation
            if pax.get('gender', '').lower() not in ['male', 'female']:
                errors.append(f"{prefix} Gender must be 'male' or 'female'")
        
        return errors

    def format_passenger_for_airiq(self, passenger: dict, reference: int) -> dict:
        """
        Format passenger data for AirIQ API requirements
        """
        return {
            "PaxRefNumber": str(reference),
            "Title": passenger['title'].upper(),
            "FirstName": passenger['first_name'].upper(),
            "LastName": passenger['last_name'].upper(),
            "DOB": passenger['date_of_birth'],  # Should be in DD/MM/YYYY format
            "Gender": passenger['gender'].title(),
            "PaxType": passenger['pax_type'].upper(),
            "PassportNo": passenger.get('passport_number', ''),
            "PassportExpiry": passenger.get('passport_expiry', ''),
            "PassportIssuedDate": passenger.get('passport_issued_date', ''),
            "PassportCountryCode": passenger.get('passport_country_code', ''),
            "InfantRef": passenger.get('infant_ref', '')
        }


# Singleton instance for reuse
airiq_service = AirIQService()
