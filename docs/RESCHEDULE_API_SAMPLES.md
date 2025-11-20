# Flight Reschedule API - Sample Requests

This document provides complete sample requests for the reschedule functionality based on AirIQ API v2.0 documentation.

## 1. Reschedule Availability

### Endpoint
```
POST /api/booking/flight-bookings/{booking_id}/reschedule/availability/
```

### Headers
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer YOUR_AUTH_TOKEN"
}
```

### Request Body Formats

**Option 1: Single Flight (One-Way) - Simple Format**
```json
{
  "flight_date": "2025-11-21",
  "departure_station": "DEL",
  "arrival_station": "BOM",
  "remarks": "Customer requested date change"
}
```

**Option 2: Multiple Flights (Round-Trip) - Array Format**
```json
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
  ],
  "remarks": "Round-trip reschedule"
}
```

### Field Descriptions

| Field | Type | Required | Format | Description |
|-------|------|----------|--------|-------------|
| `flight_date` | string | Yes* | YYYY-MM-DD | New flight date (for single flight format) |
| `departure_station` | string | No* | IATA Code | 3-letter departure airport code (for single flight) |
| `arrival_station` | string | No* | IATA Code | 3-letter arrival airport code (for single flight) |
| `flights` | array | Yes** | Array | Array of flight segments (for round-trip/multi-segment) |
| `flights[].flight_date` | string | Yes | YYYY-MM-DD | Flight date for this segment |
| `flights[].departure_station` | string | Yes | IATA Code | 3-letter departure airport code |
| `flights[].arrival_station` | string | Yes | IATA Code | 3-letter arrival airport code |
| `remarks` | string | No | Text | Optional remarks for the request |

*Required for single flight format  
**Required for multi-segment format

### Complete Example - One-Way Flight

**Request:**
```bash
curl -X POST "https://api.yourapp.com/api/booking/flight-bookings/12345/reschedule/availability/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "flight_date": "2025-09-12",
    "departure_station": "DEL",
    "arrival_station": "BOM",
    "remarks": "Reschedule to September"
  }'
```

**Internal AirIQ Payload (Auto-generated):**
```json
{
  "TripType": "O",
  "AgentInfo": {
    "AgentId": "YOUR_AGENT_ID",
    "UserName": "your_username",
    "AppType": "API",
    "Version": 2.0
  },
  "AvailInfo": [
    {
      "DepartureStation": "DEL",
      "ArrivalStation": "BOM",
      "FlightDate": "20250912"
    }
  ],
  "AiriqPNR": "BX18DK0003",
  "Remarks": "Reschedule to September"
}
```

### Complete Example - Round Trip

**Request (New Array Format - Recommended):**
```bash
curl -X POST "https://api.yourapp.com/api/booking/flight-bookings/67890/reschedule/availability/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
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
    "remarks": "Round-trip reschedule"
  }'
```

**Internal AirIQ Payload (Auto-generated for Round-Trip):**
```json
{
  "TripType": "R",
  "AgentInfo": {
    "AgentId": "YOUR_AGENT_ID",
    "UserName": "your_username",
    "AppType": "API",
    "Version": 2.0
  },
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
  "AiriqPNR": "BX18DK0003",
  "Remarks": "Round-trip reschedule"
}
```

### Success Response Example
```json
{
  "status": "success",
  "message": "Reschedule availability retrieved",
  "data": {
    "reschedule_availability": {
      "Trackid": "AQ1529473540502431215295031386525F6RGWLZIXC",
      "ItineraryFlightList": [
        {
          "Items": [
            {
              "FlightDetails": [
                {
                  "FlightID": "4752",
                  "AirlineDescription": "6E",
                  "FlightNumber": "6E 853",
                  "Origin": "DEL",
                  "Destination": "BOM",
                  "DepartureTerminal": "1",
                  "ArrivalTerminal": "2",
                  "DepartureDateTime": "12 Sep 2025 01:55",
                  "ArrivalDateTime": "12 Sep 2025 04:15",
                  "Class": "R",
                  "JourneyTime": "140",
                  "Cabin": "E",
                  "FareBasisCode": "AA07",
                  "Stops": "0",
                  "AirlineCategory": "LCC",
                  "AvailSeat": "30",
                  "Refundable": "True",
                  "Baggage": "15kg"
                }
              ],
              "Fares": [
                {
                  "Currency": "INR",
                  "FareType": "N",
                  "Faredescription": [
                    {
                      "Paxtype": "ADT",
                      "BaseAmount": "1250",
                      "TotalTaxAmount": "691",
                      "GrossAmount": "1941",
                      "NetAmount": "1902.18"
                    }
                  ],
                  "FlightId": "6E0"
                }
              ]
            }
          ]
        }
      ],
      "Status": {
        "Error": "",
        "ResultCode": "1",
        "SequenceID": "15294735405024312"
      }
    }
  }
}
```

### Error Response Examples

**Invalid Date Format:**
```json
{
  "status": "error",
  "message": "Invalid flight_date format. Use YYYY-MM-DD",
  "data": {}
}
```

**Missing AirIQ PNR:**
```json
{
  "status": "error",
  "message": "AirIQ PNR missing on booking",
  "data": {}
}
```

**AirIQ API Failure:**
```json
{
  "status": "error",
  "message": "Unable to fetch reschedule availability: Unable to get avail flight details for the requested PNR. Kindly contact customer care.",
  "data": {}
}
```

---

## 2. Reschedule Confirmation

### Endpoint
```
POST /api/booking/flight-bookings/{booking_id}/reschedule/confirm/
```

### Headers
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer YOUR_AUTH_TOKEN"
}
```

### Request Body Format
```json
{
  "track_id": "AQ1529473540502431215295031386525F6RGWLZIXC",
  "contact_no": "9876543210",
  "remarks": "Confirmed new flight",
  "flag": "CONFIRM",
  "flight_details": {
    "origin": "DEL",
    "destination": "BOM",
    "trip_type": "O",
    "base_amount": 1250,
    "gross_amount": 1941,
    "segments": [
      {
        "FlightID": "4752",
        "FlightNumber": "6E 853",
        "Origin": "DEL",
        "Destination": "BOM",
        "DepartureDateTime": "12 Sep 2025 01:55",
        "ArrivalDateTime": "12 Sep 2025 04:15"
      }
    ]
  }
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `track_id` | string | Yes | Track ID from reschedule availability response |
| `contact_no` | string | Yes | Customer contact number |
| `remarks` | string | No | Optional remarks |
| `flag` | string | No | "CHECKFARE" or "CONFIRM" (default: "CONFIRM") |
| `flight_details` | object | Yes | Complete flight details object |
| `flight_details.origin` | string | Yes | 3-letter IATA origin code |
| `flight_details.destination` | string | Yes | 3-letter IATA destination code |
| `flight_details.trip_type` | string | Yes | "O" (One-way), "R" (Round-trip), or "Y" (Round-trip Special) |
| `flight_details.base_amount` | number | Yes | Base fare amount |
| `flight_details.gross_amount` | number | Yes | Total amount including taxes |
| `flight_details.segments` | array | Yes | Array of flight segment objects |

### Segment Object Structure
```json
{
  "FlightID": "4752",
  "FlightNumber": "6E 853",
  "Origin": "DEL",
  "Destination": "BOM",
  "DepartureDateTime": "12 Sep 2025 01:55",
  "ArrivalDateTime": "12 Sep 2025 04:15"
}
```

### Complete Example - One-Way Direct Flight

**Request:**
```bash
curl -X POST "https://api.yourapp.com/api/booking/flight-bookings/12345/reschedule/confirm/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "track_id": "AQ1529473540502431215295031386525F6RGWLZIXC",
    "contact_no": "9876543210",
    "remarks": "Rescheduled due to urgent work",
    "flag": "CONFIRM",
    "flight_details": {
      "origin": "DEL",
      "destination": "BOM",
      "trip_type": "O",
      "base_amount": 1250,
      "gross_amount": 1941,
      "segments": [
        {
          "FlightID": "4752",
          "FlightNumber": "6E 853",
          "Origin": "DEL",
          "Destination": "BOM",
          "DepartureDateTime": "12 Sep 2025 01:55",
          "ArrivalDateTime": "12 Sep 2025 04:15"
        }
      ]
    }
  }'
```

### Complete Example - One-Way with Connection

**Request:**
```bash
curl -X POST "https://api.yourapp.com/api/booking/flight-bookings/12345/reschedule/confirm/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "track_id": "AQ1529473540502431215295031386525F6RGWLZIXC",
    "contact_no": "9876543210",
    "remarks": "Connection flight selected",
    "flag": "CONFIRM",
    "flight_details": {
      "origin": "IXB",
      "destination": "DEL",
      "trip_type": "O",
      "base_amount": 15900,
      "gross_amount": 19873,
      "segments": [
        {
          "FlightID": "7368",
          "FlightNumber": "6E 292",
          "Origin": "IXB",
          "Destination": "CCU",
          "DepartureDateTime": "14 Nov 2023 14:20",
          "ArrivalDateTime": "14 Nov 2023 15:25"
        },
        {
          "FlightID": "7369",
          "FlightNumber": "6E 2516",
          "Origin": "CCU",
          "Destination": "DEL",
          "DepartureDateTime": "14 Nov 2023 16:50",
          "ArrivalDateTime": "14 Nov 2023 19:25"
        }
      ]
    }
  }'
```

### Complete Example - Check Fare Before Confirmation

**Request:**
```bash
curl -X POST "https://api.yourapp.com/api/booking/flight-bookings/12345/reschedule/confirm/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -d '{
    "track_id": "AQ1529473540502431215295031386525F6RGWLZIXC",
    "contact_no": "9876543210",
    "remarks": "Check fare first",
    "flag": "CHECKFARE",
    "flight_details": {
      "origin": "DEL",
      "destination": "BOM",
      "trip_type": "O",
      "base_amount": 1250,
      "gross_amount": 1941,
      "segments": [
        {
          "FlightID": "4752",
          "FlightNumber": "6E 853",
          "Origin": "DEL",
          "Destination": "BOM",
          "DepartureDateTime": "12 Sep 2025 01:55",
          "ArrivalDateTime": "12 Sep 2025 04:15"
        }
      ]
    }
  }'
```

### Success Response Example
```json
{
  "status": "success",
  "message": "Reschedule processed",
  "data": {
    "reschedule_response": {
      "Status": {
        "Error": "",
        "ResultCode": "1",
        "SequenceID": "15060631274218514"
      },
      "AgentInfo": {
        "AgentId": "YOUR_AGENT_ID",
        "UserName": "your_username",
        "AppType": "API",
        "Version": 2.0
      },
      "AiriqPNR": "BT27GF0027",
      "Trackid": "AQ1529473540502431215295031386525F6RGWLZIXC"
    }
  }
}
```

### Error Response Examples

**Missing Required Fields:**
```json
{
  "status": "error",
  "message": "track_id, contact_no and flight_details are required",
  "data": {}
}
```

**Missing PNRs:**
```json
{
  "status": "error",
  "message": "PNRs missing on booking",
  "data": {}
}
```

**AirIQ API Failure:**
```json
{
  "status": "error",
  "message": "Unable to process reschedule: Unable to Reschedule for the requested PNR. Kindly contact customer care.",
  "data": {}
}
```

---

## 3. Internal AirIQ Payload Reference

### Reschedule Availability (RescheduleAvail)

The system automatically converts your request to AirIQ format:

**One-Way Flight - Your Request:**
```json
{
  "flight_date": "2025-09-12",
  "departure_station": "DEL",
  "arrival_station": "BOM"
}
```

**Converted to AirIQ:**
```json
{
  "TripType": "O",
  "AgentInfo": {
    "AgentId": "AGENT_ID_FROM_ENV",
    "UserName": "USERNAME_FROM_ENV",
    "AppType": "API",
    "Version": 2.0
  },
  "AvailInfo": [
    {
      "DepartureStation": "DEL",
      "ArrivalStation": "BOM",
      "FlightDate": "20250912"
    }
  ],
  "AirIqPNR": "FROM_BOOKING_RECORD",
  "Remarks": "FROM_YOUR_REQUEST"
}
```

**Round-Trip - Your Request:**
```json
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

**Converted to AirIQ:**
```json
{
  "TripType": "R",
  "AgentInfo": {
    "AgentId": "AGENT_ID_FROM_ENV",
    "UserName": "USERNAME_FROM_ENV",
    "AppType": "API",
    "Version": 2.0
  },
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
  "AirIqPNR": "FROM_BOOKING_RECORD",
  "Remarks": "FROM_YOUR_REQUEST"
}
```

### Reschedule Confirmation (Reschedule)

**Your Request:**
```json
{
  "track_id": "TRACK_ID_FROM_AVAILABILITY",
  "contact_no": "9876543210",
  "flag": "CONFIRM",
  "flight_details": {
    "origin": "DEL",
    "destination": "BOM",
    "trip_type": "O",
    "base_amount": 1250,
    "gross_amount": 1941,
    "segments": [...]
  }
}
```

**Converted to AirIQ:**
```json
{
  "AgentInfo": {
    "AgentId": "AGENT_ID_FROM_ENV",
    "UserName": "USERNAME_FROM_ENV",
    "AppType": "API",
    "Version": 2.0
  },
  "SegmentInfo": {
    "BaseOrigin": "DEL",
    "BaseDestination": "BOM",
    "TripType": "O"
  },
  "Trackid": "TRACK_ID_FROM_AVAILABILITY",
  "AirIqPNR": "FROM_BOOKING_RECORD",
  "Remarks": "FROM_YOUR_REQUEST",
  "Flag": "CONFIRM",
  "ContactNo": "9876543210",
  "ItineraryInfo": [
    {
      "FlightDetails": [...],
      "BaseAmount": "1250",
      "GrossAmount": "1941"
    }
  ]
}
```

---

## 4. Key Points to Remember

### Date Format
- **Your API Input:** `YYYY-MM-DD` (e.g., "2025-09-12")
- **AirIQ Internal:** `YYYYMMDD` (e.g., "20250912")
- The system automatically converts the date format

### Trip Types
- `O` = One-way
- `R` = Round-trip
- `Y` = Round-trip Special

### Flags for Reschedule Confirmation
- `CHECKFARE` = Check the fare before confirming
- `CONFIRM` = Directly confirm the reschedule

### DateTime Format in Segments
- Format: `DD MMM YYYY HH:MM`
- Example: "12 Sep 2025 01:55"

### PNR Requirements
- **Reschedule Availability:** Requires `airiq_pnr` only
- **Reschedule Confirmation:** Requires both `airiq_pnr` and `airline_pnr`

---

## 5. Testing Workflow

### Step 1: Get Reschedule Availability

**For One-Way Flight:**
```bash
POST /api/booking/flight-bookings/12345/reschedule/availability/
{
  "flight_date": "2025-09-12",
  "departure_station": "DEL",
  "arrival_station": "BOM"
}
```

**For Round-Trip Flight:**
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

### Step 2: Extract Required Information
From the availability response, extract:
- `Trackid` (required for confirmation)
- `FlightID` from selected flight
- `FlightNumber`
- `Origin`, `Destination`
- `DepartureDateTime`, `ArrivalDateTime`
- `BaseAmount`, `GrossAmount` from Fares

### Step 3: Confirm Reschedule
```bash
POST /api/booking/flight-bookings/12345/reschedule/confirm/
{
  "track_id": "EXTRACTED_TRACKID",
  "contact_no": "9876543210",
  "flag": "CONFIRM",
  "flight_details": {
    "origin": "EXTRACTED_ORIGIN",
    "destination": "EXTRACTED_DESTINATION",
    "trip_type": "O",
    "base_amount": EXTRACTED_BASE_AMOUNT,
    "gross_amount": EXTRACTED_GROSS_AMOUNT,
    "segments": [EXTRACTED_FLIGHT_DETAILS]
  }
}
```

---

## 6. Postman Collection

You can import these examples into Postman:

### Environment Variables
```json
{
  "base_url": "https://api.yourapp.com",
  "auth_token": "YOUR_AUTH_TOKEN",
  "booking_id": "12345"
}
```

### Collection Structure
1. **Reschedule Availability**
   - Method: POST
   - URL: `{{base_url}}/api/booking/flight-bookings/{{booking_id}}/reschedule/availability/`
   - Headers: Authorization: Bearer {{auth_token}}
   - Body: See examples above

2. **Reschedule Confirmation**
   - Method: POST
   - URL: `{{base_url}}/api/booking/flight-bookings/{{booking_id}}/reschedule/confirm/`
   - Headers: Authorization: Bearer {{auth_token}}
   - Body: See examples above

---

## 7. Common Issues and Solutions

### Issue: "Invalid flight_date format"
**Solution:** Ensure date is in `YYYY-MM-DD` format, not `YYYYMMDD`

### Issue: "AirIQ PNR missing on booking"
**Solution:** Booking must have a valid AirIQ PNR from successful booking

### Issue: "PNRs missing on booking"
**Solution:** For confirmation, booking must have both `airiq_pnr` and `airline_pnr`

### Issue: "track_id, contact_no and flight_details are required"
**Solution:** All three fields must be present in the confirmation request

### Issue: AirIQ returns "Unable to get avail flight details"
**Solution:** Check if:
- The PNR is valid and not already traveled
- The date is in the future
- The route matches the original booking

---

## Contact
For additional support, refer to the AirIQ API documentation or contact the API integration team.
