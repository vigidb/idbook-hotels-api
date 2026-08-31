# Permissions vs Scopes: Key Differences

## Overview

**Permissions** and **Scopes** are **NOT the same**. They work together to provide fine-grained access control:

- **Permissions** = **WHAT** actions can be performed
- **Scopes** = **WHERE/WHOM** those actions can be performed on

## Permissions (WHAT)

Permissions define **what actions** a user can perform in the system.

### Examples:
- `booking.view` - Can view bookings
- `booking.create` - Can create bookings
- `booking.cancel` - Can cancel bookings
- `accounts.refund` - Can process refunds
- `corporate.approve` - Can approve corporate accounts

### How it works:
```python
# User has permission to view bookings
has_permission(user, "booking.view", business)  # Returns True/False
```

### In JWT Token:
```json
{
  "permissions": [
    "booking.view",
    "booking.create",
    "accounts.refund"
  ]
}
```

## Scopes (WHERE/WHOM)

Scopes define **geographical or organizational boundaries** where permissions apply.

### Two Types of Scopes:

#### 1. Region Scope
Restricts access to specific geographical regions.

**Example:**
- User can view bookings, but **only in Tamil Nadu (TN)** and **Karnataka (KA)**

```python
UserRole:
  user: John
  role: Booking Manager
  business: Business A
  region: "TN"  # ← Scope: Only Tamil Nadu
  permissions: ["booking.view", "booking.create"]
```

**Result:**
- ✅ Can view booking in Chennai (TN)
- ✅ Can view booking in Bangalore (KA) - if also has KA region
- ❌ Cannot view booking in Mumbai (MH)

#### 2. Association Scope
Restricts access to specific organizations/entities.

**Example:**
- Corporate Account Manager can manage bookings, but **only for Company X**

```python
UserRole:
  user: Sarah
  role: Corporate Account Manager
  business: Business A
  association_id: 123  # ← Scope: Only Company ID 123
  permissions: ["booking.view", "booking.update"]
```

**Result:**
- ✅ Can view booking for Company 123
- ❌ Cannot view booking for Company 456

### In JWT Token:
```json
{
  "scopes": {
    "regions": ["TN", "KA"],
    "association_ids": ["123", "456"]
  }
}
```

## How They Work Together

### Permission Check Flow:

```python
def has_permission(user, permission_code, business, obj=None):
    # Step 1: Check if user has the PERMISSION (WHAT)
    if user_has_permission(user, permission_code):
        
        # Step 2: If object provided, check SCOPE (WHERE/WHOM)
        if obj:
            # Check region scope
            if user_role.region and obj.region != user_role.region:
                return False  # ❌ Out of region scope
            
            # Check association scope
            if user_role.association_id and obj.company_id != user_role.association_id:
                return False  # ❌ Out of association scope
        
        return True  # ✅ Has permission AND within scope
    else:
        return False  # ❌ Doesn't have permission
```

## Real-World Example

### Scenario: Regional Booking Manager

**User:** Rajesh  
**Role:** Booking Manager  
**Business:** Idbook Mumbai  
**Permissions:** `["booking.view", "booking.create", "booking.cancel"]`  
**Scopes:** 
- `region: "TN"` (Tamil Nadu only)
- `association_id: 789` (Company 789 only)

### What Rajesh Can Do:

| Action | Booking Location | Booking Company | Result |
|--------|------------------|-----------------|--------|
| View booking | Chennai (TN) | Company 789 | ✅ **Allowed** - Has permission + within scope |
| View booking | Mumbai (MH) | Company 789 | ❌ **Denied** - Out of region scope |
| View booking | Chennai (TN) | Company 456 | ❌ **Denied** - Out of association scope |
| Create booking | Chennai (TN) | Company 789 | ✅ **Allowed** - Has permission + within scope |
| Cancel booking | Chennai (TN) | Company 789 | ✅ **Allowed** - Has permission + within scope |
| Refund booking | Chennai (TN) | Company 789 | ❌ **Denied** - Doesn't have `accounts.refund` permission |

## Summary Table

| Aspect | Permissions | Scopes |
|--------|-------------|--------|
| **Purpose** | WHAT actions | WHERE/WHOM actions apply |
| **Type** | Action-based | Location/Entity-based |
| **Examples** | `booking.view`, `accounts.refund` | `region: "TN"`, `association_id: 123` |
| **Stored in** | Role → Permissions (ManyToMany) | UserRole → region, association_id |
| **Check** | "Can user do X?" | "Can user do X on this object?" |
| **Scope** | Global (if no scope restriction) | Limited to specific regions/entities |

## When to Use Each

### Use Permissions When:
- You need to control **what actions** users can perform
- Example: "Can this user refund money?" → Check `accounts.refund` permission

### Use Scopes When:
- You need to restrict **where** or **for whom** actions can be performed
- Example: "Can this user view bookings in Mumbai?" → Check region scope
- Example: "Can this user manage Company X's bookings?" → Check association scope

## Combined Example in Code

```python
# User wants to view a booking
booking = Booking.objects.get(id=123)
booking.region = "TN"
booking.company_id = 789

# Check permission + scope
if has_permission(user, "booking.view", business, obj=booking):
    # User has:
    # 1. ✅ "booking.view" permission (WHAT)
    # 2. ✅ Region scope includes "TN" (WHERE)
    # 3. ✅ Association scope includes company 789 (WHOM)
    return booking
else:
    # Either:
    # - ❌ No "booking.view" permission, OR
    # - ❌ Region doesn't match, OR
    # - ❌ Company doesn't match
    raise PermissionDenied()
```

## Conclusion

**Permissions** and **Scopes** are **complementary**, not the same:

- **Permissions** = The **ability** to do something
- **Scopes** = The **boundaries** where that ability applies

Together, they provide **RBAC (Role-Based Access Control) + ABAC (Attribute-Based Access Control)** - a powerful hybrid permission system!
