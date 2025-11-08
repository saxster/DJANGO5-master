# Cross-Cutting Concerns for Kotlin/Android Frontend

> **Essential patterns that span all domains**: Observability, error handling, caching, file uploads, analytics

---

## Table of Contents

1. [Authentication & Authorization](#authentication--authorization)
2. [Error Handling Patterns](#error-handling-patterns)
3. [Logging & Observability](#logging--observability)
4. [Network & File Upload](#network--file-upload)
5. [Caching Strategy](#caching-strategy)
6. [Analytics & Tracking](#analytics--tracking)
7. [Background Processing](#background-processing)
8. [Security Best Practices](#security-best-practices)

---

## Authentication & Authorization

### JWT Token Management

#### Token Storage (Android KeyStore)

```kotlin
// Core/Security/TokenManager.kt
class TokenManager(private val context: Context) {
    private val keyStore: KeyStore = KeyStore.getInstance("AndroidKeyStore").apply {
        load(null)
    }
    
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()
    
    private val sharedPreferences = EncryptedSharedPreferences.create(
        context,
        "auth_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    
    fun saveTokens(accessToken: String, refreshToken: String, expiresIn: Long) {
        val expiryTime = System.currentTimeMillis() + (expiresIn * 1000)
        
        sharedPreferences.edit {
            putString(KEY_ACCESS_TOKEN, accessToken)
            putString(KEY_REFRESH_TOKEN, refreshToken)
            putLong(KEY_EXPIRY_TIME, expiryTime)
        }
    }
    
    fun getAccessToken(): String? {
        val token = sharedPreferences.getString(KEY_ACCESS_TOKEN, null)
        val expiryTime = sharedPreferences.getLong(KEY_EXPIRY_TIME, 0)
        
        // Check if token expired or expires in < 5 minutes
        if (System.currentTimeMillis() + (5 * 60 * 1000) >= expiryTime) {
            return null  // Trigger refresh
        }
        
        return token
    }
    
    fun clearTokens() {
        sharedPreferences.edit().clear().apply()
    }
    
    companion object {
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
        private const val KEY_EXPIRY_TIME = "expiry_time"
    }
}
```

#### Automatic Token Refresh

```kotlin
// Network/TokenAuthenticator.kt
class TokenAuthenticator(
    private val tokenManager: TokenManager,
    private val authApi: AuthApi
) : Authenticator {
    
    override fun authenticate(route: Route?, response: Response): Request? {
        // Don't retry if we already tried once
        if (response.request.header("Authorization-Retry") != null) {
            return null
        }
        
        synchronized(this) {
            val currentToken = tokenManager.getAccessToken()
            val responseToken = response.request.header("Authorization")?.removePrefix("Bearer ")
            
            // Token was already refreshed by another request
            if (responseToken != currentToken && currentToken != null) {
                return response.request.newBuilder()
                    .header("Authorization", "Bearer $currentToken")
                    .build()
            }
            
            // Refresh token
            val refreshToken = tokenManager.getRefreshToken() ?: return null
            
            val newToken = try {
                authApi.refreshToken(RefreshTokenRequest(refreshToken)).execute()
            } catch (e: IOException) {
                return null
            }
            
            if (!newToken.isSuccessful || newToken.body() == null) {
                // Refresh failed - logout
                tokenManager.clearTokens()
                return null
            }
            
            tokenManager.saveTokens(
                newToken.body()!!.accessToken,
                newToken.body()!!.refreshToken,
                newToken.body()!!.expiresIn
            )
            
            return response.request.newBuilder()
                .header("Authorization", "Bearer ${newToken.body()!!.accessToken}")
                .header("Authorization-Retry", "true")
                .build()
        }
    }
}
```

#### Multi-Tenant Header Injection

```kotlin
// Network/TenantInterceptor.kt
class TenantInterceptor(
    private val tenantProvider: TenantProvider
) : Interceptor {
    
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        
        val tenantId = tenantProvider.getCurrentTenantId()
        val correlationId = UUID.randomUUID().toString()
        
        val newRequest = originalRequest.newBuilder()
            .header("X-Client-ID", tenantId)
            .header("X-Correlation-ID", correlationId)
            .header("X-Device-ID", DeviceUtils.getDeviceId())
            .header("X-App-Version", BuildConfig.VERSION_NAME)
            .build()
        
        return chain.proceed(newRequest)
    }
}
```

---

## Error Handling Patterns

### Standardized Error Response

#### Backend Response Structure

```json
{
  "success": false,
  "data": null,
  "errors": [
    {
      "error_code": "VALIDATION_ERROR",
      "message": "Invalid input data",
      "field": "title",
      "details": "Title must be between 3 and 200 characters"
    },
    {
      "error_code": "GPS_ACCURACY_TOO_LOW",
      "message": "GPS accuracy must be less than 50 meters",
      "field": "location.accuracy",
      "details": "Current accuracy: 85.3m"
    }
  ],
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-11-07T12:34:56Z"
}
```

#### Kotlin Error Models

```kotlin
// Data/Models/ApiResponse.kt
data class ApiResponse<T>(
    val success: Boolean,
    val data: T?,
    val errors: List<ApiError>?,
    val correlation_id: String,
    val timestamp: String,
    val execution_time_ms: Double? = null
)

data class ApiError(
    val error_code: String,
    val message: String,
    val field: String? = null,
    val details: String? = null
)

// Convert to domain errors
fun List<ApiError>.toDomainErrors(): List<DomainError> {
    return map { apiError ->
        when (apiError.error_code) {
            "VALIDATION_ERROR" -> DomainError.ValidationError(
                field = apiError.field ?: "",
                message = apiError.message
            )
            "GPS_ACCURACY_TOO_LOW" -> DomainError.GpsError(apiError.message)
            "FACIAL_RECOGNITION_FAILED" -> DomainError.BiometricError(apiError.message)
            "NETWORK_ERROR" -> DomainError.NetworkError(apiError.message)
            else -> DomainError.UnknownError(apiError.message)
        }
    }
}

sealed class DomainError {
    data class ValidationError(val field: String, val message: String) : DomainError()
    data class GpsError(val message: String) : DomainError()
    data class BiometricError(val message: String) : DomainError()
    data class NetworkError(val message: String) : DomainError()
    data class UnknownError(val message: String) : DomainError()
}
```

#### Error Handling in Repositories

```kotlin
// Data/Repositories/BaseRepository.kt
sealed class Result<out T> {
    data class Success<T>(val data: T) : Result<T>()
    data class Error(val errors: List<DomainError>, val correlationId: String) : Result<Nothing>()
    data class NetworkError(val exception: IOException) : Result<Nothing>()
}

suspend fun <T> safeApiCall(
    correlationIdProvider: () -> String = { UUID.randomUUID().toString() },
    apiCall: suspend () -> Response<ApiResponse<T>>
): Result<T> {
    return try {
        val response = apiCall()
        
        when {
            response.isSuccessful && response.body()?.success == true -> {
                Result.Success(response.body()!!.data!!)
            }
            response.isSuccessful && response.body()?.success == false -> {
                Result.Error(
                    errors = response.body()!!.errors!!.toDomainErrors(),
                    correlationId = response.body()!!.correlation_id
                )
            }
            else -> {
                Result.Error(
                    errors = listOf(DomainError.UnknownError("HTTP ${response.code()}")),
                    correlationId = correlationIdProvider()
                )
            }
        }
    } catch (e: IOException) {
        Result.NetworkError(e)
    }
}
```

---

## Logging & Observability

### Structured Logging with Timber

#### Setup

```kotlin
// Application.kt
class IntelliWizApp : Application() {
    override fun onCreate() {
        super.onCreate()
        
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        } else {
            Timber.plant(CrashlyticsTree())
        }
    }
}

// Utils/Logging/CrashlyticsTree.kt
class CrashlyticsTree : Timber.Tree() {
    override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
        if (priority == Log.VERBOSE || priority == Log.DEBUG) {
            return  // Don't log verbose/debug in production
        }
        
        // Log to Crashlytics
        FirebaseCrashlytics.getInstance().log("$tag: $message")
        
        if (t != null && priority >= Log.ERROR) {
            FirebaseCrashlytics.getInstance().recordException(t)
        }
    }
}
```

#### Correlation ID Logging

```kotlin
// Utils/Logging/LoggingInterceptor.kt
class CorrelationLoggingInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val correlationId = request.header("X-Correlation-ID")
        
        Timber.tag("API").d(
            """
            ┌──────────────────────────────────────────────────────────────────────
            │ Request: ${request.method} ${request.url}
            │ Correlation-ID: $correlationId
            │ Headers: ${request.headers}
            └──────────────────────────────────────────────────────────────────────
            """.trimIndent()
        )
        
        val startTime = System.currentTimeMillis()
        val response = chain.proceed(request)
        val duration = System.currentTimeMillis() - startTime
        
        Timber.tag("API").d(
            """
            ┌──────────────────────────────────────────────────────────────────────
            │ Response: ${response.code} (${duration}ms)
            │ Correlation-ID: $correlationId
            │ Server Time: ${response.header("X-Execution-Time-Ms")}ms
            └──────────────────────────────────────────────────────────────────────
            """.trimIndent()
        )
        
        return response
    }
}
```

### Firebase Performance Monitoring

```kotlin
// Utils/Performance/PerformanceMonitor.kt
object PerformanceMonitor {
    
    fun traceApiCall(endpoint: String, block: () -> Unit) {
        val trace = FirebasePerformance.getInstance().newTrace("api_$endpoint")
        trace.start()
        
        try {
            block()
            trace.incrementMetric("success_count", 1)
        } catch (e: Exception) {
            trace.incrementMetric("failure_count", 1)
            throw e
        } finally {
            trace.stop()
        }
    }
    
    fun traceSync(syncType: String, recordCount: Int, block: () -> Unit) {
        val trace = FirebasePerformance.getInstance().newTrace("sync_$syncType")
        trace.putMetric("record_count", recordCount.toLong())
        trace.start()
        
        try {
            block()
        } finally {
            trace.stop()
        }
    }
}

// Usage in ViewModel
viewModelScope.launch {
    PerformanceMonitor.traceApiCall("checkin") {
        attendanceRepository.checkIn(checkInData)
    }
}
```

---

## Network & File Upload

### Photo Upload with Compression

#### Compression Utilities

```kotlin
// Utils/ImageUtils.kt
object ImageUtils {
    
    /**
     * Compress image to target size and dimensions
     * 
     * @param file Original image file
     * @param maxSizeBytes Maximum file size (default 5MB)
     * @param quality JPEG quality 0-100 (default 85)
     * @param maxDimension Maximum width/height (default 1920)
     * @return Compressed file
     */
    fun compressImage(
        file: File,
        maxSizeBytes: Long = 5 * 1024 * 1024,  // 5MB
        quality: Int = 85,
        maxDimension: Int = 1920
    ): File {
        val bitmap = BitmapFactory.decodeFile(file.path)
        
        // Calculate scaling
        val scale = minOf(
            maxDimension.toFloat() / bitmap.width,
            maxDimension.toFloat() / bitmap.height,
            1f
        )
        
        val scaledBitmap = if (scale < 1f) {
            Bitmap.createScaledBitmap(
                bitmap,
                (bitmap.width * scale).toInt(),
                (bitmap.height * scale).toInt(),
                true
            )
        } else {
            bitmap
        }
        
        // Fix orientation from EXIF
        val orientedBitmap = fixOrientation(file.path, scaledBitmap)
        
        // Compress to file
        val compressedFile = File.createTempFile("compressed_", ".jpg")
        var currentQuality = quality
        
        do {
            compressedFile.outputStream().use { out ->
                orientedBitmap.compress(Bitmap.CompressFormat.JPEG, currentQuality, out)
            }
            currentQuality -= 5
        } while (compressedFile.length() > maxSizeBytes && currentQuality > 20)
        
        return compressedFile
    }
    
    private fun fixOrientation(imagePath: String, bitmap: Bitmap): Bitmap {
        val exif = ExifInterface(imagePath)
        val orientation = exif.getAttributeInt(
            ExifInterface.TAG_ORIENTATION,
            ExifInterface.ORIENTATION_NORMAL
        )
        
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            else -> return bitmap
        }
        
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    }
    
    /**
     * Strip EXIF data except timestamp
     */
    fun stripExif(file: File): File {
        val exif = ExifInterface(file.path)
        val timestamp = exif.getAttribute(ExifInterface.TAG_DATETIME)
        
        // Clear all EXIF
        exif.setAttribute(ExifInterface.TAG_GPS_LATITUDE, null)
        exif.setAttribute(ExifInterface.TAG_GPS_LONGITUDE, null)
        exif.setAttribute(ExifInterface.TAG_MAKE, null)
        exif.setAttribute(ExifInterface.TAG_MODEL, null)
        
        // Restore timestamp
        if (timestamp != null) {
            exif.setAttribute(ExifInterface.TAG_DATETIME, timestamp)
        }
        
        exif.saveAttributes()
        return file
    }
}
```

#### Multipart Upload

```kotlin
// Data/Api/FileUploadApi.kt
interface FileUploadApi {
    
    @Multipart
    @POST("api/v2/operations/attachments/upload/")
    suspend fun uploadAttachment(
        @Part("job_id") jobId: RequestBody,
        @Part("description") description: RequestBody,
        @Part file: MultipartBody.Part,
        @Part("metadata") metadata: RequestBody
    ): Response<ApiResponse<AttachmentResponse>>
}

// Repository implementation
suspend fun uploadJobPhoto(
    jobId: Long,
    photoFile: File,
    description: String
): Result<Attachment> {
    // Compress image
    val compressedFile = ImageUtils.compressImage(
        file = photoFile,
        maxSizeBytes = 5 * 1024 * 1024,
        quality = 85,
        maxDimension = 1920
    )
    
    // Strip EXIF
    val sanitizedFile = ImageUtils.stripExif(compressedFile)
    
    // Prepare multipart
    val filePart = MultipartBody.Part.createFormData(
        "file",
        sanitizedFile.name,
        sanitizedFile.asRequestBody("image/jpeg".toMediaTypeOrNull())
    )
    
    val metadata = JSONObject().apply {
        put("capture_timestamp", Instant.now().toString())
        put("device_id", DeviceUtils.getDeviceId())
        put("original_size_bytes", photoFile.length())
        put("compressed_size_bytes", sanitizedFile.length())
    }
    
    return safeApiCall {
        fileUploadApi.uploadAttachment(
            jobId = jobId.toString().toRequestBody(),
            description = description.toRequestBody(),
            file = filePart,
            metadata = metadata.toString().toRequestBody("application/json".toMediaTypeOrNull())
        )
    }
}
```

#### Background Upload with WorkManager

```kotlin
// Workers/PhotoUploadWorker.kt
class PhotoUploadWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {
    
    override suspend fun doWork(): Result {
        val jobId = inputData.getLong("job_id", -1)
        val photoPath = inputData.getString("photo_path") ?: return Result.failure()
        
        val photoFile = File(photoPath)
        if (!photoFile.exists()) {
            return Result.failure()
        }
        
        return when (val result = uploadPhoto(jobId, photoFile)) {
            is com.intelliwiz.core.Result.Success -> {
                photoFile.delete()  // Clean up after successful upload
                Result.success()
            }
            is com.intelliwiz.core.Result.Error -> {
                if (runAttemptCount < 3) {
                    Result.retry()  // Retry up to 3 times
                } else {
                    Result.failure()
                }
            }
            is com.intelliwiz.core.Result.NetworkError -> Result.retry()
        }
    }
    
    companion object {
        fun enqueue(context: Context, jobId: Long, photoFile: File) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .setRequiresBatteryNotLow(true)
                .build()
            
            val uploadWork = OneTimeWorkRequestBuilder<PhotoUploadWorker>()
                .setInputData(workDataOf(
                    "job_id" to jobId,
                    "photo_path" to photoFile.absolutePath
                ))
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    1,
                    TimeUnit.MINUTES
                )
                .build()
            
            WorkManager.getInstance(context)
                .enqueueUniqueWork(
                    "upload_photo_$jobId",
                    ExistingWorkPolicy.REPLACE,
                    uploadWork
                )
        }
    }
}
```

---

## Caching Strategy

### Room Database Cache Configuration

#### Cache Eviction Policy

```kotlin
// Data/Database/CacheManager.kt
class CacheManager(private val database: AppDatabase) {
    
    suspend fun evictStaleData() {
        val cutoff = Clock.System.now().minus(30.days)
        
        withContext(Dispatchers.IO) {
            // Delete old jobs
            database.jobDao().deleteOlderThan(cutoff.toEpochMilliseconds())
            
            // Delete synced photos
            database.photoDao().deleteSyncedPhotosOlderThan(cutoff.toEpochMilliseconds())
            
            // Delete completed tasks
            database.taskDao().deleteCompletedOlderThan(cutoff.toEpochMilliseconds())
        }
        
        Timber.i("Cache eviction complete")
    }
    
    suspend fun checkStorageQuota(): StorageStatus {
        val totalSize = database.openHelper.readableDatabase.path?.let { path ->
            File(path).length()
        } ?: 0L
        
        val maxSize = 500 * 1024 * 1024  // 500MB
        
        return when {
            totalSize > maxSize * 0.9 -> {
                evictStaleData()
                StorageStatus.CRITICAL
            }
            totalSize > maxSize * 0.7 -> StorageStatus.WARNING
            else -> StorageStatus.OK
        }
    }
}

enum class StorageStatus {
    OK, WARNING, CRITICAL
}
```

#### TTL-Based Caching

```kotlin
// Data/Models/CachedEntity.kt
data class CachedJob(
    @PrimaryKey val id: Long,
    val data: String,  // JSON serialized
    val cachedAt: Long,
    val ttlSeconds: Long = 3600  // 1 hour default
) {
    fun isStale(): Boolean {
        val now = System.currentTimeMillis()
        return now - cachedAt > (ttlSeconds * 1000)
    }
}

// Repository with cache
class JobRepository(
    private val api: OperationsApi,
    private val dao: JobDao,
    private val networkMonitor: NetworkMonitor
) {
    
    fun getJob(jobId: Long): Flow<Resource<Job>> = flow {
        // Emit cached version first
        val cached = dao.getJobById(jobId)
        if (cached != null && !cached.isStale()) {
            emit(Resource.Success(Json.decodeFromString(cached.data)))
        }
        
        // Fetch fresh data if online
        if (networkMonitor.isOnline()) {
            when (val result = safeApiCall { api.getJob(jobId) }) {
                is Result.Success -> {
                    // Update cache
                    dao.insert(CachedJob(
                        id = jobId,
                        data = Json.encodeToString(result.data),
                        cachedAt = System.currentTimeMillis()
                    ))
                    emit(Resource.Success(result.data))
                }
                is Result.Error -> emit(Resource.Error(result.errors))
            }
        }
    }.flowOn(Dispatchers.IO)
}
```

---

## Analytics & Tracking

### Firebase Analytics Setup

```kotlin
// Analytics/AnalyticsTracker.kt
class AnalyticsTracker(private val context: Context) {
    
    private val analytics = FirebaseAnalytics.getInstance(context)
    
    fun logEvent(event: AnalyticsEvent) {
        val bundle = Bundle().apply {
            event.parameters.forEach { (key, value) ->
                when (value) {
                    is String -> putString(key, value)
                    is Int -> putInt(key, value)
                    is Long -> putLong(key, value)
                    is Double -> putDouble(key, value)
                    is Boolean -> putBoolean(key, value)
                }
            }
        }
        
        analytics.logEvent(event.name, bundle)
        Timber.d("Analytics: ${event.name} - ${event.parameters}")
    }
    
    fun setUserId(userId: Long) {
        analytics.setUserId(userId.toString())
    }
    
    fun setUserProperty(key: String, value: String) {
        analytics.setUserProperty(key, value)
    }
}

// Event definitions
sealed class AnalyticsEvent(val name: String, val parameters: Map<String, Any>) {
    
    data class Login(val method: String) : AnalyticsEvent(
        "login",
        mapOf("method" to method)
    )
    
    data class JobStarted(val jobId: Long, val jobType: String) : AnalyticsEvent(
        "job_started",
        mapOf(
            "job_id" to jobId,
            "job_type" to jobType
        )
    )
    
    data class CheckIn(val postId: Long, val hasFacialRecognition: Boolean) : AnalyticsEvent(
        "check_in",
        mapOf(
            "post_id" to postId,
            "has_facial_recognition" to hasFacialRecognition
        )
    )
    
    data class TicketCreated(val priority: String, val category: String) : AnalyticsEvent(
        "ticket_created",
        mapOf(
            "priority" to priority,
            "category" to category
        )
    )
    
    data class SyncCompleted(val recordCount: Int, val durationMs: Long) : AnalyticsEvent(
        "sync_completed",
        mapOf(
            "record_count" to recordCount,
            "duration_ms" to durationMs
        )
    )
}

// Usage
analyticsTracker.logEvent(AnalyticsEvent.CheckIn(
    postId = 123,
    hasFacialRecognition = true
))
```

---

**Document Version**: 1.0  
**Last Updated**: Nov 7, 2025  
**Next Review**: Before Kotlin implementation begins
