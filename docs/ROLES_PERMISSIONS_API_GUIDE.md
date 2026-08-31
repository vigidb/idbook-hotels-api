# Roles & Permissions Management API Guide

Complete API documentation for managing roles, permissions, and scopes in Idbook Business Group.

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
All endpoints require JWT authentication:
```
Authorization: Bearer <access_token>
```

---

## 1. Super Admin APIs

### 1.1 Create Business Role

**Endpoint:** `POST /api/v1/administrator/roles/`

**Description:** Create a new role for a business (Super Admin only)

**Request:**
```json
{
  "name": "Accounts Manager",
  "short_code": "ACC",
  "description": "Manages all financial operations including wallet transactions, refunds, invoice generation, and account reconciliation. Has access to view and process all payment-related activities.",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [1, 2, 3, 4, 5]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Applied Coupon Created",
  "data": {
    "id": 10,
    "name": "Accounts Manager",
    "short_code": "ACC",
    "description": "Manages all financial operations including wallet transactions, refunds, invoice generation, and account reconciliation. Has access to view and process all payment-related activities.",
    "business": 1,
    "business_name": "Idbook Main",
    "group": 1,
    "group_name": "BUSINESS-GRP",
    "is_system_role": false,
    "permissions": [1, 2, 3, 4, 5],
    "permissions_detail": [
      {
        "id": 1,
        "name": "Can view booking",
        "codename": "view_booking",
        "permission_code": "booking.view",
        "module": "booking",
        "description": "View booking"
      },
      {
        "id": 2,
        "name": "Can add booking",
        "codename": "add_booking",
        "permission_code": "booking.create",
        "module": "booking",
        "description": "Create booking"
      }
    ],
    "created": "2024-01-15T10:30:00Z",
    "updated": "2024-01-15T10:30:00Z"
  }
}
```

---

### 1.2 List Roles (with Business Filter)

**Endpoint:** `GET /api/v1/administrator/roles/?business_id=1&is_system_role=false`

**Description:** Get all roles, optionally filtered by business

**Query Parameters:**
- `business_id` (optional): Filter by business
- `is_system_role` (optional): Filter system roles (true/false)

**Response:**
```json
{
  "status": "success",
  "message": "List Retrieved",
  "data": {
    "count": 15,
    "results": [
      {
        "id": 1,
        "name": "Accounts Manager",
        "short_code": "ACC",
        "description": "Manages all financial operations including wallet transactions, refunds, invoice generation, and account reconciliation.",
        "business": 1,
        "business_name": "Idbook Main",
        "group": 1,
        "group_name": "BUSINESS-GRP",
        "is_system_role": false,
        "permissions": [1, 2, 3]
      },
      {
        "id": 2,
        "name": "Content Manager",
        "short_code": "CM",
        "business": 1,
        "group": 1,
        "is_system_role": false,
        "permissions": [10, 11, 12]
      }
    ]
  }
}
```

---

### 1.3 Get Role Details

**Endpoint:** `GET /api/v1/administrator/roles/{id}/`

**Response:**
```json
{
  "status": "success",
  "message": "Item Retrieved",
    "data": {
      "id": 1,
      "name": "Accounts Manager",
      "short_code": "ACC",
      "description": "Manages all financial operations including wallet transactions, refunds, invoice generation, and account reconciliation.",
      "business": 1,
      "business_name": "Idbook Main",
      "group": 1,
      "group_name": "BUSINESS-GRP",
      "is_system_role": false,
      "permissions": [1, 2, 3, 4, 5],
      "permissions_detail": [...]
    }
}
```

---

### 1.4 Update Role

**Endpoint:** `PUT /api/v1/administrator/roles/{id}/`

**Request:**
```json
{
  "name": "Senior Accounts Manager",
  "short_code": "SACC",
  "description": "Senior-level accounts management with additional approval and reporting capabilities. Can manage all financial operations and has access to advanced reporting features.",
  "permissions": [1, 2, 3, 4, 5, 6, 7]
}
```

---

### 1.5 Clone Role to Another Business

**Endpoint:** `POST /api/v1/administrator/roles/{id}/clone/`

**Request:**
```json
{
  "business_id": 2
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Role cloned successfully",
  "data": {
    "id": 20,
    "name": "Accounts Manager",
    "short_code": "ACC",
    "business": 2,
    "group": 1,
    "is_system_role": false,
    "permissions": [1, 2, 3, 4, 5]
  }
}
```

---

### 1.6 Get Role Permissions

**Endpoint:** `GET /api/v1/administrator/roles/{id}/permissions/`

**Response:**
```json
{
  "status": "success",
  "message": "Role permissions retrieved",
  "data": {
    "role_id": 1,
    "permissions": [
      {
        "id": 1,
        "name": "Can view booking",
        "codename": "view_booking",
        "content_type": "booking.booking"
      },
      {
        "id": 2,
        "name": "Can add booking",
        "codename": "add_booking",
        "content_type": "booking.booking"
      }
    ]
  }
}
```

---

### 1.7 Update Role Permissions

**Endpoint:** `PUT /api/v1/administrator/roles/{id}/permissions/`

**Request:**
```json
{
  "permission_ids": [1, 2, 3, 4, 5, 10, 11]
}
```

---

### 1.8 List All Permissions

**Endpoint:** `GET /api/v1/administrator/permissions/`

**Response:**
```json
{
  "status": "success",
  "message": "permissions",
    "data": {
      "permissions_ids": [1, 2, 3, 4, 5, ...],
      "permissions": [
        {
          "id": 1,
          "name": "Can view booking",
          "codename": "view_booking",
          "permission_code": "booking.view",
          "module": "booking",
          "description": "View booking",
          "content_type": 10
        }
      ],
      "permissions_by_module": {
        "booking": [
          {
            "id": 1,
            "name": "Can view booking",
            "codename": "view_booking",
            "permission_code": "booking.view",
            "module": "booking",
            "description": "View booking"
          }
        ],
        "accounts": [...]
      }
    }
}
```

---

## 2. User Role Assignment APIs

### 2.1 Assign Role to User

**Endpoint:** `POST /api/v1/administrator/user-roles/`

**Description:** Assign a role to a user with optional scopes

**Request (Basic Assignment):**
```json
{
  "user": 21,
  "role": 1,
  "business": 1,
  "is_active": true
}
```

**Request (With Region Scope):**
```json
{
  "user": 21,
  "role": 1,
  "business": 1,
  "region": "TN",
  "is_active": true
}
```

**Request (With Association Scope - Corporate):**
```json
{
  "user": 21,
  "role": 5,
  "business": 1,
  "association_id": 123,
  "is_active": true
}
```

**Request (With Both Scopes):**
```json
{
  "user": 21,
  "role": 1,
  "business": 1,
  "region": "TN",
  "association_id": 123,
  "is_active": true
}
```

**Response:**
```json
{
  "status": "success",
  "message": "User role assigned successfully",
  "data": {
    "id": 50,
    "user": 21,
    "user_email": "user@example.com",
    "user_mobile": "9876543210",
    "user_name": "John Doe",
    "role": 1,
    "role_name": "Accounts Manager",
    "role_description": "Manages all financial operations including wallet transactions, refunds, invoice generation, and account reconciliation.",
    "role_short_code": "ACC",
    "business": 1,
    "business_name": "Idbook Main",
    "region": "TN",
    "association_id": 123,
    "is_active": true,
    "assigned_by": 1,
    "assigned_by_email": "admin@idbook.com",
    "assigned_at": "2024-01-15T10:30:00Z",
    "scope_description": "Region: TN | Company ID: 123",
    "created": "2024-01-15T10:30:00Z",
    "updated": "2024-01-15T10:30:00Z"
  }
}
```

---

### 2.2 List User Roles

**Endpoint:** `GET /api/v1/administrator/user-roles/?user_id=21&business_id=1`

**Query Parameters:**
- `user_id` (optional): Filter by user
- `business_id` (optional): Filter by business

**Response:**
```json
{
  "status": "success",
  "message": "List Retrieved",
  "data": {
    "count": 2,
    "results": [
      {
        "id": 50,
        "user": 21,
        "role": 1,
        "business": 1,
        "region": "TN",
        "association_id": 123,
        "is_active": true,
        "user_email": "user@example.com",
        "role_name": "Accounts Manager",
        "business_name": "Idbook Main"
      }
    ]
  }
}
```

---

### 2.3 Update User Role (Change Scope)

**Endpoint:** `PUT /api/v1/administrator/user-roles/{id}/`

**Request:**
```json
{
  "region": "KA",
  "association_id": 456,
  "is_active": true
}
```

---

### 2.4 Remove User Role

**Endpoint:** `DELETE /api/v1/administrator/user-roles/{id}/`

**Response:**
```json
{
  "status": "success",
  "message": "User role removed successfully",
  "data": null
}
```

---

### 2.5 Bulk Assign Roles

**Endpoint:** `POST /api/v1/administrator/user-roles/bulk-assign/`

**Request:**
```json
{
  "assignments": [
    {
      "user": 21,
      "role": 1,
      "business": 1,
      "region": "TN"
    },
    {
      "user": 22,
      "role": 2,
      "business": 1,
      "association_id": 123
    },
    {
      "user": 23,
      "role": 3,
      "business": 1,
      "region": "KA",
      "association_id": 456
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Bulk assignment completed: 3 created, 0 errors",
  "data": {
    "created": [
      {
        "id": 50,
        "user": 21,
        "role": 1,
        "business": 1,
        "region": "TN"
      },
      {
        "id": 51,
        "user": 22,
        "role": 2,
        "business": 1,
        "association_id": 123
      },
      {
        "id": 52,
        "user": 23,
        "role": 3,
        "business": 1,
        "region": "KA",
        "association_id": 456
      }
    ],
    "errors": []
  }
}
```

---

## 3. Permission Check APIs

### 3.1 Check User Permission

**Endpoint:** `GET /api/v1/auth/permissions/check/?permission=booking.view&business_id=1`

**Query Parameters:**
- `permission` (required): Permission code (e.g., `booking.view`)
- `business_id` (optional): Business context

**Response:**
```json
{
  "status": "success",
  "message": "Permission check completed",
  "data": {
    "has_permission": true,
    "permission": "booking.view"
  }
}
```

---

### 3.2 Get User Permissions

**Endpoint:** `GET /api/v1/auth/user/permissions/?business_id=1`

**Response:**
```json
{
  "status": "success",
  "message": "User permissions retrieved",
  "data": {
    "permissions": [
      "booking.view",
      "booking.create",
      "accounts.refund",
      "corporate.approve"
    ],
    "roles": [
      {
        "id": 1,
        "name": "Accounts Manager",
        "short_code": "ACC",
        "region": "TN",
        "association_id": 123
      }
    ],
    "scopes": {
      "regions": ["TN", "KA"],
      "association_ids": ["123", "456"]
    },
    "business_id": 1
  }
}
```

---

## 4. Complete Setup Examples for Business Group

### 4.1 Setup: Accounts Role

**Step 1: Create Accounts Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Accounts Manager",
  "short_code": "ACC",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [1, 2, 3, 4, 5]
}
```

**Step 2: Assign to User with Region Scope**
```http
POST /api/v1/administrator/user-roles/
Content-Type: application/json

{
  "user": 21,
  "role": 1,
  "business": 1,
  "region": "TN",
  "is_active": true
}
```

---

### 4.2 Setup: Content/Marketing Role

**Step 1: Create Content Manager Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Content Manager",
  "short_code": "CM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [10, 11, 12, 13]
}
```

---

### 4.3 Setup: Promotion & Discount Management

**Step 1: Create Promotion Manager Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Promotion Manager",
  "short_code": "PM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [20, 21, 22, 23, 24]
}
```

---

### 4.4 Setup: Hotel Management

**Step 1: Create Hotel Manager Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Hotel Manager",
  "short_code": "HM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [30, 31, 32, 33, 34]
}
```

---

### 4.5 Setup: Corporate Management (with Association Scope)

**Step 1: Create Corporate Account Manager Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Corporate Account Manager",
  "short_code": "CAM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [40, 41, 42, 43]
}
```

**Step 2: Assign to User with Association Scope**
```http
POST /api/v1/administrator/user-roles/
Content-Type: application/json

{
  "user": 25,
  "role": 5,
  "business": 1,
  "association_id": 123,
  "is_active": true
}
```

**Result:** User can only manage bookings for Company ID 123

---

### 4.6 Setup: Agent Management (with Region & Association Scope)

**Step 1: Create Agent Manager Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Agent Manager",
  "short_code": "AM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [50, 51, 52, 53]
}
```

**Step 2: Assign with Both Scopes**
```http
POST /api/v1/administrator/user-roles/
Content-Type: application/json

{
  "user": 26,
  "role": 6,
  "business": 1,
  "region": "TN",
  "association_id": 789,
  "is_active": true
}
```

**Result:** User can manage agents only in Tamil Nadu and only for Agent ID 789

---

### 4.7 Setup: Booking Management (Multiple Types)

**Step 1: Create Booking Manager Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Booking Manager",
  "short_code": "BM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [
    60,  // view_booking
    61,  // add_booking
    62,  // change_booking
    63,  // cancel_booking
    64,  // view_flight_booking
    65,  // view_hotel_booking
    66,  // view_visa_booking
    67,  // view_car_booking
    68   // view_holiday_package
  ]
}
```

**Step 2: Assign with Association Scope (Account Manager)**
```http
POST /api/v1/administrator/user-roles/
Content-Type: application/json

{
  "user": 27,
  "role": 7,
  "business": 1,
  "association_id": 123,
  "is_active": true
}
```

**Result:** User can manage all booking types, but only for Company 123

---

### 4.8 Setup: Query Management

**Step 1: Create Query Manager Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Query Manager",
  "short_code": "QM",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [70, 71, 72, 73]
}
```

---

### 4.9 Setup: HR - People Management

**Step 1: Create HR Manager Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "HR Manager",
  "short_code": "HR",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [80, 81, 82, 83, 84]
}
```

---

### 4.10 Setup: Tech/Developer Role

**Step 1: Create Developer Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Developer",
  "short_code": "DEV",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [90, 91, 92, 93, 94, 95]
}
```

---

### 4.11 Setup: Support Team Role

**Step 1: Create Support Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Support Team",
  "short_code": "SUP",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [100, 101, 102, 103]
}
```

---

### 4.12 Setup: Super Admin Role

**Step 1: Create Super Admin Role (System Role)**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Super Admin",
  "short_code": "SA",
  "business": null,
  "group": 1,
  "is_system_role": true,
  "permissions": [1, 2, 3, 4, 5, 10, 11, 12, ...]  // All permissions
}
```

**Note:** System roles have `business: null` and `is_system_role: true`

---

## 5. Permission Code Reference

### Common Permission Codes (Django Format → Custom Format)

| Django Codename | Custom Code | Description |
|----------------|-------------|-------------|
| `view_booking` | `booking.view` | View bookings |
| `add_booking` | `booking.create` | Create bookings |
| `change_booking` | `booking.update` | Update bookings |
| `delete_booking` | `booking.delete` | Delete bookings |
| `view_wallet` | `wallet.view` | View wallet |
| `refund` | `accounts.refund` | Process refunds |
| `view_corporate` | `corporate.view` | View corporate accounts |
| `approve_corporate` | `corporate.approve` | Approve corporate accounts |
| `view_hotel` | `hotel.view` | View hotels |
| `manage_hotel` | `hotel.manage` | Manage hotels |
| `view_agent` | `agent.view` | View agents |
| `manage_agent` | `agent.manage` | Manage agents |
| `view_discount` | `discount.view` | View discounts |
| `approve_discount` | `discount.approve` | Approve discounts |

---

## 6. Complete Workflow Example

### Scenario: Setup Corporate Account Manager for Tamil Nadu

**Step 1: Get Business ID**
```http
GET /api/v1/org-managements/business-details/
```

**Step 2: Get Group ID (BUSINESS-GRP)**
```http
GET /api/v1/administrator/permissions/
# Note: Groups are managed via Django admin or API
```

**Step 3: Get Permission IDs**
```http
GET /api/v1/administrator/permissions/
# Find IDs for: view_booking, add_booking, view_corporate, approve_corporate
```

**Step 4: Create Role**
```http
POST /api/v1/administrator/roles/
Content-Type: application/json

{
  "name": "Corporate Account Manager - TN",
  "short_code": "CAM-TN",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [40, 41, 42, 43]
}
```

**Step 5: Assign Role to User**
```http
POST /api/v1/administrator/user-roles/
Content-Type: application/json

{
  "user": 30,
  "role": 10,
  "business": 1,
  "region": "TN",
  "association_id": 123,
  "is_active": true
}
```

**Step 6: Verify Assignment**
```http
GET /api/v1/administrator/user-roles/?user_id=30&business_id=1
```

**Step 7: Test Permission**
```http
GET /api/v1/auth/permissions/check/?permission=corporate.approve&business_id=1
```

---

## 7. Postman Collection Structure

### Collection: Idbook Roles & Permissions Management

```
📁 Idbook Roles & Permissions
  📁 Super Admin - Roles
    📄 Create Role
    📄 List Roles
    📄 Get Role Details
    📄 Update Role
    📄 Clone Role
    📄 Get Role Permissions
    📄 Update Role Permissions
  📁 Super Admin - User Roles
    📄 Assign Role to User
    📄 List User Roles
    📄 Update User Role
    📄 Remove User Role
    📄 Bulk Assign Roles
  📁 Permission Checks
    📄 Check Permission
    📄 Get User Permissions
  📁 Business Group Setup
    📄 Accounts Manager
    📄 Content Manager
    📄 Promotion Manager
    📄 Hotel Manager
    📄 Corporate Manager
    📄 Agent Manager
    📄 Booking Manager
    📄 Query Manager
    📄 HR Manager
    📄 Developer
    📄 Support Team
    📄 Super Admin
```

---

## 8. Sample Environment Variables for Postman

```json
{
  "base_url": "http://localhost:8000/api/v1",
  "access_token": "your_jwt_token_here",
  "business_id": 1,
  "user_id": 21,
  "role_id": 1
}
```

---

## 9. Error Responses

### 400 Bad Request
```json
{
  "status": "error",
  "message": "Validation Error",
  "data": {
    "business": ["This field is required."],
    "permissions": ["Invalid permission IDs."]
  }
}
```

### 403 Forbidden
```json
{
  "status": "error",
  "message": "You don't have permission to manage this user",
  "data": null
}
```

### 404 Not Found
```json
{
  "status": "error",
  "message": "Role not found",
  "data": null
}
```

---

## 10. Quick Reference: All Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/administrator/roles/` | Create role |
| GET | `/administrator/roles/` | List roles |
| GET | `/administrator/roles/{id}/` | Get role |
| PUT | `/administrator/roles/{id}/` | Update role |
| POST | `/administrator/roles/{id}/clone/` | Clone role |
| GET | `/administrator/roles/{id}/permissions/` | Get role permissions |
| PUT | `/administrator/roles/{id}/permissions/` | Update role permissions |
| POST | `/administrator/user-roles/` | Assign role to user |
| GET | `/administrator/user-roles/` | List user roles |
| PUT | `/administrator/user-roles/{id}/` | Update user role |
| DELETE | `/administrator/user-roles/{id}/` | Remove user role |
| POST | `/administrator/user-roles/bulk-assign/` | Bulk assign roles |
| GET | `/auth/permissions/check/` | Check permission |
| GET | `/auth/user/permissions/` | Get user permissions |

---

This guide provides complete API documentation for managing roles, permissions, and scopes in your Idbook Business Group system.
