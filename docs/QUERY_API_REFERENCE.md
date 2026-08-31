# Query API Reference - Complete Workflow

**Base URL:** `{{base_url}}/api/v1/booking/queries/`

## Query Status Flow
```
pending → documents_reviewed (Visa only) → quoted → confirmed → completed
                                                  ↓
                                              cancelled
```

## Available Query Types
- `VISA` - Visa processing
- `EVENT` - Events and conferences
- `VEHICLE` - Cab/Vehicle bookings
- `HOTEL` - Hotel group bookings
- `FLIGHT` - Flight group bookings
- `HOLIDAYPACK` - Holiday packages

---

## 1. VISA Query Workflow

### 1.1 Create VISA Query (B2C Customer)
```
POST /api/v1/booking/queries/
Authorization: Bearer {{token}}  (Optional - can be guest)
Content-Type: application/json
```

```json
{
    "query_type": "VISA",
    "booking_for": "B2C",
    "query_data": {
        "destination_country": "United States",
        "travel_date": "2025-03-15",
        "visa_type": "tourist",
        "passport_number": "J1234567",
        "passport_expiry": "2030-06-15",
        "travel_purpose": "Tourism and leisure travel for 2 weeks",
        "traveler_name": "John Doe",
        "traveler_email": "john.doe@example.com",
        "traveler_phone": "+91-9876543210",
        "traveler_nationality": "Indian",
        "adult_count": 2,
        "child_count": 1,
        "documents_available": ["passport", "bank_statement", "employment_letter"]
    },
    "expires_at": "2025-02-28T23:59:59Z"
}
```

### 1.2 Create VISA Query (Corporate)
```json
{
    "query_type": "VISA",
    "booking_for": "CORPORATE",
    "company": 1,
    "referred_by": 5,
    "referral_type": "EMPLOYEE",
    "query_data": {
        "destination_country": "Singapore",
        "travel_date": "2025-04-10",
        "visa_type": "business",
        "travelers": [
            {
                "name": "Rahul Sharma",
                "passport_number": "K7654321",
                "passport_expiry": "2029-08-20",
                "designation": "Senior Manager"
            },
            {
                "name": "Priya Singh",
                "passport_number": "K7654322",
                "passport_expiry": "2028-12-15",
                "designation": "Project Lead"
            }
        ],
        "travel_purpose": "Business meeting with Singapore branch",
        "company_invitation_letter": true,
        "adult_count": 2,
        "trip_duration": "5 days"
    },
    "expires_at": "2025-03-20T23:59:59Z"
}
```

---

## 2. EVENT Query Workflow

### 2.1 Create Corporate Conference Query
```
POST /api/v1/booking/queries/
Authorization: Bearer {{token}}
Content-Type: application/json
```

```json
{
    "query_type": "EVENT",
    "booking_for": "CORPORATE",
    "company": 1,
    "referred_by": 3,
    "referral_type": "EMPLOYEE",
    "query_data": {
        "event_name": "Annual Sales Conference 2025",
        "event_type": "conference",
        "event_date": "2025-05-15T09:00:00Z",
        "event_end_date": "2025-05-17T18:00:00Z",
        "location": "Bangalore",
        "preferred_venues": ["Taj West End", "ITC Gardenia", "JW Marriott"],
        "attendee_count": 150,
        "budget_range": "250000_500000",
        "requirements": {
            "conference_hall": true,
            "breakout_rooms": 4,
            "accommodation": 100,
            "meals": ["breakfast", "lunch", "dinner", "tea_breaks"],
            "av_equipment": true,
            "transportation": true
        },
        "special_requirements": "Need stage setup for keynote, live streaming capability",
        "contact_person": {
            "name": "Amit Kumar",
            "email": "amit.kumar@company.com",
            "phone": "+91-9876543210"
        }
    },
    "expires_at": "2025-04-01T23:59:59Z"
}
```

### 2.2 Create Wedding Event Query (B2C)
```json
{
    "query_type": "EVENT",
    "booking_for": "B2C",
    "query_data": {
        "event_name": "Sharma - Gupta Wedding",
        "event_type": "wedding",
        "event_date": "2025-11-20T18:00:00Z",
        "event_end_date": "2025-11-22T23:00:00Z",
        "location": "Jaipur",
        "attendee_count": 500,
        "budget_range": "above_500000",
        "wedding_functions": [
            {"function": "Mehndi", "date": "2025-11-20", "guests": 200},
            {"function": "Sangeet", "date": "2025-11-21", "guests": 350},
            {"function": "Wedding Ceremony", "date": "2025-11-22", "guests": 500}
        ],
        "requirements": {
            "venue_type": "Palace/Heritage",
            "accommodation_rooms": 150,
            "catering": "Pure Vegetarian",
            "decoration": "Traditional with Modern Touch",
            "photography": true,
            "entertainment": ["DJ", "Live Band", "Traditional Dancers"]
        },
        "contact_person": {
            "name": "Rajesh Sharma",
            "email": "rajesh.sharma@gmail.com",
            "phone": "+91-9876543211"
        }
    },
    "expires_at": "2025-08-01T23:59:59Z"
}
```

---

## 3. VEHICLE/CAB Query Workflow

### 3.1 Outstation Trip Query
```
POST /api/v1/booking/queries/
```

```json
{
    "query_type": "VEHICLE",
    "booking_for": "B2C",
    "query_data": {
        "trip_type": "outstation",
        "pickup_location": "Delhi Airport (DEL)",
        "drop_location": "Agra (Taj Mahal)",
        "pickup_datetime": "2025-02-14T06:00:00Z",
        "return_datetime": "2025-02-15T20:00:00Z",
        "vehicle_type": "CAR",
        "vehicle_preference": "SUV",
        "passenger_count": 4,
        "luggage_count": 4,
        "additional_stops": ["Mathura (Krishna Temple)", "Vrindavan"],
        "special_requirements": "AC vehicle, English speaking driver, baby seat required",
        "contact": {
            "name": "Michael Smith",
            "email": "michael.smith@email.com",
            "phone": "+1-555-123-4567"
        }
    },
    "expires_at": "2025-02-10T23:59:59Z"
}
```

### 3.2 Corporate Monthly Rental Query
```json
{
    "query_type": "VEHICLE",
    "booking_for": "CORPORATE",
    "company": 1,
    "referred_by": 5,
    "referral_type": "EMPLOYEE",
    "query_data": {
        "trip_type": "monthly_rental",
        "city": "Bangalore",
        "start_date": "2025-03-01",
        "end_date": "2025-03-31",
        "vehicle_type": "CAR",
        "vehicle_category": "Sedan",
        "usage_type": "Employee Transportation",
        "estimated_km_per_day": 100,
        "working_days": 26,
        "duty_hours": {"start": "08:00", "end": "20:00"},
        "number_of_vehicles": 3,
        "requirements": ["AC vehicles", "GPS tracking", "Experienced drivers", "Fuel included"],
        "billing_preference": "Monthly Invoice",
        "contact": {
            "name": "HR Department",
            "email": "hr@company.com",
            "phone": "+91-80-12345678"
        }
    },
    "expires_at": "2025-02-20T23:59:59Z"
}
```

---

## 4. HOTEL Query Workflow

### 4.1 Group Hotel Booking Query
```
POST /api/v1/booking/queries/
```

```json
{
    "query_type": "HOTEL",
    "booking_for": "CORPORATE",
    "company": 1,
    "query_data": {
        "destination": "Mumbai",
        "checkin_date": "2025-04-10",
        "checkout_date": "2025-04-13",
        "rooms_required": 25,
        "room_type_preference": "Deluxe",
        "adult_count": 50,
        "child_count": 0,
        "star_rating_preference": "4-5 star",
        "meal_plan": "MAP (Breakfast + Dinner)",
        "budget_per_room": 6000,
        "preferred_hotels": ["Novotel Mumbai", "Courtyard by Marriott", "Hyatt Regency"],
        "purpose": "Team offsite and training",
        "requirements": [
            "Conference room for 50 pax",
            "Projector and AV setup",
            "Separate billing for rooms and F&B"
        ],
        "contact": {
            "name": "Admin Team",
            "email": "admin@company.com",
            "phone": "+91-22-12345678"
        }
    },
    "expires_at": "2025-03-25T23:59:59Z"
}
```

---

## 5. HOLIDAY PACKAGE Query Workflow

### 5.1 Create Holiday Package Query
```
POST /api/v1/booking/queries/
```

```json
{
    "query_type": "HOLIDAYPACK",
    "booking_for": "B2C",
    "query_data": {
        "destination": "Ladakh",
        "travel_dates": {
            "start_date": "2025-06-15",
            "end_date": "2025-06-22"
        },
        "duration": "7N/8D",
        "adult_count": 4,
        "child_count": 2,
        "infant_count": 0,
        "budget_range": "100000_250000",
        "travel_style": "Adventure with Comfort",
        "interests": ["Monasteries", "Lake visits", "Mountain biking", "Photography"],
        "must_visit": ["Pangong Lake", "Nubra Valley", "Khardung La", "Magnetic Hill"],
        "accommodation_preference": "3-4 star hotels/camps",
        "meal_preference": "All meals included",
        "special_requests": "Need oxygen cylinders for high altitude, one member has asthma",
        "departure_city": "Delhi",
        "contact": {
            "name": "Ravi Verma",
            "email": "ravi.verma@email.com",
            "phone": "+91-9876543212"
        }
    },
    "expires_at": "2025-05-15T23:59:59Z"
}
```

---

## 6. FLIGHT Query Workflow

### 6.1 Group Flight Booking Query
```
POST /api/v1/booking/queries/
```

```json
{
    "query_type": "FLIGHT",
    "booking_for": "CORPORATE",
    "company": 1,
    "query_data": {
        "trip_type": "ROUND",
        "origin": "BLR",
        "origin_city": "Bangalore",
        "destination": "GOI",
        "destination_city": "Goa",
        "departure_date": "2025-03-20",
        "return_date": "2025-03-23",
        "adult_count": 30,
        "child_count": 0,
        "infant_count": 0,
        "flight_class": "ECONOMY",
        "preferred_airlines": ["IndiGo", "Air India"],
        "flexible_dates": true,
        "preferred_time": {
            "departure": "Morning (6 AM - 12 PM)",
            "return": "Evening (4 PM - 10 PM)"
        },
        "special_requests": "Need same flight for all passengers, prefer window and aisle seats",
        "purpose": "Team offsite trip to Goa",
        "contact": {
            "name": "Travel Desk",
            "email": "travel@company.com",
            "phone": "+91-80-87654321"
        }
    },
    "expires_at": "2025-03-10T23:59:59Z"
}
```

---

## 7. Communication Management

### 7.1 Add Internal Note
```
POST /api/v1/booking/queries/{{query_id}}/add-communication/
Authorization: Bearer {{token}}
Content-Type: application/json
```

```json
{
    "communication_type": "NOTE",
    "message": "Received query. Reviewing documents submitted by customer. Passport copy is clear, need to verify bank statements.",
    "is_internal": true
}
```

### 7.2 Log Customer Call
```json
{
    "communication_type": "CALL",
    "message": "Called customer to discuss visa requirements. Customer confirmed travel dates and provided additional employment details. Discussed processing time of 7-10 business days.",
    "is_internal": false
}
```

### 7.3 Email Communication
```json
{
    "communication_type": "EMAIL",
    "message": "Dear Customer,\n\nThank you for choosing IDBOOK. We have identified 3 potential venues for your conference:\n\n1. Taj West End - ₹3,50,000/day\n2. ITC Gardenia - ₹2,80,000/day\n3. JW Marriott - ₹4,00,000/day\n\nPlease let us know your preference.\n\nBest regards,\nIDBook Events Team",
    "is_internal": false
}
```

**Communication Types:** `NOTE`, `EMAIL`, `CALL`, `SMS`, `STATUS_UPDATE`, `QUOTE_UPDATE`

---

## 8. Update Query (Status, Quote, Itinerary)

### 8.1 Update Status to Documents Reviewed (Visa)
```
PATCH /api/v1/booking/queries/{{query_id}}/
Authorization: Bearer {{token}}
Content-Type: application/json
```

```json
{
    "status": "documents_reviewed",
    "admin_notes": "All documents verified. Ready to proceed with visa application."
}
```

### 8.2 Update Quote Amount and Itinerary
```json
{
    "quote_amount": 12500.00,
    "itinerary_details": {
        "visa_fee": 8000,
        "service_charge": 2500,
        "courier_charges": 500,
        "tax": 1500,
        "processing_time": "7-10 business days",
        "embassy_slot": "2025-03-01",
        "documents_required": [
            "Original Passport",
            "Passport Size Photos (2)",
            "Bank Statement (6 months)",
            "ITR (2 years)",
            "Employment Letter"
        ]
    }
}
```

---

## 9. Proforma Invoice Management

### 9.1 Create Proforma Invoice
```
POST /api/v1/booking/queries/{{query_id}}/create-proforma-invoice/
Authorization: Bearer {{admin_token}}
```

**Response:**
```json
{
    "status": "success",
    "message": "Proforma invoice created successfully",
    "data": {
        "query": {
            "id": 1,
            "query_reference": "QRY-VISA-000001",
            "status": "quoted"
        },
        "invoice": {
            "id": 1,
            "invoice_number": "PI-000001",
            "invoice_type": "PROFORMA",
            "total_amount": 12500.00,
            "status": "Pending"
        }
    }
}
```

---

## 10. Document Upload

### 10.1 Upload Document
```
POST /api/v1/booking/queries/{{query_id}}/upload-document/
Authorization: Bearer {{admin_token}}
Content-Type: multipart/form-data
```

**Form Data:**
| Key | Value | Description |
|-----|-------|-------------|
| document_type | `proforma_pdf` | Type of document |
| file | [PDF File] | The file to upload |

**Document Types:**
- `proforma_pdf` - Proforma invoice PDF
- `invoice_pdf` - Final invoice PDF
- `receipt_pdf` - Payment receipt PDF
- `credit_note_pdf` - Credit note PDF
- `voucher_pdf` - Booking voucher PDF
- `other` - Other documents (requires `name` field)

### 10.2 Upload Other Document
```
Form Data:
- document_type: other
- name: Passport Copy
- file: [PDF File]
```

---

## 11. Convert Query to Booking

### 11.1 Convert to Booking (Admin Only)
```
POST /api/v1/booking/queries/{{query_id}}/convert-to-booking/
Authorization: Bearer {{admin_token}}
```

**Prerequisites:**
- `quote_amount` must be set (> 0)
- `raised_by` must be set (user assigned)
- Query must not already be converted

**Response:**
```json
{
    "status": "success",
    "message": "Query converted to booking successfully",
    "data": {
        "query": {
            "id": 1,
            "query_reference": "QRY-VISA-000001",
            "status": "confirmed"
        },
        "booking": {
            "id": 1,
            "reference_code": "IDB-2024-000001",
            "confirmation_code": "CONF-000001",
            "booking_type": "VISA",
            "status": "pending",
            "final_amount": 12500.00
        }
    }
}
```

---

## 12. Query Filtering & Listing

### 12.1 List All Queries
```
GET /api/v1/booking/queries/
Authorization: Bearer {{token}}
```

### 12.2 Filter by Query Type
```
GET /api/v1/booking/queries/?query_type=VISA
GET /api/v1/booking/queries/?query_type=EVENT
GET /api/v1/booking/queries/?query_type=VEHICLE
GET /api/v1/booking/queries/?query_type=HOTEL
GET /api/v1/booking/queries/?query_type=FLIGHT
GET /api/v1/booking/queries/?query_type=HOLIDAYPACK
```

### 12.3 Filter by Status
```
GET /api/v1/booking/queries/?status=pending
GET /api/v1/booking/queries/?status=quoted
GET /api/v1/booking/queries/?status=confirmed
GET /api/v1/booking/queries/?status=completed
GET /api/v1/booking/queries/?status=cancelled
```

### 12.4 Filter by Booking For
```
GET /api/v1/booking/queries/?booking_for=B2C
GET /api/v1/booking/queries/?booking_for=CORPORATE
GET /api/v1/booking/queries/?booking_for=AGENT
```

### 12.5 Filter by Company
```
GET /api/v1/booking/queries/?company_id=1
```

### 12.6 Filter by User
```
GET /api/v1/booking/queries/?raised_by=10
GET /api/v1/booking/queries/?referred_by=5
```

### 12.7 Combined Filters
```
GET /api/v1/booking/queries/?query_type=VISA&status=pending&booking_for=CORPORATE
```

---

## Complete Workflow Example (VISA)

### Step 1: Customer Creates Query
```
POST /api/v1/booking/queries/
→ Returns query_id: 1, status: "pending"
```

### Step 2: Admin Reviews Documents
```
PATCH /api/v1/booking/queries/1/
Body: {"status": "documents_reviewed", "admin_notes": "Documents verified"}
```

### Step 3: Admin Adds Communication
```
POST /api/v1/booking/queries/1/add-communication/
Body: {"communication_type": "CALL", "message": "Discussed visa requirements with customer"}
```

### Step 4: Admin Sets Quote
```
PATCH /api/v1/booking/queries/1/
Body: {"quote_amount": 12500.00, "itinerary_details": {...}}
```

### Step 5: Admin Creates Proforma Invoice
```
POST /api/v1/booking/queries/1/create-proforma-invoice/
→ Invoice created with number PI-000001
```

### Step 6: Admin Uploads Proforma PDF
```
POST /api/v1/booking/queries/1/upload-document/
Form: document_type=proforma_pdf, file=proforma.pdf
```

### Step 7: Customer Makes Payment (External)

### Step 8: Admin Converts to Booking
```
POST /api/v1/booking/queries/1/convert-to-booking/
→ Booking created, Invoice converted from PROFORMA to INVOICE
```

### Step 9: Admin Uploads Final Documents
```
POST /api/v1/booking/queries/1/upload-document/
Form: document_type=invoice_pdf, file=invoice.pdf

POST /api/v1/booking/queries/1/upload-document/
Form: document_type=receipt_pdf, file=receipt.pdf

POST /api/v1/booking/queries/1/upload-document/
Form: document_type=voucher_pdf, file=voucher.pdf
```

### Step 10: Update to Completed
```
PATCH /api/v1/booking/queries/1/
Body: {"status": "completed", "admin_notes": "Visa approved and delivered to customer"}
```


