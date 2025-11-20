# AirIQ Flight Booking API Endpoints

## Overview
Complete implementation of AirIQ API integration with full documentation compliance for flight booking operations.

## Core Flight Operations

### Flight Search
**POST** `/api/v1/flights/search/`
- Real-time flight search via AirIQ API
- Inventory-based search support
- Supports one-way, round-trip, and round-trip special
- Comprehensive filtering and sorting

### Flight Pricing
**POST** `/api/v1/flights/pricing/price/`
- Detailed pricing breakdown
- Multi-passenger type support
- SSR pricing included
- Real-time fare validation

**POST** `/api/v1/flights/pricing/fare-rules/`
- Fare rules and conditions
- Cancellation policies
- Baggage allowances
- Refund conditions

### Multi-Class Support
**POST** `/api/v1/flights/pricing/multi-class/`
- Available classes for flights
- Seat availability by class
- Class-specific features

**POST** `/api/v1/flights/pricing/multi-class-fare/`
- Fare pricing by class
- Class upgrade options
- Premium service costs

### Account Management
**GET** `/api/v1/flights/pricing/account-balance/`
- Agent account balance
- Credit and topup balances
- Transaction history

## Booking Management

### Create Booking
**POST** `/api/v1/flights/bookings/`
- Complete booking creation
- Passenger validation (AirIQ compliant)
- GST information handling
- SSR services integration
- Frequent flyer support

### Booking Operations
**GET** `/api/v1/flights/bookings/{id}/`
- Retrieve booking details
- Passenger information
- Payment status
- Service details

**GET** `/api/v1/flights/bookings/{id}/track-status/`
- Real-time booking status
- AirIQ status synchronization
- Payment confirmation status

### Booking Modifications
**POST** `/api/v1/flights/bookings/{id}/reschedule-availability/`
- Available flights for reschedule
- Fare difference calculation
- Change fee information

**POST** `/api/v1/flights/bookings/{id}/reschedule/`
- Execute booking reschedule
- Payment processing
- Confirmation handling

**POST** `/api/v1/flights/bookings/{id}/cancel-hold/`
- Cancel held bookings
- Release inventory
- Refund processing

## Ancillary Services (SSR)

### Service Discovery
**GET** `/api/v1/flights/bookings/{id}/ssr-services/`
- Available meals, seats, baggage
- Service pricing
- Availability by segment
- Passenger-specific options

### Service Addition
**POST** `/api/v1/flights/bookings/{id}/add-ssr/`
- Add meals, seats, baggage
- Extra services (insurance, priority boarding)
- Payment processing
- Service confirmation

## Master Data

### Airports
**GET** `/api/v1/flights/airports/`
- IATA airport codes
- City and country information
- Search functionality
- Active airport list

### Airlines
**GET** `/api/v1/flights/airlines/`
- Airline codes and names
- Carrier categories (FSC/LCC)
- Active airline list

## Key Features Implemented

### Authentication & Security
- ✅ Base64 authentication header (AgentID*Username:Password)
- ✅ Token caching with database persistence
- ✅ Daily token limit management
- ✅ Automatic token refresh

### Data Validation
- ✅ GST format validation (15-character pattern)
- ✅ Passenger detail validation (titles, types, documents)
- ✅ Complete/partial GST information validation
- ✅ Date format standardization

### AirIQ API Coverage
- ✅ Login - Authentication with token caching
- ✅ Availability - Flight search with all parameters
- ✅ GetFareRule - Fare conditions and policies
- ✅ Pricing - Detailed fare breakdown
- ✅ GetAvailSeatMap - Seat selection interface
- ✅ Book - Comprehensive booking creation
- ✅ IssueTicket - Ticket confirmation for held bookings
- ✅ RetrieveBooking - Booking information retrieval
- ✅ GetBalance - Agent account balance
- ✅ TrackStatus - Booking status monitoring
- ✅ Cancel - Booking cancellation with penalties
- ✅ RescheduleAvail - Reschedule option discovery
- ✅ Reschedule - Booking date/time changes
- ✅ GetSSR - Available ancillary services
- ✅ AddSSR - Service addition to bookings
- ✅ HoldCancel - Held booking cancellation
- ✅ GetMultiClass - Class availability
- ✅ GetMultiClassFare - Class-specific pricing

### Response Format Compliance
- ✅ Success responses (ResultCode: "1")
- ✅ Failure responses (ResultCode: "0")
- ✅ Exception responses (ResultCode: "-1")
- ✅ Pending responses (ResultCode: "2", "-2")
- ✅ Proper error message handling

### Booking Flow Features
- ✅ Complete passenger validation
- ✅ SSR service integration
- ✅ GST information handling
- ✅ Frequent flyer program support
- ✅ Hold and immediate ticketing options
- ✅ Multi-segment flight support

### Quality Assurance
- ✅ Comprehensive test suite
- ✅ Mock API testing
- ✅ Error handling validation
- ✅ Data format compliance testing
- ✅ Integration test framework

## Request/Response Examples

### Flight Search Request
```json
{
  "origin": "DEL",
  "destination": "BOM",
  "departure_date": "2023-12-01",
  "trip_type": "O",
  "flight_class": "E",
  "adults": 1,
  "children": 0,
  "infants": 0,
  "search_mode": "BOTH"
}
```

### Booking Creation Request
```json
{
  "flight_option": 123,
  "passengers": [
    {
      "title": "MR",
      "first_name": "John",
      "last_name": "Doe",
      "date_of_birth": "01/01/1990",
      "gender": "Male",
      "passenger_type": "ADT"
    }
  ],
  "contact": {
    "country_code": "91",
    "phone": "9876543210",
    "email": "john.doe@example.com"
  },
  "gst": {
    "number": "22AAAAA0000A1Z5",
    "company_name": "Test Company",
    "address": "Test Address",
    "email": "gst@company.com",
    "mobile": "9876543210"
  },
  "hold_booking": false
}
```

### SSR Addition Request
```json
{
  "track_id": "AQ143613790123208541436182601064CGDVYIH6EK0",
  "meals_ssr": [{"PaxRefId": "1", "SegmentNo": "1", "MealId": "6785"}],
  "baggage_ssr": [{"PaxRefId": "1", "BaggId": "9735"}],
  "seats_ssr": [{"PaxRefId": "1", "SeatId": "6600"}],
  "payment_amount": 5109,
  "remarks": "Additional services"
}
```

## Error Handling

All endpoints follow standardized error response format:
```json
{
  "status": "error",
  "message": "Descriptive error message",
  "error_code": "ERROR_CODE",
  "errors": {},
  "timestamp": "2023-12-01T10:00:00Z"
}
```

## Authentication
All protected endpoints require JWT authentication:
```
Authorization: Bearer <jwt_token>
```

## Rate Limits
- AirIQ token generation: Maximum 2 per day
- API calls: Standard rate limits as per AirIQ documentation

## Support
For technical support or API issues:
- Check AirIQ API logs in Django admin
- Review comprehensive test coverage
- Contact AirIQ support: biki.mandal@airiq.in

---
*Last Updated: October 2024*
*AirIQ API Version: 2.0*