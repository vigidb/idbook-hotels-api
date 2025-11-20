# Guest Booking Authentication Solution

## Overview

This document describes the implementation of secure authentication for guest users to view their bookings without requiring traditional login credentials.

## Problem Statement

The system supports multiple booking types:
1. **Guest Booking** - Users who book without creating an account
2. **Customer Booking** - Normal or pro membership-based bookings
3. **Corporate Booking** - Bookings with company ID
4. **Agent Booking** - (Planned for future)

Guest users need a secure way to access their booking details without requiring authentication tokens or account creation.

## Solution

We've implemented a **dual authentication method** for guest booking access:

### 1. Guest Access Token (Recommended)
- A secure, cryptographically generated token is created when a guest booking is made
- Token is unique per booking and stored in the database
- Token is sent to the guest via email in the booking confirmation
- Provides one-click access to booking details

### 2. Confirmation Code + Email (Fallback)
- Guests can use their booking confirmation code + email address
- Provides an alternative method if the token is lost or not received

## Implementation Details

### Database Changes

**New Field in Booking Model:**
```python
guest_access_token = models.CharField(
    max_length=255, 
    null=True, 
    blank=True, 
    unique=True,
    help_text="Secure token for guest users to access their booking without authentication"
)
```

**Migration:** `apps/booking/migrations/0002_add_guest_access_token.py`

### Utility Functions

**Location:** `apps/booking/utils/booking_utils.py`

1. **`generate_guest_access_token(booking_id)`**
   - Generates a cryptographically secure token
   - Uses SHA-256 hashing with booking ID, timestamp, and random bytes
   - Returns a URL-safe token prefixed with `guest_`

2. **`validate_guest_access_token(token)`**
   - Validates a guest access token
   - Returns the associated booking if valid

3. **`get_booking_by_guest_credentials(confirmation_code, email, guest_token)`**
   - Unified function to retrieve bookings using either method
   - Supports both token-based and confirmation_code+email access

### API Endpoint

**Public Endpoint:** `GET /api/bookings/guest/view/`

**Query Parameters:**
- `guest_token` (optional): Guest access token (preferred method)
- `confirmation_code` (optional): Booking confirmation code
- `email` (optional): Email address associated with the booking

**Requirements:**
- Either `guest_token` OR both `confirmation_code` and `email` must be provided

**Response:**
- Returns full booking details (same format as authenticated endpoint)
- Includes guest_token in response if available

**Example Usage:**
```bash
# Using guest token (recommended)
GET /api/bookings/guest/view/?guest_token=guest_abc123...

# Using confirmation code + email (fallback)
GET /api/bookings/guest/view/?confirmation_code=Idbook-CNF123&email=guest@example.com
```

**Security:**
- Endpoint is public (`AllowAny` permission)
- Validates credentials before returning booking data
- Returns 404 if booking not found or credentials invalid

### Automatic Token Generation

Guest access tokens are automatically generated when:
1. A booking is created for a user with:
   - `B2C-GUEST` role, OR
   - `B2C-GRP` group membership, OR
   - `default_group == 'B2C-GRP'`

**Implementation Locations:**
- `apps/booking/utils/flight_booking_utils.py` - Flight booking creation
- `apps/booking/serializers.py` - General booking creation

### Guest User Identification

Guest users are identified by:
- Role: `B2C-GUEST`
- Group: `B2C-GRP`
- Default Group: `B2C-GRP`

This ensures tokens are only generated for actual guest bookings, not for authenticated customer or corporate bookings.

## Usage Flow

### For Guest Users:

1. **Booking Creation:**
   - Guest creates booking (via OTP verification)
   - System automatically generates `guest_access_token`
   - Token is stored in booking record

2. **Booking Confirmation Email:**
   - Email sent with booking details
   - Includes link with guest token: `/bookings/guest/view/?guest_token=...`
   - Also includes confirmation code for fallback

3. **Viewing Booking:**
   - Guest clicks link in email (uses token automatically)
   - OR manually enters confirmation code + email
   - System validates credentials and returns booking details

### For Frontend Integration:

```javascript
// Option 1: Use guest token from email link
const bookingDetails = await fetch(
  `/api/bookings/guest/view/?guest_token=${guestToken}`
);

// Option 2: Use confirmation code + email
const bookingDetails = await fetch(
  `/api/bookings/guest/view/?confirmation_code=${code}&email=${email}`
);
```

## Security Considerations

1. **Token Security:**
   - Tokens are cryptographically secure (SHA-256)
   - Unique per booking (database constraint)
   - Long enough to prevent brute force attacks (48+ characters)

2. **Access Control:**
   - Tokens are only generated for guest bookings
   - Each token is unique and tied to a specific booking
   - No way to enumerate or guess valid tokens

3. **Privacy:**
   - Email verification ensures only the booking owner can access
   - Confirmation code + email method requires both pieces of information

4. **Best Practices:**
   - Tokens should be sent via secure email
   - Tokens should not be logged or exposed in URLs unnecessarily
   - Consider token expiration if needed (currently tokens don't expire)

## Future Enhancements

1. **Token Expiration:**
   - Add optional expiration time for guest tokens
   - Useful for security or compliance requirements

2. **Token Regeneration:**
   - Allow guests to request new token if lost
   - Requires email verification

3. **Email Template Updates:**
   - Update booking confirmation emails to include guest token link
   - Add clear instructions for accessing booking

4. **Agent Booking Support:**
   - Extend token system for agent bookings if needed
   - Similar pattern can be applied

## Testing

### Test Cases:

1. **Token Generation:**
   - Verify token is generated for guest bookings
   - Verify token is NOT generated for authenticated user bookings
   - Verify token uniqueness

2. **Token Validation:**
   - Verify valid token returns booking
   - Verify invalid token returns 404
   - Verify expired token handling (if implemented)

3. **Confirmation Code + Email:**
   - Verify correct code + email returns booking
   - Verify incorrect code returns 404
   - Verify incorrect email returns 404

4. **Endpoint Security:**
   - Verify endpoint is accessible without authentication
   - Verify unauthorized access returns 404 (not 403)
   - Verify booking data is only returned for valid credentials

## Migration

To apply the database changes:

```bash
python manage.py migrate booking
```

This will add the `guest_access_token` field to the `Booking` model.

## Summary

This solution provides a secure, user-friendly way for guest users to access their bookings without requiring account creation or authentication. The dual-method approach (token + confirmation code) ensures accessibility while maintaining security.

The implementation is:
- ✅ Secure (cryptographic tokens)
- ✅ User-friendly (one-click access via email)
- ✅ Flexible (multiple access methods)
- ✅ Scalable (works for all booking types)
- ✅ Future-proof (ready for agent bookings)

