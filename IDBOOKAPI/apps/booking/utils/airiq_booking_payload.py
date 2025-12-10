"""
AirIQ Booking Payload Builder
Constructs the complete AirIQ booking request using minimal user input + stored session data
"""

from typing import Dict, List
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def build_airiq_booking_payload(
    flight_booking, user_data: Dict, stored_pricing_data: Dict = None
) -> Dict:
    """
    Build complete AirIQ booking payload from minimal user input + stored data

    Args:
        flight_booking: FlightBooking instance with stored session data
        user_data: User-provided data (passengers, contact, preferences)
        stored_pricing_data: Optional pricing response data (if not in flight_booking)

    Returns:
        Complete AirIQ booking request payload
    """

    # Get session data from flight booking
    search_session = flight_booking.search_session_data or {}
    selected_flight = flight_booking.selected_flight_data or {}

    # Extract passenger counts from session (from original search)
    passenger_counts = search_session.get("passenger_counts", {})
    adult_count = passenger_counts.get("adults", 1)
    child_count = passenger_counts.get("children", 0)
    infant_count = passenger_counts.get("infants", 0)

    # Build base payload structure
    payload = {
        # === AGENT INFO (System Config) ===
        "AgentInfo": {
            "AgentId": settings.AIRIQ_AGENT_ID,
            "UserName": settings.AIRIQ_USERNAME,
            "AppType": "API",
            "Version": 2.0,
        },
        # === PASSENGER COUNTS (From Search Session) ===
        "AdultCount": adult_count,
        "ChildCount": child_count,
        "InfantCount": infant_count,
        # === FLIGHT ITINERARY (From Pricing Response) ===
        "ItineraryFlightsInfo": _build_itinerary_info(
            flight_booking, user_data, selected_flight
        ),
        # === PASSENGER DETAILS (User Input Required) ===
        "PaxDetailsInfo": _build_passenger_details(user_data.get("passengers", [])),
        # === CONTACT DETAILS (User Input Required) ===
        "AddressDetails": _build_contact_details(user_data.get("contact", {})),
        # === GST INFO (Optional User Input) ===
        "GSTInfo": _build_gst_info(user_data.get("gst_info", {})),
        # === FREQUENT FLYER (Optional User Input) ===
        "FFNumberInfo": _build_frequent_flyer_info(user_data.get("frequent_flyer", [])),
        # === TRIP INFO (From Session Data) ===
        "TripType": search_session.get("trip_type", "O"),
        "BlockPNR": user_data.get("block_pnr", False),
        "BaseOrigin": search_session.get("base_origin", ""),
        "BaseDestination": search_session.get("base_destination", ""),
        "TrackId": flight_booking.airiq_track_id or search_session.get("track_id", ""),
    }

    return payload


def _build_itinerary_info(
    flight_booking, user_data: Dict, selected_flight: Dict
) -> List[Dict]:
    """Build itinerary flights info from stored pricing data"""

    # Get pricing token from stored data
    pricing_token = selected_flight.get("pricing_token", "")
    if not pricing_token:
        raise ValueError("Pricing token not found in stored flight data")

    # Get flight segments from stored data
    flight_segments = selected_flight.get("segments", [])
    if not flight_segments:
        raise ValueError("Flight segments not found in stored flight data")

    # Build flights info from stored segments
    flights_info = []
    for segment in flight_segments:
        flight_info = {
            "FlightID": segment.get("flight_id", ""),
            "FlightNumber": segment.get("flight_number", ""),
            "Origin": segment.get("origin", ""),
            "Destination": segment.get("destination", ""),
            "DepartureDateTime": segment.get("departure_datetime", ""),
            "ArrivalDateTime": segment.get("arrival_datetime", ""),
        }
        flights_info.append(flight_info)

    # Build ancillary services from user selections
    itinerary_info = {
        "Token": pricing_token,
        "FlightsInfo": flights_info,
        "PaymentMode": "T",  # Always "T" for agent deposit
        "SeatsSSRInfo": _build_seats_ssr(user_data.get("seats", [])),
        "BaggSSRInfo": _build_baggage_ssr(user_data.get("baggage", [])),
        "MealsSSRInfo": _build_meals_ssr(user_data.get("meals", [])),
        "OtherSSRInfo": _build_other_ssr(user_data.get("other_services", [])),
        "PaymentInfo": [{"TotalAmount": str(user_data.get("total_amount", 0))}],
    }

    return [itinerary_info]


def _build_passenger_details(passengers: List[Dict]) -> List[Dict]:
    """Build passenger details from user input"""

    pax_details = []
    for i, passenger in enumerate(passengers):
        pax_detail = {
            "PaxRefNumber": str(i + 1),  # 1-indexed
            "Title": passenger.get("title", "").upper(),
            "FirstName": passenger.get("first_name", ""),
            "LastName": passenger.get("last_name", ""),
            "DOB": _format_date(passenger.get("date_of_birth", "")),
            "Gender": passenger.get("gender", ""),
            "PaxType": passenger.get("passenger_type", "ADT"),
            "PassportNo": passenger.get("passport_number", ""),
            "PassportExpiry": _format_date(passenger.get("passport_expiry", "")),
            "PassportIssuedDate": _format_date(
                passenger.get("passport_issued_date", "")
            ),
            "PassportCountryCode": passenger.get("passport_country_code", ""),
            "InfantRef": passenger.get("infant_reference", ""),
        }
        pax_details.append(pax_detail)

    return pax_details


def _build_contact_details(contact: Dict) -> Dict:
    """Build contact details from user input"""

    return {
        "CountryCode": contact.get("country_code", "91"),
        "ContactNumber": contact.get("phone", ""),
        "EmailID": contact.get("email", ""),
    }


def _build_gst_info(gst_info: Dict) -> Dict:
    """Build GST info from user input (optional)"""

    return {
        "GSTNumber": gst_info.get("gst_number", ""),
        "GSTCompanyName": gst_info.get("company_name", ""),
        "GSTAddress": gst_info.get("address", ""),
        "GSTEmailID": gst_info.get("email", ""),
        "GSTMobileNumber": gst_info.get("mobile", ""),
    }


def _build_frequent_flyer_info(ff_info: List[Dict]) -> List[Dict]:
    """Build frequent flyer info from user input (optional)"""

    ff_details = []
    for ff in ff_info:
        ff_detail = {
            "SegRefNumber": ff.get("segment_ref", "1"),
            "PaxRefNumber": ff.get("passenger_ref", "1"),
            "AirlineCode": ff.get("airline_code", ""),
            "FlyerNumber": ff.get("flyer_number", ""),
            "Itinref": ff.get("itinerary_ref", "0"),
        }
        ff_details.append(ff_detail)

    return ff_details


def _build_seats_ssr(seats: List[Dict]) -> List[Dict]:
    """Build seat SSR info from user selections"""

    seat_ssr = []
    for seat in seats:
        seat_info = {
            "PaxRefNumber": str(seat.get("passenger_ref", 1)),
            "SeatID": seat.get("seat_id", ""),
        }
        seat_ssr.append(seat_info)

    return seat_ssr


def _build_baggage_ssr(baggage: List[Dict]) -> List[Dict]:
    """Build baggage SSR info from user selections"""

    baggage_ssr = []
    for bag in baggage:
        bag_info = {
            "BaggageID": bag.get("baggage_id", ""),
            "PaxRefNumber": str(bag.get("passenger_ref", 1)),
        }
        baggage_ssr.append(bag_info)

    return baggage_ssr


def _build_meals_ssr(meals: List[Dict]) -> List[Dict]:
    """Build meal SSR info from user selections"""

    meal_ssr = []
    for meal in meals:
        meal_info = {
            "MealID": meal.get("meal_id", ""),
            "PaxRefNumber": str(meal.get("passenger_ref", 1)),
        }
        meal_ssr.append(meal_info)

    return meal_ssr


def _build_other_ssr(other_services: List[Dict]) -> List[Dict]:
    """Build other SSR info from user selections"""

    other_ssr = []
    for service in other_services:
        service_info = {
            "OtherSSRID": service.get("service_id", ""),
            "PaxRefNumber": str(service.get("passenger_ref", 1)),
        }
        other_ssr.append(service_info)

    return other_ssr


def _format_date(date_string: str) -> str:
    """Format date string to DD/MM/YYYY for AirIQ"""

    if not date_string:
        return ""

    try:
        # Handle various input formats and convert to DD/MM/YYYY
        from datetime import datetime

        # Try different input formats
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_string, fmt)
                return dt.strftime("%d/%m/%Y")
            except ValueError:
                continue

        # If no format matched, return as-is
        logger.warning(f"Could not parse date format: {date_string}")
        return date_string

    except Exception as e:
        logger.error(f"Error formatting date {date_string}: {str(e)}")
        return ""
