# Migration Guide: Type-Safe API Contracts

**For**: Android/Kotlin and iOS/Swift Teams
**Effective**: October 5, 2025
**Timeline**: 6-week gradual migration
**Status**: Backward compatible (no immediate action required)

---

## Overview

The backend has been enhanced with **comprehensive type-safe contracts** across all API surfaces:

- ✅ **REST v2**: Pydantic-validated requests/responses
- ✅ **WebSocket**: Structured message types
- ✅ **OpenAPI**: Consolidated schema for codegen
- ✅ **Standardized Errors**: Consistent APIResponse envelope

**Impact**: You can now generate type-safe clients automatically instead of manually maintaining data classes.

---

## Migration Timeline

### Week 1-2: **Learning & Setup** (No code changes)

**Actions**:
1. Review this guide
2. Set up codegen tools (OpenAPI Generator, kotlinx.serialization)
3. Test codegen with current staging/dev environment
4. Identify high-risk endpoints to migrate first

**Deliverable**: Working codegen pipeline generating type-safe clients

### Week 3-4: **Adopt v2 Endpoints** (New features)

**Actions**:
1. Migrate to REST v2 endpoints for new features
2. Implement WebSocket with typed messages
3. Test idempotency guarantees with retries
4. Monitor for validation errors

**Deliverable**: New features using type-safe v2 contracts

### Week 5-6: **Gradual v1 → v2 Migration** (Existing features)

**Actions**:
1. Migrate high-traffic endpoints (login, sync) to v2
2. Deprecate manual data classes in favor of generated
3. Add runtime validation on mobile side
4. Remove dead code (old untyped parsers)

**Deliverable**: 80%+ of app using type-safe contracts

### Week 7+: **Complete Migration** (Cleanup)

**Actions**:
1. Migrate remaining v1 usage to v2
2. Remove all manual data classes
3. Enable strict mode (fail on unknown fields)
4. Celebrate! 🎉

---

## Breaking Changes (NONE!)

**Good News**: This release has **ZERO breaking changes**.

- ✅ All existing v1 endpoints continue working
- ✅ Old WebSocket message formats still accepted (dual-path)
- ✅ No schema changes to existing GraphQL queries
- ✅ Backward compatible response structures

**You control the migration pace** - update endpoints as you add features.

---

## Quick Start: Generate REST Client

### 1. Download OpenAPI Schema

```bash
# From staging environment
curl https://staging-api.youtility.in/api/schema/swagger.json \
  -H "Authorization: Bearer YOUR_STAGING_TOKEN" \
  -o openapi.json

# Or from development
curl http://localhost:8000/api/schema/swagger.json > openapi.json
```

### 2. Configure Gradle

Add to `build.gradle.kts`:

```kotlin
plugins {
    kotlin("jvm") version "1.9.20"
    kotlin("plugin.serialization") version "1.9.20"
    id("org.openapi.generator") version "7.0.1"
}

dependencies {
    // Retrofit + kotlinx.serialization
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-kotlinx-serialization:2.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.0")
    implementation("com.squareup.okhttp3:okhttp:4.11.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.11.0")
}

openApiGenerate {
    generatorName.set("kotlin")
    inputSpec.set("$rootDir/openapi.json")
    outputDir.set("$buildDir/generated/openapi")
    apiPackage.set("com.youtility.api")
    modelPackage.set("com.youtility.api.models")
    configOptions.set(mapOf(
        "library" to "jvm-retrofit2",
        "serializationLibrary" to "kotlinx_serialization",
        "dateLibrary" to "java8"
    ))
}

sourceSets {
    main {
        kotlin {
            srcDir("$buildDir/generated/openapi/src/main/kotlin")
        }
    }
}

tasks.named("compileKotlin") {
    dependsOn("openApiGenerate")
}
```

### 3. Generate Client

```bash
./gradlew openApiGenerate
```

**Output**:
```
build/generated/openapi/src/main/kotlin/com/youtility/api/
├── apis/
│   ├── MobileSyncApi.kt       # Voice & batch sync
│   ├── TasksApi.kt
│   ├── AssetsApi.kt
│   └── TicketsApi.kt
└── models/
    ├── VoiceSyncRequest.kt    # Type-safe!
    ├── VoiceSyncResponse.kt
    ├── APIResponse.kt         # Standard envelope
    ├── APIError.kt
    └── ...
```

### 4. Use Generated Client

```kotlin
// OLD WAY (manual data classes, error-prone)
data class VoiceSync(val deviceId: String, val voiceData: List<Any>)  // ❌ Untyped

val json = JSONObject()
json.put("device_id", deviceId)
json.put("voice_data", voiceDataArray)
// Manual parsing, no compile-time safety

// NEW WAY (generated, type-safe)
val request = VoiceSyncRequest(
    deviceId = "android-123",
    voiceData = listOf(
        VoiceDataItem(
            verificationId = "ver-001",
            timestamp = Instant.now(),
            verified = true,
            confidenceScore = 0.95  // ✅ Type-safe (Float)
        )
    ),
    timestamp = Instant.now(),
    idempotencyKey = UUID.randomUUID().toString()
)

val response = syncApi.syncVoice(request)  // ✅ Type-safe call
when (response.data?.status) {
    "success" -> handleSuccess(response.data.syncedCount)
    "failed" -> handleErrors(response.errors)
}
```

---

## Standard Response Envelope

**ALL responses now use this structure**:

```json
{
  "success": true,
  "data": { /* Your actual data */ },
  "errors": null,
  "meta": {
    "request_id": "abc-123",
    "timestamp": "2025-10-05T12:00:00Z",
    "version": "1.0",
    "execution_time_ms": 25.5
  }
}
```

**Error responses**:

```json
{
  "success": false,
  "data": null,
  "errors": [
    {
      "field": "device_id",
      "message": "Device ID must be at least 5 characters",
      "code": "VALIDATION_ERROR",
      "details": null
    }
  ],
  "meta": {
    "request_id": "abc-456",
    "timestamp": "2025-10-05T12:01:00Z"
  }
}
```

**Kotlin mapping**:

```kotlin
@Serializable
data class APIResponse<T>(
    val success: Boolean,
    val data: T? = null,
    val errors: List<APIError>? = null,
    val meta: APIMeta
)

@Serializable
data class APIError(
    val field: String,
    val message: String,
    val code: String,
    val details: Map<String, JsonElement>? = null
)

// Usage
val response = syncApi.syncVoice(request)
if (response.success) {
    val syncedCount = response.data?.syncedCount ?: 0
    updateUI(syncedCount)
} else {
    response.errors?.forEach { error ->
        showFieldError(error.field, error.message)
    }
}
```

---

## WebSocket Migration

### OLD: Untyped Messages

```kotlin
// ❌ OLD: Manual JSON parsing, fragile
val json = JSONObject(message)
val type = json.optString("type")
when (type) {
    "heartbeat" -> {
        val timestamp = json.optString("timestamp")  // ❌ Could be null, wrong type
        handleHeartbeat(timestamp)
    }
    "server_data" -> {
        val data = json.optJSONArray("data")  // ❌ No type safety
        handleData(data)
    }
}
```

### NEW: Type-Safe Sealed Classes

```kotlin
// ✅ NEW: Copy from docs/api-contracts/WebSocketMessage.kt.example
@Serializable
sealed class WebSocketMessage {
    abstract val type: String

    @Serializable
    @SerialName("heartbeat")
    data class Heartbeat(
        override val type: String = "heartbeat",
        val timestamp: Instant
    ) : WebSocketMessage()

    @Serializable
    @SerialName("server_data")
    data class ServerData(
        override val type: String = "server_data",
        val domain: String,
        val data: List<JsonObject>,
        @SerialName("server_timestamp") val serverTimestamp: Instant
    ) : WebSocketMessage()
}

// Usage
val json = Json { ignoreUnknownKeys = true }
val message = json.decodeFromString<WebSocketMessage>(rawMessage)

when (message) {
    is WebSocketMessage.Heartbeat -> {
        handleHeartbeat(message.timestamp)  // ✅ Type-safe Instant
    }
    is WebSocketMessage.ServerData -> {
        message.data.forEach { item ->  // ✅ Type-safe iteration
            processItem(message.domain, item)
        }
    }
    // Compile error if you forget a type!
}
```

---

## Error Handling Migration

### OLD: Inconsistent Error Parsing

```kotlin
// ❌ OLD: Different error shapes per endpoint
try {
    val response = api.syncVoice(...)
} catch (e: HttpException) {
    when (e.code()) {
        400 -> {
            // Parse error manually, structure varies
            val error = JSONObject(e.message())
            val msg = error.optString("msg")  // ❌ Field name varies
            showError(msg)
        }
    }
}
```

### NEW: Standard Error Model

```kotlin
// ✅ NEW: Consistent APIResponse<T> everywhere
val response = syncApi.syncVoice(request)  // Returns APIResponse<VoiceSyncResponse>

if (!response.success) {
    response.errors?.forEach { error ->
        when (error.code) {
            "VALIDATION_ERROR" -> showFieldError(error.field, error.message)
            "RATE_LIMIT_EXCEEDED" -> scheduleRetry(error.details?.get("retry_after"))
            "AUTHENTICATION_REQUIRED" -> redirectToLogin()
            else -> showGenericError(error.message)
        }
    }
} else {
    val data = response.data!!  // ✅ Safe to unwrap when success=true
    updateUI(data.syncedCount)
}
```

---

## Idempotency for Retries

**NEW**: All v2 endpoints support `Idempotency-Key` header.

```kotlin
class RetryPolicy(private val api: MobileSyncApi) {
    suspend fun syncVoiceWithRetry(request: VoiceSyncRequest): APIResponse<VoiceSyncResponse> {
        val idempotencyKey = request.idempotencyKey ?: UUID.randomUUID().toString()

        return retry(maxAttempts = 3) {
            api.syncVoice(
                request.copy(idempotencyKey = idempotencyKey)
            )
        }
    }

    private suspend fun <T> retry(maxAttempts: Int, block: suspend () -> T): T {
        repeat(maxAttempts) { attempt ->
            try {
                return block()
            } catch (e: IOException) {
                if (attempt == maxAttempts - 1) throw e
                delay(2000L * (attempt + 1))  // Exponential backoff
            }
        }
        throw IllegalStateException("Retry logic error")
    }
}

// Benefits:
// - Same idempotency_key = Same response (within 24 hours)
// - Network retries are safe
// - No duplicate operations
```

---

## Testing Your Migration

### 1. Verify Generated Code Compiles

```bash
./gradlew compileKotlin
# Should succeed with no errors
```

### 2. Compare Old vs New

```kotlin
// Test side-by-side
@Test
fun `old and new endpoints return same data`() = runTest {
    val oldResponse = oldApi.syncVoiceLegacy(jsonPayload)
    val newResponse = newApi.syncVoice(typedRequest)

    // Should match
    assertEquals(oldResponse.syncedCount, newResponse.data?.syncedCount)
}
```

### 3. Monitor Validation Errors

Add analytics to track validation failures:

```kotlin
try {
    val message = Json.decodeFromString<WebSocketMessage>(raw)
    handleMessage(message)
} catch (e: SerializationException) {
    // Log to analytics
    analytics.track("websocket_parse_error", mapOf(
        "raw_type" to raw.substring(0, 100),
        "error" to e.message
    ))
    // Fallback to legacy parser
    handleLegacyMessage(JSONObject(raw))
}
```

---

## Common Migration Patterns

### Pattern 1: Retrofit Call Signature

```kotlin
// OLD
@POST("api/v2/sync/voice/")
suspend fun syncVoice(@Body payload: Map<String, Any>): Response<Any>

// NEW (generated)
@POST("api/v2/sync/voice/")
suspend fun syncVoice(@Body voiceSyncRequest: VoiceSyncRequest): APIResponse<VoiceSyncResponse>
```

### Pattern 2: Response Handling

```kotlin
// OLD
val response = api.syncVoice(mapOf("device_id" to deviceId, ...))
val body = response.body() as? Map<String, Any>
val status = body?.get("status") as? String  // ❌ Unsafe cast

// NEW
val response = api.syncVoice(VoiceSyncRequest(deviceId = deviceId, ...))
if (response.success) {
    val status = response.data?.status  // ✅ Type-safe String?
}
```

### Pattern 3: Enum Handling

```kotlin
// OLD
val priority = "HIGH"  // ❌ String literal, typos possible

// NEW
val priority = TaskPriority.HIGH  // ✅ Compile-time checked enum
```

---

## Rollback Plan (if needed)

If issues arise, you can rollback without backend changes:

1. **Keep old parsers**: Maintain legacy code for 6 weeks
2. **Feature flags**: Toggle new/old paths at runtime
3. **Monitoring**: Track adoption metrics
4. **Gradual rollout**: 10% → 50% → 100% of users

```kotlin
object FeatureFlags {
    val USE_TYPE_SAFE_API = RemoteConfig.getBoolean("use_type_safe_api", false)
}

suspend fun syncVoice(request: VoiceSyncRequest) {
    return if (FeatureFlags.USE_TYPE_SAFE_API) {
        newApi.syncVoice(request)  // Type-safe
    } else {
        oldApi.syncVoiceLegacy(request.toMap())  // Legacy
    }
}
```

---

## Support & Resources

### Documentation

- **Codegen Guide**: `docs/mobile/kotlin-codegen-guide.md`
- **WebSocket Contracts**: `docs/api-contracts/websocket-messages.json`
- **Kotlin Example**: `docs/api-contracts/WebSocketMessage.kt.example`

### API Endpoints

- **OpenAPI Schema**: `https://staging-api.youtility.in/api/schema/swagger.json`
- **Swagger UI**: `https://staging-api.youtility.in/api/schema/swagger/`
- **Schema Metadata**: `https://staging-api.youtility.in/api/schema/metadata/`

### Testing Environments

| Environment | Base URL | Purpose |
|------------|----------|---------|
| Development | `http://localhost:8000` | Local testing |
| Staging | `https://staging-api.youtility.in` | Integration testing |
| Production | `https://api.youtility.in` | Production |

### Support Channels

- **Slack**: `#mobile-backend-integration`
- **Email**: `api-support@youtility.in`
- **Issues**: Create GitHub issue with `[Mobile Contract]` prefix

---

## Frequently Asked Questions

### Q: Do I need to migrate all endpoints at once?

**A**: No! Migrate gradually. New features can use v2, existing features can stay on v1 until you're ready.

### Q: What if the generated code doesn't compile?

**A**: Report it! This indicates a schema issue we need to fix. Provide:
- OpenAPI schema version
- Generated file that fails
- Compiler error message

### Q: Can I customize the generated models?

**A**: Avoid customizing generated code. Instead:
- Add extension functions in separate files
- Wrap generated models in domain models
- Use mappers/adapters pattern

### Q: How do I handle unknown fields in responses?

**A**: Configure `kotlinx.serialization`:

```kotlin
val json = Json {
    ignoreUnknownKeys = true  // ✅ Forward compatibility
    coerceInputValues = true  // ✅ Handle type mismatches gracefully
}
```

### Q: Will old API versions be deprecated?

**A**: v1 will remain supported for 6 months minimum. Deprecation timeline:

- **Oct 2025**: v2 available, v1 fully supported
- **Jan 2026**: v1 marked deprecated (still works)
- **Apr 2026**: v1 sunset warnings (still works)
- **Jul 2026**: v1 removed (migrate by this date)

---

## Next Steps

1. **This Week**: Review this guide and set up codegen
2. **Next Week**: Test codegen with one endpoint (e.g., voice sync)
3. **Week 3**: Plan migration strategy with your team
4. **Week 4**: Begin gradual migration of new features

**Questions?** Reach out to the backend team - we're here to help!

---

**Last Updated**: October 5, 2025
**Backend Contact**: api@youtility.in
**Slack**: #mobile-backend-integration
