# Password Login with Email/Mobile Verification Flow

## Overview
This document explains the complete flow for password-based login when a user's email and/or mobile number is not verified.

## API Endpoints

### 1. Password Login
**Endpoint:** `POST {{base_url}}/auth/login`

**Request:**
```json
{
  "username": "user@example.com",  // or mobile number
  "password": "password123",
  "group_name": "B2C-GRP"  // optional
}
```

**Response when verification required:**
```json
{
  "status": "error",
  "message": "Email and mobile verification required. OTP sent to both.",
  "data": {
    "redirect": true,
    "verification_required": ["email", "mobile"],
    "email": "user@example.com",
    "mobile_number": "9876543210"
  },
  "status_code": 307
}
```

### 2. Generate OTP (Alternative)
**Endpoint:** `POST {{base_url}}/auth/otp/generate-otp/`

**Request:**
```json
{
  "username": "user@example.com",  // or mobile number
  "otp_for": "LOGIN",
  "group_name": "B2C-GRP"
}
```

### 3. Verify OTP
**Endpoint:** `POST {{base_url}}/auth/otp/verify-otp/`

**Request:**
```json
{
  "username": "user@example.com",  // or mobile number
  "otp": "1234",
  "otp_for": "LOGIN",
  "group_name": "B2C-GRP"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Otp Verification Success",
  "data": {
    "refreshToken": "...",
    "accessToken": "...",
    "user": { ... }
  }
}
```

## Complete Flow

### Scenario 1: Both Email and Mobile Not Verified

1. **User attempts password login**
   - User sends: `POST /auth/login` with username and password
   - Backend validates credentials
   - Backend checks: `user.email_verified = False` AND `user.mobile_verified = False`

2. **Backend sends OTP to both**
   - Generates separate OTPs (different OTP for email and mobile)
   - Sends email OTP to email via `email_generate_otp_process()`
   - Sends mobile OTP to mobile via `mobile_generate_otp_process()`
   - Returns response with `verification_required: ["email", "mobile"]`

3. **User verifies with email OTP**
   - User sends: `POST /auth/otp/verify-otp/` with `username: "user@example.com"` and OTP
   - Backend:
     - Validates OTP against email OTP record
     - Sets `user.email_verified = True`
     - Generates and returns authentication tokens

4. **User verifies with mobile OTP** (if mobile still not verified)
   - User sends: `POST /auth/otp/verify-otp/` with `username: "9876543210"` and OTP
   - Backend:
     - Validates OTP against mobile OTP record
     - Sets `user.mobile_verified = True`
     - Updates user record

### Scenario 2: Only Email Not Verified

1. **User attempts password login**
   - Backend checks: `user.email_verified = False` BUT `user.mobile_verified = True`

2. **Backend sends OTP to email only**
   - Generates OTP
   - Sends OTP to email
   - Returns response with `verification_required: ["email"]`

3. **User verifies with email OTP**
   - Backend sets `user.email_verified = True`
   - Returns authentication tokens

### Scenario 3: Only Mobile Not Verified

1. **User attempts password login**
   - Backend checks: `user.email_verified = True` BUT `user.mobile_verified = False`

2. **Backend sends OTP to mobile only**
   - Generates OTP
   - Sends OTP to mobile
   - Returns response with `verification_required: ["mobile"]`

3. **User verifies with mobile OTP**
   - Backend sets `user.mobile_verified = True`
   - Returns authentication tokens

### Scenario 4: Both Email and Mobile Verified

1. **User attempts password login**
   - Backend checks: `user.email_verified = True` AND `user.mobile_verified = True`

2. **Backend returns tokens directly**
   - No OTP required
   - Returns authentication tokens immediately

## Key Implementation Details

### Password Login (`LoginAPIView.post()`)

- Checks both `user.email_verified` and `user.mobile_verified`
- If either is `False`, generates OTP(s) and sends to unverified medium(s)
- Uses the same OTP for both email and mobile if both need verification
- Returns `307 Temporary Redirect` status with verification requirements

### Verify OTP (`OtpBasedUserEntryAPIView.verify_otp()`)

- Handles `otp_for="LOGIN"` case
- Determines if `username` is email or mobile number
- Updates verification status accordingly:
  - If email: sets `user.email_verified = True`
  - If mobile: sets `user.mobile_verified = True` and saves mobile number if missing
- Generates and returns authentication tokens after successful verification

### OTP Storage

- Email OTP: Stored in `UserOtp` with `user_account=email`, `otp_for="LOGIN"`, `otp_type="EMAIL"`
- Mobile OTP: Stored in `UserOtp` with `user_account=mobile`, `otp_for="LOGIN"`, `otp_type="MOBILE"`
- **Different OTP values** are generated for email and mobile for security reasons
- Each verification channel has its own unique OTP

## Frontend Integration

### Step 1: Attempt Password Login
```javascript
const loginResponse = await fetch('/auth/login', {
  method: 'POST',
  body: JSON.stringify({ username, password, group_name })
});

if (loginResponse.status === 307) {
  // Verification required
  const data = await loginResponse.json();
  const { verification_required, email, mobile_number } = data.data;
  
  // Show OTP input form
  // If both email and mobile need verification, user can verify either one first
}
```

### Step 2: Verify OTP
```javascript
// Verify with email OTP
const verifyResponse = await fetch('/auth/otp/verify-otp/', {
  method: 'POST',
  body: JSON.stringify({
    username: email,  // or mobile_number
    otp: otpValue,
    otp_for: 'LOGIN',
    group_name: 'B2C-GRP'
  })
});

if (verifyResponse.ok) {
  const data = await verifyResponse.json();
  // Store tokens and redirect to dashboard
  localStorage.setItem('accessToken', data.data.accessToken);
  localStorage.setItem('refreshToken', data.data.refreshToken);
}
```

## Notes

- **Separate OTPs** are generated and sent to email and mobile when both need verification (for security)
- User must verify each medium separately (email and mobile) if both are unverified
- Each medium requires its own unique OTP - email OTP cannot be used for mobile verification and vice versa
- After verifying one medium, user can still login, but the other medium remains unverified until verified separately
- OTP expires after `OTP_EXPIRY_MIN` minutes (configured in settings)
- OTP verification attempts are rate-limited to prevent brute force attacks
