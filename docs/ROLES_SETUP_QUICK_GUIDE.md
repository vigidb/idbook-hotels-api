# Quick Setup Guide: Roles & Permissions for Business Group

## Step 1: Import Postman Collection

1. Open Postman
2. Click **Import**
3. Select `postman/Roles_Permissions_Management.postman_collection.json`
4. Select `postman/Roles_Permissions_Environment.postman_environment.json`
5. Set environment variables:
   - `base_url`: `http://localhost:8000/api/v1`
   - `access_token`: Your JWT token (get from login)
   - `business_id`: Your business ID (usually 1 for main Idbook)

## Step 2: Get Permission IDs

Before creating roles, you need to know which permission IDs to use.

**Request:**
```http
GET /api/v1/administrator/permissions/
Authorization: Bearer {{access_token}}
```

**Response:** List of all available permissions with their IDs.

**Common Permission IDs (you'll need to verify these match your system):**

| Permission | Django Codename | Custom Code | Typical ID Range |
|------------|----------------|-------------|------------------|
| View Booking | `view_booking` | `booking.view` | 1-10 |
| Create Booking | `add_booking` | `booking.create` | 1-10 |
| Update Booking | `change_booking` | `booking.update` | 1-10 |
| Cancel Booking | `delete_booking` | `booking.delete` | 1-10 |
| View Wallet | `view_wallet` | `wallet.view` | 10-20 |
| Refund | `refund` | `accounts.refund` | 10-20 |
| View Corporate | `view_corporate` | `corporate.view` | 20-30 |
| Approve Corporate | `approve_corporate` | `corporate.approve` | 20-30 |
| View Hotel | `view_hotel` | `hotel.view` | 30-40 |
| Manage Hotel | `manage_hotel` | `hotel.manage` | 30-40 |
| View Agent | `view_agent` | `agent.view` | 40-50 |
| Manage Agent | `manage_agent` | `agent.manage` | 40-50 |
| View Discount | `view_discount` | `discount.view` | 50-60 |
| Approve Discount | `approve_discount` | `discount.approve` | 50-60 |

**Note:** Permission IDs vary by system. Always check the actual IDs from the permissions endpoint.

## Step 3: Get Group ID

You need the Django Group ID for "BUSINESS-GRP".

**Option 1: Via Django Admin**
- Go to `/admin/auth/group/`
- Find "BUSINESS-GRP" and note the ID

**Option 2: Via API (if available)**
- Check your existing groups endpoint

**Typical Group IDs:**
- BUSINESS-GRP: Usually 1
- CORPORATE-GRP: Usually 2
- B2C-GRP: Usually 3
- HOTELIER-GRP: Usually 4
- AGENT-GRP: Usually 5

## Step 4: Create All Business Group Roles

Use the Postman collection folder: **"Business Group Setup - Roles"**

### 4.1 Accounts Manager

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Accounts Manager",
  "short_code": "ACC",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [1, 2, 3, 4, 5]
}
```

**Permissions needed:**
- View wallet
- Create wallet transaction
- Process refund
- Generate invoice
- View accounts

---

### 4.2 Content/Marketing Manager

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Content Manager",
  "short_code": "CM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [10, 11, 12, 13]
}
```

**Permissions needed:**
- View content
- Create content
- Update content
- Delete content

---

### 4.3 Promotion & Discount Manager

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Promotion Manager",
  "short_code": "PM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [20, 21, 22, 23, 24]
}
```

**Permissions needed:**
- View discount
- Create discount
- Update discount
- Approve discount
- Delete discount

---

### 4.4 Hotel Manager

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Hotel Manager",
  "short_code": "HM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [30, 31, 32, 33, 34]
}
```

**Permissions needed:**
- View hotel
- Create hotel
- Update hotel
- Manage hotel
- Delete hotel

---

### 4.5 Corporate Account Manager (with Association Scope)

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Corporate Account Manager",
  "short_code": "CAM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [40, 41, 42, 43]
}
```

**Permissions needed:**
- View corporate
- Create corporate
- Update corporate
- Approve corporate

**Then assign with association scope:**
```json
POST /api/v1/administrator/user-roles/
{
  "user": 25,
  "role": 5,  // Corporate Account Manager role ID
  "business": 1,
  "association_id": 123,  // Company ID
  "is_active": true
}
```

**Result:** User can only manage Company ID 123

---

### 4.6 Agent Manager (with Region & Association Scope)

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Agent Manager",
  "short_code": "AM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [50, 51, 52, 53]
}
```

**Permissions needed:**
- View agent
- Create agent
- Update agent
- Manage agent

**Then assign with both scopes:**
```json
POST /api/v1/administrator/user-roles/
{
  "user": 26,
  "role": 6,  // Agent Manager role ID
  "business": 1,
  "region": "TN",
  "association_id": 789,  // Agent ID
  "is_active": true
}
```

**Result:** User can manage agents only in Tamil Nadu and only for Agent ID 789

---

### 4.7 Booking Manager (All Types)

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Booking Manager",
  "short_code": "BM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [60, 61, 62, 63, 64, 65, 66, 67, 68]
}
```

**Permissions needed:**
- View booking (general)
- Create booking
- Update booking
- Cancel booking
- View flight booking
- View hotel booking
- View visa booking
- View car booking
- View holiday package

**Assign with association scope (Account Manager):**
```json
POST /api/v1/administrator/user-roles/
{
  "user": 27,
  "role": 7,  // Booking Manager role ID
  "business": 1,
  "association_id": 123,  // Company ID (for account manager)
  "is_active": true
}
```

**Result:** User can manage all booking types, but only for Company 123

---

### 4.8 Query Manager

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Query Manager",
  "short_code": "QM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [70, 71, 72, 73]
}
```

**Permissions needed:**
- View query
- Create query
- Update query
- Resolve query

---

### 4.9 HR - People Manager

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "HR Manager",
  "short_code": "HR",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [80, 81, 82, 83, 84]
}
```

**Permissions needed:**
- View user
- Create user
- Update user
- Delete user
- Manage user roles

---

### 4.10 Tech/Developer

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Developer",
  "short_code": "DEV",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [90, 91, 92, 93, 94, 95]
}
```

**Permissions needed:**
- View logs
- View analytics
- Manage configurations
- View system settings
- Manage API keys
- View error logs

---

### 4.11 Support Team

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Support Team",
  "short_code": "SUP",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [100, 101, 102, 103]
}
```

**Permissions needed:**
- View booking (read-only)
- View query
- Update query
- View customer

---

### 4.12 Super Admin

**Request:**
```json
POST /api/v1/administrator/roles/
{
  "name": "Super Admin",
  "short_code": "SA",
  "business": null,
  "group": 1,
  "is_system_role": true,
  "permissions": [1, 2, 3, 4, 5, 10, 11, 12, 20, 21, 22, 30, 31, 32, 40, 41, 42, 50, 51, 52, 60, 61, 62, 70, 71, 72, 80, 81, 82, 90, 91, 92, 100, 101, 102]
}
```

**Note:** 
- `business: null` (system role)
- `is_system_role: true`
- Include ALL permission IDs

---

## Step 5: Assign Roles to Users

Use the Postman collection folder: **"Super Admin - User Roles"**

### Example: Assign Accounts Manager to User

```json
POST /api/v1/administrator/user-roles/
{
  "user": 21,
  "role": 1,  // Accounts Manager role ID
  "business": 1,
  "is_active": true
}
```

### Example: Assign Corporate Manager with Association

```json
POST /api/v1/administrator/user-roles/
{
  "user": 25,
  "role": 5,  // Corporate Account Manager role ID
  "business": 1,
  "association_id": 123,  // Company ID
  "is_active": true
}
```

### Example: Assign Agent Manager with Region & Association

```json
POST /api/v1/administrator/user-roles/
{
  "user": 26,
  "role": 6,  // Agent Manager role ID
  "business": 1,
  "region": "TN",
  "association_id": 789,  // Agent ID
  "is_active": true
}
```

---

## Step 6: Verify Setup

### 6.1 Check User Permissions

```http
GET /api/v1/auth/user/permissions/?business_id=1
Authorization: Bearer {{access_token}}
```

**Expected Response:**
```json
{
  "permissions": ["booking.view", "accounts.refund", ...],
  "scopes": {
    "regions": ["TN"],
    "association_ids": ["123"]
  }
}
```

### 6.2 Test Permission Check

```http
GET /api/v1/auth/permissions/check/?permission=booking.view&business_id=1
Authorization: Bearer {{access_token}}
```

**Expected Response:**
```json
{
  "has_permission": true,
  "permission": "booking.view"
}
```

---

## Complete Workflow Example

### Scenario: Setup Corporate Account Manager for Tamil Nadu

1. **Get Permission IDs**
   ```http
   GET /api/v1/administrator/permissions/
   ```
   Note IDs for: `view_corporate`, `approve_corporate`, etc.

2. **Create Role**
   ```http
   POST /api/v1/administrator/roles/
   {
     "name": "Corporate Account Manager - TN",
     "short_code": "CAM-TN",
     "business": 1,
     "group": 1,
     "is_system_role": false,
     "permissions": [40, 41, 42, 43]
   }
   ```
   Save the returned `role_id` (e.g., 10)

3. **Assign to User**
   ```http
   POST /api/v1/administrator/user-roles/
   {
     "user": 30,
     "role": 10,
     "business": 1,
     "region": "TN",
     "association_id": 123,
     "is_active": true
   }
   ```

4. **Verify**
   ```http
   GET /api/v1/administrator/user-roles/?user_id=30&business_id=1
   ```

---

## Troubleshooting

### Issue: "Business not found"
**Solution:** Verify business_id exists:
```http
GET /api/v1/org-managements/business-details/
```

### Issue: "Invalid permission IDs"
**Solution:** Get valid permission IDs:
```http
GET /api/v1/administrator/permissions/
```

### Issue: "User doesn't have permission"
**Solution:** Check user's active roles:
```http
GET /api/v1/administrator/user-roles/?user_id=21&business_id=1
```

---

## Next Steps

1. ✅ Import Postman collection
2. ✅ Get permission IDs
3. ✅ Create all roles
4. ✅ Assign roles to users
5. ✅ Test permissions
6. ✅ Build React Vite UI using these APIs

All APIs are ready to use! 🚀
