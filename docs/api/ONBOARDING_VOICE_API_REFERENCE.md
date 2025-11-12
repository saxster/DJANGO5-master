# Onboarding & Voice Features API Reference

**Version**: 1.0
**Date**: 2025-11-12
**For**: Mobile Development Team
**Base URL**: `https://api.intelliwiz.com`

---

## 📋 Table of Contents

1. [Authentication](#authentication)
2. [Capabilities System](#capabilities-system)
3. [Profile Endpoints](#profile-endpoints)
4. [Onboarding Endpoints](#onboarding-endpoints)
5. [Journal Voice Endpoints](#journal-voice-endpoints)
6. [Error Codes](#error-codes)
7. [Security](#security)

---

## 🔐 Authentication

All endpoints require JWT authentication via Bearer token.

### Login Response (Enhanced)

**Endpoint**: `POST /api/v2/auth/login/`

**Response** includes new fields:

```json
{
    "success": true,
    "data": {
        "access": "eyJ0eXAiOiJKV1QiLC...",
        "refresh": "eyJ0eXAiOiJKV1QiLC...",
        "user": {
            "id": 123,
            "username": "john.doe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "capabilities": {
                "canAccessPeople": true,
                "canAccessAttendance": true,
                "canAccessOperations": true,
                "canAccessHelpdesk": true,
                "canAccessJournal": true,
                "canAccessReports": false,
                "canAccessCalendar": true,
                "canAccessOnboarding": false,
                "canUseVoiceFeatures": false,
                "canUseVoiceBiometrics": false,
                "canApproveJobs": false,
                "canManageTeam": false,
                "canViewAnalytics": false
            },
            "first_login_completed": false,
            "onboarding_completed_at": null,
            "profile_completion_percentage": 25
        }
    },
    "meta": {
        "correlation_id": "uuid-here",
        "timestamp": "2025-11-12T10:30:00Z"
    }
}
```

**New Fields**:
- `capabilities`: All 13 capability flags (use for UI gating)
- `first_login_completed`: Boolean (for first-time user detection)
- `onboarding_completed_at`: ISO 8601 timestamp or null
- `profile_completion_percentage`: Integer 0-100

---

## 🎯 Capabilities System

### Capability Flags

| Capability | Default | Description |
|------------|---------|-------------|
| `canAccessOnboarding` | `false` | Access to onboarding module |
| `canUseVoiceFeatures` | `false` | Voice notes in journal/helpdesk |
| `canUseVoiceBiometrics` | `false` | Voice biometric authentication |

### Usage in Mobile App

```kotlin
// After login
val capabilities = loginResponse.user.capabilities

// Gate onboarding UI
if (capabilities.canAccessOnboarding) {
    // Show onboarding flow
} else {
    // Skip to main app
}

// Gate voice note button
if (capabilities.canUseVoiceFeatures) {
    // Enable voice note recording
}
```

---

## 👤 Profile Endpoints

### Get Current User Profile

**Endpoint**: `GET /api/v2/people/profile/me/`

**Authentication**: Required (Bearer token)

**Permissions**: `IsAuthenticated`

**Response** (200 OK):
```json
{
    "id": 123,
    "username": "john.doe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "phone": "+1234567890",
    "client_id": 1,
    "tenant_id": 1,
    "capabilities": {
        "canAccessOnboarding": false,
        "canUseVoiceFeatures": false,
        ...
    },
    "profile": {
        "peopleimg": "https://cdn.intelliwiz.com/media/profiles/123.jpg",
        "dateofbirth": "1990-01-15",
        "dateofjoin": "2025-01-01",
        "gender": "M",
        "profile_completion_percentage": 75
    },
    "organizational": {
        "location": "Site A",
        "department": "Security",
        "designation": "Security Officer",
        "reportto": 456,
        "client": 1,
        "bu": "Operations"
    },
    "onboarding_status": {
        "first_login_completed": true,
        "onboarding_completed_at": "2025-11-10T14:30:00Z",
        "onboarding_skipped": false
    }
}
```

**Mobile DTO**: `ProfileDto.kt`

---

### Update Current User Profile

**Endpoint**: `PATCH /api/v2/people/profile/me/`

**Authentication**: Required

**Permissions**: `IsAuthenticated`

**Request Body** (all fields optional):
```json
{
    "email": "newemail@example.com",
    "mobno": "+9876543210",
    "profile": {
        "gender": "F",
        "dateofbirth": "1990-01-15",
        "dateofjoin": "2025-01-01",
        "dateofreport": "2025-01-15"
    },
    "organizational": {
        "location": 2,
        "department": 3,
        "designation": 5
    }
}
```

**Response** (200 OK):
Same structure as GET endpoint (updated profile)

**Error Response** (400 Bad Request):
```json
{
    "errors": {
        "dateofbirth": ["Date of birth cannot be in the future"],
        "dateofjoin": ["Date of joining cannot be before date of birth"]
    }
}
```

---

### Upload Profile Image

**Endpoint**: `POST /api/v2/people/profile/me/image/`

**Authentication**: Required

**Permissions**: `IsAuthenticated`

**Content-Type**: `multipart/form-data`

**Request**:
```
image: <file> (required)
```

**Validation Rules**:
- Max size: 5MB
- Allowed formats: `image/jpeg`, `image/png`, `image/webp`, `image/gif`
- Minimum dimensions: 200x200 pixels
- Maximum dimensions: 2048x2048 pixels

**Response** (200 OK):
```json
{
    "image_url": "https://cdn.intelliwiz.com/media/profiles/123.jpg",
    "profile_completion_percentage": 100
}
```

**Error Responses**:
```json
// 400 - No file
{"error": "No image file provided"}

// 400 - Too large
{"error": "Image file too large. Maximum size is 5MB"}

// 400 - Invalid format
{"error": "Invalid file type. Allowed: image/jpeg, image/png, image/webp, image/gif"}

// 400 - Dimensions too small
{"error": "Image dimensions too small. Minimum: 200x200 pixels"}
```

**Mobile DTO**: `ProfileImageResponseDto.kt`

---

## 📝 Onboarding Endpoints

### Get Profile Completion Status

**Endpoint**: `GET /api/v2/people/profile/completion-status/`

**Authentication**: Required

**Permissions**: `IsAuthenticated` + `HasOnboardingAccess`

**Response** (200 OK):
```json
{
    "is_complete": false,
    "completion_percentage": 60,
    "missing_fields": [
        {"field": "peopleimg", "display_name": "Profile Image"},
        {"field": "dateofjoin", "display_name": "Date of Joining"}
    ],
    "has_completed_onboarding": false,
    "onboarding_completed_at": null,
    "onboarding_skipped": false,
    "first_login_completed": true,
    "can_skip_onboarding": true,
    "required_documents": [],
    "onboarding_workflow_state": null
}
```

**Error Response** (403 Forbidden):
```json
{
    "detail": "You do not have permission to access onboarding features."
}
```

**Mobile DTO**: `ProfileCompletionDto.kt`

**Required Fields**: All 10 fields are required (mobile expects all keys)

---

### Mark Onboarding Complete

**Endpoint**: `POST /api/v2/people/profile/mark-onboarding-complete/`

**Authentication**: Required

**Permissions**: `IsAuthenticated` + `HasOnboardingAccess`

**Request Body**:
```json
{
    "skipped": false,
    "completed_steps": [
        "welcome",
        "permissions",
        "profile_setup",
        "safety_briefing",
        "feature_tour"
    ]
}
```

**Valid Steps**:
- `welcome`
- `permissions`
- `profile_setup`
- `safety_briefing`
- `feature_tour`
- `voice_enrollment`

**Response** (200 OK):
```json
{
    "success": true,
    "onboarding_completed_at": "2025-11-12T10:30:00Z",
    "onboarding_skipped": false,
    "first_login_completed": true
}
```

**Error Responses**:
```json
// 403 - No capability
{
    "detail": "You do not have permission to access onboarding features."
}

// 400 - Invalid step
{
    "errors": {
        "completed_steps": ["Invalid step: 'invalid_step'"]
    }
}
```

**Mobile DTOs**:
- Request: `MarkOnboardingCompleteRequestDto.kt`
- Response: `MarkOnboardingCompleteResponseDto.kt`

---

## 🎙️ Journal Voice Endpoints

### Upload Media to Journal Entry

**Endpoint**: `POST /api/v2/wellness/journal/<entry_id>/media/`

**Authentication**: Required

**Permissions**:
- `IsAuthenticated` (always)
- `HasVoiceFeatureAccess` (only for `media_type='AUDIO'`)

**Content-Type**: `multipart/form-data`

**Request**:
```
file: <audio file>
media_type: "AUDIO"
caption: "Voice note from the field" (optional)
duration: 45 (seconds, optional for AUDIO)
```

**Validation Rules**:
- If `media_type == "AUDIO"`: User must have `canUseVoiceFeatures = true`
- If `media_type == "PHOTO/VIDEO"`: No special permission needed
- Max audio file size: 50MB
- Allowed audio formats: `audio/mpeg`, `audio/wav`, `audio/m4a`, `audio/aac`, `audio/ogg`
- Max duration: 300 seconds (5 minutes)

**Security Checks**:
1. Verify `journal_entry.user_id == request.user.id` (ownership)
2. Verify `journal_entry.tenant_id == request.user.client_id` (multi-tenancy)
3. For AUDIO files: Check `canUseVoiceFeatures` capability

**Response** (201 Created):
```json
{
    "success": true,
    "data": {
        "id": "uuid-here",
        "journal_entry_id": "entry-uuid",
        "media_type": "AUDIO",
        "file_url": "https://cdn.intelliwiz.com/media/journal/456.m4a",
        "caption": "Voice note from the field",
        "duration": 45,
        "file_size": 512000,
        "created_at": "2025-11-12T18:05:00Z"
    },
    "meta": {
        "correlation_id": "uuid-here",
        "timestamp": "2025-11-12T18:05:00Z"
    }
}
```

**Error Responses**:
```json
// 403 - No voice capability
{
    "success": false,
    "error": {
        "code": "PERMISSION_DENIED",
        "message": "You do not have permission to upload audio files"
    }
}

// 403 - Not your entry
{
    "success": false,
    "error": {
        "code": "NOT_FOUND",
        "message": "Journal entry not found or you do not have access"
    }
}

// 400 - File too large
{
    "success": false,
    "error": {
        "code": "FILE_TOO_LARGE",
        "message": "Audio file too large. Maximum: 50MB"
    }
}
```

---

### List Journal Entry Media

**Endpoint**: `GET /api/v2/wellness/journal/<entry_id>/media/list/`

**Authentication**: Required

**Permissions**: `IsAuthenticated`

**Response** (200 OK):
```json
{
    "success": true,
    "data": [
        {
            "id": "uuid-1",
            "media_type": "AUDIO",
            "file_url": "https://...",
            "caption": "Voice note",
            "file_size": 512000,
            "created_at": "2025-11-12T18:05:00Z"
        },
        {
            "id": "uuid-2",
            "media_type": "PHOTO",
            "file_url": "https://...",
            "caption": "Field photo",
            "file_size": 204800,
            "created_at": "2025-11-12T18:10:00Z"
        }
    ],
    "meta": {
        "correlation_id": "uuid-here",
        "timestamp": "2025-11-12T18:15:00Z"
    }
}
```

---

## ❌ Error Codes

### HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Request successful |
| 201 | Created | Resource created (e.g., media uploaded) |
| 400 | Bad Request | Validation error, invalid data |
| 401 | Unauthorized | Missing/invalid JWT token |
| 403 | Forbidden | Lacks required capability |
| 404 | Not Found | Resource not found or no access |
| 500 | Server Error | Database or server error |

### Error Response Format

All errors follow V2 standardized format:

```json
{
    "success": false,
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable message"
    },
    "meta": {
        "correlation_id": "uuid-here",
        "timestamp": "2025-11-12T10:30:00Z"
    }
}
```

### Common Error Codes

- `PERMISSION_DENIED`: User lacks required capability
- `NOT_FOUND`: Resource not found or access denied
- `VALIDATION_ERROR`: Invalid request data
- `FILE_TOO_LARGE`: Uploaded file exceeds size limit
- `INVALID_FORMAT`: Unsupported file format
- `DATABASE_ERROR`: Server-side database error

---

## 🔒 Security

### Capability-Based Access Control

**All protected endpoints check capabilities**:

```python
# Onboarding endpoints require:
canAccessOnboarding = true

# Voice upload requires:
canUseVoiceFeatures = true

# Voice biometrics require:
canUseVoiceBiometrics = true
```

### Multi-Tenancy

All endpoints enforce tenant isolation:
- Journal entries: `tenant_id == user.client_id`
- Profile access: Current user only
- Cross-tenant access returns 404 (not 403)

### File Upload Security

**Image Uploads**:
- Max size: 5MB
- Allowed types: JPEG, PNG, WebP, GIF
- Dimension validation (200x200 to 2048x2048)
- Secure path generation (prevents path traversal)

**Audio Uploads**:
- Max size: 50MB
- Allowed types: MP3, WAV, M4A, AAC, OGG
- Duration limit: 5 minutes
- Capability check required

---

## 📱 Mobile Integration Examples

### Kotlin API Client Example

```kotlin
// 1. Check capability after login
if (loginResponse.user.capabilities.canAccessOnboarding &&
    !loginResponse.user.hasCompletedOnboarding) {
    navigateToOnboarding()
} else {
    navigateToMain()
}

// 2. Upload profile image
val imageFile = File("avatar.jpg")
val requestBody = imageFile.asRequestBody("image/jpeg".toMediaType())
val part = MultipartBody.Part.createFormData("image", "avatar.jpg", requestBody)

val response = apiService.uploadProfileImage(part)
// Response: ProfileImageResponseDto

// 3. Mark onboarding complete
val request = MarkOnboardingCompleteRequestDto(
    skipped = false,
    completedSteps = listOf("welcome", "permissions", "profile_setup")
)
val response = apiService.markOnboardingComplete(request)
// Response: MarkOnboardingCompleteResponseDto
```

---

## 🧪 Testing Endpoints

### With cURL

```bash
# Get profile
curl -H "Authorization: Bearer $TOKEN" \
     https://api.intelliwiz.com/api/v2/people/profile/me/

# Upload image
curl -H "Authorization: Bearer $TOKEN" \
     -F "image=@avatar.jpg" \
     https://api.intelliwiz.com/api/v2/people/profile/me/image/

# Get completion status (requires capability)
curl -H "Authorization: Bearer $TOKEN" \
     https://api.intelliwiz.com/api/v2/people/profile/completion-status/

# Mark complete
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"skipped": false, "completed_steps": ["welcome"]}' \
     https://api.intelliwiz.com/api/v2/people/profile/mark-onboarding-complete/
```

### With Postman

**Collection**: Download from `/docs/postman/onboarding-voice-api.json`

**Environment Variables**:
- `base_url`: `https://staging.intelliwiz.com`
- `access_token`: (from login response)

---

## 📊 Field Mapping

### Backend ↔ Mobile Field Mapping

| Backend (snake_case) | Mobile (camelCase) | Type | Required |
|----------------------|-------------------|------|----------|
| `is_complete` | `isComplete` | Boolean | Yes |
| `completion_percentage` | `completionPercentage` | Int | Yes |
| `missing_fields` | `missingFields` | List | Yes |
| `has_completed_onboarding` | `hasCompletedOnboarding` | Boolean | Yes |
| `onboarding_completed_at` | `onboardingCompletedAt` | String? | Yes |
| `onboarding_skipped` | `onboardingSkipped` | Boolean | Yes |
| `first_login_completed` | `firstLoginCompleted` | Boolean | Yes |
| `can_skip_onboarding` | `canSkipOnboarding` | Boolean | Yes |
| `required_documents` | `requiredDocuments` | List<String> | Yes |
| `onboarding_workflow_state` | `onboardingWorkflowState` | String? | Yes |

**Note**: Backend uses snake_case, mobile uses `@SerialName` to map to camelCase.

---

## 🚦 Rate Limiting

All endpoints inherit from project-wide rate limiting:
- Authenticated requests: 60 requests/minute
- File uploads: 10 requests/minute
- Login attempts: 10 requests/minute

---

## 📞 Support

**For API Issues**:
- Slack: #mobile-backend-integration
- Backend Team: backend-team@intelliwiz.com

**For Capability Issues**:
- Contact site admin to enable capabilities
- Admin can update via Django Admin: People → Capabilities

**For Schema Issues**:
- Check this documentation for exact field names
- Compare with mobile DTOs
- Report schema drift immediately

---

**Document Version**: 1.0
**Last Updated**: 2025-11-12
**Status**: Production Ready
