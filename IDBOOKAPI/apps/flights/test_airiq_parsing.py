#!/usr/bin/env python
"""
Test script to verify AirIQ response parsing works correctly.
This can be run independently to test the parsing logic with sample data.
"""

import os
import sys
import json
from datetime import datetime, date

# Add the project directory to the Python path
sys.path.insert(0, '/Users/vigneshnnu/Documents/dev/idbook/idbook-hotels-api/IDBOOKAPI')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'IDBOOKAPI.settings')

import django
django.setup()

from apps.flights.viewsets import FlightSearchViewSet
from apps.flights.models import FlightSearchSession, FlightOption

# Sample AirIQ response based on the provided JSON structure
SAMPLE_AIRIQ_RESPONSE = {
    "Status": {
        "ResultCode": "1",
        "Error": "",
        "Success": "True"
    },
    "Trackid": "AQ144316163728603151443236663904RSCN5INQMIX",
    "ItineraryFlightList": [
        {
            "Items": [
                {
                    "FlightDetails": [
                        {
                            "FlightID": "9603",
                            "AirlineCode": "6E",
                            "AirlineDescription": "IndiGo",
                            "FlightNumber": "6E 2142",
                            "Origin": "DEL",
                            "Destination": "BOM",
                            "DepartureDateTime": "14 Nov 2023 14:20",
                            "ArrivalDateTime": "14 Nov 2023 16:40",
                            "Class": "E",
                            "FareBasisCode": "ECOFLY",
                            "AirlineCategory": "LCC",
                            "Stops": 0,
                            "JourneyTime": "140",
                            "AirCraftType": "A320",
                            "AvailSeat": 9,
                            "Baggage": "15kg",
                            "Refundable": "True"
                        }
                    ],
                    "Fares": [
                        {
                            "FareType": "normal",
                            "Currency": "INR",
                            "Faredescription": [
                                {
                                    "BaseAmount": 4500.0,
                                    "TotalTaxAmount": 1200.0,
                                    "GrossAmount": 5700.0,
                                    "FareDescription": "Economy fare with all taxes"
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        {
            "Items": [
                {
                    "FlightDetails": [
                        {
                            "FlightID": "9604",
                            "AirlineCode": "UK",
                            "AirlineDescription": "Vistara",
                            "FlightNumber": "UK 941",
                            "Origin": "DEL",
                            "Destination": "BOM",
                            "DepartureDateTime": "14 Nov 2023 18:15",
                            "ArrivalDateTime": "14 Nov 2023 20:35",
                            "Class": "E",
                            "FareBasisCode": "ECONOMY",
                            "AirlineCategory": "FSC",
                            "Stops": 0,
                            "JourneyTime": "140",
                            "AirCraftType": "A321",
                            "AvailSeat": 7,
                            "Baggage": "20kg",
                            "Refundable": "False"
                        }
                    ],
                    "Fares": [
                        {
                            "FareType": "normal",
                            "Currency": "INR",
                            "Faredescription": [
                                {
                                    "BaseAmount": 6200.0,
                                    "TotalTaxAmount": 1300.0,
                                    "GrossAmount": 7500.0,
                                    "FareDescription": "Economy fare with all taxes"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}

def test_airiq_parsing():
    """Test the AirIQ response parsing logic"""
    print("Testing AirIQ response parsing...")
    
    # Create a FlightSearchViewSet instance
    viewset = FlightSearchViewSet()
    
    # Sample search data
    search_data = {
        'origin': 'DEL',
        'destination': 'BOM',
        'departure_date': date(2023, 11, 14),
        'trip_type': 'O',
        'flight_class': 'E',
        'adults': 1,
        'children': 0,
        'infants': 0
    }
    
    # Test the parsing method
    try:
        track_id = SAMPLE_AIRIQ_RESPONSE['Trackid']
        flight_options = viewset._parse_airiq_results(
            SAMPLE_AIRIQ_RESPONSE, 
            track_id, 
            search_data
        )
        
        print(f"✅ Successfully parsed {len(flight_options)} flight options")
        
        if flight_options:
            for i, option in enumerate(flight_options, 1):
                print(f"\nFlight Option {i}:")
                print(f"  - Airline: {option.airline_code} {option.flight_number}")
                print(f"  - Route: {option.origin} → {option.destination}")
                print(f"  - Departure: {option.departure_datetime}")
                print(f"  - Arrival: {option.arrival_datetime}")
                print(f"  - Fare: ₹{option.total_fare} (Base: ₹{option.base_fare}, Tax: ₹{option.taxes})")
                print(f"  - Available Seats: {option.available_seats}")
                print(f"  - Refundable: {option.is_refundable}")
                print(f"  - AirIQ Flight ID: {option.airiq_flight_id}")
        else:
            print("❌ No flight options were parsed - this indicates a parsing issue")
            
        return len(flight_options) > 0
        
    except Exception as e:
        print(f"❌ Error during parsing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_datetime_parsing():
    """Test the datetime parsing specifically"""
    print("\nTesting datetime parsing...")
    
    viewset = FlightSearchViewSet()
    
    test_cases = [
        "14 Nov 2023 14:20",
        "14 Nov 2023 18:15",
        "2023-11-14 14:20:00",
        "invalid datetime",
        "",
        None
    ]
    
    for test_case in test_cases:
        try:
            result = viewset._parse_airiq_datetime(test_case)
            print(f"✅ '{test_case}' -> {result}")
        except Exception as e:
            print(f"❌ '{test_case}' -> Error: {e}")

def cleanup_test_data():
    """Clean up test data created during testing"""
    print("\nCleaning up test data...")
    try:
        # Delete test search sessions and flight options
        FlightSearchSession.objects.filter(origin='DEL', destination='BOM').delete()
        print("✅ Test data cleaned up successfully")
    except Exception as e:
        print(f"❌ Error cleaning up test data: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("AirIQ Response Parsing Test")
    print("=" * 60)
    
    # Run the tests
    parsing_success = test_airiq_parsing()
    test_datetime_parsing()
    
    # Clean up
    cleanup_test_data()
    
    print("\n" + "=" * 60)
    if parsing_success:
        print("🎉 All tests passed! The AirIQ parsing should now work correctly.")
    else:
        print("❌ Tests failed. There are still issues with the parsing logic.")
    print("=" * 60)