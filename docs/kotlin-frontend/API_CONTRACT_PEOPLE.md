# API Contract: People Domain

> **Domain:** People Management (Users, Profiles, Directory, Capabilities)
> **Version:** 1.0.0
> **Last Updated:** November 7, 2025
> **Base URL:** `/api/v2/people/`

---

## 📋 Table of Contents

- [Overview](#overview)
- [User Profile](#user-profile)
- [Directory & Search](#directory--search)
- [Capabilities & Permissions](#capabilities--permissions)
- [Authentication](#authentication)
- [Complete Workflows](#complete-workflows)
- [Data Model Summary](#data-model-summary)

---

## Overview

The People domain handles user management, profiles, organizational structure, and permissions.

### Multi-Model Architecture

**CRITICAL**: Django uses **3 separate models** for user data:
1. **People** - Core user (auth, username, email)
2. **PeopleProfile** - Personal details (gender, phone, address)
3. **PeopleOrganizational** - Work details (department, role, manager)

**Kotlin must denormalize** these into a single `User` entity for client performance.

### Django Implementation

- **Models:** `apps/peoples/models/user_model.py:People`, `apps/peoples/models/profile_model.py`
- **Viewsets:** `apps/peoples/api/viewsets/`
- **Serializers:** `apps/peoples/serializers.py`
- **Permissions:** `apps/peoples/permissions.py`

---

## User Profile

### 1. Get Current User Profile

**Endpoint:** `GET /api/v2/people/me/`

**Django Implementation:**
- **Viewset:** `apps/peoples/api/viewsets/people_viewset.py:PeopleViewSet.me()`
- **Serializer:** `apps/peoples/serializers.py:PeopleDetailSerializer`
- **Permissions:** `IsAuthenticated`
- **Joins:** `select_related('peopleprofile', 'peopleorganizational')`

**Purpose:** Get complete user profile (all 3 models joined)

**Response (200 OK):**
```json
{
  "id": 123,
  "username": "john.doe",
  "email": "john.doe@example.com",
  "employee_number": "EMP-123",
  "is_active": true,
  "is_staff": false,
  "profile": {
    "first_name": "John",
    "last_name": "Doe",
    "full_name": "John Doe",
    "gender": "male",
    "date_of_birth": "1990-05-15",
    "phone": "+65 9123 4567",
    "alternate_phone": "+65 8234 5678",
    "address": "123 Main St, #05-01",
    "city": "Singapore",
    "state": "Singapore",
    "postal_code": "123456",
    "country": "SG",
    "nationality": "Singaporean",
    "id_type": "nric",
    "id_number": "S1234567A",
    "avatar_url": "https://storage/avatars/123.jpg",
    "emergency_contact": {
      "name": "Jane Doe",
      "relationship": "spouse",
      "phone": "+65 9999 8888"
    }
  },
  "organizational": {
    "department": {
      "id": 10,
      "name": "Security"
    },
    "designation": {
      "id": 25,
      "title": "Security Guard",
      "level": "L2"
    },
    "business_unit": {
      "id": 789,
      "name": "Downtown Office",
      "site_type": "commercial_building"
    },
    "manager": {
      "id": 456,
      "name": "Jane Smith",
      "email": "jane.smith@example.com"
    },
    "joining_date": "2023-01-15",
    "employment_type": "full_time",
    "employment_status": "active",
    "work_location": "field",
    "shift_eligible": true
  },
  "capabilities": [
    {
      "id": 1,
      "name": "security_license",
      "display_name": "Security License",
      "category": "certification",
      "verified": true,
      "verified_at": "2023-02-01T00:00:00Z"
    },
    {
      "id": 5,
      "name": "first_aid",
      "display_name": "First Aid Certified",
      "category": "certification",
      "verified": true,
      "expiry_date": "2026-05-15"
    },
    {
      "id": 10,
      "name": "can_create_jobs",
      "display_name": "Create Jobs",
      "category": "permission",
      "verified": true
    }
  ],
  "permissions": {
    "can_create_jobs": true,
    "can_approve_jobs": false,
    "can_view_all_attendance": false,
    "can_manage_users": false,
    "is_supervisor": false,
    "is_manager": false
  },
  "devices": [
    {
      "device_id": "device-android-abc123",
      "device_model": "Samsung Galaxy S23",
      "os": "Android 14",
      "registered_at": "2025-11-01T10:00:00Z",
      "last_active": "2025-11-15T08:05:00Z",
      "is_primary": true
    }
  ],
  "preferences": {
    "language": "en",
    "timezone": "Asia/Singapore",
    "notifications_enabled": true,
    "theme": "system"
  },
  "created_at": "2023-01-15T10:00:00Z",
  "last_login": "2025-11-15T08:00:00Z",
  "correlation_id": "req-me-123"
}
```

---

### 2. Update Current User Profile

**Endpoint:** `PATCH /api/v2/people/me/`

**Django Implementation:**
- **Viewset:** `apps/peoples/api/viewsets/people_viewset.py:PeopleViewSet.update_me()`
- **Serializer:** `apps/peoples/serializers.py:PeopleUpdateSerializer`
- **Permissions:** `IsAuthenticated`

**Purpose:** Update profile fields (user can only update certain fields)

**Request:**
```json
{
  "profile": {
    "phone": "+65 9999 1111",
    "address": "456 New St, #10-02",
    "postal_code": "654321",
    "emergency_contact": {
      "name": "Jane Doe",
      "phone": "+65 9999 8888",
      "relationship": "spouse"
    }
  },
  "preferences": {
    "language": "en",
    "notifications_enabled": true,
    "theme": "dark"
  }
}
```

**Restricted Fields (cannot update via mobile):**
- `employee_number`, `username`, `email` - Admin only
- `organizational.*` - Manager/HR only
- `capabilities` - Admin only
- `permissions` - System controlled

**Response (200 OK):**
```json
{
  "id": 123,
  "profile": {
    "phone": "+65 9999 1111",
    "address": "456 New St, #10-02",
    "postal_code": "654321",
    "emergency_contact": {
      "name": "Jane Doe",
      "phone": "+65 9999 8888",
      "relationship": "spouse"
    }
  },
  "preferences": {
    "language": "en",
    "notifications_enabled": true,
    "theme": "dark"
  },
  "updated_at": "2025-11-15T10:00:00Z",
  "correlation_id": "req-update-456"
}
```

---

## Directory & Search

### 3. Search Users

**Endpoint:** `GET /api/v2/people/users/`

**Django Implementation:**
- **Viewset:** `apps/peoples/api/viewsets/people_viewset.py:PeopleViewSet.list()`
- **Serializer:** `apps/peoples/serializers.py:PeopleListSerializer`
- **Permissions:** `IsAuthenticated`

**Purpose:** Search/browse user directory (for assigning jobs, viewing team)

**Query Parameters:**
- `search`: Full-text search (name, email, employee_number)
- `department_id`: Filter by department
- `designation_id`: Filter by role
- `business_unit_id`: Filter by site
- `employment_status`: Filter: `active,on_leave,terminated`
- `capabilities`: Filter by capability (comma-separated): `security_license,first_aid`
- `page`: Page number
- `page_size`: Items per page (max 100)
- `ordering`: Sort field: `full_name,employee_number`

**Request:**
```
GET /api/v2/people/users/?search=john&department_id=10&employment_status=active&page=1&page_size=20
```

**Response (200 OK):**
```json
{
  "count": 47,
  "next": "https://api.example.com/api/v2/people/users/?page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "employee_number": "EMP-123",
      "full_name": "John Doe",
      "email": "john.doe@example.com",
      "phone": "+65 9123 4567",
      "avatar_url": "https://storage/avatars/123.jpg",
      "department": {
        "id": 10,
        "name": "Security"
      },
      "designation": {
        "id": 25,
        "title": "Security Guard"
      },
      "business_unit": {
        "id": 789,
        "name": "Downtown Office"
      },
      "employment_status": "active",
      "is_available": true,
      "capabilities": ["security_license", "first_aid"],
      "last_active": "2025-11-15T08:05:00Z"
    },
    {
      "id": 124,
      "employee_number": "EMP-124",
      "full_name": "John Smith",
      "email": "john.smith@example.com",
      "phone": "+65 9234 5678",
      "avatar_url": "https://storage/avatars/124.jpg",
      "department": {
        "id": 10,
        "name": "Security"
      },
      "designation": {
        "id": 26,
        "title": "Senior Security Guard"
      },
      "business_unit": {
        "id": 790,
        "name": "North Campus"
      },
      "employment_status": "active",
      "is_available": false,
      "capabilities": ["security_license", "first_aid", "supervisor"],
      "last_active": "2025-11-14T18:00:00Z"
    }
  ]
}
```

---

### 4. Get User Details (Other User)

**Endpoint:** `GET /api/v2/people/users/{id}/`

**Purpose:** Get public profile of another user (limited fields for privacy)

**Response (200 OK):**
```json
{
  "id": 456,
  "employee_number": "EMP-456",
  "full_name": "Jane Smith",
  "email": "jane.smith@example.com",
  "phone": "+65 9234 5678",
  "avatar_url": "https://storage/avatars/456.jpg",
  "department": {
    "id": 10,
    "name": "Security"
  },
  "designation": {
    "id": 30,
    "title": "Supervisor"
  },
  "business_unit": {
    "id": 789,
    "name": "Downtown Office"
  },
  "employment_status": "active",
  "capabilities": ["security_license", "first_aid", "supervisor"],
  "is_supervisor": true,
  "is_manager": false,
  "reports_to": {
    "id": 999,
    "name": "Operations Manager"
  },
  "correlation_id": "req-user-789"
}
```

**Privacy Note:**
- Personal details (DOB, address, ID number) NOT exposed
- Only work-related info visible to other users

---

## Capabilities & Permissions

### 5. Get My Capabilities

**Endpoint:** `GET /api/v2/people/capabilities/`

**Django Implementation:**
- **Viewset:** `apps/peoples/api/viewsets/capability_viewset.py:CapabilityViewSet.my_capabilities()`
- **Permissions:** `IsAuthenticated`

**Purpose:** Get current user's capabilities and permissions (for feature gating)

**Response (200 OK):**
```json
{
  "user_id": 123,
  "capabilities": [
    {
      "id": 1,
      "name": "security_license",
      "display_name": "Security License",
      "category": "certification",
      "description": "Valid security guard license",
      "verified": true,
      "verified_at": "2023-02-01T00:00:00Z",
      "verified_by": {
        "id": 999,
        "name": "HR Manager"
      },
      "expiry_date": "2026-02-01",
      "requires_renewal": false,
      "days_until_expiry": 452
    },
    {
      "id": 5,
      "name": "first_aid",
      "display_name": "First Aid Certified",
      "category": "certification",
      "verified": true,
      "expiry_date": "2026-05-15",
      "requires_renewal": false,
      "days_until_expiry": 555
    },
    {
      "id": 10,
      "name": "can_create_jobs",
      "display_name": "Create Jobs",
      "category": "permission",
      "description": "Can create and assign work orders",
      "verified": true,
      "verified_at": "2023-01-15T00:00:00Z"
    }
  ],
  "permissions": {
    "jobs": {
      "can_create": true,
      "can_update_own": true,
      "can_update_all": false,
      "can_delete": false,
      "can_approve": false
    },
    "attendance": {
      "can_checkin": true,
      "can_checkout": true,
      "can_view_own": true,
      "can_view_team": false,
      "can_approve": false
    },
    "helpdesk": {
      "can_create_tickets": true,
      "can_update_own_tickets": true,
      "can_view_all_tickets": false,
      "can_assign_tickets": false,
      "can_close_tickets": false
    },
    "reports": {
      "can_view_own_reports": true,
      "can_view_team_reports": false,
      "can_view_all_reports": false,
      "can_export": true
    }
  },
  "roles": ["field_worker", "technician"],
  "is_supervisor": false,
  "is_manager": false,
  "is_admin": false,
  "correlation_id": "req-capabilities-999"
}
```

**Usage in Kotlin:**
```kotlin
// Feature gating based on capabilities
val userCapabilities = apiService.getMyCapabilities()

// Show "Create Job" button only if user has permission
if (userCapabilities.permissions.jobs.canCreate) {
    CreateJobButton(onClick = { /* ... */ })
}

// Check capability before feature access
if (userCapabilities.hasCapability("security_license")) {
    // Allow security-specific features
}

// Check expiring certifications
val expiringCerts = userCapabilities.capabilities
    .filter { it.daysUntilExpiry != null && it.daysUntilExpiry < 30 }

if (expiringCerts.isNotEmpty()) {
    showExpiryWarning(expiringCerts)
}
```

---

### 6. Update Avatar

**Endpoint:** `POST /api/v2/people/me/avatar/`

**Django Implementation:**
- **Service:** `apps/core/services/secure_file_upload_service.py:SecureFileUploadService`
- **Permissions:** `IsAuthenticated`

**Purpose:** Upload profile photo

**Request (multipart/form-data):**
```
POST /api/v2/people/me/avatar/
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="avatar"; filename="profile.jpg"
Content-Type: image/jpeg

<binary image data>
--boundary--
```

**Response (200 OK):**
```json
{
  "avatar_url": "https://storage/avatars/123.jpg",
  "uploaded_at": "2025-11-15T10:00:00Z",
  "file_size": 245678,
  "correlation_id": "req-avatar-123"
}
```

**Error Responses:**

**400 Bad Request** - File too large:
```json
{
  "error_code": "FILE_TOO_LARGE",
  "message": "File size exceeds maximum allowed",
  "max_size_bytes": 5242880,
  "uploaded_size_bytes": 8388608,
  "correlation_id": "req-avatar-123"
}
```

**400 Bad Request** - Invalid file type:
```json
{
  "error_code": "INVALID_FILE_TYPE",
  "message": "File type not allowed",
  "allowed_types": ["image/jpeg", "image/png"],
  "uploaded_type": "image/gif",
  "correlation_id": "req-avatar-123"
}
```

---

### 7. Change Password

**Endpoint:** `POST /api/v2/people/me/change-password/`

**Django Implementation:**
- **Service:** `apps/peoples/services/password_reset_service.py:PasswordResetService`
- **Permissions:** `IsAuthenticated`

**Purpose:** Change user's own password

**Request:**
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword456!",
  "confirm_password": "NewPassword456!"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Password changed successfully",
  "password_changed_at": "2025-11-15T10:05:00Z",
  "tokens_invalidated": true,
  "correlation_id": "req-password-456"
}
```

**Error Responses:**

**400 Bad Request** - Weak password:
```json
{
  "error_code": "WEAK_PASSWORD",
  "message": "Password does not meet security requirements",
  "requirements": {
    "min_length": 8,
    "require_uppercase": true,
    "require_lowercase": true,
    "require_digit": true,
    "require_special_char": true
  },
  "violations": [
    "missing_special_character",
    "too_short"
  ],
  "correlation_id": "req-password-456"
}
```

**400 Bad Request** - Incorrect current password:
```json
{
  "error_code": "INVALID_CURRENT_PASSWORD",
  "message": "Current password is incorrect",
  "correlation_id": "req-password-456"
}
```

---

## Directory & Search

### 8. Get Organizational Hierarchy

**Endpoint:** `GET /api/v2/people/hierarchy/`

**Purpose:** Get organizational tree (for showing team structure)

**Query Parameters:**
- `root_user_id`: Start from specific manager (default: current user's manager)
- `depth`: How many levels deep (default: 2, max: 5)

**Response (200 OK):**
```json
{
  "root": {
    "id": 999,
    "name": "Operations Manager",
    "designation": "Operations Manager",
    "avatar_url": "https://storage/avatars/999.jpg",
    "direct_reports": [
      {
        "id": 456,
        "name": "Jane Smith",
        "designation": "Supervisor",
        "avatar_url": "https://storage/avatars/456.jpg",
        "direct_reports": [
          {
            "id": 123,
            "name": "John Doe",
            "designation": "Security Guard",
            "avatar_url": "https://storage/avatars/123.jpg",
            "direct_reports": []
          },
          {
            "id": 124,
            "name": "Mike Johnson",
            "designation": "Security Guard",
            "avatar_url": "https://storage/avatars/124.jpg",
            "direct_reports": []
          }
        ]
      },
      {
        "id": 457,
        "name": "Alice Brown",
        "designation": "Supervisor",
        "avatar_url": "https://storage/avatars/457.jpg",
        "direct_reports": []
      }
    ]
  },
  "total_count": 125,
  "correlation_id": "req-hierarchy-789"
}
```

---

### 9. Get Team Members

**Endpoint:** `GET /api/v2/people/my-team/`

**Purpose:** Get all users reporting to current user (if supervisor/manager)

**Response (200 OK):**
```json
{
  "manager": {
    "id": 456,
    "name": "Jane Smith",
    "designation": "Supervisor"
  },
  "team_size": 8,
  "direct_reports": [
    {
      "id": 123,
      "name": "John Doe",
      "employee_number": "EMP-123",
      "designation": "Security Guard",
      "avatar_url": "https://storage/avatars/123.jpg",
      "employment_status": "active",
      "current_status": {
        "is_on_shift": true,
        "shift_site": "Downtown Office",
        "checked_in": true,
        "checkin_time": "2025-11-15T08:05:00Z"
      },
      "capabilities": ["security_license", "first_aid"],
      "last_active": "2025-11-15T08:05:00Z"
    }
  ],
  "correlation_id": "req-team-111"
}
```

**Error Response:**

**403 Forbidden** - Not a supervisor:
```json
{
  "error_code": "NOT_A_SUPERVISOR",
  "message": "You do not have team members assigned to you",
  "correlation_id": "req-team-111"
}
```

---

## Authentication

### 10. Update Device Registration

**Endpoint:** `POST /api/v2/people/me/devices/`

**Purpose:** Register mobile device for push notifications

**Request:**
```json
{
  "device_id": "device-android-abc123",
  "device_model": "Samsung Galaxy S23",
  "os": "Android",
  "os_version": "14",
  "app_version": "2.1.0",
  "fcm_token": "fcm-token-xyz789...",
  "is_primary": true
}
```

**Response (201 Created):**
```json
{
  "device_id": "device-android-abc123",
  "registered_at": "2025-11-15T10:00:00Z",
  "fcm_token": "fcm-token-xyz789...",
  "is_primary": true,
  "correlation_id": "req-device-456"
}
```

---

## Complete Workflows

### Workflow 1: First Login → Profile Setup

```
1. User logs in for first time
   POST /api/v2/auth/login/
   → Returns access token + refresh token
   → Store securely in KeyStore

2. Get user profile
   GET /api/v2/people/me/
   → Shows incomplete profile (no avatar, no preferences)
   → UI prompts for completion

3. Upload avatar
   POST /api/v2/people/me/avatar/
   → Store avatar URL locally

4. Update preferences
   PATCH /api/v2/people/me/
   → Set language, timezone, notifications

5. Register device for notifications
   POST /api/v2/people/me/devices/
   → FCM token registered
   → Ready for push notifications

6. Get capabilities
   GET /api/v2/people/capabilities/
   → Store locally for feature gating
   → Show appropriate UI based on permissions
```

### Workflow 2: Supervisor Views Team

```
1. Supervisor opens "My Team" screen
   GET /api/v2/people/my-team/
   → Get 8 direct reports
   → Show who's on shift, who's checked in

2. Click on team member
   GET /api/v2/people/users/123/
   → Show John Doe's public profile
   → Show current shift status

3. View team attendance
   GET /api/v2/attendance/team-records/?supervisor=456
   → See all team member attendance for today
   → Identify who's late, who's on time

4. Approve pending attendance
   POST /api/v2/attendance/{id}/approve/
   → Approve John's attendance record
```

---

## Data Model Summary

### User Entity (Kotlin - Denormalized)

```kotlin
data class User(
    // Core (People model)
    val id: Long,
    val username: String,
    val email: String,
    val employeeNumber: String,
    val isActive: Boolean,
    val isStaff: Boolean,

    // Profile (PeopleProfile model)
    val firstName: String,
    val lastName: String,
    val fullName: String,
    val gender: Gender?,
    val dateOfBirth: LocalDate?,
    val phone: String?,
    val alternatePhone: String?,
    val address: String?,
    val city: String?,
    val postalCode: String?,
    val country: String?,
    val nationality: String?,
    val avatarUrl: String?,
    val emergencyContact: EmergencyContact?,

    // Organizational (PeopleOrganizational model)
    val department: Department?,
    val designation: Designation?,
    val businessUnit: BusinessUnit?,
    val manager: UserSummary?,
    val joiningDate: LocalDate?,
    val employmentType: EmploymentType,
    val employmentStatus: EmploymentStatus,
    val workLocation: WorkLocationType,
    val shiftEligible: Boolean,

    // Computed/Related
    val capabilities: List<Capability>,
    val permissions: Permissions,
    val devices: List<Device>,
    val preferences: UserPreferences,
    val createdAt: Instant,
    val lastLogin: Instant?
)

// Django has 3 models, Kotlin has 1 entity
// Mapping done in repository layer
```

### Denormalization Strategy

**Django (Normalized):**
```sql
SELECT * FROM peoples_people p
JOIN peoples_peopleprofile pp ON p.id = pp.user_id
JOIN peoples_peopleorganizational po ON p.id = po.user_id
WHERE p.id = 123;
-- Returns 3 rows joined
```

**Kotlin/SQLite (Denormalized):**
```sql
SELECT * FROM users WHERE id = 123;
-- Returns 1 row with all fields flattened
```

**Why?**
- Faster reads on mobile (1 query vs 3)
- Simpler UI code (no need to join in memory)
- Offline-first requires local cache (SQLite can't JOIN across network)
- Trade-off: Slightly more storage, but mobile storage is cheap

---

## Multi-Tenant Context

### How client_id is Managed

**Every request includes:**
```
X-Client-ID: 42
Authorization: Bearer eyJhbGc...
```

**Kotlin interceptor:**
```kotlin
class TenantInterceptor(
    private val tenantManager: TenantManager
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val clientId = tenantManager.getCurrentClientId()

        val request = original.newBuilder()
            .header("X-Client-ID", clientId.toString())
            .build()

        return chain.proceed(request)
    }
}
```

**Storing client_id:**
- Received in login response: `{"access_token": "...", "client_id": 42}`
- Stored in encrypted SharedPreferences
- Attached to every request automatically

**Handling wrong tenant:**
```json
{
  "error_code": "TENANT_MISMATCH",
  "message": "You do not have access to this resource",
  "requested_resource_tenant": 99,
  "your_tenant": 42
}
```

---

## Testing Checklist

- [ ] Get current user profile
- [ ] Update profile fields
- [ ] Upload avatar photo
- [ ] Change password
- [ ] Get capabilities
- [ ] Search users by name
- [ ] Search users by department
- [ ] Get user details (other user)
- [ ] Get organizational hierarchy
- [ ] Get team members (as supervisor)
- [ ] Register device for notifications
- [ ] Verify multi-tenant isolation
- [ ] Handle profile not found
- [ ] Handle permission denied errors

---

## Offline Support

### Caching Strategy

**Cache user profile:**
- Store in Room database after first fetch
- Refresh on app start (if online)
- Use cached version if offline
- Show "Last updated: X minutes ago" in UI

**Cache directory:**
- Store frequently accessed users (recently viewed)
- Limit to 100 users
- LRU eviction policy

**Sync profile updates:**
- Update profile offline → store in pending queue
- Sync when online via WebSocket
- Handle version conflicts (server may have newer data)

---

## Security Notes

### PII Protection
- Phone, address, DOB, ID number are **sensitive PII**
- Never log these fields
- Encrypt in transit (HTTPS) and at rest (encrypted SharedPreferences)
- User can request data deletion (GDPR)

### Multi-Factor Authentication (if enabled)
- MFA setup endpoint: `POST /api/v2/people/me/mfa/setup/`
- MFA verify: `POST /api/v2/auth/mfa/verify/`
- Not documented here - see API_CONTRACT_FOUNDATION.md

---

**Document Version:** 1.0.0
**Last Updated:** November 7, 2025
**Next Review:** December 7, 2025
