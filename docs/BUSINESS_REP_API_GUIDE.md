# Business Representative (Account Manager) API Guide

This guide explains how to manage business representatives (account managers) for corporate companies and hotel properties.

## Overview

Business representatives (account managers) can be assigned to:
- **Corporate Companies** (`CompanyDetail`) - Uses existing `business_rep` field
- **Hotel Properties** (`Property`) - Uses new `business_rep` field

**Note:** Business representative and account manager are the same thing. We use `business_rep` as the field name for consistency.

## Database Changes

### Models Updated

1. **CompanyDetail** (`apps/org_resources/models.py`)
   - Uses existing `business_rep` field (ForeignKey to User)
   - Related name: `business_representative`

2. **Property** (`apps/hotels/models.py`)
   - Added `business_rep` field (ForeignKey to User)
   - Related name: `property_business_rep`
   - Help text: "Business representative (account manager) assigned to this property."

### Migrations

A migration has been created:
- `apps/hotels/migrations/0002_add_business_rep_to_property.py` - Adds business_rep to Property

**To apply migrations:**
```bash
cd IDBOOKAPI
python manage.py migrate
```

---

## API Endpoints

### Corporate Company Business Representative APIs

#### 1. Get Business Representative Details

**Endpoint:** `GET /api/v1/org-resources/company-details/{company_id}/`

**Authentication:** Required (if configured)

**Response:** The `business_rep` field is included in the company details:
```json
{
  "status": "success",
  "data": {
    "id": 789,
    "company_name": "ABC Corporation",
    "business_rep": {
      "id": 123,
      "name": "John Doe",
      "email": "john.doe@example.com",
      "mobile_number": "+1234567890"
    },
    // ... other company fields
  }
}
```

**If no business rep assigned:**
```json
{
  "business_rep": null
}
```

---

#### 2. Update Business Representative

**Endpoint:** `PATCH /api/v1/org-resources/company-details/{company_id}/`

**Authentication:** Required

**Request Body:**
```json
{
  "business_rep": 456
}
```

**To remove business rep:**
```json
{
  "business_rep": null
}
```

**You can also update multiple fields at once:**
```json
{
  "business_rep": 456,
  "company_name": "Updated Company Name",
  "company_email": "new@email.com"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 789,
    "company_name": "ABC Corporation",
    "business_rep": {
      "id": 456,
      "name": "Jane Smith",
      "email": "jane.smith@example.com",
      "mobile_number": "+1234567890"
    },
    // ... other company fields
  },
  "message": "Company updated successfully"
}
```

---

#### 3. Bulk Assign Business Representative to Multiple Companies

**Endpoint:** `POST /api/v1/org-resources/company-details/bulk-assign-business-rep/`

**Authentication:** Required

**Request Body:**
```json
{
  "business_rep_id": 456,
  "company_ids": [1, 2, 3, 4, 5]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "business_rep": {
      "id": 456,
      "name": "Jane Smith",
      "email": "jane.smith@example.com"
    },
    "updated_companies": 5,
    "company_ids": [1, 2, 3, 4, 5]
  },
  "message": "Business representative assigned to 5 company(ies) successfully"
}
```

**Error Response (if some companies not found):**
```json
{
  "status": "error",
  "data": null,
  "message": "Companies with IDs [6, 7] not found",
  "error_code": "COMPANIES_NOT_FOUND"
}
```

---

### Hotel Property Business Representative APIs

#### 1. Get Business Representative Details

**Endpoint:** `GET /api/v1/hotels/properties/{property_id}/`

**Authentication:** Required (if configured)

**Response:** The `business_rep` field is included in the property details (visible to authorized users):
```json
{
  "status": "success",
  "data": {
    "id": 789,
    "name": "Grand Hotel",
    "business_rep": {
      "id": 123,
      "name": "John Doe",
      "email": "john.doe@example.com",
      "mobile_number": "+1234567890"
    },
    // ... other property fields
  }
}
```

**If no business rep assigned:**
```json
{
  "business_rep": null
}
```

**Note:** Business rep details are only visible to:
- Superusers
- Property managers (`managed_by`)
- Property creators (`added_by`)

---

#### 2. Update Business Representative

**Endpoint:** `PATCH /api/v1/hotels/properties/{property_id}/`

**Authentication:** Required

**Request Body:**
```json
{
  "business_rep": 456
}
```

**To remove business rep:**
```json
{
  "business_rep": null
}
```

**You can also update multiple fields at once:**
```json
{
  "business_rep": 456,
  "name": "Updated Hotel Name",
  "status": "Active"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 789,
    "name": "Grand Hotel",
    "business_rep": {
      "id": 456,
      "name": "Jane Smith",
      "email": "jane.smith@example.com",
      "mobile_number": "+1234567890"
    },
    // ... other property fields
  },
  "message": "Property updated successfully"
}
```

---

#### 3. Bulk Assign Business Representative to Multiple Properties

**Endpoint:** `POST /api/v1/hotels/properties/bulk-assign-business-rep/`

**Authentication:** Required

**Request Body:**
```json
{
  "business_rep_id": 456,
  "property_ids": [10, 11, 12, 13, 14]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "business_rep": {
      "id": 456,
      "name": "Jane Smith",
      "email": "jane.smith@example.com"
    },
    "updated_properties": 5,
    "property_ids": [10, 11, 12, 13, 14]
  },
  "message": "Business representative assigned to 5 property(ies) successfully"
}
```

**Error Response (if some properties not found):**
```json
{
  "status": "error",
  "data": null,
  "message": "Properties with IDs [15, 16] not found",
  "error_code": "PROPERTIES_NOT_FOUND"
}
```

---

## Serializer Updates

### CompanyDetailSerializer

The `business_rep` field is included in the serialized output:

```json
{
  "id": 1,
  "company_name": "ABC Corporation",
  "business_rep": {
    "id": 123,
    "name": "John Doe",
    "email": "john.doe@example.com",
    "mobile_number": "+1234567890"
  },
  // ... other fields
}
```

### PropertyRetrieveSerializer

The `business_rep` field is included in property details (visible to authorized users only):

```json
{
  "id": 1,
  "name": "Grand Hotel",
  "business_rep": {
    "id": 123,
    "name": "John Doe",
    "email": "john.doe@example.com",
    "mobile_number": "+1234567890"
  },
  // ... other fields
}
```

**Note:** Business rep details are only visible to:
- Superusers
- Property managers (`managed_by`)
- Property creators (`added_by`)

---

## Error Codes

| Error Code | Description |
|------------|-------------|
| `VALIDATION_ERROR` | Missing required fields or invalid data format |
| `USER_NOT_FOUND` | Business rep user ID does not exist |
| `COMPANIES_NOT_FOUND` | One or more company IDs not found (bulk assign) |
| `PROPERTIES_NOT_FOUND` | One or more property IDs not found (bulk assign) |
| `INTERNAL_SERVER_ERROR` | Unexpected server error |

---

## Example Usage

### Assign Business Rep to a Single Company

```bash
curl -X PATCH \
  https://api.example.com/api/v1/org-resources/company-details/1/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_rep": 456
  }'
```

**Update multiple fields:**
```bash
curl -X PATCH \
  https://api.example.com/api/v1/org-resources/company-details/1/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_rep": 456,
    "company_name": "Updated Name"
  }'
```

### Assign Business Rep to a Single Property

```bash
curl -X PATCH \
  https://api.example.com/api/v1/hotels/properties/10/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_rep": 456
  }'
```

### Bulk Assign Business Rep to Multiple Properties

```bash
curl -X POST \
  https://api.example.com/api/v1/hotels/properties/bulk-assign-business-rep/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_rep_id": 456,
    "property_ids": [10, 11, 12, 13, 14]
  }'
```

### Get Business Rep for a Company

```bash
curl -X GET \
  https://api.example.com/api/v1/org-resources/company-details/1/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

The `business_rep` field will be included in the response.

---

## Notes

1. **Business Rep vs Managed By:**
   - `business_rep` is the account manager/business representative
   - `managed_by` (for properties) is the property manager
   - These can be different users or the same user

2. **Updating Business Rep:**
   - Use the standard `PATCH /api/v1/org-resources/company-details/{id}/` or `PATCH /api/v1/hotels/properties/{id}/` endpoints
   - Set `business_rep` to the user ID (integer) to assign
   - Set `business_rep` to `null` to remove the business rep
   - The field will be set to `NULL` in the database when removed

3. **Bulk Operations:**
   - All IDs in the list must exist, otherwise the operation fails
   - The operation is atomic - either all succeed or none are updated

4. **Permissions:**
   - All endpoints require authentication
   - Business rep details in property serializers are only visible to authorized users

5. **Consistency:**
   - Both CompanyDetail and Property now use `business_rep` field
   - This provides consistency across the codebase

---

## Migration Instructions

After pulling the code changes, run:

```bash
# Activate virtual environment
source venv/bin/activate

# Navigate to IDBOOKAPI directory
cd IDBOOKAPI

# Run migrations
python manage.py migrate
```

This will apply the database schema changes for the `business_rep` field in Property model.

**Note:** CompanyDetail already had the `business_rep` field, so no migration is needed for it.
