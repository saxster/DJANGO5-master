# API CONTRACT FOUNDATION
## Shared Patterns, Authentication, Errors, and Data Types

**Version**: 1.0
**Last Updated**: October 30, 2025
**Backend**: Django 5.2.1 + Django REST Framework
**Target Frontend**: Kotlin Android (API 21+)
**Base URL**: `https://api.example.com` (production) | `http://localhost:8000` (development)

---

## Table of Contents

1. [Overview](#1-overview)
2. [API Versioning Strategy](#2-api-versioning-strategy)
3. [Authentication & Authorization](#3-authentication--authorization)
4. [Request/Response Format](#4-requestresponse-format)
5. [Error Response Standard](#5-error-response-standard)
6. [Pagination & Filtering](#6-pagination--filtering)
7. [Shared Data Types](#7-shared-data-types)
8. [DateTime Standards](#8-datetime-standards)
9. [File Upload/Download](#9-file-uploaddownload)
10. [WebSocket Real-Time Sync](#10-websocket-real-time-sync)
11. [Rate Limiting](#11-rate-limiting)
12. [Security Headers](#12-security-headers)
13. [Tenant Isolation](#13-tenant-isolation)

---

## 1. Overview

This document defines the **foundation contract** between the Django REST API backend and Kotlin Android frontend. All patterns defined here apply across **all domain-specific API contracts** (Operations, People, Attendance, Help Desk, Wellness).

### System Architecture

```
┌──────────────────────────────────────────┐
│   Kotlin Android Application             │
│   ┌────────────────────────────────┐    │
│   │  Presentation (Compose UI)     │    │
│   └────────────┬───────────────────┘    │
│                │                          │
│   ┌────────────▼───────────────────┐    │
│   │  Domain (Business Logic)       │    │
│   └────────────┬───────────────────┘    │
│                │                          │
│   ┌────────────▼───────────────────┐    │
│   │  Data Layer                    │    │
│   │  ┌──────────┐   ┌───────────┐ │    │
│   │  │ Remote   │   │  Local    │ │    │
│   │  │(Retrofit)│   │  (Room)   │ │    │
│   │  └────┬─────┘   └───────────┘ │    │
│   └───────┼─────────────────────────┘    │
└───────────┼─────────────────────────────┘
            │
            │ HTTP REST + WebSocket
            │ (This Contract)
            ▼
┌──────────────────────────────────────────┐
│   Django Backend                         │
│   ┌────────────────────────────────┐    │
│   │  REST API (DRF)                │    │
│   └────────────┬───────────────────┘    │
│                │                          │
│   ┌────────────▼───────────────────┐    │
│   │  Business Logic + Services     │    │
│   └────────────┬───────────────────┘    │
│                │                          │
│   ┌────────────▼───────────────────┐    │
│   │  PostgreSQL + PostGIS          │    │
│   └────────────────────────────────┘    │
└──────────────────────────────────────────┘
```

### Design Principles

1. **One Integrated System**: Frontend and backend are parts of a unified application, not separate systems
2. **Contracts as Source of Truth**: Every byte that crosses the boundary is explicitly defined
3. **Offline-First**: Client works fully offline, syncs opportunistically
4. **Type Safety**: All data structures have compile-time verification
5. **Tenant Isolation**: All data is scoped to `client_id` (with optional `bu_id`)
6. **Idempotency**: Operations can be safely retried

---

## 2. API Versioning Strategy

### URL Path Versioning

**Format**: `/api/{version}/{domain}/{resource}/`

**Supported Versions**:
- **v1** (current, stable) - Production use
- **v2** (preview) - New features, opt-in

**Examples**:
```
/api/v1/operations/jobs/
/api/v1/people/users/
/api/v1/wellness/journal/
/api/v2/operations/tasks/  (preview feature)
```

### Version Selection

**Default**: If version not specified in URL, defaults to `v1`

**Client Recommendation**: Always specify version explicitly in URLs

### Breaking Changes Policy

**Definition of Breaking Change**:
- Removing an endpoint
- Renaming a field
- Changing field type
- Making a required field optional (or vice versa)
- Changing error response structure

**Process**:
1. New version introduced (e.g., v2) with breaking changes
2. Old version (v1) marked deprecated with sunset date
3. Deprecation warnings sent in response headers: `Deprecation: true`, `Sunset: Sat, 01 Jan 2026 00:00:00 GMT`
4. Old version remains available for **6 months minimum**
5. After sunset date, old version returns `410 Gone`

### Non-Breaking Changes

These can be added to existing versions without incrementing:
- Adding new optional fields
- Adding new endpoints
- Adding new error codes
- Expanding enum values (with backward compatibility)

### Version Response Header

All responses include: `API-Version: v1`

---

## 3. Authentication & Authorization

### Authentication Mechanism: JWT (JSON Web Tokens)

**Library**: `djangorestframework-simplejwt`

**Token Types**:
1. **Access Token** - Short-lived (1 hour), used for API requests
2. **Refresh Token** - Long-lived (7 days), used to obtain new access tokens

### Authentication Flow

#### 3.1 Initial Login

**Endpoint**: `POST /api/v1/auth/login/`

**Request**:
```json
{
  "username": "jdoe@example.com",
  "password": "SecurePass123!",
  "device_id": "android-uuid-abc123"  // Optional but recommended
}
```

**Response** (200 OK):
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzMwMzA3NjAwLCJpYXQiOjE3MzAzMDQwMDAsImp0aSI6ImFiYzEyMyIsInVzZXJfaWQiOjQ1Nn0.xyz",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTczMDkwODgwMCwiaWF0IjoxNzMwMzA0MDAwLCJqdGkiOiJkZWY0NTYiLCJ1c2VyX2lkIjo0NTZ9.abc",
  "user": {
    "id": 456,
    "username": "jdoe@example.com",
    "email": "jdoe@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "full_name": "John Doe",
    "bu_id": 2,
    "client_id": 10,
    "department": "Operations",
    "role": "Field Technician",
    "capabilities": {
      "view_reports": true,
      "create_reports": false,
      "manage_users": false,
      "view_all_sites": false
    },
    "profile_image": "https://cdn.example.com/avatars/456.jpg",
    "is_active": true,
    "is_staff": false,
    "date_joined": "2024-01-15T08:00:00Z",
    "last_login": "2025-10-30T09:00:00Z"
  }
}
```

**Error Response** (401 Unauthorized):
```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Unable to log in with provided credentials.",
    "details": null,
    "correlation_id": "abc-123-def-456"
  }
}
```

**Error Response** (403 Forbidden - Account Disabled):
```json
{
  "error": {
    "code": "ACCOUNT_DISABLED",
    "message": "This account has been disabled. Please contact your administrator.",
    "details": null,
    "correlation_id": "abc-123-def-789"
  }
}
```

#### 3.2 Using Access Token

**Authorization Header**:
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

**Example Request**:
```http
GET /api/v1/operations/jobs/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
Accept: application/json
```

#### 3.3 Token Refresh

When access token expires (after 1 hour), use refresh token to obtain new tokens.

**Endpoint**: `POST /api/v1/auth/refresh/`

**Request**:
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response** (200 OK):
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",  // New access token
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."  // New refresh token (rotated)
}
```

**Note**: Refresh tokens are **rotated on use** - the old refresh token is blacklisted, and a new one is issued. This prevents token replay attacks.

**Error Response** (401 Unauthorized - Token Expired):
```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Token is invalid or expired",
    "details": {
      "token_type": "refresh",
      "error_detail": "Token has expired"
    },
    "correlation_id": "abc-123-def-012"
  }
}
```

**Client Behavior**:
1. Store access token in memory
2. Store refresh token in encrypted SharedPreferences / KeyStore
3. On 401 error, attempt token refresh automatically
4. If refresh fails, redirect to login screen

#### 3.4 Logout

**Endpoint**: `POST /api/v1/auth/logout/`

**Request**:
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response** (200 OK):
```json
{
  "message": "Successfully logged out"
}
```

**Client Behavior**:
1. Delete tokens from local storage
2. Clear user session data
3. Clear Room cache (optional, depends on privacy requirements)
4. Redirect to login screen

### JWT Token Structure

**Access Token Claims**:
```json
{
  "token_type": "access",
  "exp": 1730307600,  // Expiration timestamp
  "iat": 1730304000,  // Issued at timestamp
  "jti": "abc123",    // JWT ID (unique identifier)
  "user_id": 456      // User ID
}
```

**Refresh Token Claims**:
```json
{
  "token_type": "refresh",
  "exp": 1730908800,  // Expiration timestamp (7 days from issue)
  "iat": 1730304000,
  "jti": "def456",
  "user_id": 456
}
```

### Authorization: Capabilities System

**Model**: Dynamic permissions stored in `capabilities` JSON field on User model.

**Common Capabilities**:
```json
{
  // Reports
  "view_reports": true,
  "create_reports": true,
  "edit_reports": false,
  "delete_reports": false,

  // User Management
  "manage_users": false,
  "view_user_profiles": true,

  // Operations
  "create_jobs": true,
  "assign_jobs": false,
  "complete_jobs": true,

  // Site Access
  "view_all_sites": false,  // If false, only sees assigned sites

  // Admin
  "access_admin_panel": false,
  "view_audit_logs": false
}
```

**Checking Permissions**:
- Server-side: Enforced by Django permission classes
- Client-side: Use `capabilities` object from user response to show/hide UI elements

**Example - Hide "Create Report" button**:
```kotlin
if (user.capabilities["create_reports"] == true) {
    CreateReportButton()
}
```

### Security Best Practices

1. **Never log tokens** (they grant full access)
2. **Store refresh tokens encrypted** using Android KeyStore
3. **Access tokens in memory only** (or encrypted SharedPreferences if persistence required)
4. **Implement token refresh interceptor** to handle 401 errors automatically
5. **Clear tokens on logout** and on app uninstall
6. **Use HTTPS only** in production (enforce with network security config)

---

## 4. Request/Response Format

### Request Headers (Standard)

```http
Authorization: Bearer <access_token>  // Required for authenticated endpoints
Content-Type: application/json       // For POST/PUT/PATCH with JSON body
Accept: application/json             // Recommended
User-Agent: IntelliwizKotlin/1.0.0  // Recommended for analytics
X-Device-ID: android-uuid-abc123    // Recommended for device tracking
```

### Response Headers (Standard)

```http
Content-Type: application/json
API-Version: v1
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 598
X-RateLimit-Reset: 1730307600
```

### Request Body Format

**JSON Only**: All POST/PUT/PATCH requests use JSON bodies (except file uploads, which use multipart/form-data).

**Example**:
```json
{
  "title": "Inspect HVAC system",
  "status": "pending",
  "assigned_to": 456
}
```

### Response Body Format

**Success Response Structure**:

For single object:
```json
{
  "id": 123,
  "field1": "value1",
  "field2": "value2",
  ...
}
```

For collections (with pagination):
```json
{
  "count": 150,
  "next": "https://api.example.com/api/v1/operations/jobs/?page=2",
  "previous": null,
  "results": [
    {...},
    {...}
  ]
}
```

**Error Response Structure**: See [Section 5](#5-error-response-standard)

---

## 5. Error Response Standard

### Standardized Error Envelope

**All errors** follow this structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      // Optional field-level errors or additional context
    },
    "correlation_id": "abc-123-def-456"  // For support/debugging
  }
}
```

### Error Code Taxonomy

#### 4xx Client Errors

| HTTP Status | Error Code | Description | Client Action |
|-------------|------------|-------------|---------------|
| 400 | `VALIDATION_ERROR` | Input validation failed | Show field errors to user |
| 400 | `BAD_REQUEST` | Malformed request | Log error, retry if transient |
| 400 | `MISSING_CREDENTIALS` | Username/password not provided | Prompt user to fill required fields |
| 400 | `INVALID_JSON` | JSON parsing failed | Log error, check request body |
| 401 | `INVALID_CREDENTIALS` | Wrong username/password | Show login error, allow retry |
| 401 | `AUTHENTICATION_FAILED` | Token invalid/expired | Attempt token refresh, then re-login |
| 401 | `NOT_AUTHENTICATED` | No token provided | Redirect to login |
| 403 | `PERMISSION_DENIED` | Insufficient permissions | Show "access denied" message |
| 403 | `ACCOUNT_DISABLED` | User account disabled | Show message, contact admin |
| 404 | `NOT_FOUND` | Resource doesn't exist | Show "not found" message |
| 404 | `ENDPOINT_NOT_FOUND` | URL doesn't exist | Log error, check API version |
| 409 | `DUPLICATE_ENTRY` | Unique constraint violation | Show specific field error |
| 409 | `CONFLICT` | Resource state conflict | Reload resource, show conflict |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests | Wait for `Retry-After` seconds |

#### 5xx Server Errors

| HTTP Status | Error Code | Description | Client Action |
|-------------|------------|-------------|---------------|
| 500 | `DATABASE_ERROR` | Database operation failed | Retry with exponential backoff |
| 500 | `INTERNAL_ERROR` | Unexpected server error | Retry, then show generic error |
| 502 | `BAD_GATEWAY` | Upstream service failure | Retry, show "service unavailable" |
| 503 | `SERVICE_UNAVAILABLE` | Server overloaded/maintenance | Retry after delay, show maintenance message |

### Field-Level Validation Errors

**Format**: `details` object contains field names as keys, arrays of error messages as values.

**Example** (400 Bad Request):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "email": [
        "Enter a valid email address."
      ],
      "phone": [
        "This field is required."
      ],
      "mood_rating": [
        "Ensure this value is less than or equal to 10."
      ]
    },
    "correlation_id": "abc-123-def-456"
  }
}
```

**Client Mapping**:
```kotlin
data class ApiError(
    val code: String,
    val message: String,
    val details: Map<String, List<String>>?,
    @SerialName("correlation_id") val correlationId: String
)

sealed class AppError : Throwable() {
    data class ValidationError(val fieldErrors: Map<String, List<String>>) : AppError()
    data class NetworkError(val code: Int, override val message: String) : AppError()
    object Unauthorized : AppError()
    object NotFound : AppError()
    data class UnknownError(override val cause: Throwable) : AppError()
}

fun ApiError.toAppError(): AppError = when (code) {
    "VALIDATION_ERROR" -> AppError.ValidationError(details ?: emptyMap())
    "AUTHENTICATION_FAILED", "NOT_AUTHENTICATED", "INVALID_CREDENTIALS" -> AppError.Unauthorized
    "NOT_FOUND" -> AppError.NotFound
    else -> AppError.NetworkError(500, message)
}
```

### Correlation IDs

**Purpose**: Track requests across client/server for debugging.

**Format**: UUID v4 (e.g., `abc-123-def-456`)

**Generation**: Server-side (included in all error responses)

**Usage**: User reports error → provide correlation ID → backend can find exact request in logs

---

## 6. Pagination & Filtering

### Pagination Strategy

Two pagination types supported:

#### 6.1 Page Number Pagination (Default)

**Use Case**: General listing, browsing

**Query Parameters**:
- `page` (integer, default: 1)
- `page_size` (integer, default: 25, max: 100)

**Example Request**:
```
GET /api/v1/operations/jobs/?page=2&page_size=50
```

**Response**:
```json
{
  "count": 150,
  "next": "https://api.example.com/api/v1/operations/jobs/?page=3&page_size=50",
  "previous": "https://api.example.com/api/v1/operations/jobs/?page=1&page_size=50",
  "results": [...]
}
```

#### 6.2 Cursor Pagination (For Sync)

**Use Case**: Mobile sync, large datasets

**Query Parameters**:
- `cursor` (opaque string, obtained from previous response)
- `page_size` (integer, default: 25, max: 100)

**Example Request**:
```
GET /api/v1/operations/jobs/?cursor=cD0yMDI1LTEwLTMwKzEwJTNBMDAlM0EwMC4wMDAwMDA%3D&page_size=50
```

**Response**:
```json
{
  "next": "https://api.example.com/api/v1/operations/jobs/?cursor=cD0yMDI1LTEwLTMwKzExJTNBMDAlM0EwMC4wMDAwMDA%3D&page_size=50",
  "previous": null,
  "results": [...]
}
```

**Advantages**:
- Consistent results even if data changes
- Better performance for large offsets
- Recommended for sync operations

### Filtering

**Query Parameter Format**: `?{field}={value}`

**Examples**:
```
GET /api/v1/operations/jobs/?status=in_progress
GET /api/v1/operations/jobs/?status=in_progress&assigned_to=456
GET /api/v1/people/users/?is_active=true&department=Operations
GET /api/v1/help-desk/tickets/?priority=P0&status=open
```

**Common Filter Fields** (per domain):
- **Jobs**: `status`, `job_type`, `assigned_to`, `bu_id`, `client_id`, `scheduled_date`
- **Users**: `is_active`, `department`, `bu_id`, `client_id`
- **Tickets**: `status`, `priority`, `category`, `assigned_to`
- **Journal**: `entry_type`, `privacy_scope`, `is_draft`

### Search

**Query Parameter**: `?search={query}`

**Behavior**: Full-text search across multiple fields (defined per endpoint)

**Examples**:
```
GET /api/v1/people/users/?search=john
GET /api/v1/operations/jobs/?search=HVAC
```

### Ordering

**Query Parameter**: `?ordering={field}` (ascending) or `?ordering=-{field}` (descending)

**Examples**:
```
GET /api/v1/operations/jobs/?ordering=-created_at
GET /api/v1/help-desk/tickets/?ordering=due_date
```

**Multiple Fields**:
```
GET /api/v1/operations/jobs/?ordering=-priority,created_at
```

### Combined Filters

**All query parameters can be combined**:

```
GET /api/v1/operations/jobs/?status=in_progress&assigned_to=456&ordering=-created_at&page=1&page_size=25
```

---

## 7. Shared Data Types

### 7.1 Enumerations (Common Across Domains)

#### Sync Status
```python
SYNC_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('pending_sync', 'Pending Sync'),
    ('synced', 'Synced'),
    ('sync_error', 'Sync Error'),
    ('pending_delete', 'Pending Delete'),
]
```

**Kotlin Mapping**:
```kotlin
enum class SyncStatus {
    @SerialName("draft") DRAFT,
    @SerialName("pending_sync") PENDING_SYNC,
    @SerialName("synced") SYNCED,
    @SerialName("sync_error") SYNC_ERROR,
    @SerialName("pending_delete") PENDING_DELETE
}
```

### 7.2 Common JSON Structures

#### Location/Coordinates

**Django (PostGIS Point)** → **JSON**:
```json
{
  "lat": 28.6139,
  "lng": 77.2090
}
```

**Kotlin Mapping**:
```kotlin
@Serializable
data class Coordinates(
    val lat: Double,  // -90 to 90
    val lng: Double   // -180 to 180
)
```

#### User Reference (Lightweight)

**Format**:
```json
{
  "id": 456,
  "username": "jdoe",
  "full_name": "John Doe"
}
```

**Kotlin Mapping**:
```kotlin
@Serializable
data class UserReference(
    val id: Int,
    val username: String,
    @SerialName("full_name") val fullName: String
)
```

#### Pagination Metadata

**Format**:
```json
{
  "count": 150,
  "next": "https://api.example.com/...",
  "previous": null
}
```

**Kotlin Mapping**:
```kotlin
@Serializable
data class PaginatedResponse<T>(
    val count: Int,
    val next: String?,
    val previous: String?,
    val results: List<T>
)
```

### 7.3 Audit Fields (Common to Most Models)

**Fields**:
```json
{
  "id": 123,
  "created_at": "2025-10-30T09:00:00Z",
  "updated_at": "2025-10-30T10:30:00Z",
  "created_by": 456,
  "created_by_name": "John Doe",
  "modified_by": 456,
  "modified_by_name": "John Doe"
}
```

**Kotlin Mapping**:
```kotlin
interface Auditable {
    val createdAt: Instant
    val updatedAt: Instant
    val createdBy: Int?
    val createdByName: String?
    val modifiedBy: Int?
    val modifiedByName: String?
}
```

---

## 8. DateTime Standards

### Format: ISO 8601 with UTC Timezone

**Format String**: `YYYY-MM-DDTHH:MM:SS.ffffffZ`

**Examples**:
- `2025-10-30T09:00:00.000000Z`
- `2025-10-30T09:00:00Z` (without microseconds, also accepted)

### Serialization

**Django → JSON**: Always UTC timezone, ISO 8601 format

**Example**:
```json
{
  "created_at": "2025-10-30T09:00:00Z",
  "scheduled_date": "2025-10-31",  // Date-only fields use YYYY-MM-DD
  "event_time": "2025-10-30T09:00:00.123456Z"
}
```

### Kotlin Mapping

**Library**: `kotlinx-datetime`

**Types**:
- **Instant** (for UTC timestamps): `2025-10-30T09:00:00Z`
- **LocalDate** (for date-only): `2025-10-31`
- **LocalTime** (for time-only): `09:00:00`

**Serialization**:
```kotlin
@Serializable
data class Example(
    @Serializable(with = InstantSerializer::class)
    val createdAt: Instant,

    @Serializable(with = LocalDateSerializer::class)
    val scheduledDate: LocalDate,

    @Serializable(with = LocalTimeSerializer::class)
    val shiftStart: LocalTime
)
```

### Timezone Handling

**Server**: All timestamps stored and returned in **UTC**

**Client**: Convert to local timezone for display only

**Example**:
```kotlin
// Receive from API
val createdAtUtc: Instant = Instant.parse("2025-10-30T09:00:00Z")

// Convert to local timezone for display
val createdAtLocal = createdAtUtc.toLocalDateTime(TimeZone.currentSystemDefault())

// Display
Text("Created: ${createdAtLocal.format(...)}")
```

**Never send local timezone timestamps to server** - always convert to UTC first.

---

## 9. File Upload/Download

### Upload Pattern: Multipart Form Data

**Endpoint Pattern**: `POST /api/v1/{domain}/{resource}/upload/`

**Content-Type**: `multipart/form-data`

**Request Structure**:
```http
POST /api/v1/wellness/journal/123/media/ HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="photo.jpg"
Content-Type: image/jpeg

[binary data]
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="media_type"

PHOTO
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="caption"

Inspection photo
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

**Response** (201 Created):
```json
{
  "id": "uuid-abc-123",
  "file": "https://cdn.example.com/media/journal/2025/10/30/photo.jpg",
  "original_filename": "photo.jpg",
  "mime_type": "image/jpeg",
  "file_size": 245678,
  "media_type": "PHOTO",
  "caption": "Inspection photo",
  "created_at": "2025-10-30T09:00:00Z"
}
```

### File Type Restrictions

**Allowed Extensions by Category**:
```json
{
  "PHOTO": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
  "VIDEO": [".mp4", ".mov", ".avi", ".webm"],
  "DOCUMENT": [".pdf", ".doc", ".docx", ".txt"],
  "AUDIO": [".mp3", ".wav", ".m4a", ".aac", ".ogg"]
}
```

**File Size Limits**:
- **Photos**: 10 MB max
- **Videos**: 100 MB max
- **Documents**: 25 MB max
- **Audio**: 50 MB max

**Security Validation** (server-side):
- Filename sanitization (no path traversal)
- Extension whitelist check
- MIME type validation
- Virus scanning (if configured)
- File size limit enforcement

### Download Pattern

**Direct URL** (preferred for CDN):
```json
{
  "file": "https://cdn.example.com/media/journal/2025/10/30/photo.jpg"
}
```

**Authenticated Download** (for sensitive files):
```
GET /api/v1/wellness/journal/media/uuid-abc-123/download/
Authorization: Bearer <access_token>
```

**Response**: Binary file with appropriate `Content-Type` and `Content-Disposition: attachment` headers.

### Kotlin Implementation

**Using Retrofit**:
```kotlin
interface JournalApiService {
    @Multipart
    @POST("journal/{entry_id}/media/")
    suspend fun uploadMedia(
        @Path("entry_id") entryId: String,
        @Part file: MultipartBody.Part,
        @Part("media_type") mediaType: RequestBody,
        @Part("caption") caption: RequestBody?
    ): MediaAttachmentDTO
}

// Usage
val file = File(uri.path)
val requestFile = file.asRequestBody("image/jpeg".toMediaType())
val filePart = MultipartBody.Part.createFormData("file", file.name, requestFile)
val mediaType = "PHOTO".toRequestBody("text/plain".toMediaType())

val response = apiService.uploadMedia(entryId, filePart, mediaType, null)
```

---

## 10. WebSocket Real-Time Sync

### Connection URL

**Pattern**: `wss://api.example.com/ws/{domain}/{resource}/`

**Authentication**: JWT token via query parameter

**Example**:
```
wss://api.example.com/ws/mobile/sync/?token=eyJ0eXAiOiJKV1Qi...&device_id=android-uuid-abc123
```

### Connection Lifecycle

#### 10.1 Establish Connection

**Client → Server**:
```javascript
// OkHttp WebSocket
val request = Request.Builder()
    .url("wss://api.example.com/ws/mobile/sync/?token=$accessToken&device_id=$deviceId")
    .build()

val webSocket = client.newWebSocket(request, listener)
```

**Server → Client** (connection established):
```json
{
  "type": "connection_established",
  "user_id": 456,
  "device_id": "android-uuid-abc123",
  "server_time": "2025-10-30T09:00:00Z",
  "features": {
    "real_time_sync": true,
    "push_notifications": true,
    "bi_directional_sync": true,
    "conflict_resolution": true
  }
}
```

#### 10.2 Heartbeat (Keep-Alive)

**Client → Server** (every 30 seconds):
```json
{
  "type": "heartbeat",
  "client_time": "2025-10-30T09:00:00Z"
}
```

**Server → Client** (response):
```json
{
  "type": "heartbeat_response",
  "server_time": "2025-10-30T09:00:00Z"
}
```

**Server → Client** (proactive, every 30 seconds):
```json
{
  "type": "server_heartbeat",
  "server_time": "2025-10-30T09:00:00Z"
}
```

### Message Types

#### Client → Server

| Type | Purpose | Required Fields |
|------|---------|-----------------|
| `start_sync` | Initiate sync session | `sync_id`, `data_types`, `total_items` |
| `sync_data` | Send data batch | `sync_id`, `data` |
| `request_server_data` | Request server updates | `request_type`, `since_timestamp` |
| `resolve_conflict` | Resolve data conflict | `conflict_id`, `resolution_strategy`, `resolved_data` |
| `subscribe_events` | Subscribe to event types | `event_types[]` |
| `heartbeat` | Keep connection alive | `client_time` |
| `device_status` | Update device status | `status`, `device_info?` |

#### Server → Client

| Type | Purpose |
|------|---------|
| `connection_established` | Connection confirmed |
| `sync_session_started` | Sync session confirmed |
| `sync_progress` | Sync progress update |
| `server_data_response` | Server data for bidirectional sync |
| `conflict_resolved` | Conflict resolution result |
| `subscription_confirmed` | Event subscription confirmed |
| `heartbeat_response` | Heartbeat acknowledgment |
| `server_heartbeat` | Server keepalive |
| `push_notification` | Real-time notification |
| `error` | Error message |

### Sync Session Flow

**1. Start Sync**:
```json
{
  "type": "start_sync",
  "sync_id": "sync-uuid-abc123",
  "data_types": ["journal_entries", "attendance"],
  "total_items": 150
}
```

**2. Server Confirms**:
```json
{
  "type": "sync_session_started",
  "sync_id": "sync-uuid-abc123",
  "server_time": "2025-10-30T09:00:00Z"
}
```

**3. Client Sends Data Batch**:
```json
{
  "type": "sync_data",
  "sync_id": "sync-uuid-abc123",
  "batch_number": 1,
  "total_batches": 3,
  "data": {
    "journal_entries": [
      {
        "mobile_id": "uuid-entry-1",
        "title": "Morning reflection",
        "mood_rating": 8,
        "sync_status": "pending_sync",
        "version": 1,
        ...
      }
    ]
  }
}
```

**4. Server Responds with Progress**:
```json
{
  "type": "sync_progress",
  "sync_id": "sync-uuid-abc123",
  "batch_number": 1,
  "status": "success",
  "items_processed": 50,
  "items_total": 150,
  "progress_percentage": 33
}
```

**5. Server Sends Conflicts (if any)**:
```json
{
  "type": "conflict_detected",
  "conflict_id": "conflict-uuid-abc",
  "mobile_id": "uuid-entry-1",
  "server_version": 2,
  "client_version": 2,
  "server_data": {...},
  "client_data": {...}
}
```

**6. Client Resolves Conflict**:
```json
{
  "type": "resolve_conflict",
  "conflict_id": "conflict-uuid-abc",
  "resolution_strategy": "last_write_wins",
  "resolved_data": {...}
}
```

### Rate Limiting

**Limits**:
- **100 messages per 60 seconds** per connection
- **3 strikes** (rate limit violations) → connection closed

**Error Response**:
```json
{
  "type": "error",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Please slow down your requests.",
  "timestamp": "2025-10-30T09:00:00Z"
}
```

### Error Handling

**Connection Errors**:
- **Authentication Failed**: Invalid/expired token → close connection, refresh token, reconnect
- **Network Interruption**: Implement exponential backoff reconnection
- **Rate Limit**: Wait for cooldown period, resume with reduced frequency

**Kotlin Implementation**:
```kotlin
class WebSocketManager(
    private val client: OkHttpClient,
    private val authRepository: AuthRepository
) {
    private var webSocket: WebSocket? = null
    private var reconnectAttempts = 0
    private val maxReconnectAttempts = 5

    fun connect() {
        val token = authRepository.getAccessToken()
        val deviceId = authRepository.getDeviceId()

        val request = Request.Builder()
            .url("wss://api.example.com/ws/mobile/sync/?token=$token&device_id=$deviceId")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                reconnectAttempts = 0
                // Connection established
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                handleMessage(Json.decodeFromString<WebSocketMessage>(text))
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                handleConnectionFailure(t)
            }
        })
    }

    private fun handleConnectionFailure(error: Throwable) {
        if (reconnectAttempts < maxReconnectAttempts) {
            val delay = 2.0.pow(reconnectAttempts).toLong() * 1000 // Exponential backoff
            reconnectAttempts++

            scope.launch {
                delay(delay)
                connect()
            }
        }
    }
}
```

---

## 11. Rate Limiting

### Limits by User Type

| User Type | Limit | Window |
|-----------|-------|--------|
| Anonymous | 60 requests | 1 hour |
| Authenticated | 600 requests | 1 hour |
| Premium | 6000 requests | 1 hour |

### Response Headers

**On every response**:
```http
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 598
X-RateLimit-Reset: 1730307600
```

**On rate limit exceeded** (429 Too Many Requests):
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 3600
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1730307600
```

**Response Body**:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Request was throttled. Expected available in 3600 seconds.",
    "details": {
      "retry_after": 3600
    },
    "correlation_id": "abc-123-def-456"
  }
}
```

### Client Behavior

**Implement retry with exponential backoff**:
```kotlin
class RateLimitInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())

        if (response.code == 429) {
            val retryAfter = response.header("Retry-After")?.toLongOrNull() ?: 60

            // Store for UI display
            rateLimitExceeded.emit(retryAfter)

            // Don't retry automatically for 429 - let user decide
        }

        return response
    }
}
```

---

## 12. Security Headers

All API responses include security headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

### Client Enforcement

**Network Security Config** (`res/xml/network_security_config.xml`):
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.example.com</domain>
        <pin-set expiration="2026-01-01">
            <pin digest="SHA-256">base64hash==</pin>
            <pin digest="SHA-256">backuphash==</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

---

## 13. Tenant Isolation

### Automatic Tenant Filtering

**All API requests are automatically scoped to the authenticated user's `client_id`**.

**User Tenant Context** (from login response):
```json
{
  "client_id": 10,  // Tenant organization
  "bu_id": 2        // Business unit (optional sub-tenant)
}
```

**Behavior**:
- Non-superusers **only see data from their `client_id`**
- Queries automatically filtered: `queryset.filter(client_id=user.client_id)`
- Attempting to access another tenant's data returns `404 Not Found` (not `403 Forbidden` to avoid information leakage)

**Example**:
```
GET /api/v1/operations/jobs/999/

If job 999 belongs to client_id=5, but user is from client_id=10:
  → Returns 404 (not 403)
```

### Business Unit Isolation (Optional)

**If `bu_id` is set**, data is further scoped to business unit.

**Filter Behavior**:
```python
# Django backend
if user.bu_id:
    queryset = queryset.filter(client_id=user.client_id, bu_id=user.bu_id)
else:
    queryset = queryset.filter(client_id=user.client_id)
```

---

## Summary

This foundation document defines the **shared patterns** used across all domain-specific API contracts:

✅ **JWT Authentication** with token rotation
✅ **Standardized Error Responses** with correlation IDs
✅ **Pagination** (page-based and cursor-based)
✅ **Filtering, Search, Ordering** query parameters
✅ **DateTime** in ISO 8601 UTC format
✅ **File Upload/Download** with security validation
✅ **WebSocket Real-Time Sync** with conflict resolution
✅ **Rate Limiting** with retry guidance
✅ **Tenant Isolation** enforced automatically

**Next Steps**: Review domain-specific contracts:
- [API_CONTRACT_OPERATIONS.md](./API_CONTRACT_OPERATIONS.md)
- [API_CONTRACT_PEOPLE.md](./API_CONTRACT_PEOPLE.md)
- [API_CONTRACT_ATTENDANCE.md](./API_CONTRACT_ATTENDANCE.md)
- [API_CONTRACT_HELPDESK.md](./API_CONTRACT_HELPDESK.md)
- [API_CONTRACT_WELLNESS.md](./API_CONTRACT_WELLNESS.md)

---

**Document Version**: 1.0
**Last Reviewed**: October 30, 2025
**Maintainer**: Backend & Mobile Teams
**Review Cycle**: Quarterly or on major API changes
