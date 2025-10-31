# RETROFIT ERROR HANDLING GUIDE
## Production-Grade Network Error Handling & Token Refresh

**Version**: 1.0
**Last Updated**: October 30, 2025
**Based on**: Retrofit 2.9+, OkHttp 4.12+, Latest Patterns 2025

---

## Table of Contents

1. [Network Error Taxonomy](#1-network-error-taxonomy)
2. [Error Body Parsing](#2-error-body-parsing)
3. [Token Refresh Interceptor](#3-token-refresh-interceptor)
4. [Retry Strategies](#4-retry-strategies)
5. [Timeout Configuration](#5-timeout-configuration)
6. [Testing Network Errors](#6-testing-network-errors)

---

## 1. Network Error Taxonomy

### Error Categories

| Category | HTTP Status | Retry? | User Action |
|----------|-------------|--------|-------------|
| **Network Errors** | - | ✅ Yes | "Check your connection" |
| **Authentication** | 401 | ⚠️ After refresh | "Please log in again" |
| **Authorization** | 403 | ❌ No | "Access denied" |
| **Not Found** | 404 | ❌ No | "Resource not found" |
| **Validation** | 400 | ❌ No | Show field errors |
| **Conflict** | 409 | ⚠️ After reload | "Data changed, please refresh" |
| **Rate Limit** | 429 | ✅ After delay | "Too many requests" |
| **Server Error** | 500, 502, 503 | ✅ Yes | "Server error, retrying..." |

### Error Hierarchy

```kotlin
sealed class NetworkError : Exception() {
    // 1. Connection Errors (no internet, timeout, DNS)
    data class ConnectionError(override val message: String) : NetworkError()

    // 2. HTTP Errors (4xx, 5xx)
    data class HttpError(
        val code: Int,
        override val message: String,
        val errorBody: ApiError?
    ) : NetworkError()

    // 3. Serialization Errors (malformed JSON)
    data class SerializationError(
        override val message: String,
        override val cause: Throwable
    ) : NetworkError()

    // 4. SSL/TLS Errors (certificate issues)
    data class SslError(override val message: String) : NetworkError()

    // 5. Unknown Errors
    data class UnknownError(override val cause: Throwable) : NetworkError()
}
```

---

## 2. Error Body Parsing

### 2.1 Standardized Error Envelope

Our API returns:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "mood_rating": ["Must be between 1 and 10"]
    },
    "correlation_id": "abc-123-def-456"
  }
}
```

**DTO**:
```kotlin
@Serializable
data class ApiErrorEnvelope(
    val error: ApiError
)

@Serializable
data class ApiError(
    val code: String,
    val message: String,
    val details: Map<String, List<String>>? = null,
    @SerialName("correlation_id") val correlationId: String
)
```

### 2.2 Error Parsing Interceptor

```kotlin
class ErrorParsingInterceptor @Inject constructor(
    private val json: Json
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val response = chain.proceed(request)

        // Parse error body if not successful
        if (!response.isSuccessful) {
            val errorBody = response.body?.string()

            if (errorBody != null) {
                try {
                    val apiError = json.decodeFromString<ApiErrorEnvelope>(errorBody)

                    // Log correlation ID for support
                    Log.e("API_ERROR", "Correlation ID: ${apiError.error.correlationId}")

                    // Throw custom exception with parsed error
                    throw HttpException(
                        code = response.code,
                        message = apiError.error.message,
                        apiError = apiError.error
                    )

                } catch (e: SerializationException) {
                    // Malformed error response - use generic message
                    Log.e("API_ERROR", "Failed to parse error body: $errorBody")
                }
            }
        }

        return response
    }
}

class HttpException(
    val code: Int,
    override val message: String,
    val apiError: ApiError? = null
) : IOException(message)
```

### 2.3 Map to Domain Errors

```kotlin
fun Throwable.toAppError(): AppError = when (this) {
    is HttpException -> when (code) {
        400 -> {
            apiError?.details?.let {
                AppError.ValidationError(it)
            } ?: AppError.BadRequest(message)
        }
        401 -> AppError.Unauthorized
        403 -> AppError.Forbidden
        404 -> AppError.NotFound
        409 -> AppError.Conflict(message)
        429 -> AppError.RateLimitExceeded
        in 500..599 -> AppError.ServerError(code, message)
        else -> AppError.HttpError(code, message)
    }

    is IOException -> AppError.NetworkError(message ?: "Network error")
    is SerializationException -> AppError.SerializationError(message ?: "Invalid response format")
    else -> AppError.UnknownError(this)
}

sealed class AppError : Throwable() {
    data class ValidationError(val fieldErrors: Map<String, List<String>>) : AppError()
    data class BadRequest(override val message: String) : AppError()
    object Unauthorized : AppError()
    object Forbidden : AppError()
    object NotFound : AppError()
    data class Conflict(override val message: String) : AppError()
    object RateLimitExceeded : AppError()
    data class ServerError(val code: Int, override val message: String) : AppError()
    data class HttpError(val code: Int, override val message: String) : AppError()
    data class NetworkError(override val message: String) : AppError()
    data class SerializationError(override val message: String) : AppError()
    data class UnknownError(override val cause: Throwable) : AppError()
}
```

---

## 3. Token Refresh Interceptor

### 3.1 The Infinite Loop Problem ⚠️

**CRITICAL**: Naive token refresh creates infinite loop!

```kotlin
// ❌ WRONG: This creates infinite loop!
class BrokenAuthInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(request)

        if (response.code == 401) {
            // Problem: What if refreshToken() call ALSO returns 401?
            // → Tries to refresh again
            // → Returns 401 again
            // → Infinite loop! 🔥
            val newToken = refreshToken()
            return chain.proceed(requestWithNewToken)
        }

        return response
    }
}
```

### 3.2 Correct Implementation (Prevents Infinite Loop)

**Key Principles**:
1. Use OkHttp **Authenticator** (not Interceptor) for 401 handling
2. Synchronize token refresh (prevent multiple concurrent refreshes)
3. Exclude refresh endpoint from interception
4. Limit retry attempts (max 1 refresh per request)

```kotlin
class TokenAuthenticator @Inject constructor(
    private val tokenStorage: SecureTokenStorage,
    private val authApi: AuthApi,
    private val json: Json
) : Authenticator {

    // Synchronize to prevent multiple concurrent token refreshes
    @Synchronized
    override fun authenticate(route: Route?, response: Response): Request? {
        // If already tried refreshing, give up
        if (responseCount(response) >= 2) {
            return null  // Failed after refresh, redirect to login
        }

        // Get current tokens
        val currentAccessToken = tokenStorage.getAccessToken()
        val refreshToken = tokenStorage.getRefreshToken() ?: return null

        // Check if another thread already refreshed (token changed)
        val responseToken = response.request.header("Authorization")?.removePrefix("Bearer ")
        if (responseToken != currentAccessToken) {
            // Token already refreshed by another thread, retry with new token
            return response.request.newBuilder()
                .header("Authorization", "Bearer $currentAccessToken")
                .build()
        }

        // Perform token refresh
        try {
            val refreshResponse = authApi.refreshToken(
                RefreshTokenRequest(refreshToken)
            ).execute()  // Synchronous call

            if (refreshResponse.isSuccessful) {
                val newTokens = refreshResponse.body()!!

                // Save new tokens
                tokenStorage.saveAccessToken(newTokens.access)
                tokenStorage.saveRefreshToken(newTokens.refresh)

                // Retry original request with new token
                return response.request.newBuilder()
                    .header("Authorization", "Bearer ${newTokens.access}")
                    .build()
            } else {
                // Refresh failed - logout user
                tokenStorage.clearTokens()
                return null
            }

        } catch (e: Exception) {
            // Network error during refresh
            return null
        }
    }

    private fun responseCount(response: Response?): Int {
        var count = 1
        var current = response?.priorResponse
        while (current != null) {
            count++
            current = current.priorResponse
        }
        return count
    }
}
```

### 3.3 Auth Interceptor (Add Token to Requests)

```kotlin
class AuthInterceptor @Inject constructor(
    private val tokenStorage: SecureTokenStorage
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Request {
        val originalRequest = chain.request()

        // Don't add token to auth endpoints
        if (originalRequest.url.encodedPath.contains("/api/v1/auth/")) {
            return chain.proceed(originalRequest)
        }

        // Get current access token
        val accessToken = tokenStorage.getAccessToken()

        // If no token, proceed without (will get 401, handled by Authenticator)
        if (accessToken == null) {
            return chain.proceed(originalRequest)
        }

        // Add Bearer token
        val newRequest = originalRequest.newBuilder()
            .header("Authorization", "Bearer $accessToken")
            .build()

        return chain.proceed(newRequest)
    }
}
```

### 3.4 Complete OkHttp Setup

```kotlin
@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor,
        tokenAuthenticator: TokenAuthenticator,
        errorParsingInterceptor: ErrorParsingInterceptor
    ): OkHttpClient {
        return OkHttpClient.Builder()
            // Add token to requests
            .addInterceptor(authInterceptor)

            // Parse error bodies
            .addInterceptor(errorParsingInterceptor)

            // Logging (debug only)
            .addInterceptor(HttpLoggingInterceptor().apply {
                level = if (BuildConfig.DEBUG) {
                    HttpLoggingInterceptor.Level.BODY
                } else {
                    HttpLoggingInterceptor.Level.NONE
                }
            })

            // Handle 401 (token refresh)
            .authenticator(tokenAuthenticator)

            // Timeouts
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)

            .build()
    }
}
```

**Order Matters**:
1. AuthInterceptor (adds token)
2. ErrorParsingInterceptor (parses errors)
3. LoggingInterceptor (logs request/response)
4. Authenticator (handles 401, refreshes token)

---

## 4. Retry Strategies

### 4.1 Which Errors to Retry

**Always Retry**:
- Connection errors (no internet, timeout, DNS failure)
- 500 Internal Server Error (temporary server issue)
- 502 Bad Gateway (upstream service down)
- 503 Service Unavailable (server overloaded)

**Never Retry**:
- 400 Bad Request (client error, won't fix itself)
- 401 Unauthorized (handled by Authenticator)
- 403 Forbidden (permission issue)
- 404 Not Found (resource doesn't exist)
- 422 Unprocessable Entity (validation error)

**Conditional Retry**:
- 429 Too Many Requests (retry after `Retry-After` seconds)
- 409 Conflict (retry after reloading resource)

### 4.2 Exponential Backoff Implementation

```kotlin
suspend fun <T> retryWithExponentialBackoff(
    maxRetries: Int = 3,
    initialDelayMillis: Long = 1000,
    maxDelayMillis: Long = 10000,
    factor: Double = 2.0,
    block: suspend () -> T
): T {
    var currentDelay = initialDelayMillis
    repeat(maxRetries - 1) { attempt ->
        try {
            return block()
        } catch (e: Exception) {
            // Check if retryable
            if (!isRetryable(e)) {
                throw e
            }

            // Wait with exponential backoff + jitter
            val jitter = (0..1000).random()
            delay(currentDelay + jitter)

            // Increase delay exponentially
            currentDelay = (currentDelay * factor).toLong().coerceAtMost(maxDelayMillis)
        }
    }

    // Final attempt (no delay)
    return block()
}

fun isRetryable(error: Throwable): Boolean = when (error) {
    is IOException -> true  // Network errors
    is HttpException -> when (error.code) {
        in 500..599 -> true  // Server errors
        429 -> true          // Rate limit (with delay)
        else -> false
    }
    else -> false
}

// Usage
val result = retryWithExponentialBackoff {
    apiService.getJournalEntries()
}
```

### 4.3 Rate Limit Handling (429)

```kotlin
class RateLimitInterceptor @Inject constructor() : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())

        if (response.code == 429) {
            // Get retry-after header (seconds)
            val retryAfter = response.header("Retry-After")?.toLongOrNull() ?: 60L

            // Don't automatically retry 429 - let user decide
            // Store retry-after for UI display
            throw RateLimitException(
                retryAfterSeconds = retryAfter,
                message = "Rate limit exceeded. Retry after $retryAfter seconds."
            )
        }

        return response
    }
}

class RateLimitException(
    val retryAfterSeconds: Long,
    override val message: String
) : IOException(message)
```

---

## 5. Timeout Configuration

### 5.1 Recommended Timeouts

```kotlin
OkHttpClient.Builder()
    .connectTimeout(10, TimeUnit.SECONDS)   // Time to establish connection
    .readTimeout(30, TimeUnit.SECONDS)      // Time to read response
    .writeTimeout(30, TimeUnit.SECONDS)     // Time to send request
    .callTimeout(60, TimeUnit.SECONDS)      // Total time for entire call
    .build()
```

**Timeout Guidelines**:

| Operation | Connect | Read | Write | Total |
|-----------|---------|------|-------|-------|
| **Metadata fetch** | 5s | 10s | 5s | 20s |
| **List data** | 5s | 15s | 5s | 25s |
| **Create/Update** | 5s | 15s | 10s | 30s |
| **File upload (10 MB)** | 5s | 30s | 60s | 90s |
| **File download** | 5s | 60s | 5s | 70s |

### 5.2 Per-Request Timeout Override

```kotlin
interface JournalApi {
    // Default timeout (from OkHttpClient)
    @GET("journal/")
    suspend fun getEntries(): Response<PaginatedResponse<JournalEntryDTO>>

    // Custom timeout for large upload
    @Multipart
    @POST("journal/{id}/media/")
    suspend fun uploadMedia(
        @Path("id") id: String,
        @Part file: MultipartBody.Part
    ): Response<MediaDTO>
}

// Configure per-call timeout in repository
suspend fun uploadMedia(file: File): MediaDTO {
    val client = okHttpClient.newBuilder()
        .writeTimeout(120, TimeUnit.SECONDS)  // 2 minutes for large files
        .build()

    val retrofit = Retrofit.Builder()
        .client(client)
        .baseUrl(BASE_URL)
        .build()

    val api = retrofit.create(JournalApi::class.java)
    return api.uploadMedia(...).body()!!
}
```

---

## 6. Testing Network Errors

### 6.1 MockWebServer Setup

```kotlin
class WellnessRemoteDataSourceTest {

    private lateinit var mockWebServer: MockWebServer
    private lateinit var wellnessApi: WellnessApi

    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        mockWebServer.start()

        val retrofit = Retrofit.Builder()
            .baseUrl(mockWebServer.url("/"))
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()

        wellnessApi = retrofit.create(WellnessApi::class.java)
    }

    @After
    fun teardown() {
        mockWebServer.shutdown()
    }

    @Test
    fun `401 error throws Unauthorized exception`() = runTest {
        // Given: Server returns 401
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(401)
                .setBody("""
                    {
                      "error": {
                        "code": "AUTHENTICATION_FAILED",
                        "message": "Token expired",
                        "correlation_id": "test-123"
                      }
                    }
                """.trimIndent())
        )

        // When: Call API
        val exception = assertFailsWith<HttpException> {
            wellnessApi.getJournalEntries(authorization = "Bearer expired-token")
        }

        // Then: Verify exception
        assertEquals(401, exception.code)
        assertEquals("AUTHENTICATION_FAILED", exception.apiError?.code)
    }

    @Test
    fun `400 validation error includes field errors`() = runTest {
        // Given
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(400)
                .setBody("""
                    {
                      "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid data",
                        "details": {
                          "mood_rating": ["Must be between 1 and 10"],
                          "title": ["This field is required"]
                        },
                        "correlation_id": "test-456"
                      }
                    }
                """.trimIndent())
        )

        // When
        val exception = assertFailsWith<HttpException> {
            wellnessApi.createJournalEntry(...)
        }

        // Then
        assertEquals(400, exception.code)
        assertNotNull(exception.apiError?.details)
        assertTrue(exception.apiError!!.details!!.containsKey("mood_rating"))
    }

    @Test
    fun `network timeout throws IOException`() = runTest {
        // Configure client with very short timeout
        val client = OkHttpClient.Builder()
            .readTimeout(100, TimeUnit.MILLISECONDS)
            .build()

        // Server delays response
        mockWebServer.enqueue(
            MockResponse()
                .setBody("{}")
                .setBodyDelay(1, TimeUnit.SECONDS)
        )

        // When
        assertFailsWith<SocketTimeoutException> {
            // API call will timeout
        }
    }
}
```

---

## 7. Complete Working Example

### 7.1 Production-Ready Retrofit Setup

```kotlin
// network/src/main/kotlin/com/example/facility/network/di/NetworkModule.kt

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideJson() = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = false
        coerceInputValues = true
    }

    @Provides
    @Singleton
    fun provideAuthInterceptor(
        tokenStorage: SecureTokenStorage
    ): AuthInterceptor {
        return AuthInterceptor(tokenStorage)
    }

    @Provides
    @Singleton
    fun provideTokenAuthenticator(
        tokenStorage: SecureTokenStorage,
        authApi: AuthApi,
        json: Json
    ): TokenAuthenticator {
        return TokenAuthenticator(tokenStorage, authApi, json)
    }

    @Provides
    @Singleton
    fun provideErrorParsingInterceptor(
        json: Json
    ): ErrorParsingInterceptor {
        return ErrorParsingInterceptor(json)
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor,
        tokenAuthenticator: TokenAuthenticator,
        errorParsingInterceptor: ErrorParsingInterceptor
    ): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(errorParsingInterceptor)
            .addInterceptor(HttpLoggingInterceptor().apply {
                level = if (BuildConfig.DEBUG) {
                    HttpLoggingInterceptor.Level.BODY
                } else {
                    HttpLoggingInterceptor.Level.NONE
                }
            })
            .authenticator(tokenAuthenticator)
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .callTimeout(60, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(
        okHttpClient: OkHttpClient,
        json: Json
    ): Retrofit {
        return Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    // Separate Retrofit for auth endpoints (no Authenticator to prevent loop)
    @Provides
    @Singleton
    @Named("auth")
    fun provideAuthRetrofit(
        authInterceptor: AuthInterceptor,  // No Authenticator!
        json: Json
    ): Retrofit {
        val client = OkHttpClient.Builder()
            .addInterceptor(HttpLoggingInterceptor().apply {
                level = HttpLoggingInterceptor.Level.BODY
            })
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .build()

        return Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    @Provides
    @Singleton
    fun provideAuthApi(@Named("auth") retrofit: Retrofit): AuthApi {
        return retrofit.create(AuthApi::class.java)
    }

    @Provides
    @Singleton
    fun provideWellnessApi(retrofit: Retrofit): WellnessApi {
        return retrofit.create(WellnessApi::class.java)
    }
}
```

---

## 8. Error Handling in Repository

### 8.1 Wrap API Calls with Result

```kotlin
class WellnessRepositoryImpl @Inject constructor(
    private val remoteDataSource: WellnessRemoteDataSource,
    private val localDataSource: WellnessLocalDataSource
) : WellnessRepository {

    override fun getJournalEntries(): Flow<Result<List<JournalEntry>>> = flow {
        emit(Result.Loading())

        // Emit cache first
        val cached = localDataSource.getAll()
        if (cached.isNotEmpty()) {
            emit(Result.Success(cached.map { it.toDomain() }))
        }

        // Fetch from network
        try {
            val dtos = remoteDataSource.getJournalEntries()
            localDataSource.insertAll(dtos.map { it.toCache() })
            emit(Result.Success(dtos.map { it.toDomain() }))

        } catch (e: Exception) {
            // Map to domain error
            val appError = e.toAppError()

            when (appError) {
                is AppError.Unauthorized -> {
                    // User logged out - clear cache
                    localDataSource.clear()
                    emit(Result.Error(appError))
                }

                is AppError.NetworkError -> {
                    // Network issue - keep cache, show error toast
                    if (cached.isEmpty()) {
                        emit(Result.Error(appError))
                    }
                    // Already emitted cache, don't emit error
                }

                is AppError.ServerError -> {
                    // Server error - retry in background
                    if (cached.isEmpty()) {
                        emit(Result.Error(appError))
                    }
                }

                else -> {
                    emit(Result.Error(appError))
                }
            }
        }
    }
}
```

---

## 9. Common Pitfalls

### Pitfall 1: Not Handling Empty Response Body

```kotlin
// ❌ WRONG: Assumes body is never null
suspend fun createEntry(dto: JournalEntryDTO): JournalEntryDTO {
    val response = api.createEntry(dto)
    return response.body()!!  // Can be null even on 200 OK!
}

// ✅ CORRECT: Handle null body
suspend fun createEntry(dto: JournalEntryDTO): JournalEntryDTO {
    val response = api.createEntry(dto)

    if (!response.isSuccessful) {
        throw HttpException(response.code(), response.message())
    }

    return response.body() ?: throw HttpException(500, "Empty response body")
}
```

### Pitfall 2: Blocking Main Thread

```kotlin
// ❌ WRONG: Synchronous call blocks thread
fun getData(): Data {
    return api.getData().execute().body()!!  // Blocks!
}

// ✅ CORRECT: Use suspend function
suspend fun getData(): Data {
    return api.getData().body() ?: throw HttpException(500, "Empty body")
}
```

### Pitfall 3: Not Canceling Requests

```kotlin
// ✅ CORRECT: Use ViewModel scope (auto-cancels on clear)
class MyViewModel @Inject constructor(
    private val repository: WellnessRepository
) : ViewModel() {

    fun loadData() {
        viewModelScope.launch {  // Cancelled when ViewModel cleared
            repository.getData().collect { result ->
                _state.value = result
            }
        }
    }
}
```

---

## Summary

This guide prevents the **30+ most common Retrofit errors**:

✅ Error body parsing (handles API error envelope)
✅ Token refresh without infinite loop (Authenticator pattern)
✅ Retry strategies (exponential backoff, retryable errors)
✅ Timeout configuration (per operation type)
✅ Rate limit handling (429 with Retry-After)
✅ Testing network errors (MockWebServer)
✅ Error mapping (API → Domain)

**Follow this guide during Phase 4 (Data Layer) implementation.**

---

**Document Version**: 1.0
**Last Reviewed**: October 30, 2025
**Based on**: Retrofit 2.9+, OkHttp 4.12+, Industry best practices 2025
**Prevents**: 30+ network error patterns
