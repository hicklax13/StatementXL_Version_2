# StatementXL API Reference

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000/api/v1`  
**Authentication:** JWT Bearer Token

---

## Table of Contents

1. [Authentication](#authentication)
2. [Documents](#documents)
3. [Templates](#templates)
4. [Mappings](#mappings)
5. [Exports](#exports)
6. [Users](#users)
7. [Organizations](#organizations)
8. [Analytics](#analytics)
9. [Error Codes](#error-codes)

---

## Authentication

### POST /auth/register

Register a new user account.

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123",
  "full_name": "John Doe"
}
```

**Response:** `201 Created`

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "analyst",
  "created_at": "2025-12-31T19:00:00Z"
}
```

---

### POST /auth/login

Authenticate and receive JWT token.

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "SecurePassword123"
}
```

**Response:** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Rate Limit:** 10 requests/minute

---

### POST /auth/refresh

Refresh an expired JWT token.

**Headers:**

```
Authorization: Bearer {refresh_token}
```

**Response:** `200 OK`

```json
{
  "access_token": "new_token_here",
  "token_type": "bearer",
  "expires_in": 86400
}
```

---

## Documents

### POST /upload

Upload a PDF document for extraction.

**Headers:**

```
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

**Request Body:**

- `file`: PDF file (max 50MB)

**Response:** `201 Created`

```json
{
  "document_id": "uuid",
  "filename": "statement.pdf",
  "status": "processing",
  "tables_found": 3,
  "created_at": "2025-12-31T19:00:00Z"
}
```

**Rate Limit:** 20 requests/hour  
**Error Codes:**

- `400`: Invalid file type
- `413`: File too large
- `429`: Rate limit exceeded

---

### GET /documents/{document_id}

Get document processing status and results.

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:** `200 OK`

```json
{
  "id": "uuid",
  "filename": "statement.pdf",
  "status": "completed",
  "statement_type": "income_statement",
  "tables": [
    {
      "page": 1,
      "rows": [...],
      "confidence": 0.95
    }
  ],
  "created_at": "2025-12-31T19:00:00Z",
  "processed_at": "2025-12-31T19:01:30Z"
}
```

---

### GET /documents

List all user documents.

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

- `page` (int): Page number (default: 1)
- `limit` (int): Items per page (default: 20, max: 100)
- `status` (string): Filter by status (processing, completed, failed)

**Response:** `200 OK`

```json
{
  "documents": [
    {
      "id": "uuid",
      "filename": "statement.pdf",
      "status": "completed",
      "created_at": "2025-12-31T19:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "pages": 3
}
```

---

## Templates

### GET /templates

List available Excel templates.

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

- `statement_type` (string): Filter by type (income_statement, balance_sheet, cash_flow)
- `style` (string): Filter by style (basic, corporate, professional)

**Response:** `200 OK`

```json
{
  "templates": [
    {
      "id": "uuid",
      "name": "Income Statement - Basic",
      "statement_type": "income_statement",
      "style": "basic",
      "description": "Simple income statement template",
      "preview_url": "/templates/preview/uuid.png"
    }
  ]
}
```

---

### GET /templates/{template_id}

Get template details.

**Response:** `200 OK`

```json
{
  "id": "uuid",
  "name": "Income Statement - Basic",
  "statement_type": "income_statement",
  "style": "basic",
  "description": "Simple income statement template",
  "structure": {
    "sections": ["revenue", "expenses", "net_income"],
    "has_formulas": true
  }
}
```

---

## Mappings

### POST /mappings

Create a mapping between extracted data and template.

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "document_id": "uuid",
  "template_id": "uuid",
  "mappings": [
    {
      "source_row": 5,
      "target_cell": "B10",
      "gaap_category": "revenue"
    }
  ]
}
```

**Response:** `201 Created`

```json
{
  "mapping_id": "uuid",
  "document_id": "uuid",
  "template_id": "uuid",
  "status": "pending_review",
  "conflicts": []
}
```

---

### GET /mappings/{mapping_id}

Get mapping details and conflicts.

**Response:** `200 OK`

```json
{
  "id": "uuid",
  "document_id": "uuid",
  "template_id": "uuid",
  "status": "pending_review",
  "conflicts": [
    {
      "id": "uuid",
      "type": "duplicate_mapping",
      "description": "Multiple items mapped to same cell",
      "suggestions": [...]
    }
  ],
  "created_at": "2025-12-31T19:00:00Z"
}
```

---

### POST /mappings/{mapping_id}/resolve

Resolve mapping conflicts.

**Request Body:**

```json
{
  "conflict_id": "uuid",
  "resolution": "merge",
  "parameters": {
    "operation": "sum"
  }
}
```

**Response:** `200 OK`

```json
{
  "conflict_id": "uuid",
  "status": "resolved",
  "resolution_applied": "merge"
}
```

---

## Exports

### POST /export

Generate Excel file from mapping.

**Headers:**

```
Authorization: Bearer {access_token}
```

**Request Body:**

```json
{
  "mapping_id": "uuid",
  "format": "xlsx",
  "include_formulas": true
}
```

**Response:** `200 OK`

```json
{
  "export_id": "uuid",
  "download_url": "/exports/download/uuid",
  "filename": "statement_2024.xlsx",
  "size_bytes": 45678,
  "expires_at": "2025-12-31T23:00:00Z"
}
```

**Rate Limit:** 30 requests/hour

---

### GET /exports/download/{export_id}

Download generated Excel file.

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:** `200 OK`

- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Content-Disposition: `attachment; filename="statement_2024.xlsx"`

---

## Users

### GET /users/me

Get current user profile.

**Headers:**

```
Authorization: Bearer {access_token}
```

**Response:** `200 OK`

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "role": "analyst",
  "is_active": true,
  "created_at": "2025-01-01T00:00:00Z",
  "last_login": "2025-12-31T19:00:00Z"
}
```

---

### PATCH /users/me

Update user profile.

**Request Body:**

```json
{
  "full_name": "John Smith",
  "email": "newem ail@example.com"
}
```

**Response:** `200 OK`

---

## Organizations

### POST /organizations

Create a new organization.

**Request Body:**

```json
{
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "billing_email": "billing@acme.com"
}
```

**Response:** `201 Created`

```json
{
  "id": "uuid",
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "member_count": 1,
  "subscription_tier": "free",
  "created_at": "2025-12-31T19:00:00Z"
}
```

---

### POST /organizations/{org_id}/invite

Invite a member to organization.

**Request Body:**

```json
{
  "email": "colleague@example.com",
  "role": "member"
}
```

**Response:** `201 Created`

```json
{
  "id": "uuid",
  "email": "colleague@example.com",
  "role": "member",
  "status": "pending",
  "expires_at": "2026-01-07T19:00:00Z"
}
```

---

## Analytics

### GET /analytics

Get usage analytics.

**Headers:**

```
Authorization: Bearer {access_token}
```

**Query Parameters:**

- `range` (string): Time range (7d, 30d, 90d)

**Response:** `200 OK`

```json
{
  "total_documents": 1247,
  "total_exports": 892,
  "documents_this_month": 156,
  "avg_processing_time": 2.3,
  "popular_templates": [
    {
      "name": "Income Statement - Basic",
      "count": 342
    }
  ]
}
```

---

## Error Codes

### Standard HTTP Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created
- `400 Bad Request`: Invalid input
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `413 Payload Too Large`: File too large
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Custom Error Codes (SXL-XXX)

**Document Processing (SXL-1XX)**

- `SXL-101`: Document not found
- `SXL-102`: Invalid file type
- `SXL-103`: File too large

**Table Extraction (SXL-2XX)**

- `SXL-201`: No tables found
- `SXL-202`: OCR processing failed

**Mapping (SXL-3XX)**

- `SXL-301`: Mapping not found
- `SXL-302`: Conflict not found
- `SXL-303`: Unresolved conflicts

**Template (SXL-4XX)**

- `SXL-401`: Template not found
- `SXL-402`: Invalid template format

**Authentication (SXL-5XX)**

- `SXL-501`: Invalid credentials
- `SXL-502`: Token expired
- `SXL-503`: Account locked

**Authorization (SXL-6XX)**

- `SXL-601`: Insufficient permissions

**Validation (SXL-7XX)**

- `SXL-701`: Validation failed

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/auth/login` | 10 | 1 minute |
| `/upload` | 20 | 1 hour |
| `/export` | 30 | 1 hour |
| `/api/*` | 100 | 1 minute |
| Global | 1000 | 1 hour |

**Rate Limit Headers:**

```
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 1704067200
Retry-After: 3600
```

---

## Webhooks

### POST /webhooks/stripe

Stripe webhook endpoint for payment events.

**Headers:**

```
Stripe-Signature: {signature}
```

**Events Handled:**

- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`

---

## SDK Examples

### Python

```python
import requests

# Login
response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "user@example.com", "password": "password"}
)
token = response.json()["access_token"]

# Upload document
files = {"file": open("statement.pdf", "rb")}
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(
    "http://localhost:8000/api/v1/upload",
    files=files,
    headers=headers
)
document_id = response.json()["document_id"]
```

### JavaScript

```javascript
// Login
const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'password'
  })
});
const { access_token } = await loginResponse.json();

// Upload document
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const uploadResponse = await fetch('http://localhost:8000/api/v1/upload', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${access_token}` },
  body: formData
});
const { document_id } = await uploadResponse.json();
```

---

**API Version:** 1.0.0  
**Last Updated:** December 31, 2025  
**Support:** <support@statementxl.com>
