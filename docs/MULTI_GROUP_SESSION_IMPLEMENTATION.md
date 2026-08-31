# Multi-Group Session Implementation

## Problem Statement

Users can belong to multiple groups (B2C, Corporate, Business/Admin), but the system was using `default_group` from the database. This prevented users from:
- Switching roles on different websites/apps simultaneously
- Having different active groups in different browser tabs/sessions
- Accessing admin dashboard while logged into B2C booking site

## Solution: Active Group in JWT Token

We've implemented a solution where the **active group is stored in the JWT token**, allowing users to have different active groups in different sessions.

## Implementation Details

### 1. Custom JWT Token with Active Group

**File**: `apps/authentication/tokens.py`

- Created `CustomRefreshToken` and `CustomAccessToken` classes
- Tokens now include `active_group` claim
- Tokens also include `company_id` for quick access

**Token Claims**:
```json
{
  "user_id": 123,
  "active_group": "CORP-ADMIN",
  "company_id": 456,
  "exp": 1234567890,
  "token_type": "access"
}
```

### 2. Token Utilities

**File**: `apps/authentication/utils/token_utils.py`

**Functions**:
- `get_active_group_from_token(token_string)` - Extract active_group from token
- `get_active_group_from_request(request)` - Get active_group from request's token
- `get_user_active_group(user, request)` - Get active group with fallback logic

**Priority**:
1. `active_group` from JWT token (if request provided)
2. `user.default_group`
3. First group from `user.groups`

### 3. Switch Group Endpoint

**Endpoint**: `POST /api/auth/user/switch-group/`

**Request**:
```json
{
  "active_group": "CORP-ADMIN"
}
```

**Response**:
```json
{
  "refreshToken": "...",
  "accessToken": "...",
  "user": {
    "id": 123,
    "active_group": "CORP-ADMIN",
    ...
  }
}
```

**Features**:
- Validates user belongs to requested group
- Returns new tokens with updated `active_group`
- Allows switching between groups without re-login

### 4. Updated Login Flow

**File**: `apps/authentication/viewsets.py`

- Login accepts optional `active_group` parameter
- If provided, token is generated with that active group
- If not provided, uses `user.default_group`

**Login Request**:
```json
{
  "username": "user@example.com",
  "password": "password",
  "active_group": "B2C-GRP"  // Optional
}
```

### 5. Wallet Deduction Updates

**File**: `apps/booking/utils/booking_utils.py`

**Function**: `deduct_booking_amount(booking, company_id=None, request=None)`

- Now accepts `request` parameter
- Uses `active_group` from token to determine wallet type
- Falls back to `default_group` if token not available

**Logic**:
```python
active_group = get_user_active_group(user, request)
is_corporate_user = active_group in ('CORP-ADMIN', 'CORP-EMP', 'CORPORATE-GRP')
```

### 6. Booking Filter Updates

**File**: `apps/booking/viewsets.py`

**Method**: `booking_filter_ops()`

- Uses `active_group` from token instead of `default_group`
- Filters bookings based on active group context
- Allows viewing different booking sets based on active group

### 7. Company ID Validation Updates

**File**: `apps/booking/utils/booking_utils.py`

**Function**: `validate_company_id_for_corporate_user(user, company_id=None, request=None)`

- Uses `active_group` from token to determine if user is corporate
- Validates `company_id` requirement based on active group
- Works correctly when user switches between B2C and Corporate roles

## Usage Flow

### Scenario 1: User with Multiple Groups

1. **User logs into B2C site**:
   ```bash
   POST /api/auth/login
   {
     "username": "user@example.com",
     "password": "password",
     "active_group": "B2C-GRP"
   }
   ```
   - Gets token with `active_group: "B2C-GRP"`
   - Can make B2C bookings
   - Wallet deductions use personal wallet

2. **User opens admin dashboard in new tab**:
   ```bash
   POST /api/auth/user/switch-group
   {
     "active_group": "BUSINESS-GRP"
   }
   ```
   - Gets new token with `active_group: "BUSINESS-GRP"`
   - Can access admin features
   - Different token = different session context

3. **User makes corporate booking**:
   ```bash
   POST /api/auth/user/switch-group
   {
     "active_group": "CORP-ADMIN"
   }
   ```
   - Gets new token with `active_group: "CORP-ADMIN"`
   - Can make corporate bookings
   - Wallet deductions use company wallet

### Scenario 2: Simultaneous Sessions

- **Tab 1**: B2C site with `active_group: "B2C-GRP"` token
- **Tab 2**: Admin dashboard with `active_group: "BUSINESS-GRP"` token
- **Tab 3**: Corporate portal with `active_group: "CORP-ADMIN"` token

Each tab has its own token with its own active group, allowing simultaneous access.

## API Endpoints

### Switch Active Group
```
POST /api/auth/user/switch-group/
Authorization: Bearer <current_token>

Body:
{
  "active_group": "CORP-ADMIN"
}

Response:
{
  "refreshToken": "...",
  "accessToken": "...",
  "user": {
    "active_group": "CORP-ADMIN",
    ...
  }
}
```

### Login with Active Group
```
POST /api/auth/login

Body:
{
  "username": "user@example.com",
  "password": "password",
  "active_group": "B2C-GRP"  // Optional
}
```

## Frontend Integration

### Switching Groups

```javascript
// Switch to corporate group
const response = await fetch('/api/auth/user/switch-group/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${currentToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    active_group: 'CORP-ADMIN'
  })
});

const { refreshToken, accessToken, user } = await response.json();

// Store new tokens
localStorage.setItem('refreshToken', refreshToken);
localStorage.setItem('accessToken', accessToken);

// Now all subsequent requests use the new active_group
```

### Checking Active Group

The active group is available in:
1. **Token payload** (decode JWT to get `active_group` claim)
2. **Login/switch-group response** (`user.active_group`)
3. **User profile endpoint** (if updated to include active_group)

## Backward Compatibility

✅ **Fully backward compatible**

- If `active_group` not in token, falls back to `default_group`
- Existing tokens continue to work
- Old code that doesn't pass `request` still works (uses `default_group`)
- No database changes required

## Security Considerations

1. **Token Validation**: Active group is validated against user's actual groups
2. **Group Membership**: Users can only switch to groups they belong to
3. **Token Integrity**: Active group is part of signed JWT, cannot be tampered
4. **Session Isolation**: Each token has its own active group, sessions are independent

## Testing Checklist

- [ ] User with multiple groups can switch between them
- [ ] Wallet deduction uses correct wallet based on active_group
- [ ] Booking filters work correctly with active_group
- [ ] Company_id validation works with active_group
- [ ] User can have multiple sessions with different active groups
- [ ] Switching group returns new tokens
- [ ] Invalid group switching is rejected
- [ ] Backward compatibility with old tokens

## Migration Notes

**No database migration required** - all changes are in application logic.

**Token Migration**:
- Old tokens (without `active_group`) continue to work
- They will use `default_group` as fallback
- Users can get new tokens by switching groups or re-login

## Summary

✅ **Problem Solved**: Users can now have different active groups in different sessions
✅ **No Breaking Changes**: Fully backward compatible
✅ **Secure**: Group membership validated, tokens signed
✅ **Flexible**: Works with all booking types and payment flows

