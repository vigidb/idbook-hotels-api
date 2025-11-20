# JWT Token and User Group Integration Analysis

## Current JWT Token Implementation

### Token Generation
- **Library**: `rest_framework_simplejwt`
- **Token Type**: JWT (JSON Web Token)
- **Generation**: `RefreshToken.for_user(user)`

### Token Payload (What's in the JWT)
By default, JWT tokens from `rest_framework_simplejwt` contain:
- `user_id` - The user's ID (from USER_ID_CLAIM)
- `exp` - Token expiration timestamp
- `token_type` - Token type (usually "access")
- `jti` - JWT ID (unique token identifier)

**Note**: User group information is **NOT** included in the JWT token payload by default.

### Login Response (What's sent to client)
The login response includes full user data:
```json
{
  "refreshToken": "...",
  "accessToken": "...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "groups": [...],
    "roles": [...],
    "default_group": "CORP-ADMIN",
    "company_id": 123,
    ...
  }
}
```

## How User is Resolved from Token

### Authentication Flow
1. Client sends request with `Authorization: Bearer <access_token>`
2. DRF's `JWTAuthentication` extracts `user_id` from token
3. Database query: `User.objects.get(id=user_id)`
4. Full User object is attached to `request.user`
5. `request.user` has **all** User model fields including:
   - `default_group`
   - `company_id`
   - `groups` (many-to-many relationship)
   - `roles` (many-to-many relationship)

## Integration with Wallet Deduction Flow

### Current Implementation Status: ✅ **WORKS CORRECTLY**

Our wallet deduction logic uses `booking.user`, which is a ForeignKey to the User model:

```python
def deduct_booking_amount(booking, company_id=None):
    user = booking.user  # This is a full User model instance
    user_default_group = user.default_group  # ✅ Available
    user_groups = list(user.groups.values_list('name', flat=True))  # ✅ Available
    company_id = getattr(user, 'company_id', None)  # ✅ Available
```

**Why it works:**
- `booking.user` is a database relationship, not token-based
- When booking is created, the full User object is saved
- When wallet deduction happens, we read from the database User object
- All user fields (groups, company_id, etc.) are available from the database

## Token vs Database Access

| Information | In JWT Token? | Available from DB? | Used in Wallet Flow? |
|------------|---------------|-------------------|---------------------|
| `user_id` | ✅ Yes | ✅ Yes | ✅ Yes (via booking.user) |
| `default_group` | ❌ No | ✅ Yes | ✅ Yes |
| `company_id` | ❌ No | ✅ Yes | ✅ Yes |
| `groups` | ❌ No | ✅ Yes | ✅ Yes |
| `roles` | ❌ No | ✅ Yes | ✅ Yes |

## Recommendation: Current Implementation is Sufficient

**For wallet deduction flow**: ✅ **No changes needed**

The current implementation works correctly because:
1. Bookings store the User object (ForeignKey)
2. Wallet deduction reads from `booking.user` (database)
3. All user group information is available from the database
4. No need to extract group info from JWT token

## Optional: Custom JWT Token with Group Info

If you want to include group information in the JWT token itself (for other use cases like frontend routing, API gateway decisions, etc.), you can customize the token:

### Custom Token Claims

Create a custom token class in `apps/authentication/tokens.py`:

```python
from rest_framework_simplejwt.tokens import RefreshToken

class CustomRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        
        # Add custom claims
        token['default_group'] = user.default_group or ''
        token['company_id'] = user.company_id if hasattr(user, 'company_id') else None
        
        # Add groups
        user_groups = list(user.groups.values_list('name', flat=True))
        token['groups'] = user_groups
        
        return token
```

Then update settings:
```python
SIMPLE_JWT = {
    # ... existing settings ...
    "TOKEN_OBTAIN_SERIALIZER": "apps.authentication.serializers.CustomTokenObtainPairSerializer",
}
```

**Note**: This is optional and not required for the wallet deduction flow to work.

## Testing the Integration

### Test Case 1: Corporate User Booking
1. Corporate user logs in → Gets JWT token
2. Creates booking → `booking.user` is set to User instance
3. Payment initiated → `deduct_booking_amount()` called
4. Function reads `booking.user.default_group` → Detects "CORP-ADMIN"
5. Deducts from company wallet → ✅ Works

### Test Case 2: B2C User Booking
1. B2C user logs in → Gets JWT token
2. Creates booking → `booking.user` is set to User instance
3. Payment initiated → `deduct_booking_amount()` called
4. Function reads `booking.user.default_group` → Detects "B2C-GRP"
5. Deducts from personal wallet → ✅ Works

## Conclusion

✅ **The current JWT token implementation works correctly with the wallet deduction flow**

**Reasons:**
1. JWT token contains `user_id`
2. DRF resolves `user_id` to full User object from database
3. Booking stores User object (ForeignKey)
4. Wallet deduction reads from database User object (not token)
5. All group information is available from database

**No changes required** for the wallet deduction flow to work correctly.

