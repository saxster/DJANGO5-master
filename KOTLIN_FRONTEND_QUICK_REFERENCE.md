# Kotlin Android Frontend - Quick Reference Guide

**Version**: 1.0
**For**: Mobile app developers
**Full Contract**: See `KOTLIN_FRONTEND_API_CONTRACT.md`

---

## 🚀 Quick Start

### 1. Base Configuration

```kotlin
object ApiConfig {
    const val BASE_URL = "https://api.youtility.in"
    const val REST_BASE = "/api/v1/onboarding/"
    const val GRAPHQL_ENDPOINT = "/api/graphql/"
}
```

### 2. Authentication

```kotlin
// Get JWT token
val response = apiService.login(username, password)
val accessToken = response.access
val refreshToken = response.refresh

// Use in all requests
headers["Authorization"] = "Bearer $accessToken"
```

### 3. Essential Imports

```kotlin
import kotlinx.serialization.*
import kotlinx.serialization.json.*
import kotlinx.datetime.Instant
import okhttp3.*
import retrofit2.*
```

---

## 📋 Critical Mappings

### Data Types

| Backend | Kotlin | Example |
|---------|--------|---------|
| UUID | `String` | `"3fa85f64-5717-4562-b3fc-2c963f66afa6"` |
| Decimal | `Double` | `0.89` (as number, not string) |
| DateTime | `Instant` | Parse `"2025-09-28T12:34:56.789123Z"` |
| PointField | `GeoPoint` | Parse `"POINT (72.877 19.076)"` |

### ⚠️ CRITICAL: Coordinate Order

**Sending TO backend**:
```kotlin
{
    "gps_location": {
        "latitude": 19.076,   // Standard GPS order
        "longitude": 72.877
    }
}
```

**Receiving FROM backend**:
```kotlin
"gps_at_capture": "POINT (72.877 19.076)"  // PostGIS: (lon, lat)
                         //  ↑lon   ↑lat

// Parse as:
fun parsePointField(str: String): GeoPoint {
    val regex = """POINT \(([-\d.]+) ([-\d.]+)\)""".toRegex()
    val (lon, lat) = regex.matchEntire(str)!!.destructured
    return GeoPoint(lon.toDouble(), lat.toDouble())
}
```

---

## 🔑 Key Endpoints

### Conversational Onboarding

```kotlin
// Start conversation
POST /api/v1/onboarding/conversation/start/
{
    "language": "en",
    "client_context": {},
    "initial_input": "Setup bank security",
    "resume_existing": false
}

// Process step
POST /api/v1/onboarding/conversation/{id}/process/
{
    "user_input": "We have 3 ATMs",
    "context": {}
}

// Voice input
POST /api/v1/onboarding/conversation/{id}/voice/
Content-Type: multipart/form-data
- audio: [File] (audio/webm, audio/mp3, audio/mpeg)
- language: "en-US"

// Status
GET /api/v1/onboarding/conversation/{id}/status/
```

### Site Audit

```kotlin
// Start audit
POST /api/v1/onboarding/site-audit/start/
{
    "business_unit_id": "uuid",
    "site_type": "bank_branch",
    "language": "en",
    "operating_hours": {"start": "09:00", "end": "18:00"},
    "gps_location": {"latitude": 19.076, "longitude": 72.877}
}

// Capture observation
POST /api/v1/onboarding/site-audit/{session_id}/observation/
Content-Type: multipart/form-data
- photo: [File] (image/jpeg, image/png, image/webp, max 5MB)
- audio: [File] (audio/webm, max 10MB)
- text_input: "CCTV not working"
- gps_latitude: 19.076 (required)
- gps_longitude: 72.877 (required)
- zone_hint: "gate"

// List observations
GET /api/v1/onboarding/site-audit/{session_id}/observations/
?zone_id=uuid&severity=high&has_photo=true

// Status
GET /api/v1/onboarding/site-audit/{session_id}/status/
```

---

## 🎨 Common Data Classes

### Conversation Start

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

### Site Audit Start

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
    @SerialName("end") val end: String
)

@Serializable
data class GpsLocation(
    @SerialName("latitude") val latitude: Double,
    @SerialName("longitude") val longitude: Double
)
```

### Observation Capture

```kotlin
// Use multipart upload - see full contract for complete implementation
suspend fun captureObservation(
    sessionId: String,
    photoFile: File? = null,
    audioFile: File? = null,
    textInput: String? = null,
    gpsLatitude: Double,
    gpsLongitude: Double
): ObservationResponse {
    val requestBody = MultipartBody.Builder()
        .setType(MultipartBody.FORM)
        .apply {
            photoFile?.let {
                addFormDataPart("photo", it.name,
                    it.asRequestBody("image/jpeg".toMediaTypeOrNull()))
            }
            audioFile?.let {
                addFormDataPart("audio", it.name,
                    it.asRequestBody("audio/webm".toMediaTypeOrNull()))
            }
            textInput?.let { addFormDataPart("text_input", it) }
            addFormDataPart("gps_latitude", gpsLatitude.toString())
            addFormDataPart("gps_longitude", gpsLongitude.toString())
        }
        .build()

    // Execute request...
}
```

---

## 📊 Enums (Exhaustive)

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

enum class SiteType {
    @SerialName("bank_branch") BANK_BRANCH,
    @SerialName("atm") ATM,
    @SerialName("retail_store") RETAIL_STORE,
    @SerialName("warehouse") WAREHOUSE,
    @SerialName("office") OFFICE,
    @SerialName("industrial") INDUSTRIAL,
    @SerialName("mixed_use") MIXED_USE
}

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

enum class ImportanceLevel {
    @SerialName("critical") CRITICAL,
    @SerialName("high") HIGH,
    @SerialName("medium") MEDIUM,
    @SerialName("low") LOW
}

enum class ObservationSeverity {
    @SerialName("critical") CRITICAL,
    @SerialName("high") HIGH,
    @SerialName("medium") MEDIUM,
    @SerialName("low") LOW,
    @SerialName("info") INFO
}
```

---

## ⚠️ Common Pitfalls

### 1. Audio MIME Types

**❌ WRONG**: Only sending `audio/mpeg`
**✅ CORRECT**: Backend accepts BOTH `audio/mp3` AND `audio/mpeg`

```kotlin
// Use audio/webm for best compatibility
val mimeType = "audio/webm"

// Or detect from file extension
val mimeType = when (file.extension.lowercase()) {
    "webm" -> "audio/webm"
    "mp3" -> "audio/mp3"  // Both work
    "wav" -> "audio/wav"
    else -> "audio/mpeg"
}
```

### 2. Coordinate Order

**❌ WRONG**: Sending PostGIS format to backend
```kotlin
{
    "gps_location": {
        "longitude": 72.877,  // ❌ Backend expects lat first
        "latitude": 19.076
    }
}
```

**✅ CORRECT**: Send standard GPS order
```kotlin
{
    "gps_location": {
        "latitude": 19.076,   // ✅ Standard GPS order
        "longitude": 72.877
    }
}
```

**✅ CORRECT**: Parse PostGIS response
```kotlin
// Received: "POINT (72.877 19.076)"
val regex = """POINT \(([-\d.]+) ([-\d.]+)\)""".toRegex()
val (lon, lat) = regex.matchEntire(pointStr)!!.destructured
val geoPoint = GeoPoint(lon.toDouble(), lat.toDouble())
```

### 3. approval_id Type

**❌ WRONG**: Treating approval_id as UUID
```kotlin
val approvalId: String = "uuid-string"  // ❌
apiService.decideApproval(approvalId)   // ❌ Type mismatch
```

**✅ CORRECT**: Use Integer
```kotlin
val approvalId: Int = 12345  // ✅
apiService.decideApproval(approvalId)  // ✅
```

### 4. Idempotency

**❌ WRONG**: Manually implementing idempotency keys
```kotlin
val idempotencyKey = UUID.randomUUID()
headers["Idempotency-Key"] = idempotencyKey.toString()  // ❌ Not needed
```

**✅ CORRECT**: Backend handles it automatically
```kotlin
// Just retry with same request body - backend deduplicates
try {
    apiService.startConversation(request)
} catch (e: NetworkException) {
    // Safe to retry with same request
    apiService.startConversation(request)  // ✅
}
```

### 5. Observation Validation

**❌ WRONG**: Sending observation without any input
```kotlin
captureObservation(
    sessionId = sessionId,
    gpsLatitude = 19.076,
    gpsLongitude = 72.877
    // ❌ No photo, audio, or text_input
)
```

**✅ CORRECT**: At least one input required
```kotlin
captureObservation(
    sessionId = sessionId,
    textInput = "CCTV not working",  // ✅
    gpsLatitude = 19.076,
    gpsLongitude = 72.877
)
```

---

## 🚨 Error Handling

### Parse Errors

```kotlin
sealed class ApiError {
    data class ValidationError(val fieldErrors: Map<String, List<String>>) : ApiError()
    data class NonFieldError(val errors: List<String>) : ApiError()
    data class GenericError(val message: String) : ApiError()
    data class RateLimitError(val retryAfter: Int) : ApiError()
}

fun parseError(errorBody: String): ApiError {
    val json = Json.parseToJsonElement(errorBody).jsonObject

    return when {
        json.containsKey("errors") -> {
            val errors = json["errors"]!!.jsonArray.map { it.jsonPrimitive.content }
            ApiError.NonFieldError(errors)
        }
        json.containsKey("error") -> {
            val message = json["error"]!!.jsonPrimitive.content
            ApiError.GenericError(message)
        }
        else -> {
            val fieldErrors = json.mapValues { (_, value) ->
                value.jsonArray.map { it.jsonPrimitive.content }
            }
            ApiError.ValidationError(fieldErrors)
        }
    }
}
```

### Handle Rate Limits

```kotlin
suspend fun <T> handleApiCall(call: suspend () -> Response<T>): Result<T> {
    val response = call()

    return when (response.code()) {
        200, 201 -> Result.success(response.body()!!)
        429 -> {
            val retryAfter = response.headers()["Retry-After"]?.toIntOrNull() ?: 60
            delay(retryAfter * 1000L)  // Wait before retry
            handleApiCall(call)  // Retry
        }
        else -> Result.failure(ApiException(response))
    }
}
```

---

## 🔄 Offline Sync

### Queue Pattern

```kotlin
@Entity
data class PendingObservation(
    @PrimaryKey val clientId: String = UUID.randomUUID().toString(),
    val sessionId: String,
    val photoPath: String?,
    val audioPath: String?,
    val textInput: String?,
    val gpsLatitude: Double,
    val gpsLongitude: Double,
    val timestamp: Long,
    val syncStatus: String,  // "pending", "syncing", "synced", "failed"
    val serverId: String? = null
)

class SyncManager {
    suspend fun syncPendingObservations() {
        val pending = database.getPending()

        pending.forEach { observation ->
            try {
                database.updateStatus(observation.clientId, "syncing")

                val response = apiService.captureObservation(
                    sessionId = observation.sessionId,
                    photoFile = observation.photoPath?.let { File(it) },
                    audioFile = observation.audioPath?.let { File(it) },
                    textInput = observation.textInput,
                    gpsLatitude = observation.gpsLatitude,
                    gpsLongitude = observation.gpsLongitude
                )

                database.updateObservation(
                    clientId = observation.clientId,
                    serverId = response.observationId,
                    syncStatus = "synced"
                )
            } catch (e: Exception) {
                database.updateStatus(observation.clientId, "failed")
            }
        }
    }
}
```

---

## ⏱️ Async Polling

```kotlin
suspend fun pollTaskStatus(statusUrl: String): TaskResult {
    var retryCount = 0
    var delaySeconds = 2

    while (retryCount < 30) {  // Max 5 minutes
        val response = apiService.getStatus(statusUrl)

        when (response.status) {
            "completed" -> return TaskResult.Success(response.result)
            "failed" -> return TaskResult.Failure(response.error)
            "processing" -> {
                delay(delaySeconds * 1000L)
                delaySeconds = min(delaySeconds * 2, 30)  // Exponential backoff
                retryCount++
            }
        }
    }

    return TaskResult.Timeout
}
```

---

## 📝 Validation Helpers

```kotlin
object Validators {
    fun validateTimeFormat(time: String): Boolean {
        return time.matches(Regex("""^([0-1][0-9]|2[0-3]):[0-5][0-9]$"""))
    }

    fun validateGpsCoordinates(lat: Double, lon: Double): Boolean {
        return lat in -90.0..90.0 && lon in -180.0..180.0
    }

    fun validateImageFile(file: File, mimeType: String): Boolean {
        val allowedTypes = listOf("image/jpeg", "image/png", "image/webp")
        val maxSize = 5 * 1024 * 1024  // 5MB
        return mimeType in allowedTypes && file.length() <= maxSize
    }

    fun validateAudioFile(file: File, mimeType: String): Boolean {
        val allowedTypes = listOf(
            "audio/webm", "audio/wav", "audio/mpeg", "audio/mp3",
            "audio/ogg", "audio/m4a", "audio/aac", "audio/flac"
        )
        val maxSize = 10 * 1024 * 1024  // 10MB
        return mimeType in allowedTypes && file.length() <= maxSize
    }
}
```

---

## 🎯 Testing Checklist

**Must Test**:
- [ ] GPS coordinate order (send as lat/lon, parse as lon/lat)
- [ ] Audio upload with `audio/mp3` AND `audio/mpeg`
- [ ] approval_id as INTEGER (not UUID)
- [ ] PostGIS point parsing: `"POINT (72.877 19.076)"`
- [ ] Rate limit handling (429 with Retry-After)
- [ ] Offline observation queueing and sync
- [ ] Async task polling with exponential backoff
- [ ] Error response parsing (field vs non-field errors)

---

## 📚 Further Reading

- **Full Contract**: `KOTLIN_FRONTEND_API_CONTRACT.md` (complete API specification)
- **Backend Fixes**: `BACKEND_FIX_CHECKLIST.md` (required backend changes)
- **OpenAPI Integration**: `OPENAPI_CONTRACT_TESTING.md` (automated testing setup)

---

**Quick Reference Version**: 1.0
**Last Updated**: 2025-09-28
**Support**: api@youtility.in