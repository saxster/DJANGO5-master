# OFFLINE-FIRST ARCHITECTURE PATTERNS
## Cache Strategies, Conflict Resolution & Sync Patterns

**Version**: 1.0
**Last Updated**: October 30, 2025
**Based on**: Android Architecture Guidelines, Industry Best Practices 2025

---

## Table of Contents

1. [Cache Strategies](#1-cache-strategies)
2. [Staleness Detection](#2-staleness-detection)
3. [Conflict Resolution](#3-conflict-resolution)
4. [Pending Operations Queue](#4-pending-operations-queue)
5. [Network State Management](#5-network-state-management)
6. [Edge Cases & Recovery](#6-edge-cases--recovery)

---

## 1. Cache Strategies

### 1.1 Cache-Aside (Lazy Loading)

**Pattern**: Check cache first, fetch from network if miss, update cache

```kotlin
override fun getJournalEntries(forceRefresh: Boolean = false): Flow<Result<List<JournalEntry>>> = flow {
    // 1. Emit loading state
    emit(Result.Loading())

    // 2. Check cache first (unless force refresh)
    if (!forceRefresh) {
        val cached = localDataSource.getAll()
        if (cached.isNotEmpty() && !isCacheStale(cached)) {
            emit(Result.Success(cached.map { it.toDomain() }))
        }
    }

    // 3. Fetch from network
    try {
        val dtos = remoteDataSource.getAll()

        // 4. Update cache
        localDataSource.insertAll(dtos.map { it.toCache() })

        // 5. Emit fresh data
        emit(Result.Success(dtos.map { it.toDomain() }))

    } catch (e: Exception) {
        // Network error - only emit error if cache was empty
        if (forceRefresh || localDataSource.getAll().isEmpty()) {
            emit(Result.Error(e))
        }
    }
}

private fun isCacheStale(cached: List<CacheEntity>): Boolean {
    if (cached.isEmpty()) return true

    val oldestFetchTime = cached.minOf { it.fetchedAt }
    val now = System.currentTimeMillis()

    return (now - oldestFetchTime) > CACHE_TTL_MS
}

companion object {
    private const val CACHE_TTL_MS = 15 * 60 * 1000L  // 15 minutes
}
```

**When to Use**: Read-heavy operations, list views

---

### 1.2 Write-Through

**Pattern**: Write to cache and network simultaneously

```kotlin
override fun updateJournalEntry(id: String, updates: Map<String, Any>): Flow<Result<JournalEntry>> = flow {
    // 1. Update cache immediately (optimistic update)
    val cached = localDataSource.getById(id) ?: throw NotFoundException()
    val updated = cached.copy(
        title = updates["title"] as? String ?: cached.title,
        moodRating = updates["mood_rating"] as? Int ?: cached.moodRating,
        version = cached.version + 1,
        updatedAt = System.currentTimeMillis()
    )
    localDataSource.update(updated)

    // 2. Emit success immediately (UI updates)
    emit(Result.Success(updated.toDomain()))

    // 3. Sync to network
    try {
        val dto = remoteDataSource.update(id, updates.toDto())

        // 4. Update cache with server response
        localDataSource.update(dto.toCache())

        // 5. Emit confirmed state
        emit(Result.Success(dto.toDomain()))

    } catch (e: Exception) {
        // Revert cache on network error
        localDataSource.update(cached)  // Rollback

        emit(Result.Error(e))
    }
}
```

**When to Use**: Critical data, immediate consistency needed

**Pros**: Immediate network sync
**Cons**: Fails if offline (need fallback to write-behind)

---

### 1.3 Write-Behind (Queue for Later)

**Pattern**: Write to cache, queue for sync, sync in background

```kotlin
override fun createJournalEntry(entry: CreateRequest): Flow<Result<JournalEntry>> = flow {
    // 1. Generate mobile_id
    val mobileId = UUID.randomUUID().toString()
    val now = System.currentTimeMillis()

    // 2. Create cache entity
    val cacheEntity = CacheEntity(
        id = "temp-$mobileId",
        mobileId = mobileId,
        serverId = null,
        syncStatus = SyncStatus.PENDING_SYNC.name,
        version = 1,
        createdAt = now,
        updatedAt = now,
        ...
    )

    // 3. Save to cache
    localDataSource.insert(cacheEntity)

    // 4. Add to pending operations queue
    pendingOperationsDao.insert(
        PendingOperation(
            operationType = "CREATE",
            entityType = "JOURNAL",
            entityId = mobileId,
            payload = json.encodeToString(entry),
            createdAt = now
        )
    )

    // 5. Emit success immediately (offline-first)
    emit(Result.Success(cacheEntity.toDomain()))

    // 6. Attempt immediate sync (if online)
    if (networkMonitor.isOnline()) {
        try {
            val dto = remoteDataSource.create(entry.toDto())

            // Update cache with server ID
            localDataSource.update(cacheEntity.copy(
                id = dto.id,
                serverId = dto.id,
                syncStatus = SyncStatus.SYNCED.name,
                lastSyncTimestamp = now
            ))

            // Remove from pending queue
            pendingOperationsDao.deleteByEntityId(mobileId)

            // Emit synced state
            emit(Result.Success(dto.toDomain()))

        } catch (e: Exception) {
            // Network error - stays in pending queue for WorkManager
            // Don't emit error - local operation succeeded
        }
    }
}
```

**When to Use**: Offline-first operations, mobile apps

**Pros**: Works offline, eventual consistency
**Cons**: Complex (need pending queue, background sync)

---

## 2. Staleness Detection

### 2.1 Time-Based TTL

```kotlin
@Entity
data class CacheEntity(
    @PrimaryKey val id: String,
    val data: String,
    @ColumnInfo(name = "fetched_at") val fetchedAt: Long,
    @ColumnInfo(name = "expires_at") val expiresAt: Long
)

fun isCacheStale(entity: CacheEntity): Boolean {
    return System.currentTimeMillis() > entity.expiresAt
}

// Set TTL when caching
fun cacheResponse(dto: DTO): CacheEntity {
    val now = System.currentTimeMillis()
    return CacheEntity(
        id = dto.id,
        data = json.encodeToString(dto),
        fetchedAt = now,
        expiresAt = now + TTL_MS  // Expires in 15 minutes
    )
}

companion object {
    private const val TTL_MS = 15 * 60 * 1000L  // 15 minutes
}
```

**TTL Recommendations**:
| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| User profile | 1 hour | Changes infrequently |
| Journal entries | 15 min | User may edit frequently |
| Wellness content | 24 hours | Static content |
| Job assignments | 5 min | Changes frequently |
| Geofences | 1 hour | Rarely changes |

---

### 2.2 Version-Based (ETag)

```kotlin
// Server sends ETag header
@GET("journal/")
suspend fun getEntries(@Header("If-None-Match") etag: String?): Response<List<JournalEntryDTO>>

// Repository checks ETag
override fun getEntries(): Flow<Result<List<JournalEntry>>> = flow {
    val cached = localDataSource.getAll()
    val cachedEtag = cacheMetadata.getEtag("journal_entries")

    // Send ETag to server
    val response = api.getEntries(etag = cachedEtag)

    when (response.code()) {
        304 -> {
            // Not Modified - cache still fresh
            emit(Result.Success(cached.map { it.toDomain() }))
        }
        200 -> {
            // Modified - update cache
            val newEtag = response.headers()["ETag"]
            val dtos = response.body()!!

            localDataSource.replaceAll(dtos.map { it.toCache() })
            cacheMetadata.setEtag("journal_entries", newEtag)

            emit(Result.Success(dtos.map { it.toDomain() }))
        }
        else -> {
            throw HttpException(response.code(), response.message())
        }
    }
}
```

**When to Use**: Large datasets where 304 Not Modified saves bandwidth

---

## 3. Conflict Resolution

### 3.1 Last-Write-Wins (Timestamp-Based)

**Best for**: Single-user data, journal entries, notes

```kotlin
data class ConflictResolver @Inject constructor() {

    fun resolveLastWriteWins(
        client: JournalEntry,
        server: JournalEntryDTO
    ): JournalEntry {
        val clientTimestamp = client.audit.updatedAt.toEpochMilliseconds()
        val serverTimestamp = Instant.parse(server.updatedAt).toEpochMilliseconds()

        return if (clientTimestamp > serverTimestamp) {
            // Client wins - keep client version, bump version
            client.copy(
                syncMetadata = client.syncMetadata.copy(
                    version = (server.version ?: 1) + 1
                )
            )
        } else {
            // Server wins - accept server version
            server.toDomain()
        }
    }
}

// Usage in sync
suspend fun syncEntry(mobileId: String) {
    val client = localDataSource.getByMobileId(mobileId).toDomain()
    val dto = mapper.toDto(client)

    try {
        val server = remoteDataSource.update(client.id.value, dto)

        // Success - update cache
        localDataSource.update(server.toCache())
        pendingOperationsDao.deleteByEntityId(mobileId)

    } catch (e: HttpException) {
        if (e.code == 409) {
            // Conflict detected - server has different version
            val serverVersion = remoteDataSource.get(client.id.value)

            val resolved = conflictResolver.resolveLastWriteWins(client, serverVersion)

            // Save resolved version
            localDataSource.update(resolved.toCache())

            // Try sync again with resolved version
            remoteDataSource.update(resolved.id.value, mapper.toDto(resolved))
        } else {
            throw e
        }
    }
}
```

---

### 3.2 Version-Based (Optimistic Locking)

**Best for**: Collaborative data, preventing overwrites

```kotlin
// Client tracks version
data class SyncMetadata(
    val version: Int,
    val mobileId: String,
    val serverId: String?
)

// Client sends version with update
suspend fun updateEntry(id: String, updates: Map<String, Any>, currentVersion: Int) {
    val dto = UpdateDTO(
        ...updates,
        version = currentVersion
    )

    val response = api.updateEntry(id, dto)

    if (response.code() == 409) {
        // Version mismatch - conflict
        val serverVersion = response.body()?.version ?: throw ConflictException()

        if (serverVersion > currentVersion) {
            // Server has newer version - fetch and show to user
            val latest = api.getEntry(id).body()!!
            throw ConflictException("Entry has been modified", latest)
        }
    }
}
```

---

### 3.3 Merge Strategy (Field-Level)

**Best for**: Non-conflicting fields, arrays (append), counters (sum)

```kotlin
fun mergeFields(client: JournalEntry, server: JournalEntryDTO): JournalEntry {
    return JournalEntry(
        id = client.id,

        // Title: Last write wins
        title = if (client.audit.updatedAt > server.updatedAt) {
            client.title
        } else {
            Title(server.title)
        },

        // Mood rating: Take higher value
        moodRating = maxOf(
            client.wellbeingMetrics?.moodRating?.value ?: 0,
            server.moodRating ?: 0
        ).let { if (it > 0) MoodRating(it) else null },

        // Gratitude items: Merge arrays (union)
        gratitudeItems = (
            client.positiveReflections?.gratitudeItems.orEmpty() +
            server.gratitudeItems.orEmpty()
        ).distinct(),

        // Tags: Merge (union)
        tags = (client.tags + server.tags.orEmpty()).distinct(),

        // Version: Server + 1
        version = (server.version ?: 1) + 1
    )
}
```

---

### 3.4 User-Driven Resolution (Show Conflict UI)

**Best for**: Critical data where automatic resolution isn't safe

```kotlin
// Detect conflict
if (client.version == server.version && client.updatedAt != server.updatedAt) {
    // Show conflict resolution UI
    emit(Result.Conflict(
        clientVersion = client,
        serverVersion = server.toDomain(),
        conflictType = ConflictType.CONCURRENT_EDIT
    ))

    // Wait for user choice
    // ... (handled by UI)
}

sealed class Result<out T> {
    data class Success<T>(val data: T) : Result<T>()
    data class Error(val error: Throwable) : Result<Nothing>()
    data class Loading(val progress: Float? = null) : Result<Nothing>()
    data class Conflict<T>(
        val clientVersion: T,
        val serverVersion: T,
        val conflictType: ConflictType
    ) : Result<T>()  // New state for conflicts
}

enum class ConflictType {
    CONCURRENT_EDIT,     // Both modified same resource
    DELETE_MODIFIED,     // Client deleted, server modified
    MODIFIED_DELETE      // Client modified, server deleted
}

// UI handles conflict
@Composable
fun ConflictResolutionDialog(
    clientVersion: JournalEntry,
    serverVersion: JournalEntry,
    onResolve: (JournalEntry) -> Unit
) {
    AlertDialog(
        title = { Text("Conflict Detected") },
        text = {
            Column {
                Text("This entry was modified both on your device and the server.")
                Spacer(Modifier.height(16.dp))
                Text("Your version: ${clientVersion.title.value}")
                Text("Server version: ${serverVersion.title.value}")
            }
        },
        confirmButton = {
            Button(onClick = { onResolve(clientVersion) }) {
                Text("Keep My Version")
            }
        },
        dismissButton = {
            Button(onClick = { onResolve(serverVersion) }) {
                Text("Use Server Version")
            }
        }
    )
}
```

---

## 4. Pending Operations Queue

### 4.1 Queue Design

```kotlin
@Entity(tableName = "pending_operations")
data class PendingOperation(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    @ColumnInfo(name = "operation_type") val operationType: String,  // CREATE, UPDATE, DELETE
    @ColumnInfo(name = "entity_type") val entityType: String,  // JOURNAL, JOB, ATTENDANCE
    @ColumnInfo(name = "entity_id") val entityId: String,  // mobile_id or server_id
    @ColumnInfo(name = "payload") val payload: String,  // JSON to send to API
    @ColumnInfo(name = "priority") val priority: Int = 0,  // Higher = more important
    @ColumnInfo(name = "created_at") val createdAt: Long,
    @ColumnInfo(name = "retry_count") val retryCount: Int = 0,
    @ColumnInfo(name = "last_error") val lastError: String? = null,
    @ColumnInfo(name = "last_retry_at") val lastRetryAt: Long? = null
)
```

---

### 4.2 Queue Size Management ⚠️ CRITICAL

**Problem**: Queue can grow unbounded if user offline for weeks

**Solution**: Limit queue size, purge old operations

```kotlin
class PendingOperationsManager @Inject constructor(
    private val dao: PendingOperationsDao
) {
    companion object {
        private const val MAX_QUEUE_SIZE = 1000
        private const val MAX_AGE_DAYS = 7
        private const val PURGE_COUNT = 100
    }

    suspend fun addOperation(operation: PendingOperation) {
        // Check queue size
        val currentSize = dao.getCount()

        if (currentSize >= MAX_QUEUE_SIZE) {
            // Purge oldest low-priority operations
            dao.purgeOldestLowPriority(PURGE_COUNT)

            // If still too large, reject new operation
            if (dao.getCount() >= MAX_QUEUE_SIZE) {
                throw QueueFullException("Pending operations queue is full. Please sync.")
            }
        }

        // Purge operations older than MAX_AGE_DAYS
        val cutoff = System.currentTimeMillis() - (MAX_AGE_DAYS * 24 * 60 * 60 * 1000L)
        dao.purgeOlderThan(cutoff)

        // Add new operation
        dao.insert(operation)
    }

    suspend fun getNextBatch(batchSize: Int = 50): List<PendingOperation> {
        // Get next batch, ordered by priority (high first), then age (old first)
        return dao.getNextBatch(limit = batchSize)
    }
}

@Dao
interface PendingOperationsDao {
    @Query("SELECT COUNT(*) FROM pending_operations")
    suspend fun getCount(): Int

    @Query("DELETE FROM pending_operations WHERE id IN (SELECT id FROM pending_operations WHERE priority < 5 ORDER BY created_at ASC LIMIT :count)")
    suspend fun purgeOldestLowPriority(count: Int)

    @Query("DELETE FROM pending_operations WHERE created_at < :cutoffTimestamp")
    suspend fun purgeOlderThan(cutoffTimestamp: Long)

    @Query("SELECT * FROM pending_operations ORDER BY priority DESC, created_at ASC LIMIT :limit")
    suspend fun getNextBatch(limit: Int): List<PendingOperation>
}
```

---

### 4.3 Priority Levels

```kotlin
object OperationPriority {
    const val CRITICAL = 10  // User deletion, safety reports
    const val HIGH = 7       // Journal entries, attendance
    const val NORMAL = 5     // Updates, non-critical data
    const val LOW = 3        // Analytics, telemetry
}

// Assign priority based on entity type
fun getPriority(entityType: String, operationType: String): Int {
    return when {
        entityType == "SAFETY_REPORT" -> OperationPriority.CRITICAL
        entityType == "ATTENDANCE" && operationType == "CREATE" -> OperationPriority.HIGH
        entityType == "JOURNAL" -> OperationPriority.HIGH
        operationType == "DELETE" -> OperationPriority.HIGH  // Deletes are important
        else -> OperationPriority.NORMAL
    }
}
```

---

### 4.4 Deduplication

**Problem**: Same operation added multiple times (user taps "Save" repeatedly)

**Solution**: Use unique constraints or check before adding

```kotlin
@Entity(
    tableName = "pending_operations",
    indices = [Index(value = ["entity_id", "operation_type"], unique = true)]
)
data class PendingOperation(...)

// Room will reject duplicates automatically

// Or: Check before adding
suspend fun addOperation(operation: PendingOperation) {
    val existing = dao.findByEntityIdAndType(
        operation.entityId,
        operation.operationType
    )

    if (existing != null) {
        // Update existing operation instead of creating duplicate
        dao.update(existing.copy(
            payload = operation.payload,  // Use latest payload
            priority = maxOf(existing.priority, operation.priority),
            retryCount = 0  // Reset retry count
        ))
    } else {
        dao.insert(operation)
    }
}
```

---

## 5. Network State Management

### 5.1 Network Connectivity Monitor

```kotlin
@Singleton
class NetworkMonitor @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    private val _isOnline = MutableStateFlow(false)
    val isOnline: StateFlow<Boolean> = _isOnline.asStateFlow()

    init {
        // Register network callback
        val networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                _isOnline.value = true
            }

            override fun onLost(network: Network) {
                _isOnline.value = false
            }
        }

        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()

        connectivityManager.registerNetworkCallback(request, networkCallback)

        // Set initial state
        _isOnline.value = isCurrentlyOnline()
    }

    fun isCurrentlyOnline(): Boolean {
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}
```

### 5.2 Sync on Reconnect

```kotlin
class NetworkAwareSyncManager @Inject constructor(
    private val networkMonitor: NetworkMonitor,
    private val workManager: WorkManager
) {
    init {
        // Trigger sync when network becomes available
        networkMonitor.isOnline
            .filter { it }  // Only when online
            .distinctUntilChanged()  // Only on change (offline → online)
            .onEach {
                triggerSync()
            }
            .launchIn(CoroutineScope(Dispatchers.IO))
    }

    private fun triggerSync() {
        // Enqueue one-time sync work
        val syncRequest = OneTimeWorkRequestBuilder<SyncWorker>()
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build()
            )
            .build()

        workManager.enqueueUniqueWork(
            "one_time_sync",
            ExistingWorkPolicy.REPLACE,  // Cancel pending, start new
            syncRequest
        )
    }
}
```

---

## 6. Edge Cases & Recovery

### 6.1 User Deletes Account While Offline

**Problem**: Pending operations for deleted account

**Solution**: Mark operations as orphaned, purge on sync

```kotlin
suspend fun handleAccountDeletion(userId: Int) {
    // 1. Soft delete all local user data
    localDataSource.softDeleteUserData(userId)

    // 2. Mark pending operations as orphaned
    pendingOperationsDao.markOrphaned(userId)

    // 3. Add account deletion operation (highest priority)
    pendingOperationsDao.insert(
        PendingOperation(
            operationType = "DELETE_ACCOUNT",
            entityType = "USER",
            entityId = userId.toString(),
            payload = """{"user_id": $userId}""",
            priority = OperationPriority.CRITICAL,
            createdAt = System.currentTimeMillis()
        )
    )
}

// In SyncWorker
suspend fun processAccountDeletion(operation: PendingOperation) {
    try {
        // Delete account on server
        remoteDataSource.deleteAccount(operation.entityId.toInt())

        // Purge all orphaned operations for this user
        pendingOperationsDao.purgeOrphaned(operation.entityId.toInt())

        // Clear local cache
        localDataSource.clearUserData(operation.entityId.toInt())

    } catch (e: HttpException) {
        if (e.code == 404) {
            // Account already deleted on server - OK
            pendingOperationsDao.purgeOrphaned(operation.entityId.toInt())
        } else {
            throw e
        }
    }
}
```

---

### 6.2 Server Resource Deleted (404 on Sync)

**Problem**: Client has pending update/delete, but server already deleted resource

**Solution**: Treat 404 as success for DELETE, error for UPDATE

```kotlin
suspend fun syncOperation(operation: PendingOperation) {
    try {
        when (operation.operationType) {
            "UPDATE" -> {
                val dto = json.decodeFromString<UpdateDTO>(operation.payload)
                remoteDataSource.update(operation.entityId, dto)
            }

            "DELETE" -> {
                remoteDataSource.delete(operation.entityId)
            }
        }

        // Success - remove from queue
        pendingOperationsDao.delete(operation)

    } catch (e: HttpException) {
        when (e.code) {
            404 -> {
                // Resource not found on server
                when (operation.operationType) {
                    "DELETE" -> {
                        // Already deleted - treat as success
                        pendingOperationsDao.delete(operation)
                        localDataSource.deleteByMobileId(operation.entityId)
                    }

                    "UPDATE" -> {
                        // Can't update deleted resource - remove operation
                        pendingOperationsDao.delete(operation)
                        localDataSource.deleteByMobileId(operation.entityId)

                        // Notify user
                        notificationManager.showConflictNotification(
                            "Entry was deleted on another device"
                        )
                    }
                }
            }

            else -> throw e
        }
    }
}
```

---

### 6.3 Token Expires During Long Offline Period

**Problem**: User offline for 8+ days, refresh token expires (7-day TTL)

**Solution**: Detect expired refresh token, require re-login

```kotlin
class TokenAuthenticator @Inject constructor(
    private val tokenStorage: SecureTokenStorage,
    private val authApi: AuthApi
) : Authenticator {

    @Synchronized
    override fun authenticate(route: Route?, response: Response): Request? {
        val refreshToken = tokenStorage.getRefreshToken()

        if (refreshToken == null) {
            // No refresh token - logout and redirect to login
            tokenStorage.clearTokens()
            broadcastLogoutEvent()
            return null
        }

        try {
            val refreshResponse = authApi.refreshToken(
                RefreshTokenRequest(refreshToken)
            ).execute()

            if (refreshResponse.isSuccessful) {
                val newTokens = refreshResponse.body()!!
                tokenStorage.saveAccessToken(newTokens.access)
                tokenStorage.saveRefreshToken(newTokens.refresh)

                return response.request.newBuilder()
                    .header("Authorization", "Bearer ${newTokens.access}")
                    .build()

            } else {
                // Refresh failed
                when (refreshResponse.code()) {
                    401 -> {
                        // Refresh token expired - require re-login
                        tokenStorage.clearTokens()
                        broadcastLogoutEvent()

                        // Show notification
                        notificationManager.show(
                            "Session Expired",
                            "Please log in again"
                        )
                    }
                }

                return null
            }

        } catch (e: Exception) {
            // Network error during refresh - stay logged in, retry later
            return null
        }
    }

    private fun broadcastLogoutEvent() {
        // Send broadcast to logout user
        val intent = Intent("com.example.facility.ACTION_LOGOUT")
        context.sendBroadcast(intent)
    }
}
```

---

### 6.4 Server Validation Fails for Queued Operation

**Problem**: Client queued operation that passes local validation, but server rejects

**Solution**: Mark as error, notify user, allow edit

```kotlin
suspend fun processCreateOperation(operation: PendingOperation) {
    try {
        val dto = json.decodeFromString<JournalEntryCreateDTO>(operation.payload)
        val response = remoteDataSource.create(dto)

        // Success
        localDataSource.updateServerId(operation.entityId, response.id)
        pendingOperationsDao.delete(operation)

    } catch (e: HttpException) {
        when (e.code) {
            400 -> {
                // Server validation failed
                val fieldErrors = e.apiError?.details

                // Mark entity as sync_error
                localDataSource.updateSyncStatus(operation.entityId, SyncStatus.SYNC_ERROR)

                // Store error details
                localDataSource.updateSyncError(
                    operation.entityId,
                    "Validation failed: ${fieldErrors?.entries?.joinToString()}"
                )

                // Remove from queue (won't retry automatically)
                pendingOperationsDao.delete(operation)

                // Notify user
                notificationManager.showSyncError(
                    "Entry '${operation.entityId}' failed to sync",
                    "Please review and fix: ${fieldErrors?.keys?.joinToString()}"
                )
            }

            409 -> {
                // Conflict - handle with conflict resolution
                handleConflict(operation)
            }

            else -> {
                // Other error - retry
                throw e
            }
        }
    }
}
```

---

## 7. Background Sync Strategy

### 7.1 Sync Batch Processing

```kotlin
override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
    val pendingOps = pendingOperationsDao.getNextBatch(limit = 50)

    if (pendingOps.isEmpty()) {
        return@withContext Result.success()
    }

    var successCount = 0
    var failureCount = 0
    val errors = mutableListOf<String>()

    // Group by entity type for batch optimization
    val grouped = pendingOps.groupBy { it.entityType }

    for ((entityType, ops) in grouped) {
        when (entityType) {
            "JOURNAL" -> {
                ops.forEach { op ->
                    try {
                        processJournalOperation(op)
                        successCount++
                    } catch (e: Exception) {
                        handleOperationError(op, e)
                        failureCount++
                        errors.add("${op.entityType}:${op.entityId} - ${e.message}")
                    }
                }
            }

            // Handle other entity types
        }
    }

    // Return result
    return@withContext if (failureCount == 0) {
        Result.success(workDataOf(
            "success_count" to successCount,
            "failure_count" to 0
        ))
    } else if (successCount > 0) {
        // Partial success - continue
        Result.success(workDataOf(
            "success_count" to successCount,
            "failure_count" to failureCount,
            "errors" to errors.joinToString("; ")
        ))
    } else {
        // All failed - retry later
        Result.retry()
    }
}
```

---

### 7.2 Optimistic UI Updates

```kotlin
// Show "syncing" indicator in UI
@Composable
fun JournalEntryCard(entry: JournalEntry) {
    Card {
        Column {
            Text(entry.title.value)

            // Show sync status
            when (entry.syncMetadata.syncStatus) {
                SyncStatus.PENDING_SYNC -> {
                    Row {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Syncing...", style = MaterialTheme.typography.caption)
                    }
                }

                SyncStatus.SYNC_ERROR -> {
                    Row {
                        Icon(Icons.Default.Error, tint = Color.Red)
                        Text("Sync failed - tap to retry", color = Color.Red)
                    }
                }

                SyncStatus.SYNCED -> {
                    Icon(Icons.Default.CheckCircle, tint = Color.Green)
                }

                SyncStatus.DRAFT -> {
                    Text("Draft", style = MaterialTheme.typography.caption)
                }

                SyncStatus.PENDING_DELETE -> {
                    Text("Deleting...", style = MaterialTheme.typography.caption)
                }
            }
        }
    }
}
```

---

## 8. Testing Offline Scenarios

### 8.1 Simulate Network Conditions

```kotlin
class MockNetworkMonitor : NetworkMonitor {
    private val _isOnline = MutableStateFlow(true)
    override val isOnline: StateFlow<Boolean> = _isOnline

    fun setOnline() {
        _isOnline.value = true
    }

    fun setOffline() {
        _isOnline.value = false
    }
}

@Test
fun `create entry offline adds to pending queue`() = runTest {
    // Given: Device is offline
    networkMonitor.setOffline()

    // When: Create entry
    val result = repository.createJournalEntry(...).first()

    // Then: Success emitted (optimistic)
    assertTrue(result is Result.Success)

    // And: Added to pending queue
    val pendingOps = pendingOperationsDao.getAll()
    assertEquals(1, pendingOps.size)
    assertEquals("CREATE", pendingOps[0].operationType)
}

@Test
fun `sync succeeds when coming back online`() = runTest {
    // Given: Created entries while offline
    networkMonitor.setOffline()
    repository.createJournalEntry(...).first()
    repository.createJournalEntry(...).first()

    val pendingBefore = pendingOperationsDao.getCount()
    assertEquals(2, pendingBefore)

    // When: Network comes back, sync runs
    networkMonitor.setOnline()
    syncWorker.doWork()

    // Then: Pending operations cleared
    val pendingAfter = pendingOperationsDao.getCount()
    assertEquals(0, pendingAfter)

    // And: Entries marked as synced
    val entries = localDataSource.getAll()
    assertTrue(entries.all { it.syncStatus == SyncStatus.SYNCED.name })
}
```

---

## 9. Production Checklist

### Before Offline-First Goes Live

- [ ] Cache TTL configured appropriately per entity type
- [ ] Pending queue size limits enforced (MAX_QUEUE_SIZE)
- [ ] Old operations purged (MAX_AGE_DAYS)
- [ ] Priority levels assigned correctly
- [ ] Deduplication logic prevents duplicates
- [ ] Conflict resolution strategy defined per entity
- [ ] Network state monitoring working
- [ ] Sync triggers on reconnect
- [ ] Sync indicators in UI (syncing, error, success)
- [ ] Manual sync option available
- [ ] All offline scenarios tested:
  - [ ] Create offline → sync online
  - [ ] Update offline → sync online
  - [ ] Delete offline → sync online
  - [ ] Conflict resolution (concurrent edits)
  - [ ] Server resource deleted (404)
  - [ ] Server validation fails (400)
  - [ ] Token expires during offline period
  - [ ] Queue full scenario

---

## Summary

This guide prevents the **40+ most common offline-first errors**:

✅ Cache strategies (cache-aside, write-through, write-behind)
✅ Staleness detection (TTL, ETag, manual invalidation)
✅ Conflict resolution (last-write-wins, version-based, merge, user-driven)
✅ Pending queue management (size limits, purging, priority, deduplication)
✅ Network state management (connectivity monitor, sync triggers)
✅ Edge cases (account deletion, 404, validation failures, token expiry)
✅ Optimistic UI (sync indicators, error states)
✅ Testing patterns (simulate offline, verify sync)

**Follow this guide during Phase 4-6 implementation.**

---

**Document Version**: 1.0
**Last Reviewed**: October 30, 2025
**Based on**: Android Architecture Guidelines, Industry patterns 2025
**Prevents**: 40+ offline-first architecture errors
