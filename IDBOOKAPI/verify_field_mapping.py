#!/usr/bin/env python
"""
Script to verify current field mapping between AirIQ JSON and parsing logic
"""

# Sample AirIQ JSON structure
AIRIQ_SAMPLE = {
    "FlightDetails": [{
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
    }],
    "Fares": [{
        "FareType": "normal",
        "Currency": "INR",
        "Faredescription": [{
            "BaseAmount": 4500.0,
            "TotalTaxAmount": 1200.0,
            "GrossAmount": 5700.0,
            "FareDescription": "Economy fare with all taxes"
        }]
    }]
}

def analyze_mapping():
    """Analyze the field mapping between AirIQ and our parsing logic"""
    
    print("=" * 80)
    print("AIRIQ FIELD MAPPING VERIFICATION")
    print("=" * 80)
    
    # Extract first flight and fare for analysis
    flight_item = {"FlightDetails": AIRIQ_SAMPLE["FlightDetails"], "Fares": AIRIQ_SAMPLE["Fares"]}
    first_segment = flight_item["FlightDetails"][0]
    fares = flight_item["Fares"]
    
    print("\n📋 FLIGHT DETAILS MAPPING:")
    print("-" * 50)
    
    mappings = {
        # FlightOption model fields and their AirIQ sources
        'airiq_flight_id': first_segment.get('FlightID', ''),
        'airline_code': first_segment.get('AirlineCode', '')[:3],
        'flight_number': first_segment.get('FlightNumber', ''),
        'origin': first_segment.get('Origin', ''),
        'destination': first_segment.get('Destination', ''),
        'departure_datetime': first_segment.get('DepartureDateTime', ''),
        'arrival_datetime': first_segment.get('ArrivalDateTime', ''),
        'flight_class': first_segment.get('Class', 'E'),
        'fare_basis': first_segment.get('FareBasisCode', ''),
        'airline_category': first_segment.get('AirlineCategory', 'LCC'),
        'stops': int(first_segment.get('Stops', 0)),
        'duration_minutes': first_segment.get('JourneyTime', ''),
        'aircraft_type': first_segment.get('AirCraftType', ''),
        'available_seats': int(first_segment.get('AvailSeat', 9)),
        'baggage_info': first_segment.get('Baggage', '15kg'),
        'is_refundable': first_segment.get('Refundable', 'False').lower() == 'true',
    }
    
    for api_field, airiq_value in mappings.items():
        status = "✅" if airiq_value else "❌"
        print(f"{status} {api_field:<20} = {airiq_value}")
    
    print("\n💰 FARE INFORMATION MAPPING:")
    print("-" * 50)
    
    if fares:
        first_fare = fares[0]
        fare_desc = first_fare.get('Faredescription', [])
        if fare_desc:
            first_fare_desc = fare_desc[0]
            fare_mappings = {
                'base_fare': float(first_fare_desc.get('BaseAmount', 0)),
                'taxes': float(first_fare_desc.get('TotalTaxAmount', 0)),
                'total_fare': float(first_fare_desc.get('GrossAmount', 0)),
            }
            
            for api_field, airiq_value in fare_mappings.items():
                status = "✅" if airiq_value else "❌"
                print(f"{status} {api_field:<20} = {airiq_value}")
        else:
            print("❌ No fare descriptions found")
    else:
        print("❌ No fares found")
    
    print("\n🔧 FIELD TRANSFORMATIONS:")
    print("-" * 50)
    
    # Show transformations applied
    raw_flight_number = first_segment.get('FlightNumber', '')
    airline_code = first_segment.get('AirlineCode', '')[:3]
    
    # Flight number processing
    processed_flight_number = raw_flight_number
    if raw_flight_number.startswith(airline_code):
        processed_flight_number = raw_flight_number[len(airline_code):].strip()
    
    print(f"✅ Flight Number: '{raw_flight_number}' → '{processed_flight_number}'")
    print(f"✅ Airline Code: '{first_segment.get('AirlineCode', '')}' → '{airline_code}'")
    print(f"✅ Refundable: '{first_segment.get('Refundable', '')}' → {first_segment.get('Refundable', 'False').lower() == 'true'}")
    print(f"✅ Duration: '{first_segment.get('JourneyTime', '')}' → {first_segment.get('JourneyTime', '')} minutes")
    
    print("\n📊 SUMMARY:")
    print("-" * 50)
    
    total_fields = len(mappings)
    mapped_fields = sum(1 for v in mappings.values() if v)
    
    print(f"Total FlightOption fields: {total_fields}")
    print(f"Successfully mapped: {mapped_fields}")
    print(f"Mapping success rate: {(mapped_fields/total_fields)*100:.1f}%")
    
    # Check for any missing critical fields
    critical_fields = ['airiq_flight_id', 'airline_code', 'flight_number', 'origin', 'destination']
    missing_critical = [field for field in critical_fields if not mappings.get(field)]
    
    if missing_critical:
        print(f"⚠️  Critical fields missing: {missing_critical}")
    else:
        print("✅ All critical fields mapped successfully")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    analyze_mapping()