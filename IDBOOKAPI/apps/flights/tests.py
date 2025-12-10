## Below are not used yet - for future reference only
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from datetime import datetime, date, timedelta
from unittest.mock import patch, Mock

from .models import (
    Airline,
    Airport,
    FlightRoute,
    FlightInventory,
    FlightSearchSession,
    FlightOption,
    FlightBooking,
)
from .services.inventory_service import inventory_service


User = get_user_model()


class FlightModelsTest(TestCase):
    """Test flight-related models"""

    def setUp(self):
        # Create test data
        self.airline = Airline.objects.create(
            code="AI", name="Air India", category="FSC", country="India", is_active=True
        )

        self.origin = Airport.objects.create(
            iata_code="DEL",
            name="Indira Gandhi International Airport",
            city="New Delhi",
            country="India",
            timezone="Asia/Kolkata",
            is_active=True,
        )

        self.destination = Airport.objects.create(
            iata_code="BOM",
            name="Chhatrapati Shivaji Maharaj International Airport",
            city="Mumbai",
            country="India",
            timezone="Asia/Kolkata",
            is_active=True,
        )

        self.route = FlightRoute.objects.create(
            origin=self.origin,
            destination=self.destination,
            airline=self.airline,
            flight_duration_hours=2.0,
            distance_km=1150,
            aircraft_type="Boeing 737",
            is_active=True,
        )

    def test_airline_creation(self):
        """Test airline model creation"""
        self.assertEqual(self.airline.code, "AI")
        self.assertEqual(str(self.airline), "AI - Air India")

    def test_airport_creation(self):
        """Test airport model creation"""
        self.assertEqual(self.origin.iata_code, "DEL")
        self.assertEqual(str(self.origin), "DEL - New Delhi")

    def test_flight_route_creation(self):
        """Test flight route model creation"""
        self.assertEqual(self.route.origin, self.origin)
        self.assertEqual(self.route.destination, self.destination)
        self.assertEqual(str(self.route), "DEL → BOM (Air India)")

    def test_flight_inventory_creation(self):
        """Test flight inventory creation"""
        inventory = FlightInventory.objects.create(
            route=self.route,
            flight_number="AI101",
            departure_date=date.today() + timedelta(days=1),
            departure_time="08:00:00",
            arrival_time="10:30:00",
            flight_class="E",
            total_seats=180,
            available_seats=150,
            base_price=5000.00,
            taxes=1200.00,
            total_price=6200.00,
            is_active=True,
        )

        self.assertEqual(inventory.flight_number, "AI101")
        self.assertEqual(inventory.available_seats, 150)


class FlightAPITest(APITestCase):
    """Test flight API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", phone="1234567890", password="testpass123"
        )

        # Create test data
        self.airline = Airline.objects.create(
            code="AI", name="Air India", category="FSC", country="India", is_active=True
        )

        self.origin = Airport.objects.create(
            iata_code="DEL",
            name="Indira Gandhi International Airport",
            city="New Delhi",
            country="India",
            timezone="Asia/Kolkata",
            is_active=True,
        )

        self.destination = Airport.objects.create(
            iata_code="BOM",
            name="Chhatrapati Shivaji Maharaj International Airport",
            city="Mumbai",
            country="India",
            timezone="Asia/Kolkata",
            is_active=True,
        )

        self.route = FlightRoute.objects.create(
            origin=self.origin,
            destination=self.destination,
            airline=self.airline,
            flight_duration_hours=2.0,
            distance_km=1150,
            aircraft_type="Boeing 737",
            is_active=True,
        )

        # Create inventory
        self.inventory = FlightInventory.objects.create(
            route=self.route,
            flight_number="AI101",
            departure_date=date.today() + timedelta(days=1),
            departure_time="08:00:00",
            arrival_time="10:30:00",
            flight_class="E",
            total_seats=180,
            available_seats=150,
            base_price=5000.00,
            taxes=1200.00,
            total_price=6200.00,
            is_active=True,
        )

    def test_airports_list(self):
        """Test airports list endpoint"""
        url = reverse("flights:flight-search-airports")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.json())
        airports = response.json()["data"]
        self.assertEqual(len(airports), 2)

        # Check airport data structure
        airport = airports[0]
        self.assertIn("iata_code", airport)
        self.assertIn("name", airport)
        self.assertIn("city", airport)

    def test_airlines_list(self):
        """Test airlines list endpoint"""
        url = reverse("flights:flight-search-airlines")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.json())
        airlines = response.json()["data"]
        self.assertEqual(len(airlines), 1)

        # Check airline data structure
        airline = airlines[0]
        self.assertIn("code", airline)
        self.assertIn("name", airline)
        self.assertEqual(airline["code"], "AI")

    def test_flight_search_inventory(self):
        """Test flight search with inventory mode"""
        url = reverse("flights:flight-search-search")
        search_data = {
            "origin": "DEL",
            "destination": "BOM",
            "departure_date": (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "trip_type": "O",
            "flight_class": "E",
            "adults": 1,
            "children": 0,
            "infants": 0,
            "search_mode": "INVENTORY",
            "sort_by": "price",
        }

        response = self.client.post(url, search_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()["data"]
        self.assertIn("search_results", data)
        self.assertIn("total_results", data)
        self.assertEqual(data["search_mode"], "INVENTORY")

    def test_flight_search_invalid_data(self):
        """Test flight search with invalid data"""
        url = reverse("flights:flight-search-search")
        search_data = {
            "origin": "DEL",
            "destination": "BOM",
            "departure_date": (date.today() - timedelta(days=1)).strftime(
                "%Y-%m-%d"
            ),  # Past date
            "adults": 1,
        }

        response = self.client.post(url, search_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_flight_booking_unauthenticated(self):
        """Test flight booking requires authentication"""
        url = reverse("flights:flight-booking-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_flight_booking_authenticated(self):
        """Test flight booking with authentication"""
        self.client.force_authenticate(user=self.user)

        url = reverse("flights:flight-booking-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
