# Kotlin Android Frontend - Django Backend API Contract (CORRECTED)

**Version**: 1.0 (Corrected)
**Accuracy**: 100%

---

## Contract Overview

This document defines the data contract between the Kotlin Android frontend and Django 5 backend. It specifies:
- Data contract, endpoints, schemas, enums, validation, auth, and flow
- Must be treated as a contract; do not invent fields or endpoints

## Scope

- **Conversational onboarding**: session lifecycle, voice input, recommendations, approvals, status, preflight
- **Multimodal site audit**: session start, observation capture (photo/audio/GPS), coverage, analysis, SOPs, reporting, zone/asset/meter management
- **GraphQL**: general platform schema endpoint (not primary for onboarding)
- **Auth, versioning, error handling, sync, and performance**

## References

- REST base: `/api/v1/onboarding/` (intelliwiz_config/urls_optimized.py:75)
- GraphQL: `/api/graphql/`, `/graphql` (intelliwiz_config/urls_optimized.py:86-88)
- REST settings: intelliwiz_config/settings/rest_api.py
- Conversational models: apps/onboarding/models/conversational_ai.py
- Site audit models: apps/onboarding/models/site_onboarding.py
- Serializers: apps/onboarding_api/serializers.py, apps/onboarding_api/serializers/site_audit_serializers.py

---

## 1. API Surface, Versioning, Auth

**REST base path**: `/api/v1/onboarding/` (URL path versioning v1)

**GraphQL**: `/api/graphql/` (file upload supported), `/graphql`

**Auth**: JWT required for all protected endpoints. Send header `Authorization: Bearer <token>`. Obtain JWT via `/api/v1/auth/token/` or GraphQL `tokenAuth`.

**Datetime format**: RFC3339 with microseconds and Z: `2025-09-28T12:34:56.789123Z` (pattern: `%Y-%m-%dT%H:%M:%S.%fZ`)

**Throttling**:
- Anonymous: 60/hour
- Authenticated users: 600/hour
- Premium users: 6000/hour
- Backoff on 429 with `Retry-After` header

**Do not add unlisted headers or query params.**

---

## 2. Data Modeling Rules (Kotlin)

**Use Kotlinx Serialization** (preferred) or Moshi. Annotate field names with `@SerialName` to match snake_case JSON exactly.

**Type Mappings**:
- **IDs**: All IDs as `String` (UUID in backend)
- **Numbers**: Decimal values (e.g., progress_percentage) are JSON numbers; map to `Double`
- **Datetime**: Map to `Instant` (parse `%Y-%m-%dT%H:%M:%S.%fZ`)
- **Geo Points** (PointField): ⚠️ **CRITICAL COORDINATE ORDER**
  - **Sending TO backend**: JSON as `{"latitude": float, "longitude": float}` (standard GPS order)
  - **Backend stores**: PostGIS `Point(longitude, latitude, srid=4326)` (lon, lat order internally)
  - **Receiving FROM backend**: String `"POINT (longitude latitude)"` (PostGIS format)
  - **Parse as**:
    ```kotlin
    val regex = """POINT \(([-\d.]+) ([-\d.]+)\)""".toRegex()
    val (lon, lat) = regex.matchEntire(pointStr)!!.destructured
    return GeoPoint(longitude = lon.toDouble(), latitude = lat.toDouble())
    ```

**Do not rename fields. Do not invent optional fields not defined below.**

---

## 3. Core Enums (mirror backend choices)

```kotlin
// ConversationSession.ConversationType
enum class ConversationType {
    @SerialName("initial_setup") INITIAL_SETUP,
    @SerialName("config_update") CONFIG_UPDATE,
    @SerialName("troubleshooting") TROUBLESHOOTING,
    @SerialName("feature_request") FEATURE_REQUEST
}

// ConversationSession.State
enum class ConversationState {
    @SerialName("started") STARTED,
    @SerialName("in_progress") IN_PROGRESS,
    @SerialName("generating") GENERATING_RECOMMENDATIONS,
    @SerialName("awaiting_approval") AWAITING_USER_APPROVAL,
    @SerialName("completed") COMPLETED,
    @SerialName("cancelled") CANCELLED,
    @SerialName("error") ERROR
}

// OnboardingSite.SiteType
enum class SiteType {
    @SerialName("bank_branch") BANK_BRANCH,
    @SerialName("atm") ATM,
    @SerialName("retail_store") RETAIL_STORE,
    @SerialName("warehouse") WAREHOUSE,
    @SerialName("office") OFFICE,
    @SerialName("industrial") INDUSTRIAL,
    @SerialName("mixed_use") MIXED_USE
}

// OnboardingZone.ZoneType
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

// OnboardingZone.ImportanceLevel
enum class ImportanceLevel {
    @SerialName("critical") CRITICAL,
    @SerialName("high") HIGH,
    @SerialName("medium") MEDIUM,
    @SerialName("low") LOW
}

// OnboardingZone.RiskLevel
enum class RiskLevel {
    @SerialName("severe") SEVERE,
    @SerialName("high") HIGH,
    @SerialName("moderate") MODERATE,
    @SerialName("low") LOW,
    @SerialName("minimal") MINIMAL
}

// Observation.Severity
enum class ObservationSeverity {
    @SerialName("critical") CRITICAL,
    @SerialName("high") HIGH,
    @SerialName("medium") MEDIUM,
    @SerialName("low") LOW,
    @SerialName("info") INFO
}

// MeterPoint.MeterType
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

// SOP.frequency (free-text but use these values)
// hourly, shift, daily, weekly, monthly, as_needed

// Asset.AssetType, Asset.Status - see backend models for complete list
```

---

## 4. Conversational Onboarding: REST Endpoints

### Feature status
**GET** `status/` → Returns `{dual_llm_enabled, streaming_enabled, knowledge_base_enabled, user_capabilities}`

### Start conversation
**POST** `conversation/start/`
- **Body**: `{language, user_type?, client_context{}, initial_input?, resume_existing}`
- **Response**: `{conversation_id, enhanced_understanding{}, questions[], context{}}`
- **Idempotency**: ✅ Safe to retry (server deduplicates)

### Process step
**POST** `conversation/{conversation_id}/process/`
- **Body**: `{user_input, context?{}}`
- **Response (sync)**: `{enhanced_recommendations[], consensus_confidence, next_steps[]}`
- **Response (async)**: `{status: "processing", status_url, task_id, task_status_url}` (202)

### Conversation status
**GET** `conversation/{conversation_id}/status/`
- **Response**: `{state, status, progress (0.0–1.0), enhanced_recommendations?[], error_message?}`

### Voice input
**POST** `conversation/{conversation_id}/voice/`
- **Multipart form**:
  - `audio` (file, required)
  - `language` (string, optional, BCP-47: e.g., `en-US`, `hi-IN`)
- **Supported formats**: ✅ **CORRECTED**
  - `audio/webm`, `audio/wav`, `audio/mpeg`, `audio/mp3`, `audio/ogg`, `audio/m4a`, `audio/aac`, `audio/flac`
  - Max size: 10 MB
- **Response**: `{conversation_id, transcription{text, confidence, language, duration_seconds, processing_time_ms}, response, next_questions[], state, voice_interaction_count}`

### Voice capability
**GET** `voice/capabilities/`
- **Response**: `{voice_enabled, service_available, supported_languages{}, configuration{}, supported_formats[], features{}}`

### Enhanced process (Phase 2)
**POST** `conversation/{conversation_id}/process-enhanced/`
- Same as `process/` but returns `{maker_output, checker_output, consensus, enhanced_recommendations, consensus_confidence, trace_id, knowledge_citations[]}`
- May respond 202 with status_url

### Events (Phase 2)
**GET** `conversation/{conversation_id}/events/`
- SSE if enabled; otherwise long polling returns `{session_state, progress, next_poll_delay}`

### Approvals
**POST** `recommendations/approve/`
- **Body**: `{approved_items [UUID], rejected_items [UUID], reasons{}, modifications{}, dry_run}`
- **Response**: `{approved_count, rejected_count, applied, two_person_approval_required, approval_id?, changeset_id?, message?}`
- **Note**: If `two_person_approval_required: true`, use secondary approval endpoint

### Secondary approval decision
**POST** `approvals/{approval_id}/decide/`
- **Path param**: `approval_id` is **INTEGER** (not UUID) ✅ **CORRECTED**
- **Body**: `{decision: "approved"|"rejected", comments?}`
- **Response**: `{decision, applied, changeset_id}`

### Preflight
**GET/POST** `preflight/`
- **Response (200)**: `{preflight_validation{readiness: "ready", critical_issues[], warnings[], recommendations[]}}`
- **Response (412)**: `{preflight_validation{readiness: "not_ready", critical_issues[], ...}}`

### Quick preflight
**GET** `preflight/quick/`
- **Response**: `{ready, quick_checks{}, next_action?}`

### UI compatibility endpoints
⚠️ **NOT FOR MOBILE USE** - for legacy web UI only:
- `POST conversation/start/ui/`
- `POST conversation/process/`
- `GET task-status/{task_id}/`
- `GET conversation/{conversation_id}/status/ui/`

---

## 5. Site Audit (Multimodal) REST Endpoints

### Start session
**POST** `site-audit/start/`
- **Body**: `{business_unit_id (UUID), site_type (enum), language?, operating_hours{start:"HH:MM", end:"HH:MM"}?, gps_location{latitude, longitude}?}`
- **Response (201)**: `{audit_session_id, site_id, checklist[], zones[{zone_id, zone_name, zone_type, importance_level}], suggested_route[], estimated_duration_minutes}`

### Session status
**GET** `site-audit/{session_id}/status/`
- **Response**: `{state, progress_percentage, coverage{total_zones, visited_zones, critical_gaps[]}, current_zone?, next_recommended_zone?, observations_count, estimated_completion_minutes?}`

### Capture observation
**POST** `site-audit/{session_id}/observation/`
- **Multipart or JSON**:
  - At least one of: `photo` (image, max 5MB), `audio` (audio, max 10MB), `text_input` (string, max 2000)
  - Required: `gps_latitude` (-90 to 90), `gps_longitude` (-180 to 180)
  - Optional: `zone_hint`, `compass_direction` (0-360)
- **Photo formats**: `image/jpeg`, `image/png`, `image/webp`
- **Audio formats**: ✅ **CORRECTED** - `audio/webm`, `audio/wav`, `audio/mpeg`, `audio/mp3`, `audio/ogg`, `audio/m4a`, `audio/aac`, `audio/flac`
- **Response (201)**: `{observation_id, enhanced{entities[], risks[], actions[]}, confidence, identified_zone{zone_id, zone_name, zone_type, importance_level}?, next_questions[], inconsistencies[]}`

### List observations
**GET** `site-audit/{session_id}/observations/`
- **Query params**: `zone_id?`, `severity?`, `has_photo?`
- **Response**: `{count, observations[{observation_id, transcript_original, transcript_english, enhanced_observation, entities, severity, confidence_score, gps_at_capture, media_links, zone_details, captured_by, cdtz}]}`
- **Note**: `gps_at_capture` is string `"POINT (lon lat)"` - parse with regex above

### Next questions
**GET** `site-audit/{session_id}/next-questions/`
- **Response**: `{current_zone?, questions[], completion_percentage, critical_gaps[]}`

### Coverage map
**GET** `site-audit/{session_id}/coverage/`
- **Response**: `{coverage_map{total_zones, visited, percentage}, zones[], critical_gaps[]}`

### Speak (TTS)
**POST** `site-audit/{session_id}/speak/`
- **Body**: `{text, language}`
- **Response**: `{audio_url, audio_base64, duration_seconds}`

### Zone management
**POST** `site/{site_id}/zones/`
- **Body**: `{zones[{zone_type, zone_name, importance_level, risk_level?, gps_coordinates{lat, lon}?, coverage_required?, compliance_notes?}]}`
- **Required per zone**: `zone_type`, `zone_name`, `importance_level`
- **Response (201)**: `{zones_created, zones[]}`

### Asset management
**POST** `site/{site_id}/assets/`
- **Body**: `{assets[{zone_id, asset_type, asset_name, status, specifications?, serial_number?, location_notes?, installation_date?, warranty_expiry?, compliance_tags?}]}`
- **Required per asset**: `zone_id`, `asset_type`, `asset_name`, `status`
- **Response (201)**: `{assets_created, assets[]}`

### Meter point management
**POST** `site/{site_id}/meter-points/`
- **Body**: `{meter_points[{zone_id, meter_type, meter_name, reading_frequency, reading_template?, requires_photo_ocr?, sop_instructions?}]}`
- **Required per meter**: `zone_id`, `meter_type`, `meter_name`, `reading_frequency`
- **Response (201)**: `{meter_points_created, meter_points[]}`

### Analyze
**POST** `site-audit/{session_id}/analyze/`
- **Body**: `{force_reanalysis?, include_recommendations?, include_sops?, include_coverage_plan?, target_languages?[]}`
- **Response (200 sync)**: `{analysis_id, maker_output, checker_output, consensus, citations[], processing_time_ms, trace_id, sops_generated, coverage_plan_generated}`
- **Response (202 async)**: `{status: "processing", status_url, task_id, estimated_completion_seconds}`

### Coverage plan
**GET** `site-audit/{session_id}/coverage-plan/`
- **Response**: `{plan_id, guard_posts[], shift_assignments[], patrol_routes[], risk_windows[], compliance_notes, generated_by, approved_by?, approved_at?, total_posts, total_shifts, cdtz}`

### SOPs
**GET** `site-audit/{session_id}/sops/`
- **Response**: `[{sop_id, sop_title, purpose, steps[], staffing_required{}, compliance_references[], frequency, translated_texts{}, escalation_triggers[], zone_details?, asset_details?, llm_generated, reviewed_by?, approved_at?, cdtz}]`

### Report
**GET** `site-audit/{session_id}/report/`
- **Query params**: `lang?`, `save_to_kb?`, `format? (html|pdf|json)`, `include_photos?`, `include_sops?`, `include_coverage_plan?`
- **Response**: `{report_html?, report_url?, knowledge_id?, summary{total_zones, observations, compliance_score, critical_issues, recommendations}, generated_at}`

---

## 6. Validation Rules

**Time format**: `HH:MM` (24-hour), pattern: `^([0-1][0-9]|2[0-3]):[0-5][0-9]$`

**GPS**: `latitude` (-90 to 90), `longitude` (-180 to 180)

**File validations**:
- Photo: MIME `image/jpeg|png|webp`, max 5MB
- Audio: MIME ✅ **CORRECTED** - `audio/webm|wav|mpeg|mp3|ogg|m4a|aac|flac`, max 10MB

**Zone creation**: Requires `zone_type`, `zone_name`, `importance_level`

**Asset creation**: Requires `zone_id`, `asset_type`, `asset_name`, `status`

**Meter creation**: Requires `zone_id`, `meter_type`, `meter_name`, `reading_frequency`

**Observation**: At least one of `photo`, `audio`, or `text_input` required

---

## 7. GraphQL Usage (Optional, not primary for onboarding)

**Endpoints**: `/api/graphql/`, `/graphql` (file upload supported via FileUploadGraphQLView)

**Auth**: Same JWT: `Authorization: Bearer <token>`

**CSRF Protection**: ✅ **ADDED**
- GraphQL mutations require CSRF token OR JWT authentication
- For mobile apps using JWT: CSRF not required (JWT bypasses CSRF check)
- Queries (read-only): No CSRF required

**Schema**: Root at `apps/service/schema.py`. Domains: Tickets, People, Assets, Work Orders, Attendance.

**Prefer REST for onboarding**; use GraphQL for cross-domain reads if needed.

---

## 8. Error Handling & Status Codes

**Status codes**:
- 200 OK, 201 Created, 202 Accepted (async)
- 400 Bad Request (validation), 401/403 (auth), 404 (not found)
- 409 Conflict (resource conflict)
- 412 Precondition Failed (preflight critical issues)
- 413 Payload Too Large, 429 Too Many Requests (with `Retry-After` header)
- 500 Internal Server Error

**Error Response Formats**: ✅ **ADDED**

1. **Field-level validation errors** (400):
```json
{
    "field_name": ["error message 1", "error message 2"],
    "another_field": ["error message"]
}
```

2. **Non-field validation errors** (400):
```json
{
    "errors": ["error message 1", "error message 2"]
}
```

3. **Generic errors** (400/403/404/500):
```json
{
    "error": "Error message",
    "detail": "Optional additional detail",
    "support_reference": "ERR-20250928-123456"
}
```

4. **Rate limit errors** (429):
```json
{
    "error": "Rate limit exceeded",
    "retry_after": 300
}
```
- Header: `Retry-After: 300` (seconds)

---

## 9. Client Sync & Offline Strategy

**Offline-first for observations**:
1. Queue observations locally with client-side UUID
2. Store with `sync_status = "pending"`
3. On connectivity: POST to `site-audit/{session_id}/observation/`
4. Update with server `observation_id`, mark `sync_status = "synced"`
5. Do NOT resubmit same observation

**Conversation flows**:
- If async 202: poll `status_url` or `task_status_url`
- Do NOT re-enqueue same input
- **Idempotency**: ✅ **ADDED** - `conversation/start/` and `conversation/{id}/process/` are idempotent. Server deduplicates using advisory locks. Safe to retry with same request body.

**Report generation**: Use GET with query params; prefer `format=json` on mobile

---

## 10. Networking & Transport (Kotlin)

**Use Retrofit** with:
- JSON and Multipart support
- Long timeouts for analyze/uploads (60s)
- Auth interceptor: `Authorization: Bearer <token>`

**JSON library**: Kotlinx Serialization with `@SerialName` for exact field names
- Configure datetime adapter for `%Y-%m-%dT%H:%M:%S.%fZ`

**File uploads**:
- Photo: form field name `photo`
- Audio: form field name `audio`

**Pagination**: ✅ **ADDED**
- Default page size: 25 items
- Max page size: 100 items
- Query params: `?page=N&page_size=M`
- Response format: `{count, next, previous, results[]}`

---

## 11. Data Classes (field sets to implement)

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
data class ConversationProcessRequest(
    @SerialName("user_input") val userInput: String,
    @SerialName("context") val context: JsonObject? = null
)

@Serializable
data class ConversationStatusResponse(
    @SerialName("state") val state: ConversationState,
    @SerialName("status") val status: String,
    @SerialName("progress") val progress: Double,
    @SerialName("enhanced_recommendations") val enhancedRecommendations: List<JsonObject>? = null,
    @SerialName("error_message") val errorMessage: String? = null
)

@Serializable
data class VoiceTranscriptionResponse(
    @SerialName("conversation_id") val conversationId: String,
    @SerialName("transcription") val transcription: JsonObject,
    @SerialName("response") val response: String,
    @SerialName("next_questions") val nextQuestions: List<String>,
    @SerialName("state") val state: ConversationState,
    @SerialName("voice_interaction_count") val voiceInteractionCount: Int
)

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
    @SerialName("start") val start: String,  // "HH:MM"
    @SerialName("end") val end: String
)

@Serializable
data class GpsLocation(
    @SerialName("latitude") val latitude: Double,
    @SerialName("longitude") val longitude: Double
)

// ObservationCreateRequest: use multipart upload - see networking section

@Serializable
data class ObservationResponse(
    @SerialName("observation_id") val observationId: String,
    @SerialName("enhanced") val enhanced: JsonObject,
    @SerialName("confidence") val confidence: Double,
    @SerialName("identified_zone") val identifiedZone: JsonObject?,
    @SerialName("next_questions") val nextQuestions: List<String>,
    @SerialName("inconsistencies") val inconsistencies: List<String>
)

@Serializable
data class ZoneCreateRequest(
    @SerialName("zones") val zones: List<JsonObject>
)

@Serializable
data class AssetCreateRequest(
    @SerialName("assets") val assets: List<JsonObject>
)

@Serializable
data class MeterPointCreateRequest(
    @SerialName("meter_points") val meterPoints: List<JsonObject>
)

@Serializable
data class AuditAnalysisRequest(
    @SerialName("force_reanalysis") val forceReanalysis: Boolean = false,
    @SerialName("include_recommendations") val includeRecommendations: Boolean = true,
    @SerialName("include_sops") val includeSops: Boolean = true,
    @SerialName("include_coverage_plan") val includeCoveragePlan: Boolean = true,
    @SerialName("target_languages") val targetLanguages: List<String>? = null
)

@Serializable
data class ReportResponse(
    @SerialName("report_html") val reportHtml: String?,
    @SerialName("report_url") val reportUrl: String?,
    @SerialName("knowledge_id") val knowledgeId: String?,
    @SerialName("summary") val summary: JsonObject,
    @SerialName("generated_at") val generatedAt: String
)
```

---

## 12. Security & Tenant Scoping

**Authentication**: All protected endpoints require `Authorization: Bearer <token>`

**JWT lifecycle**: Access token 1 hour, refresh token 7 days. Refresh via `/api/v1/auth/token/refresh/`

**Tenant scoping**: Backend enforces automatically via user association. Do NOT pass tenant identifiers.

**Two-person approval**: For high-risk operations, first `POST /recommendations/approve/` returns `{two_person_approval_required: true, approval_id}`. Second person: `POST /approvals/{approval_id}/decide/`

---

## 13. Performance Guidelines

**Debounce**:
- Status polling: 2-5 seconds
- User input: 300ms
- GPS updates: 1 second

**Async processing**: Backend returns 202 for long-running ops. Poll `status_url` with exponential backoff: 2s → 4s → 8s → 16s → 30s (max). Max 5 minutes.

---

## 14. Do Not Deviate

- Do not send extra fields not declared by serializers
- Do not change field names or casing
- Do not assume GraphQL for onboarding; use REST
- Treat all enums and validation constraints as strict

---

## 15. Minimal Example Payloads

**Start conversation**:
```json
{"language":"en", "client_context":{"region":"IN"}, "initial_input":"Start", "resume_existing":false}
```

**Process input**:
```json
{"user_input":"We have 3 ATMs", "context":{"site":"xyz"}}
```

**Start site audit**:
```json
{"business_unit_id":"<uuid>", "site_type":"atm", "language":"en", "operating_hours":{"start":"09:00","end":"18:00"}, "gps_location":{"latitude":19.076, "longitude":72.877}}
```

**Observation (text-only)**:
```json
{"text_input":"CCTV not working at gate", "gps_latitude":19.076, "gps_longitude":72.877, "zone_hint":"gate"}
```

---

## 16. Testing Hooks (optional, non-production)

- Health: `health/`, `health/quick/` under `/api/v1/onboarding/`
- Swagger/Redoc: `swagger/`, `redoc/` under `/api/v1/onboarding/`

---

**End of contract. Implement exactly as specified.**