# AirIQ JSON Keys vs API Response Keys Comparison

## Field Mapping Analysis

Based on your AirIQ response structure and FlightOptionSerializer, here's the detailed field mapping comparison:

### ✅ **MATCHED FIELDS** (AirIQ → API Response)

| AirIQ JSON Key | API Response Key | Status | Notes |
|----------------|------------------|---------|-------|
| `FlightID` | `airiq_flight_id` | ✅ Match | Internal tracking ID |
| `AirlineCode` | `airline_code` | ✅ Match | 2-letter airline code (6E, UK, etc.) |
| `FlightNumber` | `flight_number` | ✅ Match | Flight number (processed to remove airline code) |
| `Origin` | `origin` | ✅ Match | Origin airport IATA code |
| `Destination` | `destination` | ✅ Match | Destination airport IATA code |
| `DepartureDateTime` | `departure_datetime` | ✅ Match | Parsed and timezone-aware |
| `ArrivalDateTime` | `arrival_datetime` | ✅ Match | Parsed and timezone-aware |
| `Class` | `flight_class` | ✅ Match | Flight class (E, B, F) |
| `FareBasisCode` | `fare_basis` | ✅ Match | Fare basis code |
| `AirlineCategory` | `airline_category` | ✅ Match | LCC/FSC category |
| `Stops` | `stops` | ✅ Match | Number of stops |
| `JourneyTime` | `duration_minutes` | ✅ Match | Converted to minutes |
| `AirCraftType` | `aircraft_type` | ✅ Match | Aircraft type |
| `AvailSeat` | `available_seats` | ✅ Match | Available seats |
| `Baggage` | `baggage_info` | ✅ Match | Stored as JSON object |
| `Refundable` | `is_refundable` | ✅ Match | Boolean conversion |
| `Fares[0].Faredescription[0].BaseAmount` | `base_fare` | ✅ Match | Base fare amount |
| `Fares[0].Faredescription[0].TotalTaxAmount` | `taxes` | ✅ Match | Tax amount |
| `Fares[0].Faredescription[0].GrossAmount` | `total_fare` | ✅ Match | Total fare amount |

### 🔄 **TRANSFORMED/ENHANCED FIELDS**

| AirIQ Data | API Response Key | Transformation |
|------------|------------------|----------------|
| `AirlineCode` | `airline_info` | Enriched with airline name, category, logo from database |
| `Origin` | `origin_info` | Enriched with airport name, city, country from database |
| `Destination` | `destination_info` | Enriched with airport name, city, country from database |
| `DepartureDateTime` | `formatted_departure` | Formatted into date, time, datetime objects |
| `ArrivalDateTime` | `formatted_arrival` | Formatted into date, time, datetime objects |
| `JourneyTime` | `formatted_duration` | Formatted as "2h 20m" format |

### ➕ **API-ONLY FIELDS**

| API Response Key | Source | Purpose |
|------------------|--------|---------|
| `id` | Database | Primary key for FlightOption |
| `can_hold` | System | Whether booking can be held (always true for AirIQ) |
| `fare_rules` | Database/AirIQ | Fare rules (stored as JSON) |

### ❌ **NOT USED FROM AIRIQ**

| AirIQ JSON Key | Reason Not Used |
|----------------|-----------------|
| `AirlineDescription` | Used for fallback only, prefer `AirlineCode` |
| `Currency` | Assumed to be INR |
| `FareType` | Not mapped to API response |
| `FareDescription` | Not included in response |

## Sample Comparison

### AirIQ Response:
```json
{
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
    "Faredescription": [{
      "BaseAmount": 4500.0,
      "TotalTaxAmount": 1200.0,
      "GrossAmount": 5700.0
    }]
  }]
}
```

### Your API Response:
```json
{
  "id": 257,
  "airiq_flight_id": "9603",
  "airline_code": "6E",
  "flight_number": "2142",
  "origin": "DEL",
  "destination": "BOM",
  "departure_datetime": "2023-11-14T14:20:00+05:30",
  "arrival_datetime": "2023-11-14T16:40:00+05:30",
  "flight_class": "E",
  "fare_basis": "ECOFLY",
  "airline_category": "LCC",
  "stops": 0,
  "duration_minutes": 140,
  "aircraft_type": "A320",
  "base_fare": "4500.00",
  "taxes": "1200.00",
  "total_fare": "5700.00",
  "available_seats": 9,
  "baggage_info": {"checked": "15kg"},
  "is_refundable": true,
  "can_hold": true,
  "airline_info": {
    "code": "6E",
    "name": "IndiGo",
    "category": "LCC",
    "logo_url": null
  },
  "origin_info": {
    "iata_code": "DEL",
    "name": "Indira Gandhi International Airport",
    "city": "New Delhi",
    "country": "India"
  },
  "destination_info": {
    "iata_code": "BOM",
    "name": "Chhatrapati Shivaji Maharaj International Airport",
    "city": "Mumbai",
    "country": "India"
  },
  "formatted_departure": {
    "date": "2023-11-14",
    "time": "14:20",
    "datetime": "2023-11-14 14:20"
  },
  "formatted_arrival": {
    "date": "2023-11-14",
    "time": "16:40", 
    "datetime": "2023-11-14 16:40"
  },
  "formatted_duration": "2h 20m"
}
```

## Key Mapping Rules Applied

1. **Direct Mapping**: Most fields map 1:1 with appropriate data type conversion
2. **Data Enhancement**: Basic fields are enriched with additional information from your database
3. **Format Standardization**: 
   - Datetimes are converted to ISO format with timezone
   - Flight numbers cleaned (airline code removed if duplicated)
   - Duration converted to minutes and formatted
   - Fares converted to decimal format
4. **Nested Structure Flattening**: AirIQ's nested fare structure is flattened to top-level fields
5. **Boolean Conversion**: String "True"/"False" converted to actual booleans

## Conclusion

✅ **YES, the field mappings are correctly aligned!**

The parsing logic correctly maps all relevant AirIQ JSON keys to your API response keys. The transformation includes:
- Direct field mapping where appropriate
- Data type conversions (string to boolean, string to decimal, etc.)
- Format standardization (datetime, duration, etc.)
- Data enrichment with additional information from your database
- Nested structure flattening for easier consumption

Your API response provides a much richer and more standardized format compared to the raw AirIQ response, making it easier for frontend applications to consume.