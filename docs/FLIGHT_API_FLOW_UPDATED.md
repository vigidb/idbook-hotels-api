# Updated IDBOOK Flight Booking API Flow

## Key Changes Made

### 1. **Renamed Search to Availability**
- **Old**: `/api/v1/flights/search/search/` - Created pricing session during search
- **New**: `/api/v1/flights/search/availability/` - Only returns flight options grouped by flight number

### 2. **Flight Grouping by Flight Number**
- **Problem**: Same flight (e.g., AI 131 DEL-BOM 10:30) appeared multiple times with different fares
- **Solution**: Group by flight number + route + time, combine all fare options

### 3. **Separate Pricing Session Creation**
- **Old**: Pricing session created during search
- **New**: Pricing session created only when user selects flights for detailed pricing

## New API Flow

### Step 1: Flight Availability
```
POST /api/v1/flights/search/availability/
{
    "origin": "DEL",
    "destination": "BOM", 
    "departure_date": "2024-12-25",
    "adults": 1,
    "children": 0,
    "infants": 0,
    "trip_type": "O",
    "flight_class": "E"
}
```

**Response Structure**:
```json
{
    "status": "success",
    "data": {
        "flights": [
            {
                "flight_number": "AI 131",
                "airline_code": "AI",
                "airline_name": "Air India",
                "origin": "DEL",
                "destination": "BOM",
                "departure_datetime": "25 Dec 2024 10:30",
                "arrival_datetime": "25 Dec 2024 12:45",
                "duration": "2h 15m",
                "stops": 0,
                "segments": [...],
                "fare_options": [
                    {
                        "fare_key": "token1",
                        "fare_type": "Economy",
                        "base_fare": 4500,
                        "taxes": 1000,
                        "total_fare": 5500,
                        "is_refundable": false,
                        "booking_class": "Q"
                    },
                    {
                        "fare_key": "token2", 
                        "fare_type": "Economy",
                        "base_fare": 5200,
                        "taxes": 1000,
                        "total_fare": 6200,
                        "is_refundable": true,
                        "booking_class": "Y"
                    }
                ],
                "cheapest_fare": { /* cheapest option */ },
                "refundable_fare": { /* cheapest refundable option */ }
            }
        ],
        "search_params": {...},
        "results_count": 15
    }
}
```

### Step 2: Detailed Pricing (Creates Session)
```
POST /api/v1/flights/search/pricing/
{
    "search_params": { /* from availability response */ },
    "selected_flights": [
        {
            "flight_number": "AI 131",
            "selected_fare": {
                "fare_key": "token1",
                "total_fare": 5500
            }
        }
    ],
    "ancillary_services": {
        "seats": [],
        "meals": [],
        "baggage": []
    }
}
```

**Response**: Creates pricing session + detailed breakdown

### Step 3: Booking (Existing)
Uses the pricing session from Step 2

## Benefits of Changes

✅ **Cleaner UX**: Users see flights grouped by flight number, not scattered
✅ **Multiple Fare Options**: Users can compare refundable vs non-refundable for same flight  
✅ **Efficient**: No session created unless user proceeds to pricing
✅ **Better Performance**: Less storage, faster availability search
✅ **Scalable**: Can handle multiple fare classes per flight

## Implementation Details

### Flight Grouping Logic
- **Group Key**: `{flight_number}_{origin}_{destination}_{departure_time}`
- **Fare Sorting**: Cheapest fare shown first, refundable fare highlighted
- **Multiple Classes**: Economy Basic, Economy Flex, Premium, Business

### Session Management  
- **Session Creation**: Only when user selects specific flights + fares
- **Session Duration**: 15 minutes (extendable)
- **Session Content**: Selected flights + pricing breakdown + ancillary services

### Error Handling
- **AirIQ Failures**: Graceful fallback with proper error messages
- **Session Expiry**: Clear messaging and session extension options
- **Validation**: Comprehensive input validation for all endpoints