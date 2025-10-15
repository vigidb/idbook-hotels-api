"""
Comprehensive test suite for AirIQ integration validation
Tests all APIs according to AirIQ documentation requirements
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta

from apps.flights.services.airiq_service import AirIQService, AirIQException
from apps.flights.models import FlightBooking, AirIQTokenCache


class TestAirIQAuthentication(TestCase):
    """Test authentication and token management"""
    
    def setUp(self):
        self.service = AirIQService()
    
    def test_auth_header_creation(self):
        """Test Base64 authentication header creation according to docs"""
        # Test format: AgentID*Username:Password
        auth_header = self.service._create_auth_header()
        
        import base64
        expected = f"{self.service.agent_id}*{self.service.username}:{self.service.password}"
        expected_encoded = base64.b64encode(expected.encode('ascii')).decode('ascii')
        
        self.assertEqual(auth_header, expected_encoded)
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_authentication_success(self, mock_request):
        """Test successful authentication with correct response handling"""
        # Mock successful authentication response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "AgentID": "TEST_AGENT",
            "UserName": "test_user",
            "Token": "3HjkLnFINC1SU05LTDA0MDAxMDEwNytBSDQtOTcwK0FINC1kaGFuYWErQ=",
            "Status": {
                "ResultCode": "1",
                "Error": "",
                "SequenceID": "1221485289115"
            }
        }
        mock_request.return_value = mock_response
        
        # Test authentication
        result = self.service.authenticate()
        
        self.assertTrue(result)
        self.assertIsNotNone(self.service._auth_token)
        self.assertIsNotNone(self.service._token_expires_at)
        
        # Verify token is cached in database
        cached_token = AirIQTokenCache.get_valid_token()
        self.assertEqual(cached_token, self.service._auth_token)
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_authentication_failure(self, mock_request):
        """Test authentication failure handling"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "AgentID": "",
            "Status": {
                "Error": "Invalid Credentials",
                "ResultCode": "0",
                "SequenceID": "13070550229411"
            },
            "Token": "",
            "UserName": ""
        }
        mock_request.return_value = mock_response
        
        with self.assertRaises(AirIQException) as context:
            self.service.authenticate()
        
        self.assertIn("Authentication failed", str(context.exception))


class TestAirIQFlightSearch(TestCase):
    """Test flight search functionality"""
    
    def setUp(self):
        self.service = AirIQService()
        self.service._auth_token = "test_token"
        self.service._token_expires_at = timezone.now() + timedelta(hours=1)
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_search_flights_success(self, mock_request):
        """Test successful flight search according to docs"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ItineraryFlightList": [
                {
                    "Items": [
                        {
                            "FlightDetails": [
                                {
                                    "FlightID": "7368",
                                    "AirlineDescription": "6E",
                                    "FlightNumber": "6E 292",
                                    "Origin": "IXB",
                                    "Destination": "CCU",
                                    "DepartureDateTime": "14 Nov 2023 14:20",
                                    "ArrivalDateTime": "14 Nov 2023 15:25",
                                    "Class": "R",
                                    "JourneyTime": "140",
                                    "AvailSeat": "30"
                                }
                            ],
                            "Fares": [
                                {
                                    "Currency": "INR",
                                    "FareType": "N",
                                    "Faredescription": [
                                        {
                                            "Paxtype": "ADT",
                                            "BaseAmount": "15900.00",
                                            "TotalTaxAmount": "3973.00",
                                            "GrossAmount": "19873.00"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ],
            "Status": {
                "Error": "",
                "ResultCode": "1",
                "SequenceID": "11413958113534"
            },
            "Trackid": "AQ130816280740263181308249563236LAHRK1IJE3F"
        }
        mock_request.return_value = mock_response
        
        search_params = {
            'origin': 'DEL',
            'destination': 'BOM',
            'departure_date': '20231114',
            'trip_type': 'O',
            'flight_class': 'E',
            'adults': 1,
            'children': 0,
            'infants': 0,
            'fare_type': 'N',
            'direct_only': False
        }
        
        response_data, track_id = self.service.search_flights(search_params)
        
        self.assertEqual(track_id, "AQ130816280740263181308249563236LAHRK1IJE3F")
        self.assertIn('ItineraryFlightList', response_data)
        
        # Verify request payload structure matches docs
        call_args = mock_request.call_args
        payload = call_args[1]['json']
        
        self.assertIn('AgentInfo', payload)
        self.assertIn('TripType', payload)
        self.assertIn('AvailInfo', payload)
        self.assertIn('PassengersInfo', payload)
        
        # Check AgentInfo structure
        agent_info = payload['AgentInfo']
        self.assertEqual(agent_info['AppType'], 'API')
        self.assertEqual(agent_info['Version'], 2.0)
    
    def test_search_flights_validation(self):
        """Test search parameter validation"""
        # Test missing required fields
        with self.assertRaises(KeyError):
            self.service.search_flights({})
        
        # Test invalid trip type handling
        search_params = {
            'origin': 'DEL',
            'destination': 'BOM',
            'departure_date': '20231114',
            'trip_type': 'INVALID'
        }
        
        # Should not raise error as trip_type is validated by serializer


class TestAirIQBookingFlow(TestCase):
    """Test complete booking flow"""
    
    def setUp(self):
        self.service = AirIQService()
        self.service._auth_token = "test_token"
        self.service._token_expires_at = timezone.now() + timedelta(hours=1)
    
    def test_passenger_validation(self):
        """Test passenger validation according to docs"""
        # Valid passengers
        valid_passengers = [
            {
                'title': 'MR',
                'first_name': 'John',
                'last_name': 'Doe',
                'date_of_birth': '01/01/1990',
                'gender': 'male',
                'pax_type': 'ADT'
            }
        ]
        
        errors = self.service.validate_passenger_details(valid_passengers)
        self.assertEqual(len(errors), 0)
        
        # Invalid passengers
        invalid_passengers = [
            {
                'title': 'INVALID',  # Invalid title
                'first_name': '',     # Missing name
                'last_name': 'Doe',
                'gender': 'invalid',  # Invalid gender
                'pax_type': 'INVALID' # Invalid passenger type
            }
        ]
        
        errors = self.service.validate_passenger_details(invalid_passengers)
        self.assertGreater(len(errors), 0)
    
    def test_gst_validation(self):
        """Test GST validation according to docs format"""
        # Valid GST format: 2 digits + 5 letters + 4 digits + 3 alphanumeric
        valid_gst = "22AAAAA0000A1Z5"
        self.assertTrue(self.service.validate_gst_format(valid_gst))
        
        # Invalid formats
        invalid_gst_cases = [
            "",                    # Empty
            "22AAAAA0000A1",      # Too short
            "22AAAAA0000A1Z56",   # Too long
            "AAAAAAA0000A1Z5",    # Wrong pattern
            "22AAAAA000AA1Z5",    # Wrong pattern
        ]
        
        for invalid_gst in invalid_gst_cases:
            self.assertFalse(self.service.validate_gst_format(invalid_gst))
    
    def test_passenger_formatting(self):
        """Test passenger data formatting for AirIQ"""
        passenger = {
            'title': 'mr',
            'first_name': 'john',
            'last_name': 'doe',
            'date_of_birth': '01/01/1990',
            'gender': 'male',
            'pax_type': 'adt',
            'passport_number': 'A1234567',
            'passport_expiry': '01/01/2030',
            'passport_issued_date': '01/01/2020',
            'passport_country_code': 'IN'
        }
        
        formatted = self.service.format_passenger_for_airiq(passenger, 1)
        
        self.assertEqual(formatted['PaxRefNumber'], '1')
        self.assertEqual(formatted['Title'], 'MR')  # Should be uppercase
        self.assertEqual(formatted['FirstName'], 'JOHN')  # Should be uppercase
        self.assertEqual(formatted['LastName'], 'DOE')  # Should be uppercase
        self.assertEqual(formatted['Gender'], 'Male')  # Should be title case
        self.assertEqual(formatted['PaxType'], 'ADT')  # Should be uppercase


class TestAirIQAncillaryServices(TestCase):
    """Test SSR and ancillary services"""
    
    def setUp(self):
        self.service = AirIQService()
        self.service._auth_token = "test_token"
        self.service._token_expires_at = timezone.now() + timedelta(hours=1)
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_get_ssr_services(self, mock_request):
        """Test GetSSR API according to docs"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "TrackId": "AQ143613790123208541436182601064CGDVYIH6EK0",
            "SsrDetails": {
                "Baggages": [
                    {
                        "Amount": "4500",
                        "Code": "ExcessBaggage 10KG|EB10",
                        "Description": "ExcessBaggage 10KG",
                        "Id": "9735"
                    }
                ],
                "Meals": [
                    {
                        "Amount": "300",
                        "Code": "Vegetables in Red Thai Curry|VCC2",
                        "Description": "Vegetables in Red Thai Curry",
                        "Id": "6785"
                    }
                ],
                "Seats": [
                    {
                        "SeatAmount": "799",
                        "SeatName": "1A",
                        "Id": "6457"
                    }
                ]
            },
            "Status": {
                "Error": "",
                "ResultCode": "1",
                "SequenceID": "14361379012320854"
            }
        }
        mock_request.return_value = mock_response
        
        response = self.service.get_ssr_services("AF23HC0015", "BEK4PX")
        
        self.assertIn('SsrDetails', response)
        self.assertIn('Baggages', response['SsrDetails'])
        self.assertIn('Meals', response['SsrDetails'])
        self.assertIn('Seats', response['SsrDetails'])
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_add_ssr_services(self, mock_request):
        """Test AddSSR API according to docs"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Status": {
                "Error": "",
                "ResultCode": "1",
                "SequenceID": "14371202877260315"
            }
        }
        mock_request.return_value = mock_response
        
        meals_ssr = [{"PaxRefId": "1", "SegmentNo": "1", "MealId": "6785"}]
        baggage_ssr = [{"PaxRefId": "1", "BaggId": "9735"}]
        seats_ssr = [{"PaxRefId": "1", "SeatId": "6600"}]
        other_ssr = [{"OtherSSRId": "2142", "PaxRefId": "1"}]
        
        response = self.service.add_ssr_services(
            airiq_pnr="AF23HC0015",
            airline_pnr="BEK4PX",
            track_id="AQ143613790123208541436182601064CGDVYIH6EK0",
            meals_ssr=meals_ssr,
            baggage_ssr=baggage_ssr,
            seats_ssr=seats_ssr,
            other_ssr=other_ssr,
            payment_amount=5109,
            remarks="Test SSR addition"
        )
        
        # Verify request structure
        call_args = mock_request.call_args
        payload = call_args[1]['json']
        
        self.assertEqual(payload['AirIqPNR'], "AF23HC0015")
        self.assertEqual(payload['AirlinePNR'], "BEK4PX")
        self.assertEqual(payload['MealsSSR'], meals_ssr)
        self.assertEqual(payload['BaggSSR'], baggage_ssr)
        self.assertEqual(payload['SeatsSSR'], seats_ssr)
        self.assertEqual(payload['OtherSSR'], other_ssr)


class TestAirIQManagementAPIs(TestCase):
    """Test booking management APIs"""
    
    def setUp(self):
        self.service = AirIQService()
        self.service._auth_token = "test_token"
        self.service._token_expires_at = timezone.now() + timedelta(hours=1)
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_cancel_booking(self, mock_request):
        """Test cancellation API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "CancelStatus": "SUCCESS",
            "Remarks": "Your request to Cancel has been processed successfully.",
            "PenalityAmount": "1000",
            "TotalBookingAmount": "19873",
            "Status": {
                "ResultCode": "1",
                "Error": "",
                "SequenceID": "12480132846525607"
            }
        }
        mock_request.return_value = mock_response
        
        response = self.service.cancel_booking("BX18DK0003", "CANCEL", "Customer request")
        
        self.assertEqual(response['CancelStatus'], 'SUCCESS')
        self.assertIn('PenalityAmount', response)
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_get_account_balance(self, mock_request):
        """Test account balance API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Status": {
                "Error": "",
                "ResultCode": "1",
                "SequenceID": "12401475083610"
            },
            "TopupBalance": "1022.01",
            "CreditBalance": "00.00"
        }
        mock_request.return_value = mock_response
        
        response = self.service.get_account_balance()
        
        self.assertEqual(response['TopupBalance'], "1022.01")
        self.assertEqual(response['CreditBalance'], "00.00")
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_reschedule_availability(self, mock_request):
        """Test reschedule availability API"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Trackid": "AQ1529473540502431215295031386525F6RGWLZIXC",
            "ItineraryFlightList": [],
            "Status": {
                "Error": "",
                "ResultCode": "1",
                "SequenceID": "15294735405024312"
            }
        }
        mock_request.return_value = mock_response
        
        response = self.service.reschedule_availability(
            trip_type="O",
            departure_station="DEL",
            arrival_station="BOM",
            flight_date="20250810",
            airiq_pnr="BX18DK0003",
            remarks="Reschedule request"
        )
        
        self.assertIn('Trackid', response)
        self.assertIn('ItineraryFlightList', response)


@pytest.mark.integration
class TestAirIQIntegration(TestCase):
    """Integration tests with actual AirIQ sandbox (if available)"""
    
    def setUp(self):
        self.service = AirIQService()
    
    @pytest.mark.skip("Requires valid AirIQ credentials")
    def test_full_booking_flow(self):
        """Test complete booking flow from search to confirmation"""
        # This would test the complete flow:
        # 1. Authentication
        # 2. Flight search
        # 3. Pricing
        # 4. Seat map (optional)
        # 5. Booking creation
        # 6. Ticketing (if not blocked)
        # 7. Booking retrieval
        pass


class TestErrorHandling(TestCase):
    """Test error handling and response parsing"""
    
    def setUp(self):
        self.service = AirIQService()
        self.service._auth_token = "test_token"
        self.service._token_expires_at = timezone.now() + timedelta(hours=1)
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_api_failure_response(self, mock_request):
        """Test handling of API failure responses"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ItineraryFlightList": None,
            "Status": {
                "Error": "Request format is invalid",
                "ResultCode": "0",
                "SequenceID": "11413958113534"
            }
        }
        mock_request.return_value = mock_response
        
        with self.assertRaises(AirIQException) as context:
            self.service.search_flights({
                'origin': 'DEL',
                'destination': 'BOM',
                'departure_date': '20231114'
            })
        
        self.assertIn("Request format is invalid", str(context.exception))
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_api_exception_response(self, mock_request):
        """Test handling of API exception responses"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ItineraryFlightList": None,
            "Status": {
                "Error": "EX-Unable to fetch the flight results.",
                "ResultCode": "-1",
                "SequenceID": "1141345598894"
            }
        }
        mock_request.return_value = mock_response
        
        with self.assertRaises(AirIQException) as context:
            self.service.search_flights({
                'origin': 'DEL',
                'destination': 'BOM',
                'departure_date': '20231114'
            })
        
        self.assertIn("Unable to fetch the flight results", str(context.exception))
    
    @patch('apps.flights.services.airiq_service.requests.request')
    def test_network_error_handling(self, mock_request):
        """Test network error handling"""
        import requests
        mock_request.side_effect = requests.RequestException("Network error")
        
        response, success = self.service._make_request("http://test.com", {})
        
        self.assertFalse(success)
        self.assertIn('error', response)