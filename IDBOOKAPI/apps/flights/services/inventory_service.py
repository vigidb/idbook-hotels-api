## Below are not used yet. Invventory ticket are not possible to book. Only AirIQ block PNRs are possible to book.
## We can remove below if not needed. For future reference only.
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db.models import Q, F
from django.core.exceptions import ValidationError
import logging

from ..models import (
    Airport,
    Airline,
    FlightRoute,
    FlightInventory,
    FlightSearchSession,
    FlightOption,
)

logger = logging.getLogger(__name__)


class InventoryService:
    """
    Service for managing flight inventory (pre-booked tickets)
    Handles inventory search, availability checks, and booking management
    """

    def search_inventory_flights(self, search_params: dict) -> List[FlightOption]:
        """
        Search for flights in inventory based on search parameters
        Args:
            search_params: {
                'origin': 'DEL',
                'destination': 'BOM',
                'departure_date': datetime.date,
                'return_date': datetime.date,  # Optional for round trip
                'trip_type': 'O',  # O=One-way, R=Round-trip
                'flight_class': 'E',  # E=Economy, B=Business, F=First
                'adults': 1,
                'children': 0,
                'infants': 0,
                'direct_only': False,
                'sort_by': 'price'  # 'price', 'duration', 'departure_time'
            }
        Returns:
            List of FlightOption objects
        """
        try:
            # Get airports
            origin_airport = Airport.objects.get(iata_code=search_params["origin"])
            destination_airport = Airport.objects.get(
                iata_code=search_params["destination"]
            )
        except Airport.DoesNotExist as e:
            logger.error(f"Airport not found: {e}")
            return []

        # Base query for inventory
        inventory_query = FlightInventory.objects.filter(
            route__origin=origin_airport,
            route__destination=destination_airport,
            flight_date=search_params["departure_date"],
            status="ACTIVE",
            is_active=True,
        )

        # Filter by available seats for the requested class
        flight_class = search_params.get("flight_class", "E")
        total_passengers = search_params.get("adults", 1) + search_params.get(
            "children", 0
        )

        if flight_class == "E":
            inventory_query = inventory_query.filter(
                economy_available__gte=total_passengers
            )
        elif flight_class == "B":
            inventory_query = inventory_query.filter(
                business_available__gte=total_passengers
            )
        elif flight_class == "F":
            inventory_query = inventory_query.filter(
                first_available__gte=total_passengers
            )

        # Apply direct flight filter
        if search_params.get("direct_only", False):
            inventory_query = inventory_query.filter(route__stops=0)

        # Create search session for tracking
        search_session = self._create_search_session(search_params, "INVENTORY")

        # Convert inventory to flight options
        flight_options = []
        for inventory in inventory_query:
            flight_option = self._create_flight_option_from_inventory(
                inventory, flight_class, search_session
            )
            if flight_option:
                flight_options.append(flight_option)

        # Sort results
        flight_options = self._sort_flight_options(
            flight_options, search_params.get("sort_by", "price")
        )

        # Update search session with results count
        search_session.results_count = len(flight_options)
        search_session.save()

        return flight_options

    def _create_search_session(
        self, search_params: dict, search_mode: str
    ) -> FlightSearchSession:
        """Create search session for tracking"""
        session = FlightSearchSession.objects.create(
            origin=search_params["origin"],
            destination=search_params["destination"],
            departure_date=search_params["departure_date"],
            return_date=search_params.get("return_date"),
            trip_type=search_params.get("trip_type", "O"),
            flight_class=search_params.get("flight_class", "E"),
            adults=search_params.get("adults", 1),
            children=search_params.get("children", 0),
            infants=search_params.get("infants", 0),
            search_mode=search_mode,
            expires_at=timezone.now()
            + timedelta(hours=2),  # Search results expire in 2 hours
        )
        return session

    def _create_flight_option_from_inventory(
        self,
        inventory: FlightInventory,
        flight_class: str,
        search_session: FlightSearchSession,
    ) -> Optional[FlightOption]:
        """Convert inventory item to flight option"""
        try:
            route = inventory.route

            # Calculate pricing based on class
            base_fare = inventory.get_class_price(flight_class)
            taxes = base_fare * 0.15  # Approximate tax calculation
            total_fare = base_fare + taxes

            # Determine duration
            duration_minutes = route.duration_minutes

            flight_option = FlightOption.objects.create(
                search_session=search_session,
                inventory_flight=inventory,
                airline_code=route.airline.code,
                flight_number=route.flight_number,
                origin=route.origin.iata_code,
                destination=route.destination.iata_code,
                departure_datetime=inventory.departure_datetime,
                arrival_datetime=inventory.arrival_datetime,
                flight_class=flight_class,
                fare_basis=f"{flight_class}INV",  # Inventory fare basis
                airline_category=route.airline.category,
                stops=0,  # Inventory flights are typically direct
                duration_minutes=duration_minutes,
                aircraft_type=route.aircraft_type,
                base_fare=base_fare,
                taxes=taxes,
                total_fare=total_fare,
                available_seats=inventory.get_available_seats(flight_class),
                baggage_info={"checked": "20KG", "cabin": "7KG"},  # Default baggage
                is_refundable=True,  # Inventory flights are typically refundable
                can_hold=False,  # No need to hold inventory flights
            )

            return flight_option

        except Exception as e:
            logger.error(f"Error creating flight option from inventory: {e}")
            return None

    def _sort_flight_options(
        self, flight_options: List[FlightOption], sort_by: str
    ) -> List[FlightOption]:
        """Sort flight options based on criteria"""
        if sort_by == "price":
            return sorted(flight_options, key=lambda x: x.total_fare)
        elif sort_by == "duration":
            return sorted(flight_options, key=lambda x: x.duration_minutes)
        elif sort_by == "departure_time":
            return sorted(flight_options, key=lambda x: x.departure_datetime)
        else:
            return flight_options

    def check_availability(
        self, inventory_id: int, flight_class: str, passengers: int
    ) -> bool:
        """
        Check if inventory has sufficient availability
        Args:
            inventory_id: FlightInventory ID
            flight_class: E/B/F
            passengers: Number of passengers
        """
        try:
            inventory = FlightInventory.objects.get(id=inventory_id, is_active=True)
            available_seats = inventory.get_available_seats(flight_class)
            return available_seats >= passengers
        except FlightInventory.DoesNotExist:
            return False

    def reserve_seats(
        self, inventory_id: int, flight_class: str, passengers: int
    ) -> bool:
        """
        Reserve seats in inventory (temporary hold)
        Args:
            inventory_id: FlightInventory ID
            flight_class: E/B/F
            passengers: Number of passengers
        Returns:
            True if reservation successful, False otherwise
        """
        try:
            inventory = FlightInventory.objects.select_for_update().get(
                id=inventory_id, is_active=True
            )

            # Check availability again under lock
            if not self.check_availability(inventory_id, flight_class, passengers):
                return False

            # Reserve seats by reducing available count
            if flight_class == "E":
                inventory.economy_available = F("economy_available") - passengers
            elif flight_class == "B":
                inventory.business_available = F("business_available") - passengers
            elif flight_class == "F":
                inventory.first_available = F("first_available") - passengers

            inventory.available_seats = F("available_seats") - passengers
            inventory.booked_seats = F("booked_seats") + passengers

            inventory.save(
                update_fields=[
                    "economy_available",
                    "business_available",
                    "first_available",
                    "available_seats",
                    "booked_seats",
                ]
            )

            # Refresh from database to get updated values
            inventory.refresh_from_db()

            # Update status if fully booked
            if inventory.available_seats == 0:
                inventory.status = "FULL"
                inventory.save(update_fields=["status"])

            return True

        except FlightInventory.DoesNotExist:
            logger.error(f"Inventory {inventory_id} not found for reservation")
            return False
        except Exception as e:
            logger.error(f"Error reserving seats: {e}")
            return False

    def release_seats(
        self, inventory_id: int, flight_class: str, passengers: int
    ) -> bool:
        """
        Release reserved seats back to inventory
        Args:
            inventory_id: FlightInventory ID
            flight_class: E/B/F
            passengers: Number of passengers
        Returns:
            True if release successful, False otherwise
        """
        try:
            inventory = FlightInventory.objects.select_for_update().get(id=inventory_id)

            # Release seats by increasing available count
            if flight_class == "E":
                inventory.economy_available = F("economy_available") + passengers
            elif flight_class == "B":
                inventory.business_available = F("business_available") + passengers
            elif flight_class == "F":
                inventory.first_available = F("first_available") + passengers

            inventory.available_seats = F("available_seats") + passengers
            inventory.booked_seats = F("booked_seats") - passengers

            inventory.save(
                update_fields=[
                    "economy_available",
                    "business_available",
                    "first_available",
                    "available_seats",
                    "booked_seats",
                ]
            )

            # Refresh from database to get updated values
            inventory.refresh_from_db()

            # Update status if no longer full
            if inventory.status == "FULL" and inventory.available_seats > 0:
                inventory.status = "ACTIVE"
                inventory.save(update_fields=["status"])

            return True

        except FlightInventory.DoesNotExist:
            logger.error(f"Inventory {inventory_id} not found for release")
            return False
        except Exception as e:
            logger.error(f"Error releasing seats: {e}")
            return False

    def get_inventory_details(self, inventory_id: int) -> Optional[Dict]:
        """Get detailed inventory information"""
        try:
            inventory = FlightInventory.objects.select_related(
                "route__airline", "route__origin", "route__destination"
            ).get(id=inventory_id)

            return {
                "id": inventory.id,
                "flight_number": inventory.route.full_flight_number,
                "airline": {
                    "code": inventory.route.airline.code,
                    "name": inventory.route.airline.name,
                    "category": inventory.route.airline.category,
                },
                "route": {
                    "origin": {
                        "code": inventory.route.origin.iata_code,
                        "name": inventory.route.origin.name,
                        "city": inventory.route.origin.city,
                    },
                    "destination": {
                        "code": inventory.route.destination.iata_code,
                        "name": inventory.route.destination.name,
                        "city": inventory.route.destination.city,
                    },
                },
                "schedule": {
                    "departure": inventory.departure_datetime,
                    "arrival": inventory.arrival_datetime,
                    "duration_minutes": inventory.route.duration_minutes,
                },
                "availability": {
                    "economy": {
                        "total": inventory.economy_total,
                        "available": inventory.economy_available,
                        "price": inventory.economy_price,
                    },
                    "business": {
                        "total": inventory.business_total,
                        "available": inventory.business_available,
                        "price": inventory.business_price,
                    },
                    "first": {
                        "total": inventory.first_total,
                        "available": inventory.first_available,
                        "price": inventory.first_price,
                    },
                },
                "status": inventory.status,
                "total_available": inventory.available_seats,
            }

        except FlightInventory.DoesNotExist:
            return None

    def bulk_create_inventory(
        self, inventory_data: List[Dict]
    ) -> Tuple[int, List[str]]:
        """
        Bulk create flight inventory
        Args:
            inventory_data: List of inventory dictionaries
        Returns:
            (created_count, error_messages)
        """
        created_count = 0
        error_messages = []

        for data in inventory_data:
            try:
                # Validate required fields
                required_fields = [
                    "route_id",
                    "flight_date",
                    "departure_datetime",
                    "arrival_datetime",
                ]
                for field in required_fields:
                    if field not in data:
                        raise ValueError(f"Missing required field: {field}")

                # Get route
                route = FlightRoute.objects.get(id=data["route_id"])

                # Create inventory
                inventory = FlightInventory.objects.create(
                    route=route,
                    flight_date=data["flight_date"],
                    departure_datetime=data["departure_datetime"],
                    arrival_datetime=data["arrival_datetime"],
                    total_seats=data.get("total_seats", 180),
                    available_seats=data.get("available_seats", 180),
                    economy_total=data.get("economy_total", 150),
                    economy_available=data.get("economy_available", 150),
                    business_total=data.get("business_total", 20),
                    business_available=data.get("business_available", 20),
                    first_total=data.get("first_total", 10),
                    first_available=data.get("first_available", 10),
                    economy_price=data.get("economy_price", 5000),
                    business_price=data.get("business_price", 15000),
                    first_price=data.get("first_price", 25000),
                    status=data.get("status", "ACTIVE"),
                )
                created_count += 1

            except Exception as e:
                error_messages.append(f"Error creating inventory item: {e}")
                logger.error(f"Bulk inventory creation error: {e}")

        return created_count, error_messages

    def get_route_availability_summary(
        self, origin: str, destination: str, date_range: Tuple[datetime, datetime]
    ) -> List[Dict]:
        """
        Get availability summary for a route across date range
        Args:
            origin: Origin airport IATA code
            destination: Destination airport IATA code
            date_range: (start_date, end_date)
        """
        try:
            origin_airport = Airport.objects.get(iata_code=origin)
            destination_airport = Airport.objects.get(iata_code=destination)

            inventory_query = (
                FlightInventory.objects.filter(
                    route__origin=origin_airport,
                    route__destination=destination_airport,
                    flight_date__range=date_range,
                    is_active=True,
                )
                .select_related("route__airline")
                .order_by("flight_date", "departure_datetime")
            )

            summary = []
            for inventory in inventory_query:
                summary.append(
                    {
                        "id": inventory.id,
                        "flight_date": inventory.flight_date,
                        "flight_number": inventory.route.full_flight_number,
                        "airline": inventory.route.airline.name,
                        "departure_time": inventory.departure_datetime.time(),
                        "arrival_time": inventory.arrival_datetime.time(),
                        "total_available": inventory.available_seats,
                        "economy_available": inventory.economy_available,
                        "business_available": inventory.business_available,
                        "first_available": inventory.first_available,
                        "economy_price": inventory.economy_price,
                        "business_price": inventory.business_price,
                        "first_price": inventory.first_price,
                        "status": inventory.status,
                    }
                )

            return summary

        except Airport.DoesNotExist:
            return []


# Singleton instance for reuse
inventory_service = InventoryService()
