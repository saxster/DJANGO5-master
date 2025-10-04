# Kotlin Android Frontend - Django Backend API Contract

**Version**: 1.0
**Last Updated**: 2025-09-28
**Status**: Production-Ready Contract

---

## 📋 Table of Contents

1. [Contract Overview](#contract-overview)
2. [Backend Prerequisites](#backend-prerequisites)
3. [API Surface, Versioning & Auth](#api-surface-versioning--auth)
4. [Data Modeling Rules](#data-modeling-rules)
5. [Core Enums](#core-enums)
6. [Conversational Onboarding Endpoints](#conversational-onboarding-endpoints)
7. [Site Audit Endpoints](#site-audit-endpoints)
8. [Validation Rules](#validation-rules)
9. [GraphQL Usage](#graphql-usage)
10. [Error Handling & Status Codes](#error-handling--status-codes)
11. [Client Sync & Offline Strategy](#client-sync--offline-strategy)
12. [Networking & Transport](#networking--transport)
13. [Data Classes & Kotlin Mappings](#data-classes--kotlin-mappings)
14. [Security & Tenant Scoping](#security--tenant-scoping)
15. [Performance Guidelines](#performance-guidelines)
16. [Testing & Validation](#testing--validation)
17. [Contract Enforcement](#contract-enforcement)

---

## Contract Overview

### Purpose

This document defines the **immutable data contract** between the Kotlin Android frontend and Django 5 backend for the YOUTILITY5 facility management platform. It specifies:

- REST and GraphQL API endpoints
- Request/response schemas
- Data types and validation rules
- Authentication and security requirements
- Error handling patterns
- Offline-first sync strategies

### Scope

- **Conversational onboarding**: Session lifecycle, voice input, recommendations, approvals, status, preflight
- **Multimodal site audit**: Session start, observation capture (photo/audio/GPS), coverage, analysis, SOPs, reporting, zone/asset/meter management
- **GraphQL**: General platform schema endpoint (not primary for onboarding)
- **Auth, versioning, error handling, sync, and performance**

### Contract Rules

**⚠️ CRITICAL: This is a binding contract**

1. **Do NOT invent fields or endpoints** not specified in this document
2. **Do NOT change field names or casing** - all fields are snake_case
3. **Do NOT assume libraries are available** - verify each external dependency
4. **Do NOT deviate from enum values** - enums are exhaustive and final
5. **Do NOT skip validation** - all rules must be enforced client-side
6. **Do test against live backend** - contract tests must pass before production

### References

Backend code locations for verification:

- REST base: `/api/v1/onboarding/` → `intelliwiz_config/urls_optimized.py:75`
- GraphQL: `/api/graphql/`, `/graphql` → `intelliwiz_config/urls_optimized.py:86-88`
- REST settings: `intelliwiz_config/settings/rest_api.py`
- Conversational models: `apps/onboarding/models/conversational_ai.py`
- Site audit models: `apps/onboarding/models/site_onboarding.py`
- Site audit REST: `apps/onboarding_api/views/site_audit_views.py`
- Conversational REST: `apps/onboarding_api/views.py`
- Serializers: `apps/onboarding_api/serializers.py`, `apps/onboarding_api/serializers/site_audit_serializers.py`
- URL routes: `apps/onboarding_api/urls.py`

---

## Backend Prerequisites

### 🚨 REQUIRED BACKEND FIXES

Before using this contract, the backend **MUST** resolve these inconsistencies:

#### 1. Audio MIME Type Standardization (CRITICAL)

**Issue**: Backend has conflicting audio format specifications:
- `views.py:2385-2391` accepts: `audio/mp3`
- `site_audit_serializers.py:183-186` validates: `audio/mpeg`

**Required Fix**: Backend must accept BOTH `audio/mp3` AND `audio/mpeg` as valid MIME types.

**Backend Code Change Required**:
```python
# In site_audit_serializers.py and views.py - standardize to:
SUPPORTED_AUDIO_FORMATS = [
    'audio/webm',
    'audio/wav',
    'audio/mpeg',  # Standard MIME type
    'audio/mp3',   # Non-standard but widely used
    'audio/ogg',
    'audio/m4a',
    'audio/aac',
    'audio/flac'
]
```

**Verification**: Test voice upload with both `audio/mp3` and `audio/mpeg` Content-Type headers.

#### 2. PostGIS Coordinate Serialization Clarification

**Issue**: Coordinate order ambiguity in documentation.

**Clarification Needed**: Backend already handles this correctly but docs must specify:
- Input JSON: `{latitude: float, longitude: float}` (standard GPS order)
- Backend converts to: `Point(longitude, latitude, srid=4326)` (PostGIS order)
- Output string: `"POINT (longitude latitude)"` (PostGIS order)

**Verification**: Confirmed in `site_audit_views.py:169-174`.

### Backend Verification Checklist

Before deploying Kotlin client:

- [ ] Audio MIME type fix deployed and tested
- [ ] Coordinate serialization documented and verified
- [ ] CSRF middleware active for GraphQL endpoints
- [ ] JWT authentication configured and tested
- [ ] Rate limiting active (600/hour for authenticated users)
- [ ] All endpoints return proper error response structures

---

## API Surface, Versioning & Auth

### Base Paths

- **REST API**: `/api/v1/onboarding/`
- **GraphQL**: `/api/graphql/` (file upload supported), `/graphql`

### Versioning

- **Method**: URL path versioning (`v1`)
- **Current Version**: `v1`
- **Supported Versions**: `['v1', 'v2']` (v2 planned for 2026-06-30)
- **Header**: `X-API-Version: v1` (optional, defaults to v1)

### Authentication

**Required for all protected endpoints**:

```
Authorization: Bearer <jwt_token>
```

**JWT Acquisition**:
- REST: `POST /api/v1/auth/token/`
  - Request: `{"username": "user@example.com", "password": "secure_password"}`
  - Response: `{"access": "jwt_token", "refresh": "refresh_token"}`
- GraphQL: `mutation { tokenAuth(username: "user", password: "pass") { token } }`

**JWT Lifecycle**:
- Access token lifetime: 1 hour
- Refresh token lifetime: 7 days
- Refresh endpoint: `POST /api/v1/auth/token/refresh/` with `{"refresh": "refresh_token"}`

### Date/Time Format

**ALL datetime fields**:
- Format: RFC3339 with microseconds and UTC timezone
- Pattern: `%Y-%m-%dT%H:%M:%S.%fZ`
- Example: `2025-09-28T12:34:56.789123Z`
- Kotlin: Parse to `kotlinx.datetime.Instant`

### Throttling & Rate Limits

**Rate Limit Tiers**:
- Anonymous: `60/hour`
- Authenticated users: `600/hour` (default)
- Premium users: `6000/hour`

**On 429 Too Many Requests**:
- Response includes `Retry-After` header (seconds)
- Implement exponential backoff: `delay = min(2^retry_count, 300)` seconds
- Max retries: 3

### Content Types

**Request Headers**:
```
Content-Type: application/json           # For JSON requests
Content-Type: multipart/form-data        # For file uploads
Authorization: Bearer <token>            # Always required for protected endpoints
Accept: application/json                 # Optional
X-API-Version: v1                        # Optional
```

### Additional Headers

**Do NOT add** unlisted custom headers without backend coordination.

---

## Data Modeling Rules

### Kotlin Type Mappings

**CRITICAL MAPPINGS** (backend → Kotlin):

| Backend Type | Django Field | Kotlin Type | Notes |
|--------------|--------------|-------------|-------|
| UUID | `UUIDField` | `String` | Use `serializers.UUIDField()` to validate, parse from string |
| Decimal | `DecimalField` | `Double` | Backend sends as JSON number (not string) |
| DateTime | `DateTimeField` | `kotlinx.datetime.Instant` | Parse `%Y-%m-%dT%H:%M:%S.%fZ` with microseconds |
| Time | `TimeField` | `String` | Format: `"HH:MM"` (24-hour) |
| PointField | PostGIS `PointField` | Custom `GeoPoint` | Parse from `"POINT (lon lat)"` string |
| JSONField | PostgreSQL `JSONField` | `JsonObject` or data class | Deserialize to appropriate type |
| Integer | `IntegerField` | `Int` | Standard mapping |
| Boolean | `BooleanField` | `Boolean` | Standard mapping |
| String | `CharField`, `TextField` | `String` | Standard mapping |

### PostGIS Coordinate Handling (CRITICAL)

**⚠️ COORDINATE ORDER MATTERS**

Django/PostGIS uses **(longitude, latitude)** order internally, NOT standard GPS (latitude, longitude).

**Sending Coordinates TO Backend** (e.g., site start, observation capture):
```kotlin
// Your Kotlin data class
data class GpsLocation(
    val latitude: Double,  // Standard GPS order
    val longitude: Double
)

// JSON sent to backend
{
    "gps_location": {
        "latitude": 19.076,   // ← Backend expects this name
        "longitude": 72.877   // ← Backend expects this name
    }
}

// Backend automatically converts to: Point(72.877, 19.076, srid=4326)
```

**Receiving Coordinates FROM Backend** (e.g., observation list):
```kotlin
// Backend returns PostGIS string format
"gps_at_capture": "POINT (72.877 19.076)"
                         // ↑lon   ↑lat

// Your Kotlin parser
data class GeoPoint(val longitude: Double, val latitude: Double)

fun parsePointField(pointStr: String): GeoPoint? {
    // Pattern: "POINT (lon lat)"
    val regex = """POINT \(([-\d.]+) ([-\d.]+)\)""".toRegex()
    val match = regex.matchEntire(pointStr) ?: return null
    val (lon, lat) = match.destructured
    return GeoPoint(
        longitude = lon.toDouble(),
        latitude = lat.toDouble()
    )
}
```

**Example Usage**:
```kotlin
// Sending observation
val request = ObservationCreateRequest(
    gps_latitude = 19.076,   // Standard GPS order in request
    gps_longitude = 72.877,
    text_input = "CCTV not working"
)

// Receiving observation
val observation: ObservationResponse = apiService.getObservations(sessionId)
val point = parsePointField(observation.gps_at_capture)
// point.latitude = 19.076
// point.longitude = 72.877
```

### Serialization Rules

**Use Kotlinx Serialization** (recommended):

```kotlin
@Serializable
data class ConversationStartRequest(
    @SerialName("language") val language: String = "en",
    @SerialName("user_type") val userType: String? = null,
    @SerialName("client_context") val clientContext: JsonObject = JsonObject(emptyMap()),
    @SerialName("initial_input") val initialInput: String? = null,
    @SerialName("resume_existing") val resumeExisting: Boolean = false
)
```

**Key Rules**:
1. **Always use `@SerialName`** to match backend snake_case
2. **Never rename fields** - use exact backend names
3. **Mark optional fields nullable** with `?` or provide defaults
4. **Use `JsonObject` for unstructured JSON fields**
5. **Validate UUIDs** as strings, not `java.util.UUID`

### Numbers & Precision

Backend configuration: `COERCE_DECIMAL_TO_STRING = False`

**This means**:
- Decimal fields are sent as JSON numbers: `"progress": 0.75` (not `"0.75"`)
- Map to Kotlin `Double`, not `String`
- Example: `confidence_score`, `progress_percentage`, `gps_latitude`, `gps_longitude`

---

## Core Enums

**⚠️ EXHAUSTIVE AND FINAL** - Do not add unlisted values.

### ConversationSession.ConversationType

**Source**: `apps/onboarding/models/conversational_ai.py:35-39`

```kotlin
enum class ConversationType {
    @SerialName("initial_setup") INITIAL_SETUP,
    @SerialName("config_update") CONFIG_UPDATE,
    @SerialName("troubleshooting") TROUBLESHOOTING,
    @SerialName("feature_request") FEATURE_REQUEST
}
```

### ConversationSession.State

**Source**: `apps/onboarding/models/conversational_ai.py:41-48`

```kotlin
enum class ConversationState {
    @SerialName("started") STARTED,
    @SerialName("in_progress") IN_PROGRESS,
    @SerialName("generating") GENERATING_RECOMMENDATIONS,
    @SerialName("awaiting_approval") AWAITING_USER_APPROVAL,
    @SerialName("completed") COMPLETED,
    @SerialName("cancelled") CANCELLED,
    @SerialName("error") ERROR
}
```

### OnboardingSite.SiteType

**Source**: `apps/onboarding/models/site_onboarding.py:43-50`

```kotlin
enum class SiteType {
    @SerialName("bank_branch") BANK_BRANCH,
    @SerialName("atm") ATM,
    @SerialName("retail_store") RETAIL_STORE,
    @SerialName("warehouse") WAREHOUSE,
    @SerialName("office") OFFICE,
    @SerialName("industrial") INDUSTRIAL,
    @SerialName("mixed_use") MIXED_USE
}
```

### OnboardingZone.ZoneType

**Source**: `apps/onboarding/models/site_onboarding.py:155-169`

```kotlin
enum class ZoneType {
    @SerialName("gate") GATE,
    @SerialName("perimeter") PERIMETER,
    @SerialName("entry_exit") ENTRY_EXIT,
    @SerialName("vault") VAULT,
    @SerialName("atm") ATM,
    @SerialName("control_room") CONTROL_ROOM,
    @SerialName("parking") PARKING,
    @SerialName("loading_dock") LOADING_DOCK,
    @SerialName("emergency_exit") EMERGENCY_EXIT,
    @SerialName("asset_storage") ASSET_STORAGE,
    @SerialName("cash_counter") CASH_COUNTER,
    @SerialName("server_room") SERVER_ROOM,
    @SerialName("reception") RECEPTION,
    @SerialName("other") OTHER
}
```

### OnboardingZone.ImportanceLevel

**Source**: `apps/onboarding/models/site_onboarding.py:171-175`

```kotlin
enum class ImportanceLevel {
    @SerialName("critical") CRITICAL,
    @SerialName("high") HIGH,
    @SerialName("medium") MEDIUM,
    @SerialName("low") LOW
}
```

### OnboardingZone.RiskLevel

**Source**: `apps/onboarding/models/site_onboarding.py:177-182`

```kotlin
enum class RiskLevel {
    @SerialName("severe") SEVERE,
    @SerialName("high") HIGH,
    @SerialName("moderate") MODERATE,
    @SerialName("low") LOW,
    @SerialName("minimal") MINIMAL
}
```

### Observation.Severity

**Source**: `apps/onboarding/models/site_onboarding.py:258-263`

```kotlin
enum class ObservationSeverity {
    @SerialName("critical") CRITICAL,
    @SerialName("high") HIGH,
    @SerialName("medium") MEDIUM,
    @SerialName("low") LOW,
    @SerialName("info") INFO
}
```

### MeterPoint.MeterType

**Source**: `apps/onboarding/models/site_onboarding.py:580-589`

```kotlin
enum class MeterType {
    @SerialName("electricity") ELECTRICITY,
    @SerialName("water") WATER,
    @SerialName("diesel") DIESEL,
    @SerialName("fire_pressure") FIRE_PRESSURE,
    @SerialName("logbook") LOGBOOK,
    @SerialName("temperature") TEMPERATURE,
    @SerialName("generator_hours") GENERATOR_HOURS,
    @SerialName("ups_status") UPS_STATUS,
    @SerialName("other") OTHER
}
```

### SOP.Frequency

**Source**: `apps/onboarding/models/site_onboarding.py:702-704`

**Note**: Free-text field in backend, but use these standard values:

```kotlin
enum class SOPFrequency(val value: String) {
    HOURLY("hourly"),
    SHIFT("shift"),
    DAILY("daily"),
    WEEKLY("weekly"),
    MONTHLY("monthly"),
    AS_NEEDED("as_needed")
}
```

### Asset.AssetType

**Source**: `apps/onboarding/models/site_onboarding.py:448-463`

```kotlin
enum class AssetType {
    @SerialName("camera") CAMERA,
    @SerialName("dvr_nvr") DVR_NVR,
    @SerialName("lighting") LIGHTING,
    @SerialName("metal_detector") METAL_DETECTOR,
    @SerialName("xray_machine") XRAY_MACHINE,
    @SerialName("alarm_system") ALARM_SYSTEM,
    @SerialName("access_reader") ACCESS_READER,
    @SerialName("biometric") BIOMETRIC,
    @SerialName("intercom") INTERCOM,
    @SerialName("barrier_gate") BARRIER_GATE,
    @SerialName("safe_vault") SAFE_VAULT,
    @SerialName("fire_extinguisher") FIRE_EXTINGUISHER,
    @SerialName("fire_alarm") FIRE_ALARM,
    @SerialName("emergency_light") EMERGENCY_LIGHT,
    @SerialName("other") OTHER
}
```

### Asset.Status

**Source**: `apps/onboarding/models/site_onboarding.py:465-470`

```kotlin
enum class AssetStatus {
    @SerialName("operational") OPERATIONAL,
    @SerialName("needs_repair") NEEDS_REPAIR,
    @SerialName("not_installed") NOT_INSTALLED,
    @SerialName("planned") PLANNED,
    @SerialName("decommissioned") DECOMMISSIONED
}
```

---

## Conversational Onboarding Endpoints

### Feature Status

**Endpoint**: `GET /api/v1/onboarding/status/`

**Purpose**: Check enabled features and user capabilities

**Authentication**: Required

**Response**:
```json
{
    "dual_llm_enabled": true,
    "streaming_enabled": false,
    "knowledge_base_enabled": true,
    "user_capabilities": {
        "can_approve": true,
        "can_modify_recommendations": true,
        "requires_two_person_approval": false
    }
}
```

**Kotlin Example**:
```kotlin
@Serializable
data class FeatureStatusResponse(
    @SerialName("dual_llm_enabled") val dualLlmEnabled: Boolean,
    @SerialName("streaming_enabled") val streamingEnabled: Boolean,
    @SerialName("knowledge_base_enabled") val knowledgeBaseEnabled: Boolean,
    @SerialName("user_capabilities") val userCapabilities: UserCapabilities
)

@Serializable
data class UserCapabilities(
    @SerialName("can_approve") val canApprove: Boolean,
    @SerialName("can_modify_recommendations") val canModifyRecommendations: Boolean,
    @SerialName("requires_two_person_approval") val requiresTwoPersonApproval: Boolean
)
```

---

### Start Conversation

**Endpoint**: `POST /api/v1/onboarding/conversation/start/`

**Purpose**: Initialize a new conversational onboarding session

**Authentication**: Required

**Idempotency**: ✅ Safe to retry with same parameters (server deduplicates)

**Request Body**:
```json
{
    "language": "en",
    "user_type": "admin",
    "client_context": {
        "region": "IN",
        "industry": "banking"
    },
    "initial_input": "I need to set up security for a bank branch",
    "resume_existing": false
}
```

**Request Schema**:
- `language`: String (ISO 639-1 code), default `"en"`
- `user_type`: String, optional
- `client_context`: JSON object, default `{}`
- `initial_input`: String (max 1000 chars), optional
- `resume_existing`: Boolean, default `false`

**Response (200 OK)**:
```json
{
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "enhanced_understanding": {
        "intent": "security_setup",
        "domain": "banking",
        "priority": "high"
    },
    "questions": [
        {
            "question": "What type of facility are you securing?",
            "field": "site_type",
            "options": ["bank_branch", "atm", "retail_store"]
        }
    ],
    "context": {
        "region": "IN",
        "industry": "banking"
    }
}
```

**Error Responses**:
- `403 Forbidden`: Conversational onboarding not enabled for this user
- `400 Bad Request`: User not associated with a client/business unit
- `409 Conflict`: Active session already exists (includes `existing_session_id`)

**Kotlin Example**:
```kotlin
@Serializable
data class ConversationStartRequest(
    @SerialName("language") val language: String = "en",
    @SerialName("user_type") val userType: String? = null,
    @SerialName("client_context") val clientContext: JsonObject = JsonObject(emptyMap()),
    @SerialName("initial_input") val initialInput: String? = null,
    @SerialName("resume_existing") val resumeExisting: Boolean = false
)

@Serializable
data class ConversationStartResponse(
    @SerialName("conversation_id") val conversationId: String,
    @SerialName("enhanced_understanding") val enhancedUnderstanding: JsonObject,
    @SerialName("questions") val questions: List<JsonObject>,
    @SerialName("context") val context: JsonObject
)
```

---

### Process Conversation Step

**Endpoint**: `POST /api/v1/onboarding/conversation/{conversation_id}/process/`

**Purpose**: Submit user input to advance the conversation

**Authentication**: Required

**Idempotency**: ✅ Safe to retry with same input (server deduplicates)

**Path Parameters**:
- `conversation_id`: UUID string of the conversation session

**Request Body**:
```json
{
    "user_input": "We have 3 ATM machines and 1 branch office",
    "context": {
        "current_step": "site_details"
    }
}
```

**Request Schema**:
- `user_input`: String (max 2000 chars), required
- `context`: JSON object, optional

**Response (Synchronous - 200 OK)**:
```json
{
    "enhanced_recommendations": [
        {
            "recommendation_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "title": "ATM Security Coverage Plan",
            "description": "Deploy 24/7 security coverage for ATM locations",
            "confidence_score": 0.92,
            "authoritative_sources": [
                {
                    "document": "RBI Master Direction 2021",
                    "section": "Physical Security Requirements"
                }
            ]
        }
    ],
    "consensus_confidence": 0.89,
    "next_steps": [
        "Review recommended security zones",
        "Configure guard shift schedules",
        "Set up monitoring equipment"
    ]
}
```

**Response (Asynchronous - 202 Accepted)**:
```json
{
    "status": "processing",
    "status_url": "/api/v1/onboarding/conversation/3fa85f64-5717-4562-b3fc-2c963f66afa6/status/",
    "task_id": "celery-task-uuid",
    "task_status_url": "/api/v1/onboarding/tasks/celery-task-uuid/status/",
    "estimated_completion_seconds": 15
}
```

**When Async is Used**:
- User input > 500 characters
- Session has > 10 conversation turns
- LLM processing expected to exceed 5 seconds

**Kotlin Example**:
```kotlin
@Serializable
data class ConversationProcessRequest(
    @SerialName("user_input") val userInput: String,
    @SerialName("context") val context: JsonObject? = null
)

@Serializable
data class ConversationProcessResponse(
    @SerialName("enhanced_recommendations") val enhancedRecommendations: List<RecommendationItem>? = null,
    @SerialName("consensus_confidence") val consensusConfidence: Double? = null,
    @SerialName("next_steps") val nextSteps: List<String>? = null,
    // Async fields
    @SerialName("status") val status: String? = null,
    @SerialName("status_url") val statusUrl: String? = null,
    @SerialName("task_id") val taskId: String? = null,
    @SerialName("task_status_url") val taskStatusUrl: String? = null,
    @SerialName("estimated_completion_seconds") val estimatedCompletionSeconds: Int? = null
)

@Serializable
data class RecommendationItem(
    @SerialName("recommendation_id") val recommendationId: String,
    @SerialName("title") val title: String,
    @SerialName("description") val description: String,
    @SerialName("confidence_score") val confidenceScore: Double,
    @SerialName("authoritative_sources") val authoritativeSources: List<JsonObject>
)
```

---

### Conversation Status

**Endpoint**: `GET /api/v1/onboarding/conversation/{conversation_id}/status/`

**Purpose**: Get current conversation state and progress

**Authentication**: Required

**Path Parameters**:
- `conversation_id`: UUID string

**Response (200 OK)**:
```json
{
    "state": "in_progress",
    "status": "in_progress",
    "progress": 0.65,
    "enhanced_recommendations": [
        {
            "recommendation_id": "uuid",
            "title": "Recommendation title",
            "confidence_score": 0.92
        }
    ],
    "error_message": null
}
```

**Response Schema**:
- `state`: Enum (ConversationState) - current session state
- `status`: String - alias of `state` for backward compatibility
- `progress`: Float (0.0 to 1.0) - completion percentage
- `enhanced_recommendations`: Array, optional - available recommendations
- `error_message`: String, optional - error details if state is "error"

**Kotlin Example**:
```kotlin
@Serializable
data class ConversationStatusResponse(
    @SerialName("state") val state: ConversationState,
    @SerialName("status") val status: String,
    @SerialName("progress") val progress: Double,
    @SerialName("enhanced_recommendations") val enhancedRecommendations: List<RecommendationItem>? = null,
    @SerialName("error_message") val errorMessage: String? = null
)
```

---

### Voice Input

**Endpoint**: `POST /api/v1/onboarding/conversation/{conversation_id}/voice/`

**Purpose**: Submit voice recording for transcription and processing

**Authentication**: Required

**Content-Type**: `multipart/form-data`

**Path Parameters**:
- `conversation_id`: UUID string

**Multipart Form Fields**:
- `audio`: File (required) - Audio recording
- `language`: String (optional) - BCP-47 language code (default: `"en-US"`)

**Supported Audio Formats** (✅ CORRECTED):
- `audio/webm`
- `audio/wav`
- `audio/mpeg` ← Standard MIME type
- `audio/mp3` ← Non-standard but accepted
- `audio/ogg`
- `audio/m4a`
- `audio/aac`
- `audio/flac`

**Maximum File Size**: 10 MB

**Supported Languages** (BCP-47 codes):
- `en-US` - English (United States)
- `en-GB` - English (United Kingdom)
- `hi-IN` - Hindi (India)
- `mr-IN` - Marathi (India)
- `ta-IN` - Tamil (India)
- `te-IN` - Telugu (India)
- `bn-IN` - Bengali (India)

**Request Example** (Multipart):
```
POST /api/v1/onboarding/conversation/3fa85f64-5717-4562-b3fc-2c963f66afa6/voice/
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="audio"; filename="recording.webm"
Content-Type: audio/webm

[binary audio data]
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="language"

hi-IN
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

**Response (200 OK)**:
```json
{
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "transcription": {
        "text": "हमारे पास तीन एटीएम मशीन हैं",
        "confidence": 0.94,
        "language": "hi-IN",
        "duration_seconds": 3.5,
        "processing_time_ms": 1250
    },
    "response": "Thank you. You mentioned you have three ATM machines. What type of location are they in?",
    "next_questions": [
        "Are the ATMs located inside bank branches or standalone?",
        "What are the operating hours for each ATM?"
    ],
    "state": "in_progress",
    "voice_interaction_count": 1
}
```

**Response Schema**:
- `conversation_id`: UUID string
- `transcription`: Object with:
  - `text`: String - transcribed text in original language
  - `confidence`: Float (0.0 to 1.0) - transcription confidence
  - `language`: String (BCP-47) - detected language
  - `duration_seconds`: Float - audio duration
  - `processing_time_ms`: Integer - processing time in milliseconds
- `response`: String - LLM response to the voice input
- `next_questions`: Array of strings - follow-up questions
- `state`: Enum (ConversationState) - current session state
- `voice_interaction_count`: Integer - total voice interactions in session

**Error Responses**:
- `400 Bad Request`: Missing audio file, unsupported format, or language
- `413 Payload Too Large`: Audio file exceeds 10 MB
- `404 Not Found`: Invalid conversation_id

**Kotlin Example**:
```kotlin
suspend fun uploadVoiceInput(
    conversationId: String,
    audioFile: File,
    language: String = "en-US"
): VoiceTranscriptionResponse {
    val requestBody = MultipartBody.Builder()
        .setType(MultipartBody.FORM)
        .addFormDataPart(
            "audio",
            audioFile.name,
            audioFile.asRequestBody("audio/webm".toMediaTypeOrNull())
        )
        .addFormDataPart("language", language)
        .build()

    val request = Request.Builder()
        .url("${baseUrl}/conversation/${conversationId}/voice/")
        .header("Authorization", "Bearer $jwtToken")
        .post(requestBody)
        .build()

    // Execute request...
}

@Serializable
data class VoiceTranscriptionResponse(
    @SerialName("conversation_id") val conversationId: String,
    @SerialName("transcription") val transcription: TranscriptionDetails,
    @SerialName("response") val response: String,
    @SerialName("next_questions") val nextQuestions: List<String>,
    @SerialName("state") val state: ConversationState,
    @SerialName("voice_interaction_count") val voiceInteractionCount: Int
)

@Serializable
data class TranscriptionDetails(
    @SerialName("text") val text: String,
    @SerialName("confidence") val confidence: Double,
    @SerialName("language") val language: String,
    @SerialName("duration_seconds") val durationSeconds: Double,
    @SerialName("processing_time_ms") val processingTimeMs: Int
)
```

---

### Voice Capabilities

**Endpoint**: `GET /api/v1/onboarding/voice/capabilities/`

**Purpose**: Check if voice input is enabled and available

**Authentication**: Required

**Response (200 OK)**:
```json
{
    "voice_enabled": true,
    "service_available": true,
    "supported_languages": {
        "en-US": "English (United States)",
        "hi-IN": "Hindi (India)",
        "mr-IN": "Marathi (India)"
    },
    "configuration": {
        "max_file_size_mb": 10,
        "default_language": "en-US",
        "min_confidence_threshold": 0.6
    },
    "supported_formats": [
        "audio/webm",
        "audio/wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/ogg",
        "audio/m4a",
        "audio/aac",
        "audio/flac"
    ],
    "features": {
        "real_time_transcription": false,
        "speaker_identification": false,
        "noise_cancellation": true,
        "multi_language_detection": false,
        "auto_language_detection": false
    }
}
```

**Kotlin Example**:
```kotlin
@Serializable
data class VoiceCapabilitiesResponse(
    @SerialName("voice_enabled") val voiceEnabled: Boolean,
    @SerialName("service_available") val serviceAvailable: Boolean,
    @SerialName("supported_languages") val supportedLanguages: Map<String, String>,
    @SerialName("configuration") val configuration: VoiceConfiguration,
    @SerialName("supported_formats") val supportedFormats: List<String>,
    @SerialName("features") val features: VoiceFeatures
)

@Serializable
data class VoiceConfiguration(
    @SerialName("max_file_size_mb") val maxFileSizeMb: Int,
    @SerialName("default_language") val defaultLanguage: String,
    @SerialName("min_confidence_threshold") val minConfidenceThreshold: Double
)

@Serializable
data class VoiceFeatures(
    @SerialName("real_time_transcription") val realTimeTranscription: Boolean,
    @SerialName("speaker_identification") val speakerIdentification: Boolean,
    @SerialName("noise_cancellation") val noiseCancellation: Boolean,
    @SerialName("multi_language_detection") val multiLanguageDetection: Boolean,
    @SerialName("auto_language_detection") val autoLanguageDetection: Boolean
)
```

---

### Enhanced Process (Phase 2)

**Endpoint**: `POST /api/v1/onboarding/conversation/{conversation_id}/process-enhanced/`

**Purpose**: Submit input with enhanced maker/checker LLM processing

**Authentication**: Required

**Request/Response**: Same as `process/` endpoint but includes additional fields:

**Response (200 OK)**:
```json
{
    "maker_output": { /* LLM 1 output */ },
    "checker_output": { /* LLM 2 validation */ },
    "consensus": { /* Merged consensus */ },
    "enhanced_recommendations": [ /* Recommendations */ ],
    "consensus_confidence": 0.91,
    "trace_id": "distributed-trace-id",
    "knowledge_citations": [
        {
            "knowledge_id": "uuid",
            "document_title": "RBI Master Direction 2021",
            "authority_level": "official"
        }
    ]
}
```

---

### Server-Sent Events (Phase 2)

**Endpoint**: `GET /api/v1/onboarding/conversation/{conversation_id}/events/`

**Purpose**: Real-time conversation updates (if streaming enabled)

**Authentication**: Required

**Response**: SSE stream or long-polling fallback

**Event Types**:
- `session_state`: State changed
- `progress`: Progress updated
- `recommendation`: New recommendation available

**Long-Polling Fallback** (if SSE not available):
```json
{
    "session_state": "in_progress",
    "progress": 0.72,
    "next_poll_delay": 3
}
```

---

### Recommendation Approval

**Endpoint**: `POST /api/v1/onboarding/recommendations/approve/`

**Purpose**: Approve or reject AI-generated recommendations

**Authentication**: Required

**Permissions**: `CanApproveAIRecommendations` permission required

**Request Body**:
```json
{
    "approved_items": [
        "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "8d0f7789-8536-51ef-c15d-f18gd2g01bf8"
    ],
    "rejected_items": [
        "9e1g8890-9647-62fg-d26e-g29he3h12cg9"
    ],
    "reasons": {
        "9e1g8890-9647-62fg-d26e-g29he3h12cg9": "Does not align with our security policy"
    },
    "modifications": {
        "7c9e6679-7425-40de-944b-e07fc1f90ae7": {
            "staffing_count": 5
        }
    },
    "dry_run": false
}
```

**Request Schema**:
- `approved_items`: Array of UUID strings, default `[]`
- `rejected_items`: Array of UUID strings, default `[]`
- `reasons`: Object mapping UUID → rejection reason string
- `modifications`: Object mapping UUID → modification object
- `dry_run`: Boolean, default `true` (preview mode)

**Response (200 OK)**:
```json
{
    "approved_count": 2,
    "rejected_count": 1,
    "applied": true,
    "two_person_approval_required": false,
    "changeset_id": "uuid-of-changeset"
}
```

**Response (Two-Person Approval Required)**:
```json
{
    "approved_count": 2,
    "rejected_count": 1,
    "applied": false,
    "two_person_approval_required": true,
    "approval_id": 12345,
    "changeset_id": "uuid-of-changeset",
    "message": "This approval requires a second person to review and decide."
}
```

**Kotlin Example**:
```kotlin
@Serializable
data class RecommendationApprovalRequest(
    @SerialName("approved_items") val approvedItems: List<String> = emptyList(),
    @SerialName("rejected_items") val rejectedItems: List<String> = emptyList(),
    @SerialName("reasons") val reasons: Map<String, String> = emptyMap(),
    @SerialName("modifications") val modifications: Map<String, JsonObject> = emptyMap(),
    @SerialName("dry_run") val dryRun: Boolean = true
)

@Serializable
data class ApprovalResponse(
    @SerialName("approved_count") val approvedCount: Int,
    @SerialName("rejected_count") val rejectedCount: Int,
    @SerialName("applied") val applied: Boolean,
    @SerialName("two_person_approval_required") val twoPersonApprovalRequired: Boolean,
    @SerialName("approval_id") val approvalId: Int? = null,  // ← INTEGER, not UUID
    @SerialName("changeset_id") val changesetId: String? = null,
    @SerialName("message") val message: String? = null
)
```

---

### Secondary Approval Decision

**Endpoint**: `POST /api/v1/onboarding/approvals/{approval_id}/decide/`

**Purpose**: Second person approval/rejection for two-person workflow

**Authentication**: Required

**Path Parameters**:
- `approval_id`: **INTEGER** (not UUID) - ID from approval response

**Request Body**:
```json
{
    "decision": "approved",
    "comments": "Reviewed and approved security recommendations"
}
```

**Request Schema**:
- `decision`: String enum: `"approved"` or `"rejected"`
- `comments`: String, optional

**Response (200 OK)**:
```json
{
    "decision": "approved",
    "applied": true,
    "changeset_id": "uuid-of-changeset"
}
```

**Kotlin Example**:
```kotlin
@Serializable
data class SecondaryApprovalRequest(
    @SerialName("decision") val decision: String, // "approved" or "rejected"
    @SerialName("comments") val comments: String? = null
)

suspend fun approveSecondary(approvalId: Int, decision: String, comments: String?) {
    // ↑ Note: Int, not String/UUID
    val request = SecondaryApprovalRequest(decision, comments)
    apiService.decideSecondaryApproval(approvalId, request)
}
```

---

### Preflight Validation

**Endpoint**: `GET /api/v1/onboarding/preflight/` or `POST /api/v1/onboarding/preflight/`

**Purpose**: Validate system readiness before deployment

**Authentication**: Required

**Response (200 OK - Ready)**:
```json
{
    "preflight_validation": {
        "readiness": "ready",
        "critical_issues": [],
        "warnings": [
            "One zone has no assets defined"
        ],
        "recommendations": [
            "Consider adding backup camera to Vault zone"
        ]
    }
}
```

**Response (412 Precondition Failed - Not Ready)**:
```json
{
    "preflight_validation": {
        "readiness": "not_ready",
        "critical_issues": [
            "No guard posts defined for critical zones",
            "Missing CCTV coverage in Vault area"
        ],
        "warnings": [],
        "recommendations": []
    }
}
```

---

### Quick Preflight

**Endpoint**: `GET /api/v1/onboarding/preflight/quick/`

**Purpose**: Fast readiness check without detailed analysis

**Authentication**: Required

**Response (200 OK)**:
```json
{
    "ready": true,
    "quick_checks": {
        "zones_configured": true,
        "coverage_plan_exists": true,
        "critical_zones_covered": true
    },
    "next_action": null
}
```

---

### UI Compatibility Endpoints

**⚠️ NOT FOR MOBILE USE** - These endpoints are for legacy web UI only.

- `POST /api/v1/onboarding/conversation/start/ui/`
- `POST /api/v1/onboarding/conversation/process/`
- `GET /api/v1/onboarding/task-status/{task_id}/`
- `GET /api/v1/onboarding/conversation/{conversation_id}/status/ui/`

**Mobile apps MUST use the standard endpoints** documented above.

---

## Site Audit Endpoints

### Start Site Audit Session

**Endpoint**: `POST /api/v1/onboarding/site-audit/start/`

**Purpose**: Initialize a new multimodal site security audit session

**Authentication**: Required

**Request Body**:
```json
{
    "business_unit_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "site_type": "bank_branch",
    "language": "en",
    "operating_hours": {
        "start": "09:00",
        "end": "18:00"
    },
    "gps_location": {
        "latitude": 19.076,
        "longitude": 72.877
    }
}
```

**Request Schema**:
- `business_unit_id`: UUID string, required
- `site_type`: Enum (SiteType), required
- `language`: String (ISO 639-1), default `"en"`
- `operating_hours`: Object, optional
  - `start`: String `"HH:MM"` (24-hour format)
  - `end`: String `"HH:MM"` (24-hour format)
- `gps_location`: Object, optional
  - `latitude`: Float (-90 to 90)
  - `longitude`: Float (-180 to 180)

**Response (201 Created)**:
```json
{
    "audit_session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "site_id": "4gb96g75-6828-5673-c4gd-3d074g77bgb7",
    "checklist": [
        {
            "category": "Physical Security",
            "items": [
                "Verify CCTV camera coverage",
                "Check perimeter fencing condition"
            ]
        }
    ],
    "zones": [
        {
            "zone_id": "5hc07h86-7939-6784-d5he-4e185h88cha8",
            "zone_name": "Main Entrance Gate",
            "zone_type": "gate",
            "importance_level": "critical"
        },
        {
            "zone_id": "6id18i97-8040-7895-e6if-5f296i99dib9",
            "zone_name": "ATM Lobby",
            "zone_type": "atm",
            "importance_level": "high"
        }
    ],
    "suggested_route": [
        {
            "order": 1,
            "zone_id": "5hc07h86-7939-6784-d5he-4e185h88cha8",
            "zone_name": "Main Entrance Gate",
            "estimated_minutes": 5
        }
    ],
    "estimated_duration_minutes": 35
}
```

**Kotlin Example**:
```kotlin
@Serializable
data class SiteAuditStartRequest(
    @SerialName("business_unit_id") val businessUnitId: String,
    @SerialName("site_type") val siteType: SiteType,
    @SerialName("language") val language: String = "en",
    @SerialName("operating_hours") val operatingHours: OperatingHours? = null,
    @SerialName("gps_location") val gpsLocation: GpsLocation? = null
)

@Serializable
data class OperatingHours(
    @SerialName("start") val start: String, // "HH:MM"
    @SerialName("end") val end: String      // "HH:MM"
)

@Serializable
data class GpsLocation(
    @SerialName("latitude") val latitude: Double,
    @SerialName("longitude") val longitude: Double
)

@Serializable
data class SiteAuditStartResponse(
    @SerialName("audit_session_id") val auditSessionId: String,
    @SerialName("site_id") val siteId: String,
    @SerialName("checklist") val checklist: List<ChecklistCategory>,
    @SerialName("zones") val zones: List<ZoneInfo>,
    @SerialName("suggested_route") val suggestedRoute: List<RouteStep>,
    @SerialName("estimated_duration_minutes") val estimatedDurationMinutes: Int
)
```

---

### Site Audit Session Status

**Endpoint**: `GET /api/v1/onboarding/site-audit/{session_id}/status/`

**Purpose**: Get current audit progress and coverage statistics

**Authentication**: Required

**Path Parameters**:
- `session_id`: UUID string (the `audit_session_id` from start response)

**Response (200 OK)**:
```json
{
    "state": "in_progress",
    "progress_percentage": 45.5,
    "coverage": {
        "total_zones": 8,
        "visited_zones": 4,
        "critical_gaps": [
            {
                "zone_id": "uuid",
                "zone_name": "Vault Area",
                "importance_level": "critical"
            }
        ]
    },
    "current_zone": "ATM Lobby",
    "next_recommended_zone": "Vault Area",
    "observations_count": 12,
    "estimated_completion_minutes": 20
}
```

**Response Schema**:
- `state`: Enum (ConversationState) - current audit state
- `progress_percentage`: Float (0.0 to 100.0)
- `coverage`: Object
  - `total_zones`: Integer
  - `visited_zones`: Integer
  - `critical_gaps`: Array of zone objects
- `current_zone`: String, optional
- `next_recommended_zone`: String, optional
- `observations_count`: Integer
- `estimated_completion_minutes`: Integer, optional

**Kotlin Example**:
```kotlin
@Serializable
data class SiteAuditStatusResponse(
    @SerialName("state") val state: ConversationState,
    @SerialName("progress_percentage") val progressPercentage: Double,
    @SerialName("coverage") val coverage: CoverageStats,
    @SerialName("current_zone") val currentZone: String? = null,
    @SerialName("next_recommended_zone") val nextRecommendedZone: String? = null,
    @SerialName("observations_count") val observationsCount: Int,
    @SerialName("estimated_completion_minutes") val estimatedCompletionMinutes: Int? = null
)

@Serializable
data class CoverageStats(
    @SerialName("total_zones") val totalZones: Int,
    @SerialName("visited_zones") val visitedZones: Int,
    @SerialName("critical_gaps") val criticalGaps: List<ZoneInfo>
)
```

---

### Capture Observation (Multimodal)

**Endpoint**: `POST /api/v1/onboarding/site-audit/{session_id}/observation/`

**Purpose**: Capture voice + photo + GPS observation during site audit

**Authentication**: Required

**Content-Type**: `multipart/form-data` or `application/json`

**Path Parameters**:
- `session_id`: UUID string

**Multipart Form Fields** (at least one required):
- `photo`: Image file, optional (JPEG/PNG/WebP, max 5MB)
- `audio`: Audio file, optional (see supported formats below, max 10MB)
- `text_input`: String, optional (max 2000 chars)
- `gps_latitude`: Float, **required** (-90 to 90)
- `gps_longitude`: Float, **required** (-180 to 180)
- `zone_hint`: String, optional (operator's zone identification hint)
- `compass_direction`: Float, optional (0 to 360 degrees)

**Supported Photo Formats**:
- `image/jpeg`
- `image/png`
- `image/webp`
- Max size: 5 MB

**Supported Audio Formats**:
- `audio/webm`
- `audio/wav`
- `audio/mpeg`
- `audio/mp3`
- `audio/ogg`
- `audio/m4a`
- `audio/aac`
- `audio/flac`
- Max size: 10 MB

**Request Example** (Multipart):
```
POST /api/v1/onboarding/site-audit/3fa85f64-5717-4562-b3fc-2c963f66afa6/observation/
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="photo"; filename="vault_door.jpg"
Content-Type: image/jpeg

[binary image data]
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="audio"; filename="observation.webm"
Content-Type: audio/webm

[binary audio data]
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="gps_latitude"

19.076
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="gps_longitude"

72.877
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="zone_hint"

Vault area
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="compass_direction"

270
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

**JSON Alternative** (text-only observation):
```json
{
    "text_input": "CCTV camera not working at main gate",
    "gps_latitude": 19.076,
    "gps_longitude": 72.877,
    "zone_hint": "gate"
}
```

**Response (201 Created)**:
```json
{
    "observation_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "enhanced": {
        "entities": [
            {"type": "asset", "name": "CCTV Camera", "status": "not_working"},
            {"type": "location", "name": "Main Gate"}
        ],
        "risks": [
            {"severity": "high", "description": "Surveillance gap at critical entry point"}
        ],
        "actions": [
            "Immediate repair of CCTV camera required",
            "Deploy temporary guard until camera operational"
        ]
    },
    "confidence": 0.89,
    "identified_zone": {
        "zone_id": "5hc07h86-7939-6784-d5he-4e185h88cha8",
        "zone_name": "Main Entrance Gate",
        "zone_type": "gate",
        "importance_level": "critical"
    },
    "next_questions": [
        "How many CCTV cameras are installed at this gate?",
        "Is there a backup camera covering this area?"
    ],
    "inconsistencies": []
}
```

**Response Schema**:
- `observation_id`: UUID string - unique ID for this observation
- `enhanced`: Object - AI-enhanced observation data
  - `entities`: Array - detected entities (assets, locations, people)
  - `risks`: Array - identified security risks
  - `actions`: Array - recommended actions
- `confidence`: Float (0.0 to 1.0) - AI confidence score
- `identified_zone`: Object or `null` - matched zone from GPS/hint
  - `zone_id`: UUID string
  - `zone_name`: String
  - `zone_type`: Enum (ZoneType)
  - `importance_level`: Enum (ImportanceLevel)
- `next_questions`: Array of strings - contextual follow-up questions
- `inconsistencies`: Array - any detected inconsistencies in data

**Error Responses**:
- `400 Bad Request`: Validation error (missing required fields, invalid GPS, unsupported format)
- `413 Payload Too Large`: File exceeds size limit
- `404 Not Found`: Invalid session_id

**Kotlin Example**:
```kotlin
suspend fun captureObservation(
    sessionId: String,
    photoFile: File? = null,
    audioFile: File? = null,
    textInput: String? = null,
    gpsLatitude: Double,
    gpsLongitude: Double,
    zoneHint: String? = null,
    compassDirection: Float? = null
): ObservationResponse {
    val requestBody = MultipartBody.Builder()
        .setType(MultipartBody.FORM)
        .apply {
            photoFile?.let {
                addFormDataPart(
                    "photo",
                    it.name,
                    it.asRequestBody("image/jpeg".toMediaTypeOrNull())
                )
            }
            audioFile?.let {
                addFormDataPart(
                    "audio",
                    it.name,
                    it.asRequestBody("audio/webm".toMediaTypeOrNull())
                )
            }
            textInput?.let { addFormDataPart("text_input", it) }
            addFormDataPart("gps_latitude", gpsLatitude.toString())
            addFormDataPart("gps_longitude", gpsLongitude.toString())
            zoneHint?.let { addFormDataPart("zone_hint", it) }
            compassDirection?.let { addFormDataPart("compass_direction", it.toString()) }
        }
        .build()

    val request = Request.Builder()
        .url("${baseUrl}/site-audit/${sessionId}/observation/")
        .header("Authorization", "Bearer $jwtToken")
        .post(requestBody)
        .build()

    // Execute request...
}

@Serializable
data class ObservationResponse(
    @SerialName("observation_id") val observationId: String,
    @SerialName("enhanced") val enhanced: EnhancedObservation,
    @SerialName("confidence") val confidence: Double,
    @SerialName("identified_zone") val identifiedZone: ZoneInfo?,
    @SerialName("next_questions") val nextQuestions: List<String>,
    @SerialName("inconsistencies") val inconsistencies: List<String>
)

@Serializable
data class EnhancedObservation(
    @SerialName("entities") val entities: List<JsonObject>,
    @SerialName("risks") val risks: List<JsonObject>,
    @SerialName("actions") val actions: List<String>
)
```

---

### List Observations

**Endpoint**: `GET /api/v1/onboarding/site-audit/{session_id}/observations/`

**Purpose**: Retrieve all observations for a site audit session

**Authentication**: Required

**Path Parameters**:
- `session_id`: UUID string

**Query Parameters** (all optional):
- `zone_id`: UUID string - filter by zone
- `severity`: Enum (ObservationSeverity) - filter by severity
- `has_photo`: Boolean - filter observations with photos

**Response (200 OK)**:
```json
{
    "count": 12,
    "observations": [
        {
            "observation_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "transcript_original": "सीसीटीवी कैमरा काम नहीं कर रहा है",
            "transcript_english": "CCTV camera is not working",
            "enhanced_observation": {
                "entities": [...],
                "risks": [...]
            },
            "entities": [...],
            "severity": "high",
            "confidence_score": 0.89,
            "gps_at_capture": "POINT (72.877 19.076)",
            "media_links": [
                "https://storage.example.com/photos/abc123.jpg"
            ],
            "zone_details": {
                "zone_id": "5hc07h86-7939-6784-d5he-4e185h88cha8",
                "zone_name": "Main Entrance Gate",
                "zone_type": "gate",
                "importance_level": "critical"
            },
            "captured_by": 42,
            "cdtz": "2025-09-28T12:34:56.789123Z"
        }
    ]
}
```

**⚠️ CRITICAL**: `gps_at_capture` Field Format

Backend returns PostGIS string: `"POINT (longitude latitude)"`

**Parse as**:
```kotlin
fun parsePointField(pointStr: String): GeoPoint? {
    val regex = """POINT \(([-\d.]+) ([-\d.]+)\)""".toRegex()
    val match = regex.matchEntire(pointStr) ?: return null
    val (lon, lat) = match.destructured
    return GeoPoint(
        longitude = lon.toDouble(),
        latitude = lat.toDouble()
    )
}
```

---

### Next Questions

**Endpoint**: `GET /api/v1/onboarding/site-audit/{session_id}/next-questions/`

**Purpose**: Get contextual questions for current audit progress

**Authentication**: Required

**Response (200 OK)**:
```json
{
    "current_zone": "Vault Area",
    "questions": [
        {
            "question": "Is the vault door biometric-enabled?",
            "field": "vault_access_control",
            "type": "boolean"
        },
        {
            "question": "How many CCTV cameras cover the vault entrance?",
            "field": "vault_camera_count",
            "type": "integer"
        }
    ],
    "completion_percentage": 45.5,
    "critical_gaps": [
        "Parking area not yet audited",
        "Emergency exit verification pending"
    ]
}
```

---

### Coverage Map

**Endpoint**: `GET /api/v1/onboarding/site-audit/{session_id}/coverage/`

**Purpose**: Get visual coverage map and remaining gaps

**Authentication**: Required

**Response (200 OK)**:
```json
{
    "coverage_map": {
        "total_zones": 8,
        "visited": 5,
        "percentage": 62.5
    },
    "zones": [
        {
            "zone_id": "uuid",
            "zone_name": "Main Gate",
            "zone_type": "gate",
            "importance_level": "critical",
            "visited": true,
            "observations_count": 3,
            "photos_count": 2,
            "status": "complete"
        }
    ],
    "critical_gaps": [
        {
            "zone_id": "uuid",
            "zone_name": "Vault Area",
            "zone_type": "vault",
            "importance_level": "critical",
            "reason": "No observations captured"
        }
    ]
}
```

---

### Text-to-Speech (TTS)

**Endpoint**: `POST /api/v1/onboarding/site-audit/{session_id}/speak/`

**Purpose**: Convert text to audio for audible guidance

**Authentication**: Required

**Request Body**:
```json
{
    "text": "Please proceed to the Vault area for your next observation.",
    "language": "en"
}
```

**Response (200 OK)**:
```json
{
    "audio_url": "https://storage.example.com/tts/abc123.mp3",
    "audio_base64": "data:audio/mp3;base64,//uQx...",
    "duration_seconds": 4.2
}
```

---

### Zone Management

**Endpoint**: `POST /api/v1/onboarding/site/{site_id}/zones/`

**Purpose**: Bulk create or update zones for a site

**Authentication**: Required

**Path Parameters**:
- `site_id`: UUID string (from audit start response)

**Request Body**:
```json
{
    "zones": [
        {
            "zone_type": "gate",
            "zone_name": "Main Entrance Gate",
            "importance_level": "critical",
            "risk_level": "high",
            "gps_coordinates": {
                "latitude": 19.076,
                "longitude": 72.877
            },
            "coverage_required": true,
            "compliance_notes": "RBI Master Direction 2021 - Entry/Exit monitoring"
        },
        {
            "zone_type": "atm",
            "zone_name": "ATM Lobby",
            "importance_level": "high",
            "risk_level": "high",
            "coverage_required": true
        }
    ]
}
```

**Required Fields** per zone:
- `zone_type`: Enum (ZoneType)
- `zone_name`: String
- `importance_level`: Enum (ImportanceLevel)

**Optional Fields**:
- `risk_level`: Enum (RiskLevel), default `"moderate"`
- `gps_coordinates`: Object `{latitude, longitude}`
- `coverage_required`: Boolean, default `true`
- `compliance_notes`: String

**Response (201 Created)**:
```json
{
    "zones_created": 2,
    "zones": [
        {
            "zone_id": "uuid",
            "zone_type": "gate",
            "zone_name": "Main Entrance Gate",
            "importance_level": "critical",
            "risk_level": "high",
            ...
        }
    ]
}
```

---

### Asset Management

**Endpoint**: `POST /api/v1/onboarding/site/{site_id}/assets/`

**Purpose**: Bulk create assets for zones

**Authentication**: Required

**Request Body**:
```json
{
    "assets": [
        {
            "zone_id": "5hc07h86-7939-6784-d5he-4e185h88cha8",
            "asset_type": "camera",
            "asset_name": "Main Gate CCTV #1",
            "status": "operational",
            "specifications": {
                "model": "Hikvision DS-2CD2T85G1",
                "resolution": "8MP",
                "coverage_angle": 110
            },
            "serial_number": "HK123456",
            "installation_date": "2024-01-15",
            "warranty_expiry": "2027-01-15",
            "compliance_tags": ["RBI_Compliant", "Night_Vision"]
        }
    ]
}
```

**Required Fields** per asset:
- `zone_id`: UUID string
- `asset_type`: Enum (AssetType)
- `asset_name`: String
- `status`: Enum (AssetStatus)

**Response (201 Created)**:
```json
{
    "assets_created": 1,
    "assets": [...]
}
```

---

### Meter Point Management

**Endpoint**: `POST /api/v1/onboarding/site/{site_id}/meter-points/`

**Purpose**: Define meter reading points requiring OCR

**Authentication**: Required

**Request Body**:
```json
{
    "meter_points": [
        {
            "zone_id": "uuid",
            "meter_type": "electricity",
            "meter_name": "Main Electrical Panel",
            "reading_frequency": "daily",
            "reading_template": {
                "unit": "kWh",
                "range": [0, 999999],
                "validation_rules": ["numeric", "increasing"]
            },
            "requires_photo_ocr": true,
            "sop_instructions": "Read meter at 9 AM daily. Record reading in logbook."
        }
    ]
}
```

**Required Fields** per meter:
- `zone_id`: UUID string
- `meter_type`: Enum (MeterType)
- `meter_name`: String
- `reading_frequency`: String (e.g., "daily", "weekly", "monthly")

**Response (201 Created)**:
```json
{
    "meter_points_created": 1,
    "meter_points": [...]
}
```

---

### Analyze Site Audit

**Endpoint**: `POST /api/v1/onboarding/site-audit/{session_id}/analyze/`

**Purpose**: Trigger AI analysis of all observations with dual-LLM consensus

**Authentication**: Required

**Request Body**:
```json
{
    "force_reanalysis": false,
    "include_recommendations": true,
    "include_sops": true,
    "include_coverage_plan": true,
    "target_languages": ["hi", "mr"]
}
```

**Request Schema**:
- `force_reanalysis`: Boolean, default `false`
- `include_recommendations`: Boolean, default `true`
- `include_sops`: Boolean, default `true`
- `include_coverage_plan`: Boolean, default `true`
- `target_languages`: Array of ISO 639-1 codes, optional

**Response (200 OK - Sync)**:
```json
{
    "analysis_id": "uuid",
    "maker_output": {
        "summary": "...",
        "risks_identified": [...],
        "recommendations": [...]
    },
    "checker_output": {
        "validation_status": "approved",
        "corrections": [],
        "additional_insights": [...]
    },
    "consensus": {
        "final_recommendations": [...],
        "risk_score": 7.2,
        "compliance_score": 85
    },
    "citations": [
        {
            "knowledge_id": "uuid",
            "document_title": "RBI Master Direction 2021",
            "section": "Physical Security Requirements"
        }
    ],
    "processing_time_ms": 3500,
    "trace_id": "distributed-trace-id",
    "sops_generated": 8,
    "coverage_plan_generated": true
}
```

**Response (202 Accepted - Async)**:
```json
{
    "status": "processing",
    "status_url": "/api/v1/onboarding/site-audit/{session_id}/status/",
    "task_id": "uuid",
    "estimated_completion_seconds": 30
}
```

---

### Get Coverage Plan

**Endpoint**: `GET /api/v1/onboarding/site-audit/{session_id}/coverage-plan/`

**Purpose**: Retrieve generated guard coverage and shift plan

**Authentication**: Required

**Response (200 OK)**:
```json
{
    "plan_id": "uuid",
    "guard_posts": [
        {
            "post_id": "P001",
            "zone": "Main Entrance Gate",
            "position": "Inside guard booth",
            "duties": ["Monitor entry/exit", "Check visitor IDs"],
            "risk_level": "high"
        }
    ],
    "shift_assignments": [
        {
            "shift_name": "Morning Shift",
            "start_time": "06:00",
            "end_time": "14:00",
            "posts_covered": ["P001", "P002", "P003"],
            "staffing": {
                "guards_required": 3,
                "supervisor_required": true
            }
        }
    ],
    "patrol_routes": [
        {
            "route_id": "R001",
            "zones": ["Perimeter", "Parking", "Loading Dock"],
            "frequency": "Every 2 hours",
            "checkpoints": ["CP001", "CP002", "CP003"]
        }
    ],
    "risk_windows": [
        {
            "start": "22:00",
            "end": "06:00",
            "zones": ["All zones"],
            "mitigation": "Increased patrol frequency, additional lighting"
        }
    ],
    "compliance_notes": "Plan complies with RBI Master Direction 2021 for bank branch security.",
    "generated_by": "ai",
    "approved_by": null,
    "approved_at": null,
    "total_posts": 5,
    "total_shifts": 3,
    "cdtz": "2025-09-28T15:30:00.000000Z"
}
```

---

### Get SOPs

**Endpoint**: `GET /api/v1/onboarding/site-audit/{session_id}/sops/`

**Purpose**: Retrieve generated Standard Operating Procedures

**Authentication**: Required

**Response (200 OK)**:
```json
[
    {
        "sop_id": "uuid",
        "sop_title": "CCTV Monitoring and Recording Procedure",
        "purpose": "Ensure continuous surveillance and evidence recording for security incidents",
        "steps": [
            {
                "step_number": 1,
                "description": "Check all CCTV monitors for clear visibility",
                "responsible_role": "Security Supervisor"
            },
            {
                "step_number": 2,
                "description": "Verify recording status on DVR",
                "responsible_role": "Security Guard"
            }
        ],
        "staffing_required": {
            "roles": ["Security Supervisor", "Security Guard"],
            "count": 2,
            "schedule": "24/7"
        },
        "compliance_references": [
            "RBI Master Direction 2021 - Section 4.2.1",
            "ASIS Physical Security Standard"
        ],
        "frequency": "hourly",
        "translated_texts": {
            "hi": {
                "title": "सीसीटीवी निगरानी और रिकॉर्डिंग प्रक्रिया",
                "purpose": "...",
                "steps": [...]
            }
        },
        "escalation_triggers": [
            "CCTV failure detected",
            "Recording stopped",
            "Monitor display issues"
        ],
        "zone_details": {
            "zone_id": "uuid",
            "zone_name": "Control Room",
            "zone_type": "control_room"
        },
        "asset_details": null,
        "llm_generated": true,
        "reviewed_by": null,
        "approved_at": null,
        "cdtz": "2025-09-28T15:30:00.000000Z"
    }
]
```

---

### Generate Report

**Endpoint**: `GET /api/v1/onboarding/site-audit/{session_id}/report/`

**Purpose**: Generate comprehensive audit report

**Authentication**: Required

**Query Parameters** (all optional):
- `lang`: String (ISO 639-1), default `"en"`
- `save_to_kb`: Boolean, default `true`
- `format`: Enum `"html"`, `"pdf"`, `"json"`, default `"html"`
- `include_photos`: Boolean, default `true`
- `include_sops`: Boolean, default `true`
- `include_coverage_plan`: Boolean, default `true`

**Response (200 OK)**:
```json
{
    "report_html": "<html>...</html>",
    "report_url": "https://storage.example.com/reports/uuid.html",
    "knowledge_id": "uuid-of-kb-document",
    "summary": {
        "total_zones": 8,
        "observations": 24,
        "compliance_score": 87,
        "critical_issues": 2,
        "recommendations": 15
    },
    "generated_at": "2025-09-28T15:45:00.000000Z"
}
```

---

## Validation Rules

### Time Format

Operating hours must use 24-hour format:
- Pattern: `HH:MM`
- Valid: `"09:00"`, `"18:30"`, `"23:59"`
- Invalid: `"9:00"` (missing leading zero), `"6:30 PM"` (not 24-hour)

**Kotlin Validation**:
```kotlin
fun validateTimeFormat(time: String): Boolean {
    val pattern = Regex("""^([0-1][0-9]|2[0-3]):[0-5][0-9]$""")
    return pattern.matches(time)
}
```

### GPS Coordinates

**Latitude**: -90.0 to 90.0
**Longitude**: -180.0 to 180.0

**Kotlin Validation**:
```kotlin
fun validateGpsCoordinates(lat: Double, lon: Double): Boolean {
    return lat in -90.0..90.0 && lon in -180.0..180.0
}
```

### File Upload Validation

**Photo Files**:
- MIME types: `image/jpeg`, `image/png`, `image/webp`
- Max size: 5 MB (5,242,880 bytes)

**Audio Files**:
- MIME types: `audio/webm`, `audio/wav`, `audio/mpeg`, `audio/mp3`, `audio/ogg`, `audio/m4a`, `audio/aac`, `audio/flac`
- Max size: 10 MB (10,485,760 bytes)

**Kotlin Validation**:
```kotlin
fun validateImageFile(file: File, mimeType: String): ValidationResult {
    val allowedTypes = listOf("image/jpeg", "image/png", "image/webp")
    val maxSize = 5 * 1024 * 1024 // 5 MB

    return when {
        mimeType !in allowedTypes -> ValidationResult.Error("Invalid image type. Allowed: JPEG, PNG, WebP")
        file.length() > maxSize -> ValidationResult.Error("Image too large. Maximum size: 5MB")
        else -> ValidationResult.Success
    }
}

fun validateAudioFile(file: File, mimeType: String): ValidationResult {
    val allowedTypes = listOf(
        "audio/webm", "audio/wav", "audio/mpeg", "audio/mp3",
        "audio/ogg", "audio/m4a", "audio/aac", "audio/flac"
    )
    val maxSize = 10 * 1024 * 1024 // 10 MB

    return when {
        mimeType !in allowedTypes -> ValidationResult.Error("Invalid audio type")
        file.length() > maxSize -> ValidationResult.Error("Audio file too large. Maximum size: 10MB")
        else -> ValidationResult.Success
    }
}
```

### Zone Creation Validation

**Required Fields**:
- `zone_type`: Must be valid ZoneType enum value
- `zone_name`: String, non-empty
- `importance_level`: Must be valid ImportanceLevel enum value

### Asset Creation Validation

**Required Fields**:
- `zone_id`: Must be valid UUID of existing zone
- `asset_type`: Must be valid AssetType enum value
- `asset_name`: String, non-empty
- `status`: Must be valid AssetStatus enum value

### Meter Point Creation Validation

**Required Fields**:
- `zone_id`: Must be valid UUID of existing zone
- `meter_type`: Must be valid MeterType enum value
- `meter_name`: String, non-empty
- `reading_frequency`: String (e.g., "daily", "weekly", "monthly")

### Observation Capture Validation

**At least ONE of** the following must be provided:
- `photo`: Valid image file
- `audio`: Valid audio file
- `text_input`: String (max 2000 chars)

**Always Required**:
- `gps_latitude`: Float (-90 to 90)
- `gps_longitude`: Float (-180 to 180)

---

## GraphQL Usage

### Endpoints

- **Primary**: `/api/graphql/` (with file upload support)
- **Alternative**: `/graphql` (same functionality)

### Authentication

Same as REST: `Authorization: Bearer <jwt_token>`

### CSRF Protection (CRITICAL)

**⚠️ GraphQL mutations require CSRF protection**

Backend uses `GraphQLCSRFProtectionMiddleware` to enforce CSRF tokens for all mutations.

**How to Handle CSRF**:

**Option 1: Use JWT-Only Mode** (Recommended for mobile)
```kotlin
// Add custom header to bypass CSRF for JWT-authenticated requests
val request = Request.Builder()
    .url("${baseUrl}/api/graphql/")
    .header("Authorization", "Bearer $jwtToken")
    .header("X-CSRFToken", "not-required-for-jwt")  // Backend checks JWT first
    .post(graphqlRequestBody)
    .build()
```

**Option 2: Obtain CSRF Token**
```kotlin
// 1. GET request to session endpoint to receive Set-Cookie with csrftoken
val sessionRequest = Request.Builder()
    .url("${baseUrl}/api/v1/auth/session/")
    .header("Authorization", "Bearer $jwtToken")
    .get()
    .build()

// 2. Extract csrftoken from response cookies
val csrfToken = extractCsrfTokenFromCookies(response)

// 3. Include in GraphQL requests
val graphqlRequest = Request.Builder()
    .url("${baseUrl}/api/graphql/")
    .header("Authorization", "Bearer $jwtToken")
    .header("X-CSRFToken", csrfToken)
    .header("Cookie", "csrftoken=$csrfToken")
    .post(graphqlRequestBody)
    .build()
```

**Queries (read-only) do NOT require CSRF**, only mutations.

### Schema

Root schema aggregator: `apps/service/schema.py`

Primary domains:
- Tickets (Help Desk)
- People (User management)
- Assets (Inventory, maintenance)
- Work Orders
- Attendance

### File Upload

GraphQL file uploads use `FileUploadGraphQLView` from `graphene-file-upload`.

**Mutation Example**:
```graphql
mutation UploadFile($file: Upload!) {
    secureUploadFile(file: $file) {
        success
        fileId
        fileUrl
    }
}
```

**Multipart Request**:
```
POST /api/graphql/
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="operations"

{"query": "mutation($file: Upload!) { secureUploadFile(file: $file) { success fileId } }", "variables": {"file": null}}
------WebKitFormBoundary
Content-Disposition: form-data; name="map"

{"0": ["variables.file"]}
------WebKitFormBoundary
Content-Disposition: form-data; name="0"; filename="document.pdf"
Content-Type: application/pdf

[binary file data]
------WebKitFormBoundary--
```

### When to Use GraphQL

**Prefer GraphQL for**:
- Cross-domain read queries (e.g., fetch user + their tickets + assets in one request)
- Real-time subscriptions (if implemented)
- Complex nested data fetching

**Prefer REST for**:
- Conversational onboarding (primary API)
- Site audit operations (multimodal captures)
- File uploads (REST is simpler for multipart)
- When you need specific HTTP status codes

---

## Error Handling & Status Codes

### HTTP Status Codes

**Success Codes**:
- `200 OK`: Successful read or update operation
- `201 Created`: Resource created successfully (e.g., observation, zone, asset)
- `202 Accepted`: Long-running task enqueued, check status URL
- `204 No Content`: Successful delete operation

**Client Error Codes**:
- `400 Bad Request`: Validation error, malformed request
- `401 Unauthorized`: Missing or invalid JWT token
- `403 Forbidden`: User lacks permission for this operation
- `404 Not Found`: Resource not found (invalid ID)
- `409 Conflict`: Resource conflict (e.g., active session already exists)
- `412 Precondition Failed`: Preflight validation failed (critical issues)
- `413 Payload Too Large`: File exceeds size limit
- `422 Unprocessable Entity`: Semantic validation error
- `429 Too Many Requests`: Rate limit exceeded

**Server Error Codes**:
- `500 Internal Server Error`: Unexpected server error
- `502 Bad Gateway`: Upstream service failure
- `503 Service Unavailable`: Service temporarily unavailable (maintenance mode)
- `504 Gateway Timeout`: Request timeout

### Error Response Formats

**Field-Level Validation Errors** (400):
```json
{
    "field_name": [
        "This field is required.",
        "Must be a valid UUID."
    ],
    "another_field": [
        "Invalid choice."
    ]
}
```

**Non-Field Validation Errors** (400):
```json
{
    "errors": [
        "At least one input required: photo, audio, or text_input"
    ]
}
```

**Generic Error** (400/403/404/500):
```json
{
    "error": "Conversation session not found"
}
```

**Detailed Error with Context** (500):
```json
{
    "error": "Failed to process voice input",
    "detail": "Speech recognition service unavailable",
    "support_reference": "ERR-20250928-123456",
    "retry_after": 30
}
```

**Rate Limit Error** (429):
```json
{
    "error": "Rate limit exceeded",
    "detail": "You have exceeded the 600 requests per hour limit",
    "retry_after": 300
}
```

**Headers**: `Retry-After: 300` (seconds)

### Kotlin Error Handling

```kotlin
sealed class ApiError {
    data class ValidationError(val fieldErrors: Map<String, List<String>>) : ApiError()
    data class NonFieldError(val errors: List<String>) : ApiError()
    data class GenericError(val message: String, val detail: String? = null) : ApiError()
    data class RateLimitError(val retryAfter: Int) : ApiError()
    data class NetworkError(val exception: Exception) : ApiError()
}

suspend fun <T> handleApiCall(call: suspend () -> Response<T>): Result<T> {
    return try {
        val response = call()
        when {
            response.isSuccessful -> {
                Result.success(response.body()!!)
            }
            response.code() == 429 -> {
                val retryAfter = response.headers()["Retry-After"]?.toIntOrNull() ?: 60
                Result.failure(ApiError.RateLimitError(retryAfter))
            }
            response.code() in 400..499 -> {
                val errorBody = response.errorBody()?.string()
                val error = parseError(errorBody)
                Result.failure(error)
            }
            else -> {
                Result.failure(ApiError.GenericError("Server error: ${response.code()}"))
            }
        }
    } catch (e: Exception) {
        Result.failure(ApiError.NetworkError(e))
    }
}

fun parseError(errorBody: String?): ApiError {
    if (errorBody == null) return ApiError.GenericError("Unknown error")

    val json = Json.parseToJsonElement(errorBody).jsonObject

    return when {
        json.containsKey("errors") -> {
            // Non-field errors
            val errors = json["errors"]?.jsonArray?.map { it.jsonPrimitive.content } ?: emptyList()
            ApiError.NonFieldError(errors)
        }
        json.containsKey("error") -> {
            // Generic error
            val message = json["error"]?.jsonPrimitive?.content ?: "Unknown error"
            val detail = json["detail"]?.jsonPrimitive?.content
            ApiError.GenericError(message, detail)
        }
        else -> {
            // Field-level validation errors
            val fieldErrors = json.mapValues { (_, value) ->
                value.jsonArray.map { it.jsonPrimitive.content }
            }
            ApiError.ValidationError(fieldErrors)
        }
    }
}
```

---

## Client Sync & Offline Strategy

### Offline-First Architecture

The mobile app is designed for **offline-first** operation, especially for site audit observations.

### Observation Capture (Offline Queue)

**Strategy**:
1. Capture observations locally with client-side UUID
2. Store in local database with `sync_status = "pending"`
3. Queue for upload when connectivity restored
4. POST to `/site-audit/{session_id}/observation/` when online
5. Update local record with server `observation_id`
6. Mark as `sync_status = "synced"`

**Kotlin Example**:
```kotlin
data class LocalObservation(
    val clientId: String = UUID.randomUUID().toString(),
    val sessionId: String,
    val photoPath: String?,
    val audioPath: String?,
    val textInput: String?,
    val gpsLatitude: Double,
    val gpsLongitude: Double,
    val timestamp: Instant,
    val syncStatus: SyncStatus,
    val serverId: String? = null // Set after successful sync
)

enum class SyncStatus {
    PENDING,
    SYNCING,
    SYNCED,
    FAILED
}

class ObservationSyncManager {
    suspend fun syncPendingObservations() {
        val pendingObservations = database.getObservationsByStatus(SyncStatus.PENDING)

        for (observation in pendingObservations) {
            try {
                database.updateStatus(observation.clientId, SyncStatus.SYNCING)

                val response = apiService.captureObservation(
                    sessionId = observation.sessionId,
                    photoFile = observation.photoPath?.let { File(it) },
                    audioFile = observation.audioPath?.let { File(it) },
                    textInput = observation.textInput,
                    gpsLatitude = observation.gpsLatitude,
                    gpsLongitude = observation.gpsLongitude
                )

                // Update local record with server ID
                database.updateObservation(
                    clientId = observation.clientId,
                    serverId = response.observationId,
                    syncStatus = SyncStatus.SYNCED
                )

            } catch (e: Exception) {
                database.updateStatus(observation.clientId, SyncStatus.FAILED)
                logger.error("Sync failed for ${observation.clientId}: ${e.message}")
            }
        }
    }
}
```

### Idempotency Handling

**Idempotent Endpoints** (safe to retry):
- `POST /conversation/start/` - Server deduplicates using advisory locks
- `POST /conversation/{id}/process/` - Server deduplicates based on input hash

**Implementation**:
Backend uses `@with_idempotency` decorator to detect and deduplicate retried requests.

**Client Behavior**:
- DO retry these endpoints on network failure (with exponential backoff)
- DO NOT manually implement idempotency keys (server handles it)
- DO include same exact request body for deduplication to work

**Non-Idempotent Endpoints** (DO NOT retry on success):
- `POST /site-audit/{id}/observation/` - Each observation is unique
- `POST /recommendations/approve/` - Each approval is unique
- All other POST/PUT/DELETE operations

### Async Task Polling

When backend returns `202 Accepted` with `status_url`:

**Polling Strategy**:
```kotlin
suspend fun pollTaskStatus(statusUrl: String, maxRetries: Int = 30): TaskResult {
    var retryCount = 0
    var delaySeconds = 2

    while (retryCount < maxRetries) {
        val response = apiService.getStatus(statusUrl)

        when (response.status) {
            "completed" -> return TaskResult.Success(response.result)
            "failed" -> return TaskResult.Failure(response.error)
            "processing" -> {
                // Exponential backoff: 2, 4, 8, 16, 30, 30, ...
                delay(delaySeconds * 1000L)
                delaySeconds = min(delaySeconds * 2, 30)
                retryCount++
            }
        }
    }

    return TaskResult.Timeout
}
```

**Best Practices**:
- Initial poll: 2 seconds after 202 response
- Exponential backoff: 2s → 4s → 8s → 16s → 30s (max)
- Max polling duration: 5 minutes
- Show progress indicator to user
- Allow user to cancel polling

### Report Generation

**Strategy**:
- Reports are generated on-demand via GET request
- For large reports, backend may return 202 Accepted
- Poll `status_url` until `report_url` is available
- Cache report URL for offline viewing

---

## Networking & Transport

### Retrofit Configuration (Recommended)

```kotlin
object ApiClient {
    private const val BASE_URL = "https://api.youtility.in"

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(AuthInterceptor())
        .addInterceptor(LoggingInterceptor())
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)  // Longer for voice/photo uploads
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        encodeDefaults = true
    }

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    val onboardingService: OnboardingApiService = retrofit.create()
}

class AuthInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()

        val token = TokenManager.getAccessToken()
            ?: return chain.proceed(originalRequest)

        val authenticatedRequest = originalRequest.newBuilder()
            .header("Authorization", "Bearer $token")
            .header("Accept", "application/json")
            .build()

        val response = chain.proceed(authenticatedRequest)

        // Handle 401 Unauthorized - refresh token
        if (response.code == 401) {
            response.close()
            return handleTokenRefresh(chain, originalRequest)
        }

        return response
    }

    private fun handleTokenRefresh(chain: Interceptor.Chain, request: Request): Response {
        synchronized(this) {
            // Refresh token
            val newToken = TokenManager.refreshAccessToken()

            // Retry original request with new token
            val newRequest = request.newBuilder()
                .header("Authorization", "Bearer $newToken")
                .build()

            return chain.proceed(newRequest)
        }
    }
}
```

### JSON Serialization

**Kotlinx Serialization** (Recommended):

```kotlin
val json = Json {
    ignoreUnknownKeys = true        // Ignore extra fields from backend
    coerceInputValues = true         // Coerce invalid values to defaults
    encodeDefaults = true            // Encode default values
    isLenient = true                 // Accept lenient JSON (e.g., unquoted keys)
    prettyPrint = false              // Compact JSON for network efficiency
}
```

**Custom Serializers**:

```kotlin
// Custom serializer for RFC3339 datetime with microseconds
object InstantSerializer : KSerializer<Instant> {
    override val descriptor = PrimitiveSerialDescriptor("Instant", PrimitiveKind.STRING)

    override fun serialize(encoder: Encoder, value: Instant) {
        // Format: 2025-09-28T12:34:56.789123Z
        val formatted = value.toString()  // ISO-8601 UTC
        encoder.encodeString(formatted)
    }

    override fun deserialize(decoder: Decoder): Instant {
        val str = decoder.decodeString()
        return Instant.parse(str)  // Supports %Y-%m-%dT%H:%M:%S.%fZ
    }
}

// Usage in data classes
@Serializable
data class ConversationSession(
    @SerialName("session_id") val sessionId: String,
    @Serializable(with = InstantSerializer::class)
    @SerialName("cdtz") val createdAt: Instant
)
```

### File Upload with Progress

```kotlin
class ProgressRequestBody(
    private val file: File,
    private val contentType: MediaType?,
    private val onProgress: (bytesWritten: Long, totalBytes: Long) -> Unit
) : RequestBody() {

    override fun contentType() = contentType

    override fun contentLength() = file.length()

    override fun writeTo(sink: BufferedSink) {
        val fileLength = file.length()
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        val inputStream = file.inputStream()
        var uploaded = 0L

        inputStream.use { input ->
            var read: Int
            while (input.read(buffer).also { read = it } != -1) {
                uploaded += read
                sink.write(buffer, 0, read)
                onProgress(uploaded, fileLength)
            }
        }
    }

    companion object {
        private const val DEFAULT_BUFFER_SIZE = 8192
    }
}

// Usage
suspend fun uploadObservationWithProgress(
    sessionId: String,
    photoFile: File,
    onProgress: (Float) -> Unit
) {
    val progressRequestBody = ProgressRequestBody(
        file = photoFile,
        contentType = "image/jpeg".toMediaTypeOrNull()
    ) { bytesWritten, totalBytes ->
        val progress = (bytesWritten.toFloat() / totalBytes.toFloat())
        onProgress(progress)
    }

    val multipartBody = MultipartBody.Builder()
        .setType(MultipartBody.FORM)
        .addFormDataPart("photo", photoFile.name, progressRequestBody)
        .addFormDataPart("gps_latitude", "19.076")
        .addFormDataPart("gps_longitude", "72.877")
        .build()

    // Execute request...
}
```

### Rate Limit Handling

```kotlin
class RateLimitInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())

        if (response.code == 429) {
            val retryAfter = response.header("Retry-After")?.toIntOrNull() ?: 60

            // Notify UI to show rate limit error
            RateLimitEvent.emit(retryAfter)

            // Optionally: Auto-retry after delay (be careful with this)
            // Thread.sleep(retryAfter * 1000L)
            // return chain.proceed(chain.request())
        }

        return response
    }
}
```

---

## Data Classes & Kotlin Mappings

### Complete Data Class Examples

**Conversation Start**:
```kotlin
@Serializable
data class ConversationStartRequest(
    @SerialName("language") val language: String = "en",
    @SerialName("user_type") val userType: String? = null,
    @SerialName("client_context") val clientContext: JsonObject = JsonObject(emptyMap()),
    @SerialName("initial_input") val initialInput: String? = null,
    @SerialName("resume_existing") val resumeExisting: Boolean = false
)

@Serializable
data class ConversationStartResponse(
    @SerialName("conversation_id") val conversationId: String,
    @SerialName("enhanced_understanding") val enhancedUnderstanding: JsonObject,
    @SerialName("questions") val questions: List<JsonObject>,
    @SerialName("context") val context: JsonObject
)
```

**Site Audit Start**:
```kotlin
@Serializable
data class SiteAuditStartRequest(
    @SerialName("business_unit_id") val businessUnitId: String,
    @SerialName("site_type") val siteType: SiteType,
    @SerialName("language") val language: String = "en",
    @SerialName("operating_hours") val operatingHours: OperatingHours? = null,
    @SerialName("gps_location") val gpsLocation: GpsLocation? = null
)

@Serializable
data class OperatingHours(
    @SerialName("start") val start: String, // "HH:MM"
    @SerialName("end") val end: String      // "HH:MM"
) {
    init {
        require(start.matches(Regex("""^([0-1][0-9]|2[0-3]):[0-5][0-9]$"""))) {
            "Invalid start time format. Use HH:MM"
        }
        require(end.matches(Regex("""^([0-1][0-9]|2[0-3]):[0-5][0-9]$"""))) {
            "Invalid end time format. Use HH:MM"
        }
    }
}

@Serializable
data class GpsLocation(
    @SerialName("latitude") val latitude: Double,
    @SerialName("longitude") val longitude: Double
) {
    init {
        require(latitude in -90.0..90.0) { "Latitude must be between -90 and 90" }
        require(longitude in -180.0..180.0) { "Longitude must be between -180 and 180" }
    }
}
```

**Observation Capture** (Multipart):
```kotlin
suspend fun captureObservation(
    sessionId: String,
    photoFile: File? = null,
    audioFile: File? = null,
    textInput: String? = null,
    gpsLatitude: Double,
    gpsLongitude: Double,
    zoneHint: String? = null,
    compassDirection: Float? = null
): ObservationResponse {
    require(photoFile != null || audioFile != null || textInput != null) {
        "At least one input required: photo, audio, or text_input"
    }
    require(gpsLatitude in -90.0..90.0) { "Invalid latitude" }
    require(gpsLongitude in -180.0..180.0) { "Invalid longitude" }

    val requestBody = MultipartBody.Builder()
        .setType(MultipartBody.FORM)
        .apply {
            photoFile?.let {
                addFormDataPart("photo", it.name, it.asRequestBody("image/jpeg".toMediaTypeOrNull()))
            }
            audioFile?.let {
                addFormDataPart("audio", it.name, it.asRequestBody("audio/webm".toMediaTypeOrNull()))
            }
            textInput?.let { addFormDataPart("text_input", it) }
            addFormDataPart("gps_latitude", gpsLatitude.toString())
            addFormDataPart("gps_longitude", gpsLongitude.toString())
            zoneHint?.let { addFormDataPart("zone_hint", it) }
            compassDirection?.let { addFormDataPart("compass_direction", it.toString()) }
        }
        .build()

    val request = Request.Builder()
        .url("${ApiClient.BASE_URL}/api/v1/onboarding/site-audit/$sessionId/observation/")
        .header("Authorization", "Bearer ${TokenManager.getAccessToken()}")
        .post(requestBody)
        .build()

    val response = okHttpClient.newCall(request).execute()

    if (!response.isSuccessful) {
        throw ApiException(response.code, response.message)
    }

    val responseBody = response.body?.string() ?: throw ApiException(500, "Empty response")
    return json.decodeFromString<ObservationResponse>(responseBody)
}

@Serializable
data class ObservationResponse(
    @SerialName("observation_id") val observationId: String,
    @SerialName("enhanced") val enhanced: EnhancedObservation,
    @SerialName("confidence") val confidence: Double,
    @SerialName("identified_zone") val identifiedZone: ZoneInfo?,
    @SerialName("next_questions") val nextQuestions: List<String>,
    @SerialName("inconsistencies") val inconsistencies: List<String>
)

@Serializable
data class EnhancedObservation(
    @SerialName("entities") val entities: List<JsonObject>,
    @SerialName("risks") val risks: List<JsonObject>,
    @SerialName("actions") val actions: List<String>
)

@Serializable
data class ZoneInfo(
    @SerialName("zone_id") val zoneId: String,
    @SerialName("zone_name") val zoneName: String,
    @SerialName("zone_type") val zoneType: ZoneType,
    @SerialName("importance_level") val importanceLevel: ImportanceLevel
)
```

**PostGIS Point Parsing**:
```kotlin
@Serializable
data class GeoPoint(
    val longitude: Double,
    val latitude: Double
) {
    companion object {
        fun fromPostGISString(pointStr: String): GeoPoint? {
            // Parse "POINT (72.877 19.076)"
            val regex = """POINT \(([-\d.]+) ([-\d.]+)\)""".toRegex()
            val match = regex.matchEntire(pointStr) ?: return null
            val (lon, lat) = match.destructured
            return GeoPoint(
                longitude = lon.toDouble(),
                latitude = lat.toDouble()
            )
        }
    }

    fun toLatLng(): LatLng {
        // Convert to Google Maps LatLng (lat, lon order)
        return LatLng(latitude, longitude)
    }

    override fun toString(): String {
        return "POINT ($longitude $latitude)"
    }
}

// Usage
@Serializable
data class ObservationItem(
    @SerialName("observation_id") val observationId: String,
    @SerialName("gps_at_capture") val gpsAtCapture: String,  // "POINT (lon lat)"
    // ... other fields
) {
    fun getParsedLocation(): GeoPoint? {
        return GeoPoint.fromPostGISString(gpsAtCapture)
    }
}
```

---

## Security & Tenant Scoping

### Authentication

All protected endpoints require JWT token:
```
Authorization: Bearer <access_token>
```

**Token Lifecycle**:
- Access token: 1 hour validity
- Refresh token: 7 days validity
- Rotate refresh tokens on use (blacklist old tokens)

### Tenant Scoping

Backend enforces tenant scoping automatically based on user association:
- User → Business Unit (Client) relationship
- All conversational onboarding operations scoped to user's client
- All site audit operations scoped to specified business unit

**Client Behavior**:
- DO NOT attempt to pass tenant identifiers manually
- Backend derives tenant from JWT user association
- Cross-tenant access is automatically blocked

### Two-Person Approval Workflow

For high-risk operations, backend may require two-person approval:

**Workflow**:
1. First person: `POST /recommendations/approve/` with `dry_run=false`
2. Backend response: `{"two_person_approval_required": true, "approval_id": 123}`
3. Second person: `POST /approvals/123/decide/` with `{"decision": "approved"}`

**Permissions**:
- First approver: Requires `CanApproveAIRecommendations` permission
- Second approver: Must be different user with same permission

### CSRF Protection (GraphQL)

GraphQL mutations require CSRF protection:

**Option 1: JWT Bypass** (Recommended for mobile):
```kotlin
// Backend checks JWT first, no CSRF needed
val request = Request.Builder()
    .url("${baseUrl}/api/graphql/")
    .header("Authorization", "Bearer $jwtToken")
    .post(graphqlRequestBody)
    .build()
```

**Option 2: CSRF Token**:
```kotlin
// 1. Obtain CSRF token from session endpoint
val csrfToken = getCsrfToken()

// 2. Include in GraphQL mutation requests
val request = Request.Builder()
    .url("${baseUrl}/api/graphql/")
    .header("Authorization", "Bearer $jwtToken")
    .header("X-CSRFToken", csrfToken)
    .header("Cookie", "csrftoken=$csrfToken")
    .post(graphqlRequestBody)
    .build()
```

### Secure Data Handling

**Do NOT log**:
- JWT tokens
- User passwords
- PII (Personally Identifiable Information)
- Voice transcripts (may contain sensitive info)

**Do log**:
- Request IDs for debugging
- Error messages (sanitized)
- Performance metrics

---

## Performance Guidelines

### Debouncing & Throttling

**Status Polling**:
- Initial poll: 2 seconds after 202 response
- Exponential backoff: 2s → 4s → 8s → 16s → 30s (max)
- Stop polling after 5 minutes or on completion

**User Input**:
- Debounce text input: 300ms
- Debounce GPS location updates: 1 second
- Do NOT send status requests more often than every 2 seconds

### Pagination

**Default Page Size**: 25 items
**Max Page Size**: 100 items

**Query Parameters**:
```
GET /api/v1/onboarding/site-audit/{session_id}/observations/?page=2&page_size=50
```

**Response Format**:
```json
{
    "count": 150,
    "next": "https://api.youtility.in/api/v1/onboarding/site-audit/{session_id}/observations/?page=3",
    "previous": "https://api.youtility.in/api/v1/onboarding/site-audit/{session_id}/observations/?page=1",
    "results": [...]
}
```

**Kotlin Implementation**:
```kotlin
@Serializable
data class PaginatedResponse<T>(
    @SerialName("count") val count: Int,
    @SerialName("next") val next: String?,
    @SerialName("previous") val previous: String?,
    @SerialName("results") val results: List<T>
)

suspend fun getAllObservations(sessionId: String): List<ObservationItem> {
    val allObservations = mutableListOf<ObservationItem>()
    var nextUrl: String? = "${ApiClient.BASE_URL}/api/v1/onboarding/site-audit/$sessionId/observations/"

    while (nextUrl != null) {
        val response: PaginatedResponse<ObservationItem> = apiService.getObservations(nextUrl)
        allObservations.addAll(response.results)
        nextUrl = response.next
    }

    return allObservations
}
```

### Async Processing

Backend returns `202 Accepted` for long-running operations:
- Voice transcription > 5 seconds
- Site audit analysis with multiple observations
- Report generation

**Always implement polling** for `202` responses.

### Caching

**Cache on client**:
- Feature status (`/status/`) - cache for 1 hour
- Voice capabilities (`/voice/capabilities/`) - cache for 1 day
- Enum definitions - cache permanently (hardcoded)

**Do NOT cache**:
- JWT tokens (store securely, but check expiry)
- Conversation status
- Observation lists
- Real-time audit progress

---

## Testing & Validation

### Integration Testing Checklist

**Authentication & Authorization**:
- [ ] JWT token acquisition via `/api/v1/auth/token/`
- [ ] Token refresh via `/api/v1/auth/token/refresh/`
- [ ] 401 Unauthorized on expired token
- [ ] 403 Forbidden on insufficient permissions

**Conversational Onboarding**:
- [ ] Start conversation with valid business unit
- [ ] 409 Conflict when active session exists
- [ ] Resume existing conversation with `resume_existing=true`
- [ ] Process conversation step (sync response)
- [ ] Process conversation step (async 202 response)
- [ ] Poll task status until completion
- [ ] Voice input upload with `audio/webm`
- [ ] Voice input upload with `audio/mp3`
- [ ] Voice input upload with `audio/mpeg`
- [ ] Get conversation status
- [ ] Approve recommendations (single approval)
- [ ] Approve recommendations (two-person workflow)
- [ ] Preflight validation (ready state)
- [ ] Preflight validation (not ready state)

**Site Audit**:
- [ ] Start site audit with GPS location
- [ ] Create zones via `/site/{site_id}/zones/`
- [ ] Create assets via `/site/{site_id}/assets/`
- [ ] Create meter points via `/site/{site_id}/meter-points/`
- [ ] Capture observation (photo only)
- [ ] Capture observation (audio only)
- [ ] Capture observation (text only)
- [ ] Capture observation (photo + audio + GPS)
- [ ] List observations with filters
- [ ] Parse `gps_at_capture` PostGIS string correctly
- [ ] Get coverage map
- [ ] Get next questions
- [ ] Trigger analysis (sync response)
- [ ] Trigger analysis (async 202 response)
- [ ] Get coverage plan
- [ ] Get generated SOPs
- [ ] Generate report (HTML format)
- [ ] Generate report (JSON format)

**Coordinate Testing** (CRITICAL):
- [ ] Send GPS location: `{latitude: 19.076, longitude: 72.877}`
- [ ] Verify backend stores as: `POINT (72.877 19.076)`
- [ ] Parse received point: `"POINT (72.877 19.076)"` → `GeoPoint(lon=72.877, lat=19.076)`
- [ ] Display on map: Convert to `LatLng(19.076, 72.877)`

**Audio Format Testing**:
- [ ] Upload `audio/webm` - accepted
- [ ] Upload `audio/mp3` - accepted
- [ ] Upload `audio/mpeg` - accepted
- [ ] Upload `audio/wav` - accepted
- [ ] Upload `audio/ogg` - accepted
- [ ] Upload invalid format `audio/aac` - rejected with 400

**Error Handling**:
- [ ] Field-level validation error (400)
- [ ] Non-field validation error (400)
- [ ] Generic error (500)
- [ ] Rate limit error (429) with Retry-After
- [ ] Network timeout
- [ ] Connection error (offline)

**Offline Sync**:
- [ ] Queue observation while offline
- [ ] Sync when connectivity restored
- [ ] Handle sync conflicts
- [ ] Retry failed syncs with exponential backoff

**GraphQL**:
- [ ] Execute query (no CSRF required)
- [ ] Execute mutation with JWT auth (no CSRF)
- [ ] Execute mutation with CSRF token
- [ ] File upload via GraphQL

**Performance**:
- [ ] Rate limiting triggered at 600 requests/hour
- [ ] Exponential backoff on 429 errors
- [ ] Status polling with correct intervals
- [ ] File upload progress reporting
- [ ] Pagination for large lists

### Contract Testing

**OpenAPI/Swagger Validation**:
```kotlin
// Use backend-generated OpenAPI spec for contract validation
class ContractTest {
    @Test
    fun `verify conversation start request schema`() {
        val requestJson = Json.encodeToString(
            ConversationStartRequest(
                language = "en",
                initialInput = "Test input"
            )
        )

        // Validate against OpenAPI schema
        val validator = OpenApiValidator.fromUrl("${baseUrl}/api/v1/onboarding/swagger.json")
        validator.validateRequest("POST", "/conversation/start/", requestJson)
    }
}
```

### Automated Testing Recommendations

**Use Pact for Consumer-Driven Contracts**:
```kotlin
@Pact(consumer = "kotlin-mobile-app", provider = "django-backend")
fun conversationStartPact(builder: PactDslWithProvider): RequestResponsePact {
    return builder
        .given("user has valid business unit association")
        .uponReceiving("start conversation request")
        .path("/api/v1/onboarding/conversation/start/")
        .method("POST")
        .headers(mapOf(
            "Authorization" to "Bearer valid_token",
            "Content-Type" to "application/json"
        ))
        .body("""{
            "language": "en",
            "client_context": {},
            "initial_input": "Start setup",
            "resume_existing": false
        }""")
        .willRespondWith()
        .status(200)
        .body(PactDslJsonBody()
            .stringType("conversation_id")
            .object("enhanced_understanding")
            .closeObject()
            .array("questions")
            .closeArray()
            .object("context")
            .closeObject()
        )
        .toPact()
}
```

---

## Contract Enforcement

### Version Control

This contract is versioned alongside the backend API:
- **Contract Version**: 1.0
- **Backend API Version**: v1
- **Last Updated**: 2025-09-28

### Change Management

**Contract Changes**:
1. Minor changes (new optional fields): Backend deployed first, then mobile update
2. Breaking changes (field removal, renamed fields): Require API version bump (v1 → v2)
3. Enum additions: Backend deployed with new values, mobile updated to recognize them

**Deprecation Policy**:
- Deprecated endpoints: 90-day notice via `Deprecation` header
- Sunset date announced via `Sunset` header
- Documentation updated with migration guide

### Compliance Verification

**Backend Responsibilities**:
- [ ] All endpoints documented in this contract are implemented
- [ ] Audio MIME type inconsistency fixed
- [ ] PostGIS coordinate serialization verified
- [ ] approval_id uses INTEGER type (not UUID)
- [ ] CSRF middleware active for GraphQL
- [ ] Error responses follow documented formats
- [ ] Rate limiting enforced at documented levels

**Frontend Responsibilities**:
- [ ] All data classes match backend serializers exactly
- [ ] Field names use exact snake_case from backend
- [ ] Enum values match backend choices exactly
- [ ] Coordinate parsing handles PostGIS (lon, lat) order
- [ ] Audio uploads support both `audio/mp3` and `audio/mpeg`
- [ ] approval_id sent as INTEGER in URL path
- [ ] Error handling covers all documented formats
- [ ] Rate limit backoff implemented

### Support & Issue Resolution

**Contract Violations**:
1. Report issue to backend team with:
   - Endpoint URL
   - Request/response payloads
   - Expected vs actual behavior
   - Contract section reference

2. Backend team investigates within 24 hours

3. Resolution:
   - Backend bug: Backend fix deployed
   - Contract error: Contract updated, mobile notified
   - Frontend bug: Frontend fix required

**Contact**:
- **Backend API Team**: api@youtility.in
- **Contract Issues**: https://github.com/youtility/api-contracts/issues
- **Emergency**: +91-XXXX-XXXXXX

---

## Appendix: Example Payloads

### Start Conversation (Complete)
```json
// Request
POST /api/v1/onboarding/conversation/start/
{
    "language": "en",
    "user_type": "admin",
    "client_context": {"region": "IN", "industry": "banking"},
    "initial_input": "Set up security for bank branch",
    "resume_existing": false
}

// Response
{
    "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "enhanced_understanding": {
        "intent": "security_setup",
        "domain": "banking",
        "priority": "high"
    },
    "questions": [
        {
            "question": "What type of facility are you securing?",
            "field": "site_type",
            "options": ["bank_branch", "atm", "retail_store"]
        }
    ],
    "context": {"region": "IN", "industry": "banking"}
}
```

### Start Site Audit (Complete)
```json
// Request
POST /api/v1/onboarding/site-audit/start/
{
    "business_unit_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "site_type": "bank_branch",
    "language": "en",
    "operating_hours": {
        "start": "09:00",
        "end": "18:00"
    },
    "gps_location": {
        "latitude": 19.076,
        "longitude": 72.877
    }
}

// Response
{
    "audit_session_id": "4gb96g75-6828-5673-c4gd-3d074g77bgb7",
    "site_id": "5hc07h86-7939-6784-d5he-4e185h88cha8",
    "checklist": [...],
    "zones": [
        {
            "zone_id": "6id18i97-8040-7895-e6if-5f296i99dib9",
            "zone_name": "Main Entrance Gate",
            "zone_type": "gate",
            "importance_level": "critical"
        }
    ],
    "suggested_route": [...],
    "estimated_duration_minutes": 35
}
```

### Capture Observation (Text-Only)
```json
// Request
POST /api/v1/onboarding/site-audit/4gb96g75-6828-5673-c4gd-3d074g77bgb7/observation/
{
    "text_input": "CCTV camera not working at main gate",
    "gps_latitude": 19.076,
    "gps_longitude": 72.877,
    "zone_hint": "gate"
}

// Response
{
    "observation_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "enhanced": {
        "entities": [
            {"type": "asset", "name": "CCTV Camera", "status": "not_working"}
        ],
        "risks": [
            {"severity": "high", "description": "Surveillance gap"}
        ],
        "actions": ["Immediate repair required"]
    },
    "confidence": 0.89,
    "identified_zone": {
        "zone_id": "6id18i97-8040-7895-e6if-5f296i99dib9",
        "zone_name": "Main Entrance Gate",
        "zone_type": "gate",
        "importance_level": "critical"
    },
    "next_questions": [...],
    "inconsistencies": []
}
```

---

**END OF CONTRACT**

**Document Status**: ✅ Production-Ready
**Version**: 1.0
**Effective Date**: 2025-09-28
**Next Review**: 2025-12-28 (Quarterly)

**Approval**:
- [ ] Backend Team Lead: __________________
- [ ] Frontend Team Lead: __________________
- [ ] QA Lead: __________________
- [ ] Product Manager: __________________

**Changelog**:
- **2025-09-28 (v1.0)**: Initial production-ready contract with all corrections applied

---

For questions or clarifications, contact: api@youtility.in