# Flight Booking API Testing Guide

## Overview
This guide provides comprehensive instructions for testing the complete flight booking user flow using Postman. The workflow covers search, hold booking, payment processing, booking management, status updates, cancellation, and refunds.

## Prerequisites

### 1. Environment Setup
Before starting, ensure you have:
- Django development server running at `http://localhost:8000`
- PostgreSQL database configured and running
- Celery worker and beat processes running (for background tasks)
- Redis running (for Celery broker)

### 2. Test User Setup
Create a test user and wallet:

```sql
-- Create test user
INSERT INTO auth_user (phone, email, first_name, last_name, is_active, is_staff, is_superuser, password)
VALUES ('9876543210', 'test@example.com', 'Test', 'User', true, false, false, 'hashed_password');

-- Create customer wallet
INSERT INTO customer_customerwallet (user_id, balance, bonus_balance, created_at, updated_at)
VALUES (1, 10000.00, 1000.00, NOW(), NOW());
```

### 3. Postman Environment Variables
Create a Postman environment with these variables:
- `base_url`: `http://localhost:8000`
- `test_phone`: `9876543210`
- `test_password`: `your_test_password`

## Complete User Flow Testing

### Phase 1: Authentication and Setup

#### 1.1 Import Postman Collection
1. Import the `Flight_Booking_Postman_Collection.json` file into Postman
2. Set up your environment variables as mentioned above

#### 1.2 Authenticate User
```
POST {{base_url}}/api/v1/auth/token/
Body: {
    "phone": "{{test_phone}}",
    "password": "{{test_password}}"
}
```
**Expected Response:**
- Status: 200 OK
- Body contains `access` and `refresh` tokens
- Token is automatically saved to environment variable `access_token`

### Phase 2: Flight Search

#### 2.1 Search for Flights
```
POST {{base_url}}/api/v1/booking/flight-search/
Headers: Authorization: Bearer {{access_token}}
Body: {
    "origin": "DEL",
    "destination": "BOM",
    "departure_date": "2024-12-25",
    "return_date": null,
    "adults": 1,
    "children": 0,
    "infants": 0,
    "class_type": "Economy"
}
```
**Expected Response:**
- Status: 200 OK
- Flight offers in response data
- First offer automatically saved to `flight_offer` variable

### Phase 3: Create Hold Booking

#### 3.1 Create Flight Hold Booking
```
POST {{base_url}}/api/v1/booking/create-flight-booking/
Headers: Authorization: Bearer {{access_token}}
Body: {
    "passengers": [
        {
            "type": "adult",
            "title": "Mr",
            "first_name": "John",
            "last_name": "Doe",
            "gender": "M",
            "date_of_birth": "1990-01-01",
            "nationality": "IN",
            "passport_number": "",
            "passport_expiry": "",
            "frequent_flyer_number": ""
        }
    ],
    "flight_offer": {{flight_offer}},
    "contact_email": "test@example.com",
    "contact_phone": "{{test_phone}}"
}
```
**Expected Response:**
- Status: 201 Created
- Booking created with HOLD status
- `booking_id` and `total_amount` saved to environment

**Validation Points:**
- Verify booking status is "HOLD"
- Check hold expiry time (typically 30 minutes)
- Confirm passenger details are saved correctly

### Phase 4: Payment Processing

#### 4.1 Get Available Payment Methods
```
GET {{base_url}}/api/v1/booking/{{booking_id}}/flight-payment/methods/
Headers: Authorization: Bearer {{access_token}}
```
**Expected Response:**
- Status: 200 OK
- Available payment methods: WALLET, PHONE_PAY, PAYU
- User wallet balance information

#### 4.2 Wallet Payment (Success Scenario)
```
POST {{base_url}}/api/v1/booking/{{booking_id}}/flight-payment/initiate/
Headers: Authorization: Bearer {{access_token}}
Body: {
    "payment_method": "WALLET",
    "amount": "{{total_amount}}"
}
```
**Expected Response:**
- Status: 200 OK
- Payment completed successfully
- Booking status changed to "CONFIRMED"

**Validation Points:**
- Verify wallet balance deducted
- Check booking status updated to CONFIRMED
- Confirm BookingPaymentDetail record created
- Verify any email/SMS notifications triggered

#### 4.3 PhonePe Payment Flow (Alternative)
**Step 1: Initiate PhonePe Payment**
```
POST {{base_url}}/api/v1/booking/{{booking_id}}/flight-payment/initiate/
Body: {
    "payment_method": "PHONE_PAY",
    "amount": "{{total_amount}}"
}
```
**Expected Response:**
- Status: 200 OK
- `payment_url` for gateway redirection
- `transaction_id` and `merchant_transaction_id` saved

**Step 2: Simulate Success Callback**
```
POST {{base_url}}/api/v1/booking/flight-payment/phonepe-callback/
Body: {
    "merchantTransactionId": "{{merchant_transaction_id}}",
    "transactionId": "{{transaction_id}}",
    "amount": {{total_amount}}00,
    "state": "COMPLETED",
    "responseCode": "SUCCESS"
}
```

### Phase 5: Booking Management

#### 5.1 Get Comprehensive Booking Details
```
GET {{base_url}}/api/v1/booking/{{booking_id}}/flight-details/
Headers: Authorization: Bearer {{access_token}}
```
**Expected Response:**
- Complete booking information
- Passenger details
- Flight information
- Payment details
- Invoice information

#### 5.2 Check Flight Status
```
GET {{base_url}}/api/v1/booking/{{booking_id}}/flight-status/
Headers: Authorization: Bearer {{access_token}}
```
**Expected Response:**
- Current booking status
- Flight status information
- Real-time updates if available

#### 5.3 Update Status from AirIQ
```
POST {{base_url}}/api/v1/booking/{{booking_id}}/flight-status/update/
Headers: Authorization: Bearer {{access_token}}
```
**Expected Response:**
- Updated status from airline system
- Any schedule changes
- Customer notifications triggered

#### 5.4 Get Booking Timeline
```
GET {{base_url}}/api/v1/booking/{{booking_id}}/flight-timeline/
Headers: Authorization: Bearer {{access_token}}
```
**Expected Response:**
- Chronological list of booking events
- Status changes with timestamps
- Payment and confirmation events

### Phase 6: User Booking Management

#### 6.1 Get User's Flight Bookings
```
GET {{base_url}}/api/v1/booking/my-flights/
Headers: Authorization: Bearer {{access_token}}
```
**Expected Response:**
- List of user's flight bookings
- Summary information for each booking

#### 6.2 Filter User Bookings
```
GET {{base_url}}/api/v1/booking/my-flights/?status=CONFIRMED&date_from=2024-12-01&date_to=2024-12-31
Headers: Authorization: Bearer {{access_token}}
```
**Test different filter combinations:**
- By status: `?status=CONFIRMED`
- By date range: `?date_from=2024-01-01&date_to=2024-12-31`
- By route: `?origin=DEL&destination=BOM`

### Phase 7: Cancellation and Refunds

#### 7.1 Cancel Booking
```
POST {{base_url}}/api/v1/booking/{{booking_id}}/cancel-booking/
Headers: Authorization: Bearer {{access_token}}
Body: {
    "reason": "Travel plans changed",
    "requested_by": "customer"
}
```
**Expected Response:**
- Status: 200 OK
- Booking status changed to "CANCELED"
- Cancellation charges calculated
- Refund eligibility determined

#### 7.2 Process Refund
```
POST {{base_url}}/api/v1/booking/{{booking_id}}/process-refund/
Headers: Authorization: Bearer {{access_token}}
Body: {
    "refund_method": "WALLET"
}
```
**Expected Response:**
- Refund amount calculated
- Wallet credited (if WALLET refund)
- Refund transaction record created

## Error Scenario Testing

### 8.1 Insufficient Wallet Balance
```
POST {{base_url}}/api/v1/booking/{{booking_id}}/flight-payment/initiate/
Body: {
    "payment_method": "WALLET",
    "amount": "99999.00"
}
```
**Expected Response:**
- Status: 400 Bad Request
- Error message about insufficient balance

### 8.2 Invalid Booking Access
```
GET {{base_url}}/api/v1/booking/99999/flight-details/
```
**Expected Response:**
- Status: 404 Not Found
- Appropriate error message

### 8.3 Expired Hold Booking Payment
1. Create a hold booking
2. Wait for hold expiry (or manually update expiry in database)
3. Attempt payment
**Expected Response:**
- Status: 400 Bad Request
- Error about expired hold

### 8.4 Invalid Flight Offer
```
POST {{base_url}}/api/v1/booking/create-flight-booking/
Body: {
    "passengers": [],
    "flight_offer": {},
    "contact_email": "test@example.com"
}
```
**Expected Response:**
- Status: 400 Bad Request
- Validation errors for missing data

## Performance Testing

### Load Testing Scenarios
1. **Concurrent Search Requests**: Test 10-50 simultaneous flight search requests
2. **Payment Processing Load**: Test multiple simultaneous payment initiations
3. **Status Update Stress**: Rapid status update requests for multiple bookings

### Tools for Load Testing
- Use Postman Collection Runner with multiple iterations
- Consider tools like Apache JMeter for heavy load testing
- Monitor database connections and response times

## Monitoring and Validation

### Database Validation Queries
```sql
-- Check booking creation
SELECT * FROM booking_booking WHERE user_id = 1 ORDER BY created_at DESC;

-- Check payment records
SELECT * FROM booking_bookingpaymentdetail WHERE booking_id = ?;

-- Check wallet transactions
SELECT * FROM customer_customerwalletransaction WHERE user_id = 1 ORDER BY created_at DESC;

-- Check booking timeline
SELECT * FROM booking_bookingtimeline WHERE booking_id = ? ORDER BY created_at;
```

### Log Monitoring
Monitor application logs for:
- Payment gateway API calls
- AirIQ integration responses
- Email/SMS notification triggers
- Error handling and exceptions
- Performance metrics

### Email/SMS Testing
Verify that notifications are sent for:
- Booking confirmation
- Payment success/failure
- Schedule changes
- Cancellation confirmations
- Refund processing

## Real-World Testing Scenarios

### Scenario 1: Happy Path - Complete Booking
1. Search flights → Select offer → Create hold → Pay with wallet → Confirm booking
2. Check details → View timeline → Get all bookings
3. **Expected Time**: 2-3 minutes for complete flow

### Scenario 2: Payment Gateway Flow
1. Search → Create hold → Initiate PhonePe payment → Complete gateway payment → Callback processing
2. **Expected Time**: 3-5 minutes including gateway simulation

### Scenario 3: Cancellation with Refund
1. Complete booking (Scenario 1) → Cancel booking → Process refund → Verify wallet credit
2. **Expected Time**: 2-3 minutes

### Scenario 4: Multi-Passenger Booking
1. Search → Create booking with 2-3 passengers → Complete payment → Verify all passenger details
2. **Expected Time**: 3-4 minutes

### Scenario 5: Error Recovery
1. Create hold → Attempt invalid payment → Fix and retry → Complete successfully
2. **Expected Time**: 3-5 minutes

## Performance Benchmarks

### Response Time Targets
- Flight search: < 3 seconds
- Booking creation: < 2 seconds  
- Payment processing: < 5 seconds
- Status updates: < 1 second
- Booking retrieval: < 1 second

### Error Rate Targets
- Payment success rate: > 99%
- Booking creation success: > 99.5%
- API availability: > 99.9%

## Troubleshooting

### Common Issues
1. **Authentication failures**: Check JWT token expiry and refresh
2. **Payment gateway errors**: Verify gateway credentials and network connectivity
3. **Database connection issues**: Check PostgreSQL connection and pool settings
4. **Celery task failures**: Verify Redis connectivity and worker processes

### Debugging Tools
- Django debug toolbar for SQL query analysis
- Celery flower for task monitoring
- Database query logs for performance analysis
- Payment gateway logs for transaction debugging

## Conclusion

This comprehensive testing guide covers all aspects of the flight booking user flow. Execute tests in the order presented for a complete validation of the system. Monitor performance, validate data integrity, and ensure proper error handling throughout the testing process.

For production deployment, run all test scenarios and ensure all benchmarks are met before releasing to users.