# Kotlin API Client Generation Guide

Comprehensive guide for generating type-safe Kotlin clients from YOUTILITY5 backend contracts.

---

## Table of Contents

1. [Overview](#overview)
2. [REST API (OpenAPI)](#rest-api-openapi)
3. [GraphQL API (Apollo)](#graphql-api-apollo)
4. [WebSocket Messages](#websocket-messages)
5. [Error Handling](#error-handling)
6. [Testing](#testing)

---

## Overview

YOUTILITY5 provides three API surfaces with full type-safe Kotlin codegen support:

| API Type | Protocol | Schema Format | Codegen Tool |
|----------|----------|---------------|--------------|
| REST v1/v2 | HTTP/HTTPS | OpenAPI 3.0 | openapi-generator-cli |
| GraphQL | HTTP/HTTPS | GraphQL SDL | Apollo Kotlin |
| WebSocket | WebSocket | JSON Schema | kotlinx-serialization |

**Benefits:**
- ✅ Compile-time type safety
- ✅ Auto-generated data classes
- ✅ IDE autocomplete
- ✅ Breaking change detection
- ✅ Reduced runtime errors

---

## REST API (OpenAPI)

### 1. Download OpenAPI Schema

```bash
# From server (requires authentication)
curl http://localhost:8000/api/schema/download/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o openapi.json

# Or from repository (if committed)
cp backend/docs/api-contracts/openapi.json .
```

### 2. Configure Gradle Build

Add OpenAPI Generator plugin to your `build.gradle.kts`:

```kotlin
plugins {
    kotlin("jvm") version "1.9.20"
    kotlin("plugin.serialization") version "1.9.20"
    id("org.openapi.generator") version "7.0.1"
}

dependencies {
    // Generated client dependencies
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-kotlinx-serialization:2.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.0")
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
        "dateLibrary" to "java8",
        "enumPropertyNaming" to "UPPERCASE"
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

Output:
```
build/generated/openapi/
├── src/main/kotlin/com/youtility/api/
│   ├── apis/
│   │   ├── SyncApi.kt              # Voice & batch sync operations
│   │   ├── TaskApi.kt
│   │   └── ...
│   └── models/
│       ├── VoiceSyncRequest.kt     # Type-safe request models
│       ├── VoiceSyncResponse.kt    # Type-safe response models
│       ├── BatchSyncRequest.kt
│       └── ...
```

### 4. Use Generated Client

```kotlin
import com.youtility.api.apis.SyncApi
import com.youtility.api.models.*
import kotlinx.coroutines.runBlocking
import retrofit2.Retrofit
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor

class YoutilityClient(
    private val baseUrl: String,
    private val authToken: String
) {
    private val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        })
        .addInterceptor { chain ->
            val request = chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $authToken")
                .build()
            chain.proceed(request)
        }
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(baseUrl)
        .client(okHttpClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    val syncApi: SyncApi = retrofit.create(SyncApi::class.java)

    // Type-safe voice sync
    suspend fun syncVoice(deviceId: String, voiceData: List<VoiceDataItem>): VoiceSyncResponse {
        val request = VoiceSyncRequest(
            deviceId = deviceId,
            voiceData = voiceData,
            timestamp = Instant.now(),
            idempotencyKey = UUID.randomUUID().toString()
        )
        return syncApi.syncVoice(request)
    }
}

// Usage
fun main() = runBlocking {
    val client = YoutilityClient(
        baseUrl = "https://api.youtility.in",
        authToken = "your_jwt_token"
    )

    val response = client.syncVoice(
        deviceId = "android-123",
        voiceData = listOf(
            VoiceDataItem(
                verificationId = "ver-001",
                timestamp = Instant.now(),
                verified = true,
                confidenceScore = 0.95
            )
        )
    )

    println("Synced: ${response.syncedCount} items")
}
```

---

## GraphQL API (Apollo)

### 1. Configure Apollo Kotlin

Add to `build.gradle.kts`:

```kotlin
plugins {
    id("com.apollographql.apollo3") version "3.8.2"
}

dependencies {
    implementation("com.apollographql.apollo3:apollo-runtime:3.8.2")
    implementation("com.apollographql.apollo3:apollo-normalized-cache-sqlite:3.8.2")
}

apollo {
    service("youtility") {
        packageName.set("com.youtility.graphql")
        schemaFile.set(file("src/main/graphql/schema.graphqls"))
        generateKotlinModels.set(true)
        codegenModels.set("operationBased")
    }
}
```

### 2. Download GraphQL Schema

```bash
# Using Apollo CLI
npx apollo client:download-schema \
  --endpoint=http://localhost:8000/api/graphql/ \
  --header="Authorization: Bearer YOUR_TOKEN" \
  app/src/main/graphql/schema.graphqls

# Or using GraphQL introspection query
curl http://localhost:8000/api/graphql/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"query":"query IntrospectionQuery { __schema { types { name } } }"}' \
  > schema.graphqls
```

### 3. Write GraphQL Queries

Create `app/src/main/graphql/SyncVoiceData.graphql`:

```graphql
mutation SyncVoiceData($input: [VoiceDataInput!]!, $idempotencyKey: String!, $deviceId: String!) {
  syncVoiceData(
    data: $input
    idempotencyKey: $idempotencyKey
    deviceId: $deviceId
  ) {
    status
    syncedCount
    conflictCount
    results {
      verificationId
      status
      serverId
    }
    serverTimestamp
  }
}
```

### 4. Generate Types

```bash
./gradlew generateApolloSources
```

### 5. Use Generated Client

```kotlin
import com.apollographql.apollo3.ApolloClient
import com.apollographql.apollo3.api.Optional
import com.apollographql.apollo3.cache.normalized.normalizedCache
import com.apollographql.apollo3.cache.normalized.sql.SqlNormalizedCacheFactory
import com.youtility.graphql.SyncVoiceDataMutation
import com.youtility.graphql.type.VoiceDataInput
import kotlinx.coroutines.runBlocking

class GraphQLClient(
    private val serverUrl: String,
    private val authToken: String,
    context: Context
) {
    private val apolloClient = ApolloClient.Builder()
        .serverUrl(serverUrl)
        .addHttpHeader("Authorization", "Bearer $authToken")
        .normalizedCache(SqlNormalizedCacheFactory(context, "youtility.db"))
        .build()

    suspend fun syncVoiceData(
        deviceId: String,
        voiceData: List<VoiceDataInput>,
        idempotencyKey: String
    ): SyncVoiceDataMutation.Data {
        val response = apolloClient.mutation(
            SyncVoiceDataMutation(
                input = voiceData,
                idempotencyKey = idempotencyKey,
                deviceId = deviceId
            )
        ).execute()

        return response.dataOrThrow()
    }
}
```

---

## WebSocket Messages

### 1. Add Dependencies

```kotlin
dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.0")
    implementation("com.squareup.okhttp3:okhttp:4.11.0")
}
```

### 2. Copy Message Types

Copy the Kotlin sealed class from `docs/api-contracts/WebSocketMessage.kt.example` to your project:

```
app/src/main/kotlin/com/youtility/websocket/WebSocketMessage.kt
```

### 3. Implement WebSocket Client

```kotlin
import okhttp3.*
import kotlinx.serialization.json.Json
import kotlinx.serialization.encodeToString
import kotlinx.serialization.decodeFromString

class YoutilityWebSocket(
    private val url: String,
    private val authToken: String,
    private val deviceId: String,
    private val onMessage: (WebSocketMessage) -> Unit
) {
    private val json = Json {
        ignoreUnknownKeys = true
    }

    private var webSocket: WebSocket? = null
    private val client = OkHttpClient()

    fun connect() {
        val request = Request.Builder()
            .url("$url?device_id=$deviceId")
            .addHeader("Authorization", "Bearer $authToken")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val message = json.decodeFromString<WebSocketMessage>(text)
                    onMessage(message)
                } catch (e: Exception) {
                    Log.e("WS", "Failed to parse message: ${e.message}")
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("WS", "Connection failed: ${t.message}")
            }
        })
    }

    fun send(message: WebSocketMessage) {
        val json = json.encodeToString(message)
        webSocket?.send(json)
    }

    fun disconnect() {
        webSocket?.close(1000, "Client disconnect")
    }
}

// Usage
val ws = YoutilityWebSocket(
    url = "wss://api.youtility.in/ws/mobile/sync",
    authToken = jwtToken,
    deviceId = "android-123"
) { message ->
    when (message) {
        is WebSocketMessage.ConnectionEstablished -> {
            Log.d("WS", "Connected: ${message.userId}")
        }
        is WebSocketMessage.ServerData -> {
            processServerData(message.data)
        }
        is WebSocketMessage.Error -> {
            handleError(message.errorCode, message.message)
        }
        else -> Log.d("WS", "Received: ${message.type}")
    }
}

ws.connect()
```

---

## Error Handling

### Standard Error Response (REST)

```kotlin
data class ApiError(
    val status: String,
    val errors: Map<String, List<String>>
)

// Handle errors
try {
    val response = syncApi.syncVoice(request)
    // Success
} catch (e: HttpException) {
    if (e.code() == 400) {
        val error = json.decodeFromString<ApiError>(e.response()?.errorBody()?.string() ?: "")
        // Display validation errors
        error.errors.forEach { (field, messages) ->
            println("$field: ${messages.joinToString()}")
        }
    }
}
```

### GraphQL Errors

```kotlin
val response = apolloClient.query(MyQuery()).execute()

if (response.hasErrors()) {
    response.errors?.forEach { error ->
        when (error.message) {
            "Authentication required" -> redirectToLogin()
            else -> showError(error.message)
        }
    }
}
```

---

## Testing

### Mock Server with OpenAPI

Use Prism or similar tools to mock the API for testing:

```bash
docker run --rm -p 4010:4010 \
  -v $(pwd)/openapi.json:/openapi.json \
  stoplight/prism:latest \
  mock -h 0.0.0.0 /openapi.json
```

### Unit Tests

```kotlin
@Test
fun testVoiceSyncRequest() = runTest {
    val mockApi = mockk<SyncApi>()
    coEvery { mockApi.syncVoice(any()) } returns VoiceSyncResponse(
        status = "success",
        syncedCount = 1,
        conflictCount = 0,
        errorCount = 0,
        results = emptyList(),
        serverTimestamp = Instant.now()
    )

    val client = YoutilityClient(mockApi)
    val response = client.syncVoice("test-device", emptyList())

    assertEquals("success", response.status)
    assertEquals(1, response.syncedCount)
}
```

---

## Continuous Integration

Add to your CI/CD pipeline:

```yaml
# .github/workflows/codegen.yml
name: Verify API Contracts

on: [pull_request]

jobs:
  codegen:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Download OpenAPI Schema
        run: |
          curl http://staging-api.youtility.in/api/schema/download/ \
            -H "Authorization: Bearer ${{ secrets.API_TOKEN }}" \
            -o openapi.json

      - name: Generate Kotlin Client
        run: ./gradlew openApiGenerate

      - name: Compile Generated Code
        run: ./gradlew compileKotlin

      - name: Fail on Breaking Changes
        run: |
          # Compare with previous schema
          diff openapi.json openapi.json.previous || exit 1
```

---

## Resources

- **OpenAPI Schema**: `http://localhost:8000/api/schema/download/`
- **GraphQL Playground**: `http://localhost:8000/api/graphql/`
- **WebSocket Endpoint**: `ws://localhost:8000/ws/mobile/sync`
- **JSON Schemas**: `docs/api-contracts/`

**Support**: For questions or issues, contact the backend team.
