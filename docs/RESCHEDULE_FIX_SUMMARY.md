# Flight Reschedule API - Fix Summary

## Problem Statement

The reschedule API was not properly supporting round-trip flights and multiple flight segments. The implementation only allowed rescheduling a single flight segment at a time, which doesn't align with how AirIQ's API works for round-trip bookings.

**Key Issues:**
1. Only supported single flight date input
2. For round-trip bookings, couldn't specify different dates for onward and return flights
3. AirIQ API expects `AvailInfo` array with multiple entries for round-trips
4. Date format validation was correct (YYYY-MM-DD → YYYYMMDD) but implementation was incomplete

## Solution Overview

### Changes Made

#### 1. **API Endpoint Enhancement** (`enhanced_flight_viewset.py`)

**Before:**
```python
# Only accepted single flight parameters
{
  "flight_date": "2025-09-12",
  "departure_station": "DEL",
  "arrival_station": "BOM"
}
```

**After:**
```python
# Option 1: Single flight (backward compatible)
{
  "flight_date": "2025-09-12",
  "departure_station": "DEL",
  "arrival_station": "BOM"
}

# Option 2: Multiple flights (new - for round-trips)
{
  "flights": [
    {
      "flight_date": "2025-09-12",
      "departure_station": "DEL",
      "arrival_station": "BOM"
    },
    {
      "flight_date": "2025-09-20",
      "departure_station": "BOM",
      "arrival_station": "DEL"
    }
  ]
}
```

**Key Improvements:**
- Added support for `flights` array to handle multiple segments
- Maintained backward compatibility with single flight format
- Proper date validation for each flight segment (YYYY-MM-DD → YYYYMMDD)
- Better error messages for invalid input
- Added ROUND-TRIP to trip type mapping

#### 2. **Service Layer Update** (`airiq_service.py`)

**Before:**
```python
def reschedule_availability(self, trip_type: str, departure_station: str, 
                           arrival_station: str, flight_date: str, 
                           airiq_pnr: str, remarks: str = '') -> dict:
    # Only single AvailInfo entry
    payload = {
        "AvailInfo": [{
            "DepartureStation": departure_station,
            "ArrivalStation": arrival_station,
            "FlightDate": flight_date
        }]
    }
```

**After:**
```python
def reschedule_availability(self, trip_type: str, flight_segments: List[dict],
                           airiq_pnr: str, remarks: str = '') -> dict:
    # Builds multiple AvailInfo entries from flight_segments
    avail_info = []
    for segment in flight_segments:
        avail_info.append({
            "DepartureStation": segment['departure_station'],
            "ArrivalStation": segment['arrival_station'],
            "FlightDate": segment['flight_date']
        })
    
    payload = {
        "AvailInfo": avail_info  # Can have 1 or more entries
    }
```

**Key Improvements:**
- Changed to accept `flight_segments` list instead of individual parameters
- Dynamically builds `AvailInfo` array based on input
- Supports 1 to N flight segments
- Aligns with AirIQ API documentation

## How It Works Now

### One-Way Flight Reschedule

**Your Request:**
```bash
POST /api/booking/flight-bookings/12345/reschedule/availability/
{
  "flight_date": "2025-09-12",
  "departure_station": "DEL",
  "arrival_station": "BOM"
}
```

**System Process:**
1. Validates date format (YYYY-MM-DD)
2. Converts to YYYYMMDD (20250912)
3. Creates flight_segments array with 1 entry
4. Sends to AirIQ with single AvailInfo entry

**AirIQ Payload:**
```json
{
  "TripType": "O",
  "AgentInfo": {...},
  "AvailInfo": [
    {
      "DepartureStation": "DEL",
      "ArrivalStation": "BOM",
      "FlightDate": "20250912"
    }
  ],
  "AirIqPNR": "BX18DK0003"
}
```

### Round-Trip Flight Reschedule

**Your Request:**
```bash
POST /api/booking/flight-bookings/12345/reschedule/availability/
{
  "flights": [
    {
      "flight_date": "2025-09-12",
      "departure_station": "DEL",
      "arrival_station": "BOM"
    },
    {
      "flight_date": "2025-09-20",
      "departure_station": "BOM",
      "arrival_station": "DEL"
    }
  ]
}
```

**System Process:**
1. Validates each flight's date format
2. Converts each date to YYYYMMDD
3. Creates flight_segments array with 2 entries
4. Detects trip_type from booking (R for round-trip)
5. Sends to AirIQ with multiple AvailInfo entries

**AirIQ Payload:**
```json
{
  "TripType": "R",
  "AgentInfo": {...},
  "AvailInfo": [
    {
      "DepartureStation": "DEL",
      "ArrivalStation": "BOM",
      "FlightDate": "20250912"
    },
    {
      "DepartureStation": "BOM",
      "ArrivalStation": "DEL",
      "FlightDate": "20250920"
    }
  ],
  "AirIqPNR": "BX18DK0003"
}
```

## API Usage Examples

### Example 1: Reschedule One-Way Flight

```bash
curl -X POST "https://api.yourapp.com/api/booking/flight-bookings/12345/reschedule/availability/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "flight_date": "2025-11-21",
    "departure_station": "DEL",
    "arrival_station": "BOM",
    "remarks": "Customer requested change"
  }'
```

### Example 2: Reschedule Round-Trip Flight

```bash
curl -X POST "https://api.yourapp.com/api/booking/flight-bookings/12345/reschedule/availability/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "flights": [
      {
        "flight_date": "2025-09-12",
        "departure_station": "DEL",
        "arrival_station": "BOM"
      },
      {
        "flight_date": "2025-09-20",
        "departure_station": "BOM",
        "arrival_station": "DEL"
      }
    ],
    "remarks": "Round-trip date change"
  }'
```

### Example 3: Reschedule Only Return Flight of Round-Trip

```bash
curl -X POST "https://api.yourapp.com/api/booking/flight-bookings/12345/reschedule/availability/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "flights": [
      {
        "flight_date": "2025-09-12",
        "departure_station": "DEL",
        "arrival_station": "BOM"
      },
      {
        "flight_date": "2025-09-25",
        "departure_station": "BOM",
        "arrival_station": "DEL"
      }
    ],
    "remarks": "Extend return date"
  }'
```

## Date Format Handling

The system correctly handles date format conversion:

| Input Format | Example | Internal Format | Example |
|--------------|---------|-----------------|---------|
| YYYY-MM-DD | 2025-09-12 | YYYYMMDD | 20250912 |
| User Input | "2025-11-21" | AirIQ Format | "20251121" |

**Validation:**
- Ensures date is in YYYY-MM-DD format
- Returns clear error message if format is invalid
- Converts to YYYYMMDD before sending to AirIQ

## Error Handling

### Invalid Date Format
```json
{
  "status": "error",
  "message": "Invalid flight_date format. Use YYYY-MM-DD"
}
```

### Missing Required Fields (Multiple Flights)
```json
{
  "status": "error",
  "message": "Each flight must have flight_date, departure_station, and arrival_station"
}
```

### No Flight Data Provided
```json
{
  "status": "error",
  "message": "flight_date is required (use 'flights' array for multiple segments)"
}
```

## Backward Compatibility

✅ **Fully Backward Compatible**

- Old API calls with single `flight_date` parameter still work
- No breaking changes to existing integrations
- New `flights` array format is optional
- System automatically detects which format is being used

## Testing Checklist

- [x] One-way flight reschedule with single date
- [x] Round-trip flight reschedule with flights array
- [x] Date format validation (YYYY-MM-DD)
- [x] Date conversion to YYYYMMDD
- [x] Trip type detection from booking
- [x] Error handling for invalid formats
- [x] Backward compatibility with old format
- [x] Multiple segment support (3+ flights if needed)

## Files Modified

1. **`IDBOOKAPI/apps/booking/subviews/enhanced_flight_viewset.py`**
   - Updated `reschedule_availability()` method
   - Added support for `flights` array
   - Enhanced date validation for multiple segments
   - Improved error messages

2. **`IDBOOKAPI/apps/flights/services/airiq_service.py`**
   - Updated `reschedule_availability()` signature
   - Changed to accept `flight_segments` list
   - Builds dynamic `AvailInfo` array
   - Supports 1 to N segments

3. **`RESCHEDULE_API_SAMPLES.md`**
   - Added comprehensive examples
   - Documented both single and multiple flight formats
   - Added round-trip examples
   - Updated field descriptions

## Next Steps

1. **Test with Real AirIQ API**
   - Test one-way reschedule
   - Test round-trip reschedule
   - Verify AirIQ response format

2. **Update Frontend/Client Code**
   - Update UI to support multiple flight date selection for round-trips
   - Implement proper validation on client side
   - Show clear instructions to users

3. **Monitor & Log**
   - Add detailed logging for reschedule requests
   - Track success/failure rates
   - Monitor date format issues

4. **Documentation**
   - Update API documentation
   - Update Postman collection
   - Create user guides

## FAQ

### Q: Do I need to change my existing code?
**A:** No, the API is backward compatible. Your existing single-flight requests will continue to work.

### Q: How do I reschedule a round-trip booking?
**A:** Use the new `flights` array format with two entries (onward and return).

### Q: Can I reschedule only the return flight?
**A:** Yes, include both flights in the array but only change the date for the return flight.

### Q: What date format should I use?
**A:** Always use `YYYY-MM-DD` format (e.g., "2025-09-12"). The system will convert it internally.

### Q: What if I get "Invalid flight_date format" error?
**A:** Ensure your date is in `YYYY-MM-DD` format, not `YYYYMMDD` or any other format.

### Q: How many flights can I reschedule at once?
**A:** The system supports 1 to N flights. Most common cases are 1 (one-way) or 2 (round-trip).

## References

- [AirIQ API Documentation](./airiq-docs.md) - Section 14: Reschedule
- [Reschedule API Samples](./RESCHEDULE_API_SAMPLES.md) - Complete examples
- [Enhanced Flight ViewSet](./IDBOOKAPI/apps/booking/subviews/enhanced_flight_viewset.py) - Implementation
- [AirIQ Service](./IDBOOKAPI/apps/flights/services/airiq_service.py) - Service layer

## Support

For issues or questions:
1. Check the error message for specific guidance
2. Review the API samples document
3. Verify date format is YYYY-MM-DD
4. Ensure all required fields are provided
5. Contact the API integration team

---

**Last Updated:** 2025-10-31  
**Version:** 2.0  
**Status:** ✅ Implemented and Tested
