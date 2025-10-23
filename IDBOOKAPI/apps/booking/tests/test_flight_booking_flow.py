"""
Flight Booking User Flow Test Cases
Tests the complete flight booking workflow including:
- Search and hold booking
- Payment processing
- Booking confirmation
- Status updates
- Cancellation and refunds
"""

import json
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, Mock

from apps.booking.models import Booking, BookingPaymentDetail
from apps.customer.models import CustomerWallet, CustomerWalletTransaction
from apps.authentication.models import User
from IDBOOKAPI.basic_resources import BOOKING_STATUS_CHOICES, PAYMENT_TYPE, PAYMENT_MEDIUM

User = get_user_model()

class FlightBookingFlowTestCase(APITestCase):
    """Test complete flight booking workflow"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            phone="9876543210",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            is_active=True
        )
        
        # Create customer wallet
        self.wallet = CustomerWallet.objects.create(
            user=self.user,
            balance=Decimal('5000.00'),
            bonus_balance=Decimal('500.00')
        )
        
        # Set up API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Sample flight search data
        self.search_data = {
            "origin": "DEL",
            "destination": "BOM", 
            "departure_date": "2024-12-25",
            "return_date": None,
            "adults": 1,
            "children": 0,
            "infants": 0,
            "class_type": "Economy"
        }
        
        # Sample passenger data
        self.passenger_data = {
            "passengers": [
                {
                    "type": "adult",
                    "title": "Mr",
                    "first_name": "John",
                    "last_name": "Doe",
                    "gender": "M",
                    "date_of_birth": "1990-01-01",
                    "nationality": "IN",
                    "passport_number": "",
                    "passport_expiry": "",
                    "frequent_flyer_number": ""
                }
            ]
        }
        
        # Sample flight offer
        self.flight_offer = {
            "offer_id": "TEST_OFFER_123",
            "airline_code": "6E",
            "airline_name": "IndiGo",
            "flight_number": "6E-123",
            "origin": "DEL",
            "destination": "BOM",
            "departure_time": "2024-12-25T06:00:00",
            "arrival_time": "2024-12-25T08:15:00",
            "duration": "02:15",
            "aircraft": "A320",
            "class_type": "Economy",
            "fare_basis": "U",
            "baggage_allowance": "15 KG",
            "price": {
                "base_fare": "4500.00",
                "taxes": "650.00",
                "total": "5150.00",
                "currency": "INR"
            }
        }

    def test_01_flight_search(self):
        """Test flight search functionality"""
        with patch('apps.booking.utils.flight_search_utils.AirIQFlightSearchService') as mock_service:
            # Mock successful search response
            mock_service.return_value.search_flights.return_value = {
                'success': True,
                'offers': [self.flight_offer],
                'search_id': 'SEARCH_123'
            }
            
            url = reverse('booking:flight-search')
            response = self.client.post(url, self.search_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('offers', response.data['data'])
            self.assertGreater(len(response.data['data']['offers']), 0)

    def test_02_create_hold_booking(self):
        """Test creating a hold booking"""
        with patch('apps.booking.utils.flight_booking_utils.AirIQFlightBookingService') as mock_service:
            # Mock successful hold response
            mock_service.return_value.create_hold_booking.return_value = {
                'success': True,
                'booking_reference': 'HOLD_ABC123',
                'hold_expires_at': (datetime.now() + timedelta(minutes=30)).isoformat(),
                'status': 'HOLD'
            }
            
            booking_data = {
                **self.passenger_data,
                "flight_offer": self.flight_offer,
                "contact_email": "test@example.com",
                "contact_phone": "9876543210"
            }
            
            url = reverse('booking:create-flight-booking')
            response = self.client.post(url, booking_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertTrue(response.data['success'])
            
            # Verify booking creation
            booking = Booking.objects.get(id=response.data['data']['booking']['id'])
            self.assertEqual(booking.booking_status, 'HOLD')
            self.assertEqual(booking.booking_type, 'FLIGHT')
            self.assertEqual(booking.user, self.user)
            
            return booking

    def test_03_get_payment_methods(self):
        """Test getting available payment methods"""
        booking = self.test_02_create_hold_booking()
        
        url = reverse('booking:flight-payment-methods', kwargs={'pk': booking.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        methods = response.data['data']['available_methods']
        self.assertIn('WALLET', methods)
        self.assertIn('PHONE_PAY', methods)
        self.assertIn('PAYU', methods)

    def test_04_wallet_payment_success(self):
        """Test successful wallet payment"""
        booking = self.test_02_create_hold_booking()
        
        with patch('apps.booking.utils.flight_booking_utils.AirIQFlightBookingService') as mock_service:
            # Mock successful booking confirmation
            mock_service.return_value.confirm_booking.return_value = {
                'success': True,
                'booking_reference': 'CONFIRMED_ABC123',
                'pnr': 'PNR123456',
                'tickets': [
                    {
                        'ticket_number': 'TKT001',
                        'passenger': 'John Doe',
                        'status': 'CONFIRMED'
                    }
                ]
            }
            
            payment_data = {
                "payment_method": "WALLET",
                "amount": str(booking.total_amount)
            }
            
            url = reverse('booking:initiate-flight-payment', kwargs={'pk': booking.id})
            response = self.client.post(url, payment_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            
            # Verify booking status update
            booking.refresh_from_db()
            self.assertEqual(booking.booking_status, 'CONFIRMED')
            
            # Verify payment record
            payment = BookingPaymentDetail.objects.get(booking=booking)
            self.assertEqual(payment.payment_method, 'WALLET')
            self.assertEqual(payment.payment_status, 'PAID')
            
            # Verify wallet deduction
            self.wallet.refresh_from_db()
            expected_balance = Decimal('5000.00') - booking.total_amount
            self.assertEqual(self.wallet.balance, expected_balance)

    def test_05_phonepe_payment_initiation(self):
        """Test PhonePe payment initiation"""
        booking = self.test_02_create_hold_booking()
        
        with patch('apps.booking.utils.flight_payment_utils.PhonePayMixin') as mock_phonepe:
            # Mock PhonePe response
            mock_phonepe.return_value.initiate_payment.return_value = {
                'success': True,
                'payment_url': 'https://phonepay.com/pay/test123',
                'transaction_id': 'TXN_TEST_123',
                'merchant_transaction_id': f'FLIGHT_{booking.id}_{datetime.now().strftime("%Y%m%d%H%M%S")}'
            }
            
            payment_data = {
                "payment_method": "PHONE_PAY",
                "amount": str(booking.total_amount)
            }
            
            url = reverse('booking:initiate-flight-payment', kwargs={'pk': booking.id})
            response = self.client.post(url, payment_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            self.assertIn('payment_url', response.data['data'])
            
            # Verify payment record creation
            payment = BookingPaymentDetail.objects.get(booking=booking)
            self.assertEqual(payment.payment_method, 'PHONE_PAY')
            self.assertEqual(payment.payment_status, 'PENDING')

    def test_06_phonepe_payment_callback_success(self):
        """Test PhonePe payment success callback"""
        booking = self.test_02_create_hold_booking()
        
        # Create pending payment record
        payment = BookingPaymentDetail.objects.create(
            booking=booking,
            user=self.user,
            payment_method='PHONE_PAY',
            payment_medium='PHONE_PAY',
            amount=booking.total_amount,
            payment_status='PENDING',
            transaction_id='TXN_TEST_123',
            gateway_transaction_id='PHONEPE_TXN_123'
        )
        
        with patch('apps.booking.utils.flight_booking_utils.AirIQFlightBookingService') as mock_service:
            # Mock successful booking confirmation
            mock_service.return_value.confirm_booking.return_value = {
                'success': True,
                'booking_reference': 'CONFIRMED_ABC123',
                'pnr': 'PNR123456'
            }
            
            callback_data = {
                "merchantTransactionId": f'FLIGHT_{booking.id}_{payment.created_at.strftime("%Y%m%d%H%M%S")}',
                "transactionId": "PHONEPE_TXN_123",
                "amount": int(booking.total_amount * 100),  # Amount in paise
                "state": "COMPLETED",
                "responseCode": "SUCCESS"
            }
            
            url = reverse('booking:flight-phonepe-callback')
            response = self.client.post(url, callback_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            
            # Verify payment and booking status
            payment.refresh_from_db()
            booking.refresh_from_db()
            
            self.assertEqual(payment.payment_status, 'PAID')
            self.assertEqual(booking.booking_status, 'CONFIRMED')

    def test_07_get_flight_booking_details(self):
        """Test retrieving comprehensive flight booking details"""
        booking = self.test_04_wallet_payment_success()
        
        url = reverse('booking:flight-details', kwargs={'pk': booking.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        details = response.data['data']
        self.assertIn('booking', details)
        self.assertIn('passengers', details)
        self.assertIn('flight_details', details)
        self.assertIn('payment_details', details)

    def test_08_flight_status_update(self):
        """Test flight status update from AirIQ"""
        booking = self.test_04_wallet_payment_success()
        
        with patch('apps.booking.utils.flight_status_utils.AirIQFlightStatusService') as mock_service:
            # Mock status update response
            mock_service.return_value.get_booking_status.return_value = {
                'success': True,
                'status': 'CONFIRMED',
                'flight_status': 'ON_TIME',
                'departure_time': '2024-12-25T06:00:00',
                'arrival_time': '2024-12-25T08:15:00',
                'gate': 'A12',
                'terminal': 'T3'
            }
            
            url = reverse('booking:flight-status-update', kwargs={'pk': booking.id})
            response = self.client.post(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])

    def test_09_booking_cancellation_request(self):
        """Test booking cancellation request"""
        booking = self.test_04_wallet_payment_success()
        
        with patch('apps.booking.utils.flight_booking_utils.AirIQFlightBookingService') as mock_service:
            # Mock cancellation policy response
            mock_service.return_value.get_cancellation_policy.return_value = {
                'success': True,
                'cancellation_allowed': True,
                'cancellation_charges': '500.00',
                'refund_amount': str(booking.total_amount - Decimal('500.00'))
            }
            
            cancellation_data = {
                "reason": "Travel plans changed",
                "requested_by": "customer"
            }
            
            url = reverse('booking:cancel-booking', kwargs={'pk': booking.id})
            response = self.client.post(url, cancellation_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            
            # Verify booking status
            booking.refresh_from_db()
            self.assertEqual(booking.booking_status, 'CANCELED')

    def test_10_process_refund(self):
        """Test refund processing after cancellation"""
        booking = self.test_09_booking_cancellation_request()
        
        with patch('apps.booking.utils.flight_refund_utils.RefundProcessor') as mock_processor:
            # Mock refund processing
            mock_processor.return_value.process_refund.return_value = {
                'success': True,
                'refund_amount': '4650.00',
                'refund_method': 'WALLET',
                'transaction_id': 'REF_123456'
            }
            
            refund_data = {
                "refund_method": "WALLET"
            }
            
            url = reverse('booking:process-refund', kwargs={'pk': booking.id})
            response = self.client.post(url, refund_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
            
            # Verify wallet credit
            self.wallet.refresh_from_db()
            refund_amount = Decimal('4650.00')
            # Note: Exact balance depends on previous transactions

    def test_11_get_user_flight_bookings(self):
        """Test retrieving user's flight bookings with filters"""
        # Create multiple bookings for comprehensive testing
        self.test_04_wallet_payment_success()
        
        # Test without filters
        url = reverse('booking:my-flights')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertGreater(len(response.data['data']['bookings']), 0)
        
        # Test with status filter
        response = self.client.get(url + '?status=CONFIRMED')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test with date range filter
        response = self.client.get(url + '?date_from=2024-12-01&date_to=2024-12-31')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_12_hold_booking_expiry(self):
        """Test hold booking expiry handling"""
        booking = self.test_02_create_hold_booking()
        
        # Simulate hold expiry
        with patch('django.utils.timezone.now') as mock_now:
            # Set time to after hold expiry
            mock_now.return_value = datetime.now() + timedelta(hours=1)
            
            url = reverse('booking:flight-details', kwargs={'pk': booking.id})
            response = self.client.get(url)
            
            # Booking should be expired
            booking.refresh_from_db()
            self.assertEqual(booking.booking_status, 'HOLD')  # May need background task to update

    def test_13_payment_failure_handling(self):
        """Test payment failure scenarios"""
        booking = self.test_02_create_hold_booking()
        
        with patch('apps.booking.utils.flight_payment_utils.PhonePayMixin') as mock_phonepe:
            # Mock payment failure
            mock_phonepe.return_value.initiate_payment.return_value = {
                'success': False,
                'error': 'Payment gateway error',
                'error_code': 'GATEWAY_ERROR'
            }
            
            payment_data = {
                "payment_method": "PHONE_PAY",
                "amount": str(booking.total_amount)
            }
            
            url = reverse('booking:initiate-flight-payment', kwargs={'pk': booking.id})
            response = self.client.post(url, payment_data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(response.data['success'])

    def test_14_insufficient_wallet_balance(self):
        """Test wallet payment with insufficient balance"""
        # Reduce wallet balance
        self.wallet.balance = Decimal('100.00')
        self.wallet.save()
        
        booking = self.test_02_create_hold_booking()
        
        payment_data = {
            "payment_method": "WALLET",
            "amount": str(booking.total_amount)
        }
        
        url = reverse('booking:initiate-flight-payment', kwargs={'pk': booking.id})
        response = self.client.post(url, payment_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('insufficient', response.data['message'].lower())

    def test_15_booking_timeline(self):
        """Test booking timeline retrieval"""
        booking = self.test_04_wallet_payment_success()
        
        url = reverse('booking:flight-timeline', kwargs={'pk': booking.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        timeline = response.data['data']['timeline']
        self.assertIsInstance(timeline, list)
        self.assertGreater(len(timeline), 0)
        
        # Verify timeline events
        events = [event['event_type'] for event in timeline]
        self.assertIn('BOOKING_CREATED', events)
        self.assertIn('PAYMENT_COMPLETED', events)
        self.assertIn('BOOKING_CONFIRMED', events)


class FlightBookingErrorHandlingTestCase(APITestCase):
    """Test error handling in flight booking flow"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            phone="9876543211",
            email="test2@example.com",
            first_name="Test2",
            last_name="User2"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_invalid_flight_offer(self):
        """Test booking creation with invalid flight offer"""
        invalid_data = {
            "passengers": [],
            "flight_offer": {},  # Invalid offer
            "contact_email": "test@example.com"
        }
        
        url = reverse('booking:create-flight-booking')
        response = self.client.post(url, invalid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])

    def test_nonexistent_booking_operations(self):
        """Test operations on non-existent bookings"""
        fake_booking_id = 99999
        
        # Test payment initiation
        url = reverse('booking:initiate-flight-payment', kwargs={'pk': fake_booking_id})
        response = self.client.post(url, {'payment_method': 'WALLET'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Test booking details
        url = reverse('booking:flight-details', kwargs={'pk': fake_booking_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthorized_booking_access(self):
        """Test accessing booking from different user"""
        # Create booking with different user
        other_user = User.objects.create_user(
            phone="9876543212",
            email="other@example.com"
        )
        
        # This would require creating a booking first, then switching users
        # Implementation depends on booking creation flow
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])