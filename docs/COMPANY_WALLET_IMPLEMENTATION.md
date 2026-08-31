# Company Wallet and User Group-Based Booking Implementation

## Overview

This document describes the implementation of user group-based wallet deduction and company_id validation for bookings. The system now automatically determines which wallet to use (company vs personal) based on the user's group, and enforces company_id requirement for corporate users.

## Business Rules

### User Groups and Wallet Types

1. **Corporate Users** (CORP-ADMIN, CORP-EMP, CORPORATE-GRP):
   - **Required**: `company_id` must be provided for all bookings
   - **Wallet**: Company wallet (deducted from company's wallet balance)
   - **Validation**: System validates company_id exists before booking creation

2. **B2C Users** (B2C-GRP, B2C-GUEST):
   - **Required**: No company_id needed
   - **Wallet**: Personal wallet (deducted from user's personal wallet balance)
   - **Validation**: No company_id validation required

3. **Other Users** (HTLR-ADMIN, FRANCH-ADMIN, etc.):
   - **Required**: No company_id needed
   - **Wallet**: Personal wallet (deducted from user's personal wallet balance)

## Implementation Details

### 1. Token Generation with User Group Information

**Location**: `apps/booking/utils/booking_utils.py`

**Function**: `generate_guest_access_token(booking_id, user=None)`

- Updated to include user group information in the token
- Token format: `{type}_{group}_{hash}`
  - `type`: "guest" for B2C users, "user" for others
  - `group`: User's default_group (truncated to 10 chars)
  - `hash`: Secure hash for uniqueness

**Example Tokens**:
- B2C user: `guest_B2C-GRP_abc123...`
- Corporate user: `user_CORP-ADM_xyz789...`

### 2. Wallet Deduction Logic

**Location**: `apps/booking/utils/booking_utils.py`

**Function**: `deduct_booking_amount(booking, company_id=None)`

**Key Changes**:
- Automatically determines user group from `booking.user`
- Checks if user is corporate (CORP-ADMIN, CORP-EMP, CORPORATE-GRP)
- For corporate users:
  - Validates `company_id` exists (from parameter or user.company_id)
  - Deducts from company wallet using `deduct_company_wallet_balance()`
  - Creates transaction with `company_id`
- For B2C/other users:
  - Deducts from personal wallet using `deduct_wallet_balance()`
  - No company_id in transaction

**Code Flow**:
```python
1. Get user from booking
2. Determine user's group (default_group or groups)
3. Check if corporate user
4. If corporate:
   - Validate company_id exists
   - Deduct from company wallet
5. If B2C/other:
   - Deduct from personal wallet
```

### 3. Company ID Validation

**Location**: `apps/booking/utils/booking_utils.py`

**Function**: `validate_company_id_for_corporate_user(user, company_id=None)`

- Validates that corporate users have `company_id`
- Returns `(is_valid, error_message)` tuple
- Used in booking creation flows to enforce requirement

### 4. Booking Creation Validation

#### Flight Bookings

**Location**: `apps/booking/subviews/enhanced_flight_viewset.py`

**Method**: `create_booking()`

- Added validation before booking creation
- Checks if user is corporate
- Validates `company_id` exists (from request or user.company_id)
- Returns error if corporate user lacks company_id

#### Hotel Bookings

**Location**: `apps/booking/viewsets.py`

**Method**: `hotel_pre_confirm_booking()`

- Added validation before booking creation
- Validates `company_id` for corporate users
- Sets `company_id` in booking_dict if valid

#### General Bookings (Serializer)

**Location**: `apps/booking/serializers.py`

**Method**: `BookingSerializer.create()`

- Added validation in serializer's create method
- Validates `company_id` before saving booking
- Raises ValidationError if corporate user lacks company_id

### 5. Payment Processing Updates

**Location**: `apps/booking/utils/flight_payment_utils.py`

**Method**: `FlightPaymentProcessor._process_wallet_payment()`

- Updated to work with new `deduct_booking_amount()` logic
- Automatically determines wallet type based on user group
- Still checks balance before deduction (for both wallet types)

### 6. Token Validation Updates

**Location**: `apps/booking/utils/booking_utils.py`

**Functions**:
- `validate_guest_access_token()`: Updated to accept both "guest_" and "user_" prefixed tokens
- `get_user_group_from_token()`: New function to extract group from token

## User Group Detection

The system detects user groups using:

1. **Primary**: `user.default_group` field
2. **Fallback**: User's groups (many-to-many relationship)
3. **Corporate Groups**: `CORP-ADMIN`, `CORP-EMP`, `CORPORATE-GRP`
4. **B2C Groups**: `B2C-GRP`, `B2C-GUEST`

## Booking Types Supported

All booking types now enforce company_id validation and use appropriate wallets:

1. ✅ **Hotel Bookings** - Validated and wallet deduction updated
2. ✅ **Flight Bookings** - Validated and wallet deduction updated
3. ✅ **Vehicle Bookings** - Validated via serializer
4. ✅ **Holiday Package Bookings** - Validated via serializer

## Wallet Deduction Flow

```
Booking Created
    ↓
User Group Determined
    ↓
Is Corporate User?
    ├─ Yes → Validate company_id exists
    │         ↓
    │      Deduct from Company Wallet
    │         ↓
    │      Create Transaction with company_id
    │
    └─ No → Deduct from Personal Wallet
              ↓
           Create Transaction without company_id
```

## Error Handling

### Company ID Missing for Corporate User

**Error Code**: `COMPANY_ID_REQUIRED`

**Message**: "Company ID is required for corporate users"

**HTTP Status**: `400 Bad Request`

**Response**:
```json
{
  "status": "error",
  "message": "Company ID is required for corporate users",
  "errors": [
    {
      "field": "company_id",
      "message": "Company ID is required for corporate users"
    }
  ],
  "error_code": "COMPANY_ID_REQUIRED"
}
```

## Testing Checklist

### Corporate User Bookings

- [ ] Corporate user creates booking without company_id → Should fail with validation error
- [ ] Corporate user creates booking with company_id → Should succeed
- [ ] Corporate user booking payment → Should deduct from company wallet
- [ ] Corporate user booking transaction → Should include company_id

### B2C User Bookings

- [ ] B2C user creates booking without company_id → Should succeed
- [ ] B2C user creates booking with company_id → Should succeed (company_id ignored)
- [ ] B2C user booking payment → Should deduct from personal wallet
- [ ] B2C user booking transaction → Should not include company_id

### Token Generation

- [ ] Corporate user booking → Token includes group info
- [ ] B2C user booking → Token includes group info
- [ ] Token validation → Correctly extracts group from token

### All Booking Types

- [ ] Hotel booking with corporate user → Validates company_id
- [ ] Flight booking with corporate user → Validates company_id
- [ ] Vehicle booking with corporate user → Validates company_id
- [ ] Holiday package booking with corporate user → Validates company_id

## Migration Notes

No database migrations required. All changes are in application logic.

## Backward Compatibility

- Existing bookings continue to work
- Old tokens (without group info) still validate
- Company_id parameter is still accepted but now validated for corporate users
- Personal wallet deductions unchanged for B2C users

## Future Enhancements

1. **Token Expiration**: Add expiration time for tokens
2. **Wallet Balance Checks**: Pre-validate wallet balance before booking creation
3. **Multi-Wallet Support**: Support for users with both personal and company wallets
4. **Agent Bookings**: Extend same pattern for agent bookings

## Summary

The implementation ensures:
- ✅ Corporate users must provide company_id for bookings
- ✅ Wallet deductions automatically use correct wallet type
- ✅ Tokens include user group information
- ✅ All booking types enforce company_id validation
- ✅ Payment processing uses appropriate wallet
- ✅ Backward compatible with existing bookings

