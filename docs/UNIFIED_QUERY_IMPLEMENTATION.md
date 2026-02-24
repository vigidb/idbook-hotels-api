# Unified Query System Implementation

## Overview

Implemented a unified Query model for all service types (Hotels, Flights, Vehicles, Packages, Visa, Events, Cabs) with comprehensive tracking, communication history, and seamless conversion to bookings.

## Key Features

### 1. Unified Query Model
- **Single model for all services**: One `Query` model handles all query types
- **Flexible data storage**: JSON field (`query_data`) for service-specific information
- **Auto-generated reference**: Unique query reference code (QRY-000001, etc.)

### 2. Comprehensive Tracking
- **Raised by**: User who created the query
- **Referred by**: Employee or user who referred the query
- **Referral type**: Employee, User, or Agent
- **Booking for**: B2C, Corporate, or Agent
- **Company support**: Full company filtering and tracking

### 3. Communication History
- **QueryCommunication model**: Separate model for all communications
- **Communication types**: Note, Email, Call, SMS, Status Update, Quote Update
- **Internal notes**: Support for internal-only communications
- **Attachments**: JSON field for attachment URLs
- **Full history**: Complete audit trail of all interactions

### 4. Invoice Integration
- **Proforma Invoice**: Create proforma invoice for queries before conversion
- **Invoice Linking**: Query directly links to Invoice model
- **Automatic Conversion**: Proforma invoice converts to final invoice on booking conversion
- **Invoice Types**: PROFORMA for queries, INVOICE for confirmed bookings

### 5. Query to Booking Conversion
- **Seamless conversion**: Admin converts query to booking with one action
- **Service-specific handling**: Automatically creates VisaBooking/EventBooking when needed
- **Bidirectional linking**: Query links to Booking, Booking links back to Query
- **Invoice conversion**: Proforma invoice automatically converts to final invoice
- **Status management**: Query status updates to "confirmed" after conversion

### 6. Enhanced Booking Model
- **Source query link**: `source_query` field links booking back to original query
- **Expiry support**: Already has `on_hold_end_time` and `payment_expires_at`
- **Invoice support**: Already has `invoice_id` linked to Invoice model

## Models

### Query Model
```python
class Query(models.Model):
    query_type          # HOTEL, FLIGHT, VISA, EVENT, etc.
    query_reference     # Auto-generated: QRY-000001
    raised_by          # User who created query
    company            # Company if corporate query
    booking_for        # B2C, CORPORATE, AGENT
    referred_by        # Employee/user who referred
    referral_type      # EMPLOYEE, USER, AGENT
    query_data         # JSON field for service-specific data
    status             # pending, quoted, confirmed, etc.
    quote_amount       # Quoted price
    invoice            # ForeignKey to Invoice (proforma initially)
    itinerary_details  # Admin-added itinerary
    admin_notes       # Admin notes
    booking           # Linked booking when converted
    expires_at        # Query expiry date
```

### Invoice Model (Enhanced)
```python
class Invoice(models.Model):
    # ... existing fields ...
    invoice_type       # PROFORMA or INVOICE
    source_query       # ForeignKey to Query (for invoices from queries)
    
    # Document PDFs
    proforma_pdf       # Proforma invoice PDF
    invoice_pdf        # Final invoice PDF
    receipt_pdf        # Payment receipt PDF
    credit_note_pdf    # Credit note PDF (refunds)
    voucher_pdf        # Booking voucher PDF
    other_documents    # JSON list of other documents [{name, url, type, uploaded_at}]
```

### QueryCommunication Model
```python
class QueryCommunication(models.Model):
    query              # Related query
    user               # User who added communication
    communication_type # NOTE, EMAIL, CALL, SMS, etc.
    subject            # Communication subject
    message            # Communication message
    attachments        # List of attachment URLs
    is_internal        # Internal note flag
    created            # Timestamp
```

### Booking Model (Enhanced)
```python
# Added field:
source_query          # Link back to original query
```

## API Endpoints

### Query Management (Standard REST)

**Create Query:**
```
POST /api/v1/booking/queries/
{
  "query_type": "VISA",
  "booking_for": "CORPORATE",
  "company": 123,
  "referred_by": 456,
  "referral_type": "EMPLOYEE",
  "query_data": {
    "destination_country": "USA",
    "travel_date": "2024-12-01",
    "visa_type": "tourist"
  }
}
```

**List Queries (with filters):**
```
GET /api/v1/booking/queries/?company_id=123&status=pending&query_type=VISA
GET /api/v1/booking/queries/?booking_for=CORPORATE
GET /api/v1/booking/queries/?referred_by=456
```

**Retrieve Query:**
```
GET /api/v1/booking/queries/{id}/
```

**Update Query (Admin):**
```
PATCH /api/v1/booking/queries/{id}/
{
  "status": "quoted",
  "quote_amount": "5000.00",
  "itinerary_details": {...},
  "admin_notes": "Customer confirmed dates"
}
```

**Add Communication:**
```
POST /api/v1/booking/queries/{id}/add-communication/
{
  "communication_type": "NOTE",
  "subject": "Customer Follow-up",
  "message": "Customer confirmed travel dates",
  "is_internal": false
}
```

**Create Proforma Invoice (Admin):**
```
POST /api/v1/booking/queries/{id}/create-proforma-invoice/
```
- Creates proforma invoice with quote_amount
- Links invoice to query
- Returns query and invoice details

**Upload Document to Invoice (Admin):**
```
POST /api/v1/booking/queries/{id}/upload-document/
Content-Type: multipart/form-data

{
  "document_type": "proforma_pdf",  // proforma_pdf, invoice_pdf, receipt_pdf, credit_note_pdf, voucher_pdf, other
  "file": <file>,
  "name": "Optional name for 'other' type"
}
```
- Uploads document to query's invoice
- Supports multiple document types
- 'other' type stores in `other_documents` JSON list

**Convert to Booking (Admin):**
```
POST /api/v1/booking/queries/{id}/convert-to-booking/
```
- Converts query to booking
- Converts proforma invoice to final invoice (if exists)
- Links booking to query and invoice

## Query Data Structure Examples

### Visa Query
```json
{
  "query_type": "VISA",
  "query_data": {
    "destination_country": "USA",
    "travel_date": "2024-12-01",
    "visa_type": "tourist",
    "passport_number": "A1234567",
    "passport_expiry": "2025-12-31",
    "travel_purpose": "Tourism",
    "documents_uploaded": ["url1", "url2"]
  }
}
```

### Event Query
```json
{
  "query_type": "EVENT",
  "query_data": {
    "event_name": "Tech Conference 2024",
    "event_type": "conference",
    "event_date": "2024-12-15T10:00:00Z",
    "event_end_date": "2024-12-17T18:00:00Z",
    "location": "Mumbai",
    "attendee_count": 50,
    "budget_range": "100000_250000"
  }
}
```

### Hotel Query
```json
{
  "query_type": "HOTEL",
  "query_data": {
    "destination": "Goa",
    "checkin_date": "2024-12-20",
    "checkout_date": "2024-12-25",
    "adults": 2,
    "children": 1,
    "room_type": "DELUXE"
  }
}
```

## User Type Handling

### B2C Users
- Can create queries
- See only their own queries
- Filter: `?raised_by={user_id}`

### Corporate Users
- Can create queries for their company
- See company queries and their own
- Filter: `?company_id={company_id}`

### Admin Users
- See all queries
- Can update status, add quotes, convert to bookings
- Full access to all operations

## Workflow

1. **User creates query** → Status: `pending`
2. **Admin reviews** → Updates status, adds notes
3. **Admin adds quote** → Sets `quote_amount`, status: `quoted`
4. **Admin creates proforma invoice** → Creates Invoice (type: PROFORMA), links to Query
5. **User reviews proforma** → Can view/download proforma invoice PDF
6. **Admin converts to booking** → Creates Booking, converts proforma to final invoice
7. **User makes payment** → Uses existing payment endpoints with final invoice
8. **Booking confirmed** → Status: `confirmed`, Invoice status: `Paid`

## Invoice Flow

```
Query Created → quote_amount set → Create Proforma Invoice (PI-000001)
                                           ↓
                                    User reviews/approves
                                           ↓
                            Convert to Booking
                                           ↓
                            Proforma → Final Invoice (INV-000001)
                                           ↓
                                    Payment processed
                                           ↓
                                    Invoice status: Paid
```

## Database Indexes

Optimized indexes for common queries:
- `(query_type, status)`
- `(company, status)`
- `(raised_by, status)`
- `(booking_for, status)`

## Admin Interface

- Query list with filters
- Query detail with inline communications
- Easy status updates
- Quote management
- Convert to booking action

## Benefits

1. **Unified Structure**: One model for all services
2. **Flexible**: JSON field allows any service-specific data
3. **Trackable**: Complete audit trail with communications
4. **Company Support**: Full corporate query management
5. **Referral Tracking**: Track who referred queries
6. **Standard REST**: Minimal custom actions, easy to use
7. **Scalable**: Easy to add new service types

## Migration Notes

Run migrations to create new models:
```bash
python manage.py makemigrations booking
python manage.py migrate
```

## Next Steps

1. Create frontend forms for query submission
2. Add email/SMS notifications for query status updates
3. Implement proforma invoice generation
4. Add query expiry automation
5. Create query dashboard for admin


