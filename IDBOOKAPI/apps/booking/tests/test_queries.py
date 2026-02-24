"""
Tests for Visa and Event booking functionality
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone

from apps.booking.models import VisaBooking, EventBooking, Booking
from apps.org_resources.models import CompanyDetail
from apps.authentication.constants import UserGroups

User = get_user_model()


class VisaBookingTestCase(TestCase):
    """Test cases for VisaBooking model and API"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            mobile_number="1234567890",
            password="testpass123"
        )
        self.user.default_group = UserGroups.B2C_GRP
        self.user.save()
        
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            mobile_number="9876543210",
            password="adminpass123"
        )
        self.admin_user.default_group = UserGroups.BUS_ADMIN
        self.admin_user.save()
        
        # Create company for corporate user
        self.company = CompanyDetail.objects.create(
            company_name="Test Company",
            email="company@example.com"
        )
        self.corporate_user = User.objects.create_user(
            email="corp@example.com",
            mobile_number="5555555555",
            password="corppass123"
        )
        self.corporate_user.default_group = UserGroups.CORP_EMP
        self.corporate_user.company_id = self.company.id
        self.corporate_user.save()
    
    def test_create_visa_booking_via_booking_api(self):
        """Test creating a visa booking via standard Booking API"""
        self.client.force_authenticate(user=self.user)
        
        data = {
            "booking_type": "VISA",
            "destination_country": "USA",
            "travel_date": (date.today() + timedelta(days=30)).isoformat(),
            "visa_type": "tourist",
            "passport_number": "A1234567",
            "travel_purpose": "Tourism",
            "subtotal": "5000.00",
            "final_amount": "5000.00",
            "adult_count": 1,
        }
        
        response = self.client.post("/api/v1/booking/bookings/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Booking.objects.filter(user=self.user, booking_type="VISA").exists())
        booking = Booking.objects.get(user=self.user, booking_type="VISA")
        self.assertIsNotNone(booking.visa_booking)
    
    def test_create_visa_booking_with_company(self):
        """Test creating visa booking with company"""
        self.client.force_authenticate(user=self.corporate_user)
        
        data = {
            "booking_type": "VISA",
            "destination_country": "UK",
            "travel_date": (date.today() + timedelta(days=60)).isoformat(),
            "visa_type": "business",
            "travel_purpose": "Business meeting",
            "company": self.company.id,
            "subtotal": "7000.00",
            "final_amount": "7000.00",
            "adult_count": 1,
        }
        
        response = self.client.post("/api/v1/booking/bookings/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking = Booking.objects.get(user=self.corporate_user, booking_type="VISA")
        self.assertEqual(booking.company.id, self.company.id)
    
    def test_list_visa_bookings_by_company(self):
        """Test listing visa bookings filtered by company"""
        # Create bookings for different companies
        booking1 = Booking.objects.create(
            user=self.user,
            booking_type="VISA",
            subtotal=Decimal("5000"),
            final_amount=Decimal("5000"),
        )
        visa1 = VisaBooking.objects.create(
            destination_country="USA",
            travel_date=date.today() + timedelta(days=30),
            visa_type="tourist",
        )
        booking1.visa_booking = visa1
        booking1.save()
        
        booking2 = Booking.objects.create(
            user=self.corporate_user,
            booking_type="VISA",
            company=self.company,
            subtotal=Decimal("7000"),
            final_amount=Decimal("7000"),
        )
        visa2 = VisaBooking.objects.create(
            destination_country="UK",
            travel_date=date.today() + timedelta(days=60),
            visa_type="business",
        )
        booking2.visa_booking = visa2
        booking2.save()
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            f"/api/v1/booking/visa-bookings/?company_id={self.company.id}"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get("data", [])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["destination_country"], "UK")
    
    def test_update_visa_booking_status_admin(self):
        """Test updating visa booking status as admin"""
        booking = Booking.objects.create(
            user=self.user,
            booking_type="VISA",
            subtotal=Decimal("5000"),
            final_amount=Decimal("5000"),
        )
        visa = VisaBooking.objects.create(
            destination_country="Germany",
            travel_date=date.today() + timedelta(days=120),
            visa_type="tourist",
            status="pending",
        )
        booking.visa_booking = visa
        booking.save()
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f"/api/v1/booking/visa-bookings/{visa.id}/",
            {"status": "quoted"},
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        visa.refresh_from_db()
        self.assertEqual(visa.status, "quoted")


class EventBookingTestCase(TestCase):
    """Test cases for EventBooking model and API"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            mobile_number="1234567890",
            password="testpass123"
        )
        self.user.default_group = UserGroups.B2C_GRP
        self.user.save()
        
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            mobile_number="9876543210",
            password="adminpass123"
        )
        self.admin_user.default_group = UserGroups.BUS_ADMIN
        self.admin_user.save()
        
        self.company = CompanyDetail.objects.create(
            company_name="Test Company",
            email="company@example.com"
        )
    
    def test_create_event_booking_via_booking_api(self):
        """Test creating an event booking via standard Booking API"""
        self.client.force_authenticate(user=self.user)
        
        event_date = timezone.now() + timedelta(days=30)
        
        data = {
            "booking_type": "EVENT",
            "event_name": "Tech Conference 2024",
            "event_type": "conference",
            "event_date": event_date.isoformat(),
            "location": "Mumbai",
            "attendee_count": 50,
            "budget_range": "100000_250000",
            "subtotal": "150000.00",
            "final_amount": "150000.00",
            "adult_count": 50,
        }
        
        response = self.client.post("/api/v1/booking/bookings/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Booking.objects.filter(user=self.user, booking_type="EVENT").exists())
        booking = Booking.objects.get(user=self.user, booking_type="EVENT")
        self.assertIsNotNone(booking.event_booking)
    
    def test_list_event_bookings_by_company(self):
        """Test listing event bookings filtered by company"""
        booking = Booking.objects.create(
            user=self.user,
            booking_type="EVENT",
            company=self.company,
            subtotal=Decimal("150000"),
            final_amount=Decimal("150000"),
        )
        event = EventBooking.objects.create(
            event_name="Corporate Seminar",
            event_type="corporate",
            event_date=timezone.now() + timedelta(days=90),
            location="Bangalore",
            attendee_count=75,
        )
        booking.event_booking = event
        booking.save()
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            f"/api/v1/booking/event-bookings/?company_id={self.company.id}"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get("data", [])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["event_name"], "Corporate Seminar")
