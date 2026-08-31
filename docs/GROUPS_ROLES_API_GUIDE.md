# Groups & Roles Management API Guide

Complete API documentation for managing Django Groups and Roles with full CRUD operations.

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

## 1. Groups Management APIs

### 1.1 Create Group

**Endpoint:** `POST /api/v1/administrator/groups/`

**Description:** Create a new Django Group

**Request:**
```json
{
  "name": "CORPORATE-GRP",
  "permissions": [1, 2, 3, 4, 5]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Group created successfully",
  "data": {
    "id": 2,
    "name": "CORPORATE-GRP",
    "permissions": [1, 2, 3, 4, 5],
    "user_count": 0,
    "role_count": 0,
    "permissions_detail": [
      {
        "id": 1,
        "name": "Can view booking",
        "codename": "view_booking",
        "permission_code": "booking.view",
        "module": "booking",
        "description": "View booking"
      }
    ]
  }
}
```

---

### 1.2 List Groups

**Endpoint:** `GET /api/v1/administrator/groups/`

**Description:** Get all groups, optionally filtered by name

**Query Parameters:**
- `name` (optional): Filter by group name (case-insensitive partial match)

**Request:**
```
GET /api/v1/administrator/groups/?name=CORPORATE
```

**Response:**
```json
{
  "status": "success",
  "message": "Groups retrieved successfully",
  "data": {
    "count": 2,
    "results": [
      {
        "id": 1,
        "name": "BUSINESS-GRP",
        "permissions": [1, 2, 3],
        "user_count": 5,
        "role_count": 3,
        "permissions_detail": [...]
      },
      {
        "id": 2,
        "name": "CORPORATE-GRP",
        "permissions": [4, 5, 6],
        "user_count": 2,
        "role_count": 1,
        "permissions_detail": [...]
      }
    ]
  }
}
```

---

### 1.3 Get Group Details

**Endpoint:** `GET /api/v1/administrator/groups/{id}/`

**Description:** Get details of a specific group

**Request:**
```
GET /api/v1/administrator/groups/1/
```

**Response:**
```json
{
  "status": "success",
  "message": "Group retrieved successfully",
  "data": {
    "id": 1,
    "name": "BUSINESS-GRP",
    "permissions": [1, 2, 3, 4, 5],
    "user_count": 5,
    "role_count": 3,
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
    ]
  }
}
```

---

### 1.4 Update Group

**Endpoint:** `PUT /api/v1/administrator/groups/{id}/` or `PATCH /api/v1/administrator/groups/{id}/`

**Description:** Update a group (PUT for full update, PATCH for partial)

**Request (PUT - Full Update):**
```json
{
  "name": "CORPORATE-GRP-UPDATED",
  "permissions": [1, 2, 3, 4, 5, 6, 7]
}
```

**Request (PATCH - Partial Update):**
```json
{
  "name": "CORPORATE-GRP-UPDATED"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Group updated successfully",
  "data": {
    "id": 2,
    "name": "CORPORATE-GRP-UPDATED",
    "permissions": [1, 2, 3, 4, 5, 6, 7],
    "user_count": 2,
    "role_count": 1,
    "permissions_detail": [...]
  }
}
```

---

### 1.5 Delete Group

**Endpoint:** `DELETE /api/v1/administrator/groups/{id}/`

**Description:** Delete a group (only if it has no users or roles)

**Request:**
```
DELETE /api/v1/administrator/groups/2/
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Group deleted successfully",
  "data": {
    "id": 2,
    "name": "CORPORATE-GRP"
  }
}
```

**Response (Error - Has Users):**
```json
{
  "status": "error",
  "message": "Cannot delete group. It has 5 user(s) assigned. Please remove all users first.",
  "data": {
    "user_count": 5
  }
}
```

**Response (Error - Has Roles):**
```json
{
  "status": "error",
  "message": "Cannot delete group. It has 3 role(s) associated. Please remove all roles first.",
  "data": {
    "role_count": 3
  }
}
```

---

## 2. Roles Management APIs

### 2.1 Create Role

**Endpoint:** `POST /api/v1/administrator/roles/`

**Description:** Create a new role

**⚠️ Important:** Only **superusers** can create system roles (`is_system_role: true`). Regular admins can only create non-system roles.

**Request (Regular Admin - Non-System Role):**
```json
{
  "name": "Accounts Manager",
  "short_code": "ACC",
  "description": "Manages all financial operations including wallet transactions, refunds, invoice generation, and account reconciliation.",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [1, 2, 3, 4, 5]
}
```

**Request (Superuser - System Role):**
```json
{
  "name": "BUS-ADMIN",
  "short_code": "BA",
  "description": "Business Administrator with full access to all business operations.",
  "business": null,
  "group": 1,
  "is_system_role": true,
  "permissions": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Role Created",
  "data": {
    "id": 10,
    "name": "Accounts Manager",
    "short_code": "ACC",
    "description": "Manages all financial operations...",
    "business": 1,
    "business_name": "Idbook Main",
    "group": 1,
    "group_name": "BUSINESS-GRP",
    "is_system_role": false,
    "permissions": [1, 2, 3, 4, 5],
    "permissions_detail": [...],
    "created": "2024-01-15T10:30:00Z",
    "updated": "2024-01-15T10:30:00Z"
  }
}
```

**Response (Error - Regular Admin Trying to Create System Role):**
```json
{
  "status": "error",
  "message": "Only superusers can create system roles. Please set is_system_role to false or contact a superuser.",
  "data": null
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
    "description": "Manages all financial operations including wallet transactions, refunds, invoice generation, and account reconciliation.",
    "business": 1,
    "business_name": "Idbook Main",
    "group": 1,
    "group_name": "BUSINESS-GRP",
    "is_system_role": false,
    "permissions": [1, 2, 3, 4, 5],
    "permissions_detail": [...],
    "created": "2024-01-15T10:30:00Z",
    "updated": "2024-01-15T10:30:00Z"
  }
}
```

---

### 2.2 List Roles

**Endpoint:** `GET /api/v1/administrator/roles/`

**Description:** Get all roles, optionally filtered by business or system role status

**⚠️ Important:** 
- **Superusers** can see all roles (system and non-system)
- **Regular Admins** can only see non-system roles (system roles are automatically filtered out)

**Query Parameters:**
- `business_id` (optional): Filter by business ID
- `is_system_role` (optional): Filter system roles (true/false) - **Only works for superusers**

**Request (Superuser):**
```
GET /api/v1/administrator/roles/?business_id=1&is_system_role=false
GET /api/v1/administrator/roles/?is_system_role=true  # Shows only system roles
```

**Request (Regular Admin):**
```
GET /api/v1/administrator/roles/?business_id=1
# System roles are automatically filtered out, even if is_system_role=true is specified
```

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
        "description": "Manages all financial operations...",
        "business": 1,
        "business_name": "Idbook Main",
        "group": 1,
        "group_name": "BUSINESS-GRP",
        "is_system_role": false,
        "permissions": [1, 2, 3],
        "permissions_detail": [...]
      }
    ]
  }
}
```

---

### 2.3 Get Role Details

**Endpoint:** `GET /api/v1/administrator/roles/{id}/`

**Description:** Get details of a specific role

**Request:**
```
GET /api/v1/administrator/roles/1/
```

**Response:**
```json
{
  "status": "success",
  "message": "Item Retrieved",
  "data": {
    "id": 1,
    "name": "Accounts Manager",
    "short_code": "ACC",
    "description": "Manages all financial operations...",
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

### 2.4 Update Role

**Endpoint:** `PUT /api/v1/administrator/roles/{id}/` or `PATCH /api/v1/administrator/roles/{id}/`

**Description:** Update a role (PUT for full update, PATCH for partial)

**⚠️ Important:** 
- **Superusers** can update any role (system or non-system)
- **Regular Admins** can only update non-system roles
- **Regular Admins** cannot convert non-system roles to system roles

**Request (Regular Admin - Non-System Role):**
```json
{
  "name": "Senior Accounts Manager",
  "short_code": "SACC",
  "description": "Senior-level accounts management with additional approval and reporting capabilities.",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [1, 2, 3, 4, 5, 6, 7]
}
```

**Request (Superuser - System Role):**
```json
{
  "name": "BUS-ADMIN-UPDATED",
  "short_code": "BA",
  "description": "Updated Business Administrator role",
  "business": null,
  "group": 1,
  "is_system_role": true,
  "permissions": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
}
```

**Response (Error - Regular Admin Trying to Update System Role):**
```json
{
  "status": "error",
  "message": "Only superusers can modify system roles. This role is protected.",
  "data": null
}
```

**Response (Error - Regular Admin Trying to Convert to System Role):**
```json
{
  "status": "error",
  "message": "Only superusers can create or modify system roles. Please set is_system_role to false or contact a superuser.",
  "data": null
}
```

**Request (PATCH - Partial Update):**
```json
{
  "description": "Updated description for Accounts Manager role"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Applied Coupon Updated",
  "data": {
    "id": 1,
    "name": "Senior Accounts Manager",
    "short_code": "SACC",
    "description": "Senior-level accounts management with additional approval and reporting capabilities.",
    "business": 1,
    "business_name": "Idbook Main",
    "group": 1,
    "group_name": "BUSINESS-GRP",
    "is_system_role": false,
    "permissions": [1, 2, 3, 4, 5, 6, 7],
    "permissions_detail": [...]
  }
}
```

---

### 2.5 Delete Role

**Endpoint:** `DELETE /api/v1/administrator/roles/{id}/`

**Description:** Delete a role

**⚠️ Important:**
- **Superusers** can delete system roles and non-system roles
- **Regular Admins** can only delete non-system roles (if no user assignments)

**Request:**
```
DELETE /api/v1/administrator/roles/10/
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Role deleted successfully",
  "data": {
    "id": 10,
    "name": "Accounts Manager"
  }
}
```

**Response (Error - Regular Admin Trying to Delete System Role):**
```json
{
  "status": "error",
  "message": "Only superusers can delete system roles. This role is protected.",
  "data": null
}
```

**Response (Error - Has User Assignments):**
```json
{
  "status": "error",
  "message": "Cannot delete role. It has 5 user assignment(s). Please remove all assignments first.",
  "data": {
    "user_assignments_count": 5
  }
}
```

**Response (Error - Has User Assignments):**
```json
{
  "status": "error",
  "message": "Cannot delete role. It has 5 user assignment(s). Please remove all assignments first.",
  "data": {
    "user_assignments_count": 5
  }
}
```

---

## 3. Additional Role Operations

### 3.1 Clone Role

**Endpoint:** `POST /api/v1/administrator/roles/{id}/clone/`

**Description:** Clone an existing role with a new name

**Request:**
```json
{
  "name": "Accounts Manager - Copy",
  "short_code": "ACC2"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Role cloned successfully",
  "data": {
    "id": 11,
    "name": "Accounts Manager - Copy",
    "short_code": "ACC2",
    ...
  }
}
```

---

### 3.2 Get/Update Role Permissions

**Endpoint:** `GET /api/v1/administrator/roles/{id}/permissions/` or `PUT /api/v1/administrator/roles/{id}/permissions/`

**Description:** Get or update permissions for a role

**Request (GET):**
```
GET /api/v1/administrator/roles/1/permissions/
```

**Response (GET):**
```json
{
  "status": "success",
  "message": "Role permissions retrieved",
  "data": {
    "role_id": 1,
    "role_name": "Accounts Manager",
    "role_description": "Manages all financial operations...",
    "permissions": [
      {
        "id": 1,
        "name": "Can view booking",
        "codename": "view_booking",
        "permission_code": "booking.view",
        "module": "booking",
        "description": "View booking"
      }
    ]
  }
}
```

**Request (PUT):**
```json
{
  "permission_ids": [1, 2, 3, 4, 5, 6, 7]
}
```

**Response (PUT):**
```json
{
  "status": "success",
  "message": "Role permissions updated",
  "data": {
    "id": 1,
    "name": "Accounts Manager",
    "permissions": [1, 2, 3, 4, 5, 6, 7],
    ...
  }
}
```

---

## 4. Common Use Cases

### 4.1 Create a New Business Group

```bash
# Step 1: Create the group
POST /api/v1/administrator/groups/
{
  "name": "BUSINESS-GRP",
  "permissions": []
}

# Step 2: Create roles for the group
POST /api/v1/administrator/roles/
{
  "name": "Business Admin",
  "short_code": "BA",
  "description": "Full business administration access",
  "business": 1,
  "group": 1,  # Use the group ID from step 1
  "is_system_role": true,
  "permissions": [1, 2, 3, ...]  # All permissions
}
```

### 4.2 Update Group Permissions

```bash
# Update group permissions
PUT /api/v1/administrator/groups/1/
{
  "name": "BUSINESS-GRP",
  "permissions": [1, 2, 3, 4, 5, 10, 11, 12]
}
```

### 4.3 Create Custom Role for Business

```bash
POST /api/v1/administrator/roles/
{
  "name": "Custom Manager",
  "short_code": "CM",
  "description": "Custom role for specific business needs",
  "business": 1,
  "group": 1,
  "is_system_role": false,
  "permissions": [1, 2, 3]
}
```

### 4.4 Delete Unused Role

```bash
# First check if role has assignments
GET /api/v1/administrator/roles/10/

# If no assignments, delete
DELETE /api/v1/administrator/roles/10/
```

---

## 5. Error Handling

### Common Errors

**400 Bad Request:**
- Validation errors (missing required fields, invalid data)
- Cannot delete system role
- Cannot delete role/group with assignments

**401 Unauthorized:**
- Missing or invalid JWT token

**403 Forbidden:**
- User doesn't have permission to perform action

**404 Not Found:**
- Group or Role with specified ID doesn't exist

**500 Internal Server Error:**
- Server-side errors

---

## 6. Notes

1. **System Roles**: Cannot be deleted. These are protected roles like BUS-ADMIN, CORP-ADMIN, etc.

2. **Group Deletion**: Can only delete groups that have:
   - No users assigned
   - No roles associated

3. **Role Deletion**: Can only delete roles that have:
   - Not a system role
   - No user assignments

4. **Permissions**: When updating permissions, provide the full list. The update replaces all existing permissions.

5. **Business Context**: Roles can be business-specific or system-wide (business=null for system roles).

6. **Group Names**: Group names should follow conventions like "BUSINESS-GRP", "CORPORATE-GRP", etc.

---

## 7. Postman Collection

All these APIs are available in the Postman collection:
- **File:** `postman/Roles_Permissions_Management.postman_collection.json`
- **Environment:** `postman/Roles_Permissions_Environment.postman_environment.json`

Import both files into Postman for easy testing.
