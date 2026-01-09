# User Groups Management API Guide

Complete API documentation for assigning and removing Django Groups from users.

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

## 1. Assign/Remove Groups from User

### 1.1 Assign Groups to User (Set - Replace All)

**Endpoint:** `POST /api/v1/administrator/users/{user_id}/groups/`

**Description:** Replace all groups for a user with the provided groups

**Request:**
```json
{
  "groups": [1, 2, 3],
  "action": "set"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "User groups updated successfully",
  "data": {
    "id": 21,
    "email": "user@example.com",
    "mobile_number": "9876543210",
    "name": "John Doe",
    "groups": [
      {"id": 1, "name": "BUSINESS-GRP"},
      {"id": 2, "name": "CORPORATE-GRP"},
      {"id": 3, "name": "AGENT-GRP"}
    ],
    "roles": [...],
    ...
  }
}
```

---

### 1.2 Add Groups to User (Keep Existing)

**Endpoint:** `POST /api/v1/administrator/users/{user_id}/groups/`

**Description:** Add groups to user while keeping existing groups

**Request:**
```json
{
  "groups": [4, 5],
  "action": "add"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Groups added to user successfully",
  "data": {
    "id": 21,
    "email": "user@example.com",
    "groups": [
      {"id": 1, "name": "BUSINESS-GRP"},
      {"id": 2, "name": "CORPORATE-GRP"},
      {"id": 4, "name": "HOTELIER-GRP"},
      {"id": 5, "name": "B2C-GRP"}
    ],
    ...
  }
}
```

---

### 1.3 Remove Groups from User

**Endpoint:** `POST /api/v1/administrator/users/{user_id}/groups/`

**Description:** Remove specific groups from user

**Request:**
```json
{
  "groups": [2, 3],
  "action": "remove"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Groups removed from user successfully",
  "data": {
    "id": 21,
    "email": "user@example.com",
    "groups": [
      {"id": 1, "name": "BUSINESS-GRP"}
    ],
    ...
  }
}
```

---

### 1.4 Update User (Alternative Method)

**Endpoint:** `PUT /api/v1/administrator/users/{user_id}/` or `PATCH /api/v1/administrator/users/{user_id}/`

**Description:** Update user including groups (if groups field is included in serializer)

**Note:** This method depends on whether the UserSerializer includes groups field. Currently, UserSerializer doesn't include groups, so use the dedicated groups endpoint above.

---

## 2. Alternative: Update Groups and Roles Together

**Endpoint:** `POST /api/v1/auth/user/update-groups-roles/`

**Description:** Update both groups and roles for a user (from authentication app)

**Request:**
```json
{
  "user_id": 21,
  "users_groups": ["BUSINESS-GRP", "CORPORATE-GRP"],
  "users_roles": ["Accounts Manager", "Booking Manager"],
  "removal_groups": ["AGENT-GRP"],
  "removal_roles": ["Support Team"]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "User groups and roles updated successfully",
  "data": []
}
```

**Note:** This endpoint uses group names (strings) instead of IDs.

---

## 3. Get User with Groups

**Endpoint:** `GET /api/v1/administrator/users/{user_id}/`

**Description:** Get user details including assigned groups

**Request:**
```
GET /api/v1/administrator/users/21/
```

**Response:**
```json
{
  "status": "success",
  "message": "Item Retrieved",
  "data": {
    "id": 21,
    "email": "user@example.com",
    "mobile_number": "9876543210",
    "name": "John Doe",
    "groups": [
      {"id": 1, "name": "BUSINESS-GRP"},
      {"id": 2, "name": "CORPORATE-GRP"}
    ],
    "roles": [
      {"id": 1, "name": "Accounts Manager"}
    ],
    ...
  }
}
```

---

## 4. List Users by Group

**Endpoint:** `GET /api/v1/administrator/users/?group=BUSINESS-GRP`

**Description:** Get all users in a specific group

**Request:**
```
GET /api/v1/administrator/users/?group=BUSINESS-GRP
```

**Response:**
```json
{
  "status": "success",
  "message": "List Retrieved",
  "data": {
    "count": 10,
    "results": [
      {
        "id": 21,
        "email": "user@example.com",
        "groups": [
          {"id": 1, "name": "BUSINESS-GRP"}
        ],
        ...
      }
    ]
  }
}
```

---

## 5. Sample Use Cases

### 5.1 Assign User to Business Group

```bash
POST /api/v1/administrator/users/21/groups/
{
  "groups": [1],  # BUSINESS-GRP ID
  "action": "set"
}
```

### 5.2 Add Corporate Access to Existing User

```bash
POST /api/v1/administrator/users/21/groups/
{
  "groups": [2],  # CORPORATE-GRP ID
  "action": "add"
}
```

### 5.3 Remove Agent Access from User

```bash
POST /api/v1/administrator/users/21/groups/
{
  "groups": [5],  # AGENT-GRP ID
  "action": "remove"
}
```

### 5.4 Replace All Groups

```bash
POST /api/v1/administrator/users/21/groups/
{
  "groups": [1, 2],  # BUSINESS-GRP and CORPORATE-GRP
  "action": "set"
}
```

---

## 6. Request Parameters

### Groups Endpoint Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `groups` | Array of Integers | Yes | List of group IDs to assign/remove |
| `action` | String | No | Action to perform: "set" (default), "add", or "remove" |

### Action Types

- **`set`** (default): Replace all user groups with the provided groups
- **`add`**: Add groups to user (keeps existing groups)
- **`remove`**: Remove groups from user (keeps other groups)

---

## 7. Error Responses

### Invalid Group IDs

```json
{
  "status": "error",
  "message": "Invalid group IDs: [99, 100]",
  "data": {
    "invalid_group_ids": [99, 100]
  }
}
```

### Invalid Action

```json
{
  "status": "error",
  "message": "Invalid action. Use 'set', 'add', or 'remove'",
  "data": null
}
```

### Groups Not a List

```json
{
  "status": "error",
  "message": "Groups must be a list of group IDs",
  "data": null
}
```

---

## 8. Notes

1. **Group IDs**: Use numeric group IDs, not group names
2. **Action Parameter**: If not provided, defaults to "set" (replace all)
3. **Validation**: All group IDs must exist, otherwise the request fails
4. **Permissions**: Requires appropriate permissions (superuser or staff)
5. **User ID**: Use the user's numeric ID in the URL path

---

## 9. Quick Reference

| Operation | Method | Endpoint | Action |
|-----------|--------|----------|--------|
| Replace all groups | POST | `/api/v1/administrator/users/{id}/groups/` | `"action": "set"` |
| Add groups | POST | `/api/v1/administrator/users/{id}/groups/` | `"action": "add"` |
| Remove groups | POST | `/api/v1/administrator/users/{id}/groups/` | `"action": "remove"` |
| Get user groups | GET | `/api/v1/administrator/users/{id}/` | - |
| List users by group | GET | `/api/v1/administrator/users/?group=GROUP_NAME` | - |

---

## 10. Example: Complete Workflow

### Step 1: Get Group IDs
```bash
GET /api/v1/administrator/groups/
```
Response will show all groups with their IDs.

### Step 2: Assign Groups to User
```bash
POST /api/v1/administrator/users/21/groups/
{
  "groups": [1, 2],
  "action": "set"
}
```

### Step 3: Verify Assignment
```bash
GET /api/v1/administrator/users/21/
```
Check the `groups` field in the response.
