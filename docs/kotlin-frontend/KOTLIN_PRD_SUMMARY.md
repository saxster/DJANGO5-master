# KOTLIN ANDROID APP - PRODUCT REQUIREMENTS DOCUMENT
## Enterprise Facility Management Mobile Application

**Version**: 1.0
**Last Updated**: October 30, 2025
**Target Platform**: Android (API 21+ / Android 5.0+)
**Tech Stack**: Kotlin + Jetpack Compose + Hilt + Room + Retrofit
**Architecture**: Clean Architecture (3-Layer)

---

## Executive Summary

Production-grade Android application for **multi-role facility management** covering:
- **Operations**: Job/task management, PPM scheduling, tours
- **People & Attendance**: Personnel management, GPS-based check-in/out
- **Help Desk**: Ticket management with SLA tracking
- **Wellness**: Journal entries with wellbeing metrics and interventions

**Key Requirements**:
- **Offline-first**: Full functionality without network
- **Real-time sync**: WebSocket bidirectional sync with conflict resolution
- **Type-safe**: Compile-time verification of all data
- **Secure**: JWT authentication, certificate pinning, encrypted local storage
- **Performant**: < 3s cold start, < 100ms UI response

---

## System Architecture

### 3-Layer Clean Architecture

```
┌─────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER (:app)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Compose UI   │  │  ViewModels  │  │  Navigation  │ │
│  │ (Material3)  │  │  (UI State)  │  │   (NavHost)  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │ Use Cases
┌────────────────────────▼────────────────────────────────┐
│  DOMAIN LAYER (:domain) - PURE KOTLIN                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Entities   │  │  Use Cases   │  │ Repository   │ │
│  │  (Business)  │  │ (Bus. Logic) │  │  Interfaces  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │ Repository Implementations
┌────────────────────────▼────────────────────────────────┐
│  DATA LAYER (:data, :network, :database)                │
│  ┌───────────────────────────────────────────────────┐ │
│  │         Repository Implementations                 │ │
│  └──────────────┬────────────────┬───────────────────┘ │
│                 │                │                       │
│  ┌──────────────▼──────────┐  ┌─▼───────────────────┐ │
│  │  Remote Data Source     │  │  Local Data Source  │ │
│  │  (:network)             │  │  (:database)        │ │
│  │  ┌──────────────────┐  │  │  ┌────────────────┐ │ │
│  │  │ Retrofit         │  │  │  │ Room           │ │ │
│  │  │ WebSocket        │  │  │  │ SQLite         │ │ │
│  │  │ DTOs             │  │  │  │ Cache Entities │ │ │
│  │  └──────────────────┘  │  │  └────────────────┘ │ │
│  └─────────────────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Module Structure

```
MyFacilityApp/
├── app/                          # Presentation layer
│   ├── src/main/
│   │   ├── kotlin/
│   │   │   └── com/example/facility/
│   │   │       ├── ui/
│   │   │       │   ├── auth/      # Login, logout screens
│   │   │       │   ├── operations/ # Jobs, tours screens
│   │   │       │   ├── people/    # People directory
│   │   │       │   ├── attendance/ # Clock in/out
│   │   │       │   ├── helpdesk/  # Tickets
│   │   │       │   ├── wellness/  # Journal, content
│   │   │       │   └── common/    # Shared UI components
│   │   │       ├── navigation/
│   │   │       └── di/           # Hilt modules
│   │   └── res/
│   └── build.gradle.kts
│
├── domain/                        # Business logic (pure Kotlin)
│   ├── src/main/kotlin/
│   │   └── com/example/facility/domain/
│   │       ├── model/            # Entities
│   │       │   ├── operations/
│   │       │   ├── people/
│   │       │   ├── attendance/
│   │       │   ├── helpdesk/
│   │       │   └── wellness/
│   │       ├── repository/       # Interfaces
│   │       └── usecase/          # Business logic
│   │           ├── auth/
│   │           ├── operations/
│   │           └── wellness/
│   └── build.gradle.kts
│
├── data/                          # Repository implementations
│   ├── src/main/kotlin/
│   │   └── com/example/facility/data/
│   │       ├── repository/       # Implementations
│   │       ├── mapper/           # DTO ↔ Entity ↔ Cache
│   │       └── source/
│   │           ├── remote/       # Remote data sources
│   │           └── local/        # Local data sources
│   └── build.gradle.kts
│
├── network/                       # Retrofit + DTOs
│   ├── src/main/kotlin/
│   │   └── com/example/facility/network/
│   │       ├── api/              # Retrofit services (generated)
│   │       ├── dto/              # Data transfer objects (generated)
│   │       ├── interceptor/      # Auth, logging
│   │       └── websocket/        # WebSocket client
│   └── build.gradle.kts
│
├── database/                      # Room + SQLite
│   ├── src/main/kotlin/
│   │   └── com/example/facility/database/
│   │       ├── entity/           # Cache entities
│   │       ├── dao/              # Data access objects
│   │       └── FacilityDatabase.kt
│   └── build.gradle.kts
│
└── common/                        # Shared utilities
    ├── src/main/kotlin/
    │   └── com/example/facility/common/
    │       ├── result/           # Result sealed class
    │       ├── util/             # Extensions, helpers
    │       └── constant/         # Constants
    └── build.gradle.kts
```

---

## Technology Stack

| Category | Technology | Version | Justification |
|----------|-----------|---------|---------------|
| **Language** | Kotlin | 1.9+ | Type-safe, concise, coroutines |
| **UI Framework** | Jetpack Compose | 1.5+ | Declarative, modern, less boilerplate |
| **DI** | Hilt | 2.48+ | Compile-time safety, Android integration |
| **Networking** | Retrofit + OkHttp | 2.9+ / 4.12+ | Industry standard, extensive ecosystem |
| **Serialization** | kotlinx.serialization | 1.6+ | Kotlin-native, code generation |
| **Database** | Room | 2.6+ | Type-safe SQL, LiveData/Flow support |
| **Async** | Coroutines + Flow | 1.7+ | Structured concurrency, reactive streams |
| **DateTime** | kotlinx-datetime | 0.5+ | Kotlin multiplatform, timezone-aware |
| **Image Loading** | Coil | 2.5+ | Kotlin-first, Compose integration |
| **WebSocket** | OkHttp WebSocket | 4.12+ | Same as HTTP client, unified |
| **Background Work** | WorkManager | 2.9+ | Deferred, guaranteed execution |

---

## Offline-First Architecture

### Principles

1. **Cache-First**: Always serve from local cache, fetch in background
2. **Optimistic Updates**: Update UI immediately, sync later
3. **Conflict Resolution**: Last-write-wins with version tracking
4. **Pending Queue**: Store offline operations, replay on reconnect

### Data Flow

**Read Flow**:
```
UI Request
  → ViewModel (triggers Use Case)
  → Repository.getJobs()
      ├─ Emit cached data immediately (if exists)
      └─ Fetch from API in background
          → Save to cache
          → Emit fresh data
  → ViewModel updates UI state
  → Compose recomposes
```

**Write Flow (Offline)**:
```
User Action (e.g., create job)
  → ViewModel (triggers Use Case)
  → Repository.createJob()
      ├─ Generate mobile_id (UUID)
      ├─ Save to local DB (status: pending_sync)
      ├─ Add to pending_operations queue
      └─ Return success immediately
  → UI shows job (with "syncing" indicator)

Background Sync (when online):
  → WorkManager worker awakens
  → Fetch pending operations
  → For each operation:
      ├─ POST to API with mobile_id
      ├─ On success:
      │   ├─ Update local DB (status: synced, store server_id)
      │   └─ Remove from queue
      └─ On conflict:
          ├─ Resolve (last-write-wins or merge)
          └─ Update local DB
  → UI updates with sync confirmation
```

### SQLite Schema Design (Client-Optimized)

**Key Principle**: SQLite is NOT a mirror of PostgreSQL. It's optimized for:
- Fast reads (denormalized)
- Offline queue management
- Cache metadata (TTL, staleness)

**Example Tables**:

```sql
-- Jobs Cache (denormalized for fast queries)
CREATE TABLE job_cache (
    id INTEGER PRIMARY KEY,
    job_number TEXT UNIQUE NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    -- Denormalized assigned user info (no join needed)
    assigned_to_id INTEGER,
    assigned_to_name TEXT,
    assigned_to_avatar TEXT,
    -- Denormalized site info
    site_id INTEGER,
    site_name TEXT,
    site_address TEXT,
    -- JSON for complex data
    question_set_json TEXT,  -- Serialized question set
    -- Sync metadata
    mobile_id TEXT UNIQUE,   -- Client-generated UUID
    server_id INTEGER,       -- Server-assigned ID (null until synced)
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'pending_sync',  -- draft, pending_sync, synced, sync_error
    last_sync_timestamp INTEGER,
    -- Cache metadata
    fetched_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    is_stale INTEGER DEFAULT 0
);

-- Pending Operations Queue
CREATE TABLE pending_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_type TEXT NOT NULL,  -- 'CREATE', 'UPDATE', 'DELETE'
    entity_type TEXT NOT NULL,     -- 'JOB', 'JOURNAL', 'ATTENDANCE'
    entity_id TEXT,                -- mobile_id or server_id
    payload TEXT NOT NULL,         -- JSON to be sent to API
    created_at INTEGER NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    last_retry_at INTEGER
);

-- User/People Cache (denormalized)
CREATE TABLE people_cache (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    department TEXT,
    role TEXT,
    -- Denormalized organizational info
    client_id INTEGER NOT NULL,
    bu_id INTEGER,
    site_ids TEXT,  -- JSON array of assigned site IDs
    -- Capabilities
    capabilities_json TEXT NOT NULL,
    -- Cache metadata
    fetched_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);

-- Journal Entries (with PII encryption)
CREATE TABLE journal_entry_local (
    id TEXT PRIMARY KEY,  -- UUID
    user_id INTEGER NOT NULL,
    entry_type TEXT NOT NULL,
    title TEXT NOT NULL,
    -- Wellbeing metrics
    mood_rating INTEGER,
    stress_level INTEGER,
    energy_level INTEGER,
    -- Complex fields as JSON
    gratitude_items_json TEXT,
    daily_goals_json TEXT,
    affirmations_json TEXT,
    -- Location
    location_site_name TEXT,
    location_lat REAL,
    location_lng REAL,
    -- Privacy
    privacy_scope TEXT NOT NULL DEFAULT 'private',
    -- Sync
    mobile_id TEXT UNIQUE,
    version INTEGER DEFAULT 1,
    sync_status TEXT DEFAULT 'pending_sync',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Attendance Events
CREATE TABLE attendance_local (
    id TEXT PRIMARY KEY,  -- UUID
    person_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,  -- 'clock_in', 'clock_out'
    event_time INTEGER NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    accuracy REAL NOT NULL,
    device_id TEXT NOT NULL,
    inside_geofence INTEGER DEFAULT 0,
    geofence_name TEXT,
    -- Sync
    sync_status TEXT DEFAULT 'pending_sync',
    created_at INTEGER NOT NULL
);

-- Geofence Cache
CREATE TABLE geofence_cache (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    site_id INTEGER,
    -- Polygon stored as JSON array of {lat, lng}
    boundary_json TEXT NOT NULL,
    radius_meters REAL,
    is_active INTEGER DEFAULT 1,
    fetched_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);

-- Cache Metadata (for TTL management)
CREATE TABLE cache_metadata (
    entity_type TEXT PRIMARY KEY,  -- 'jobs', 'people', 'tickets', etc.
    last_full_sync INTEGER,
    last_incremental_sync INTEGER,
    ttl_seconds INTEGER DEFAULT 3600
);
```

---

## Domain Layer Design

### Entities (Business Objects)

**Pure Kotlin**, no Android dependencies, fully testable.

```kotlin
// domain/src/main/kotlin/com/example/facility/domain/model/wellness/JournalEntry.kt
package com.example.facility.domain.model.wellness

import kotlinx.datetime.Instant

data class JournalEntry(
    val id: JournalId,
    val userId: UserId,
    val title: Title,
    val entryType: EntryType,
    val timestamp: Instant,
    val wellbeingMetrics: WellbeingMetrics?,
    val positiveReflections: PositiveReflections?,
    val locationContext: LocationContext?,
    val privacyScope: PrivacyScope,
    val syncMetadata: SyncMetadata,
    val audit: AuditInfo
)

// Value Objects (inline classes for type safety)
@JvmInline
value class JournalId(val value: String)  // UUID

@JvmInline
value class UserId(val value: Int)

@JvmInline
value class Title(val value: String) {
    init {
        require(value.length in 1..200) { "Title must be 1-200 characters" }
    }
}

// Enums as sealed classes (more flexible)
sealed class EntryType {
    abstract val key: String

    object MoodCheckIn : EntryType() {
        override val key = "mood_check_in"
    }

    object Gratitude : EntryType() {
        override val key = "gratitude"
    }

    object DailyReflection : EntryType() {
        override val key = "daily_reflection"
    }
    // ... more types

    companion object {
        fun from Key(key: String): EntryType? = when (key) {
            "mood_check_in" -> MoodCheckIn
            "gratitude" -> Gratitude
            "daily_reflection" -> DailyReflection
            else -> null
        }
    }
}

data class WellbeingMetrics(
    val moodRating: MoodRating?,
    val stressLevel: StressLevel?,
    val energyLevel: EnergyLevel?,
    val stressTriggers: List<String>,
    val copingStrategies: List<String>
)

@JvmInline
value class MoodRating(val value: Int) {
    init {
        require(value in 1..10) { "Mood rating must be 1-10" }
    }
}

@JvmInline
value class StressLevel(val value: Int) {
    init {
        require(value in 1..5) { "Stress level must be 1-5" }
    }
}

data class SyncMetadata(
    val mobileId: String,  // Client-generated UUID
    val serverId: String?,  // Server-assigned ID (null until synced)
    val version: Int,
    val syncStatus: SyncStatus,
    val lastSyncTimestamp: Instant?
)

enum class SyncStatus {
    DRAFT,
    PENDING_SYNC,
    SYNCED,
    SYNC_ERROR,
    PENDING_DELETE
}
```

### Use Cases (Business Logic)

**One class per operation**, enforces single responsibility.

```kotlin
// domain/src/main/kotlin/com/example/facility/domain/usecase/wellness/CreateJournalEntryUseCase.kt
package com.example.facility.domain.usecase.wellness

import com.example.facility.domain.model.wellness.*
import com.example.facility.domain.repository.WellnessRepository
import com.example.facility.common.result.Result
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

class CreateJournalEntryUseCase @Inject constructor(
    private val repository: WellnessRepository,
    private val validator: JournalEntryValidator
) {
    /**
     * Create a new journal entry with validation and offline support.
     *
     * @return Flow<Result<JournalEntry>> - emits immediately with local save, then with sync result
     */
    operator fun invoke(request: CreateJournalEntryRequest): Flow<Result<JournalEntry>> {
        // Validate domain rules
        val validationResult = validator.validate(request)
        if (validationResult is Result.Error) {
            return flowOf(validationResult)
        }

        // Delegate to repository (handles offline queue)
        return repository.createJournalEntry(request)
    }
}

data class CreateJournalEntryRequest(
    val title: String,
    val entryType: String,
    val moodRating: Int?,
    val stressLevel: Int?,
    val energyLevel: Int?,
    val gratitudeItems: List<String>?,
    val privacyScope: String
)

class JournalEntryValidator @Inject constructor() {
    fun validate(request: CreateJournalEntryRequest): Result<Unit> {
        // Title validation
        if (request.title.isBlank() || request.title.length > 200) {
            return Result.Error(ValidationError("Title must be 1-200 characters"))
        }

        // Mood rating validation
        request.moodRating?.let {
            if (it !in 1..10) {
                return Result.Error(ValidationError("Mood rating must be 1-10"))
            }
        }

        // Stress level validation
        request.stressLevel?.let {
            if (it !in 1..5) {
                return Result.Error(ValidationError("Stress level must be 1-5"))
            }
        }

        return Result.Success(Unit)
    }
}
```

### Repository Interfaces (in Domain)

```kotlin
// domain/src/main/kotlin/com/example/facility/domain/repository/WellnessRepository.kt
package com.example.facility.domain.repository

import com.example.facility.domain.model.wellness.*
import com.example.facility.common.result.Result
import kotlinx.coroutines.flow.Flow

interface WellnessRepository {

    /**
     * Get journal entries for current user.
     *
     * Emits cached data immediately, then fresh data after network fetch.
     *
     * @param forceRefresh If true, skip cache and fetch from network
     */
    fun getJournalEntries(
        entryType: EntryType? = null,
        isDraft: Boolean? = null,
        forceRefresh: Boolean = false
    ): Flow<Result<List<JournalEntry>>>

    /**
     * Get specific journal entry by ID.
     */
    fun getJournalEntry(id: JournalId): Flow<Result<JournalEntry>>

    /**
     * Create journal entry.
     *
     * Saves locally immediately, adds to sync queue, syncs in background.
     * Emits twice: once with local save, again after sync completes.
     */
    fun createJournalEntry(request: CreateJournalEntryRequest): Flow<Result<JournalEntry>>

    /**
     * Update journal entry.
     */
    fun updateJournalEntry(id: JournalId, request: UpdateJournalEntryRequest): Flow<Result<JournalEntry>>

    /**
     * Delete journal entry.
     */
    fun deleteJournalEntry(id: JournalId): Flow<Result<Unit>>

    /**
     * Get wellness content personalized for user.
     */
    fun getPersonalizedContent(): Flow<Result<List<WellnessContent>>>
}
```

---

## Data Layer Implementation

### Repository Implementation

```kotlin
// data/src/main/kotlin/com/example/facility/data/repository/WellnessRepositoryImpl.kt
package com.example.facility.data.repository

import com.example.facility.domain.repository.WellnessRepository
import com.example.facility.domain.model.wellness.*
import com.example.facility.data.source.remote.WellnessRemoteDataSource
import com.example.facility.data.source.local.WellnessLocalDataSource
import com.example.facility.data.mapper.JournalMapper
import com.example.facility.common.result.Result
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import javax.inject.Inject

class WellnessRepositoryImpl @Inject constructor(
    private val remoteDataSource: WellnessRemoteDataSource,
    private val localDataSource: WellnessLocalDataSource,
    private val mapper: JournalMapper
) : WellnessRepository {

    override fun getJournalEntries(
        entryType: EntryType?,
        isDraft: Boolean?,
        forceRefresh: Boolean
    ): Flow<Result<List<JournalEntry>>> = flow {
        // 1. Emit cached data immediately (if exists and not force refresh)
        if (!forceRefresh) {
            val cachedEntries = localDataSource.getJournalEntries(entryType, isDraft)
            if (cachedEntries.isNotEmpty()) {
                emit(Result.Success(cachedEntries.map { mapper.toDomain(it) }))
            }
        }

        // 2. Fetch from network (if online or force refresh)
        try {
            val dtos = remoteDataSource.getJournalEntries(entryType?.key, isDraft)

            // 3. Save to cache
            val cacheEntities = dtos.map { mapper.toCache(mapper.toDomain(it)) }
            localDataSource.insertJournalEntries(cacheEntities)

            // 4. Emit fresh data
            emit(Result.Success(dtos.map { mapper.toDomain(it) }))

        } catch (e: Exception) {
            // If network fails and we already emitted cache, don't emit error
            // Otherwise, emit error
            if (forceRefresh || localDataSource.getJournalEntries(entryType, isDraft).isEmpty()) {
                emit(Result.Error(e))
            }
        }
    }

    override fun createJournalEntry(request: CreateJournalEntryRequest): Flow<Result<JournalEntry>> = flow {
        // 1. Generate mobile_id
        val mobileId = UUID.randomUUID().toString()

        // 2. Create domain entity
        val entry = mapper.fromCreateRequest(request, mobileId)

        // 3. Save to local DB (status: pending_sync)
        val cacheEntity = mapper.toCache(entry)
        localDataSource.insertJournalEntry(cacheEntity)

        // 4. Add to pending operations queue
        localDataSource.addPendingOperation(
            operationType = "CREATE",
            entityType = "JOURNAL",
            entityId = mobileId,
            payload = mapper.toJsonPayload(entry)
        )

        // 5. Emit success immediately (offline-first)
        emit(Result.Success(entry))

        // 6. Attempt sync in background (if online)
        try {
            val dto = mapper.toDto(entry)
            val responseDto = remoteDataSource.createJournalEntry(dto)

            // 7. Update local DB with server ID and synced status
            val syncedEntry = entry.copy(
                syncMetadata = entry.syncMetadata.copy(
                    serverId = responseDto.id,
                    syncStatus = SyncStatus.SYNCED,
                    lastSyncTimestamp = Instant.now()
                )
            )
            localDataSource.updateJournalEntry(mapper.toCache(syncedEntry))

            // 8. Remove from pending operations
            localDataSource.removePendingOperation(mobileId)

            // 9. Emit synced entry
            emit(Result.Success(syncedEntry))

        } catch (e: Exception) {
            // Network error - stays in pending queue for WorkManager retry
            // Don't emit error - offline operation was successful
        }
    }
}
```

### Remote Data Source

```kotlin
// data/src/main/kotlin/com/example/facility/data/source/remote/WellnessRemoteDataSource.kt
package com.example.facility.data.source.remote

import com.example.facility.network.api.WellnessApi
import com.example.facility.network.dto.JournalEntryDTO
import javax.inject.Inject

class WellnessRemoteDataSource @Inject constructor(
    private val wellnessApi: WellnessApi,
    private val authProvider: AuthProvider  // Provides Bearer token
) {
    suspend fun getJournalEntries(
        entryType: String?,
        isDraft: Boolean?
    ): List<JournalEntryDTO> {
        val response = wellnessApi.wellnessJournalList(
            entryType = entryType,
            isDraft = isDraft,
            authorization = "Bearer ${authProvider.getAccessToken()}"
        )

        if (!response.isSuccessful) {
            throw NetworkException(response.code(), response.message())
        }

        return response.body()?.results ?: emptyList()
    }

    suspend fun createJournalEntry(dto: JournalEntryDTO): JournalEntryDTO {
        val response = wellnessApi.wellnessJournalCreate(
            journalEntryDTO = dto,
            authorization = "Bearer ${authProvider.getAccessToken()}"
        )

        if (!response.isSuccessful) {
            throw NetworkException(response.code(), response.message())
        }

        return response.body() ?: throw NetworkException(500, "Empty response body")
    }
}
```

### Local Data Source

```kotlin
// data/src/main/kotlin/com/example/facility/data/source/local/WellnessLocalDataSource.kt
package com.example.facility.data.source.local

import com.example.facility.database.dao.JournalDao
import com.example.facility.database.dao.PendingOperationsDao
import com.example.facility.database.entity.JournalEntryEntity
import com.example.facility.database.entity.PendingOperationEntity
import javax.inject.Inject

class WellnessLocalDataSource @Inject constructor(
    private val journalDao: JournalDao,
    private val pendingOperationsDao: PendingOperationsDao
) {
    suspend fun getJournalEntries(
        entryType: EntryType?,
        isDraft: Boolean?
    ): List<JournalEntryEntity> {
        return when {
            entryType != null && isDraft != null ->
                journalDao.getByTypeAndDraft(entryType.key, isDraft)
            entryType != null ->
                journalDao.getByType(entryType.key)
            isDraft != null ->
                journalDao.getByDraft(isDraft)
            else ->
                journalDao.getAll()
        }
    }

    suspend fun insertJournalEntry(entity: JournalEntryEntity) {
        journalDao.insert(entity)
    }

    suspend fun insertJournalEntries(entities: List<JournalEntryEntity>) {
        journalDao.insertAll(entities)
    }

    suspend fun updateJournalEntry(entity: JournalEntryEntity) {
        journalDao.update(entity)
    }

    suspend fun addPendingOperation(
        operationType: String,
        entityType: String,
        entityId: String,
        payload: String
    ) {
        pendingOperationsDao.insert(
            PendingOperationEntity(
                operationType = operationType,
                entityType = entityType,
                entityId = entityId,
                payload = payload,
                createdAt = System.currentTimeMillis(),
                retryCount = 0
            )
        )
    }

    suspend fun removePendingOperation(entityId: String) {
        pendingOperationsDao.deleteByEntityId(entityId)
    }
}
```

---

## Presentation Layer (Jetpack Compose)

### ViewModel with State Management

```kotlin
// app/src/main/kotlin/com/example/facility/ui/wellness/journal/JournalListViewModel.kt
package com.example.facility.ui.wellness.journal

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.facility.domain.usecase.wellness.GetJournalEntriesUseCase
import com.example.facility.domain.model.wellness.JournalEntry
import com.example.facility.common.result.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class JournalListViewModel @Inject constructor(
    private val getJournalEntriesUseCase: GetJournalEntriesUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow<JournalListUiState>(JournalListUiState.Loading)
    val uiState: StateFlow<JournalListUiState> = _uiState.asStateFlow()

    init {
        loadJournalEntries()
    }

    fun onRefresh() {
        loadJournalEntries(forceRefresh = true)
    }

    fun onEntryTypeFilter(entryType: String?) {
        loadJournalEntries(entryType = entryType)
    }

    private fun loadJournalEntries(
        entryType: String? = null,
        forceRefresh: Boolean = false
    ) {
        viewModelScope.launch {
            getJournalEntriesUseCase(entryType = entryType, forceRefresh = forceRefresh)
                .collect { result ->
                    _uiState.value = when (result) {
                        is Result.Success -> JournalListUiState.Success(result.data)
                        is Result.Error -> JournalListUiState.Error(result.error.message ?: "Unknown error")
                        is Result.Loading -> JournalListUiState.Loading
                    }
                }
        }
    }
}

sealed class JournalListUiState {
    object Loading : JournalListUiState()
    data class Success(val entries: List<JournalEntry>) : JournalListUiState()
    data class Error(val message: String) : JournalListUiState()
}
```

### Compose UI

```kotlin
// app/src/main/kotlin/com/example/facility/ui/wellness/journal/JournalListScreen.kt
package com.example.facility.ui.wellness.journal

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JournalListScreen(
    onEntryClick: (String) -> Unit,
    onCreateClick: () -> Unit,
    viewModel: JournalListViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("My Journal") },
                actions = {
                    IconButton(onClick = { viewModel.onRefresh() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                }
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = onCreateClick) {
                Icon(Icons.Default.Add, contentDescription = "Create Entry")
            }
        }
    ) { padding ->
        when (val state = uiState) {
            is JournalListUiState.Loading -> {
                Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            }

            is JournalListUiState.Success -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(padding),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(state.entries, key = { it.id.value }) { entry ->
                        JournalEntryCard(
                            entry = entry,
                            onClick = { onEntryClick(entry.id.value) }
                        )
                    }
                }
            }

            is JournalListUiState.Error -> {
                Column(
                    Modifier.fillMaxSize().padding(padding),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Text(state.message, style = MaterialTheme.typography.bodyLarge)
                    Spacer(Modifier.height(16.dp))
                    Button(onClick = { viewModel.onRefresh() }) {
                        Text("Retry")
                    }
                }
            }
        }
    }
}

@Composable
fun JournalEntryCard(
    entry: JournalEntry,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        onClick = onClick
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(entry.title.value, style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(4.dp))
            Text(entry.entryType.key, style = MaterialTheme.typography.bodySmall)

            entry.wellbeingMetrics?.let { metrics ->
                Spacer(Modifier.height(8.dp))
                Row {
                    metrics.moodRating?.let {
                        Chip(text = "Mood: ${it.value}/10")
                    }
                    Spacer(Modifier.width(8.dp))
                    metrics.stressLevel?.let {
                        Chip(text = "Stress: ${it.value}/5")
                    }
                }
            }

            // Sync status indicator
            if (entry.syncMetadata.syncStatus == SyncStatus.PENDING_SYNC) {
                Spacer(Modifier.height(8.dp))
                Row {
                    Icon(Icons.Default.CloudUpload, contentDescription = null, tint = Color.Gray)
                    Text("Syncing...", style = MaterialTheme.typography.bodySmall, color = Color.Gray)
                }
            }
        }
    }
}
```

---

## Background Sync (WorkManager)

```kotlin
// app/src/main/kotlin/com/example/facility/worker/SyncWorker.kt
package com.example.facility.worker

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.*
import com.example.facility.data.source.local.LocalDataSource
import com.example.facility.data.source.remote.RemoteDataSource
import com.example.facility.data.mapper.Mapper
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val localDataSource: LocalDataSource,
    private val remoteDataSource: RemoteDataSource,
    private val mapper: Mapper
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            // 1. Fetch pending operations
            val pendingOps = localDataSource.getPendingOperations()

            if (pendingOps.isEmpty()) {
                return@withContext Result.success()
            }

            // 2. Process each operation
            pendingOps.forEach { op ->
                try {
                    when (op.operationType) {
                        "CREATE" -> syncCreate(op)
                        "UPDATE" -> syncUpdate(op)
                        "DELETE" -> syncDelete(op)
                    }

                    // Remove from queue on success
                    localDataSource.removePendingOperation(op.entityId)

                } catch (e: Exception) {
                    // Increment retry count
                    localDataSource.incrementRetryCount(op.entityId, e.message)

                    // If max retries exceeded, mark as sync_error
                    if (op.retryCount >= MAX_RETRIES) {
                        localDataSource.markSyncError(op.entityId)
                        localDataSource.removePendingOperation(op.entityId)
                    }
                }
            }

            Result.success()

        } catch (e: Exception) {
            // Temporary failure - retry later
            Result.retry()
        }
    }

    private suspend fun syncCreate(op: PendingOperation) {
        when (op.entityType) {
            "JOURNAL" -> {
                val dto = Json.decodeFromString<JournalEntryDTO>(op.payload)
                val responseDto = remoteDataSource.createJournalEntry(dto)

                // Update local DB with server ID
                localDataSource.updateServerId(op.entityId, responseDto.id)
                localDataSource.markSynced(op.entityId)
            }
            // ... handle other entity types
        }
    }

    companion object {
        const val MAX_RETRIES = 3

        fun enqueue(workManager: WorkManager) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val syncRequest = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.MINUTES)
                .build()

            workManager.enqueueUniquePeriodicWork(
                "periodic_sync",
                ExistingPeriodicWorkPolicy.KEEP,
                syncRequest
            )
        }
    }
}
```

---

## Security Implementation

### Token Storage (Android KeyStore)

```kotlin
// app/src/main/kotlin/com/example/facility/security/SecureTokenStorage.kt
package com.example.facility.security

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SecureTokenStorage @Inject constructor(
    context: Context
) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val encryptedPrefs = EncryptedSharedPreferences.create(
        context,
        "secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun saveAccessToken(token: String) {
        encryptedPrefs.edit().putString(KEY_ACCESS_TOKEN, token).apply()
    }

    fun getAccessToken(): String? {
        return encryptedPrefs.getString(KEY_ACCESS_TOKEN, null)
    }

    fun saveRefreshToken(token: String) {
        encryptedPrefs.edit().putString(KEY_REFRESH_TOKEN, token).apply()
    }

    fun getRefreshToken(): String? {
        return encryptedPrefs.getString(KEY_REFRESH_TOKEN, null)
    }

    fun clearTokens() {
        encryptedPrefs.edit()
            .remove(KEY_ACCESS_TOKEN)
            .remove(KEY_REFRESH_TOKEN)
            .apply()
    }

    companion object {
        private const val KEY_ACCESS_TOKEN = "access_token"
        private const val KEY_REFRESH_TOKEN = "refresh_token"
    }
}
```

### Certificate Pinning

```xml
<!-- res/xml/network_security_config.xml -->
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.example.com</domain>
        <pin-set expiration="2026-01-01">
            <pin digest="SHA-256">base64hash1==</pin>
            <pin digest="SHA-256">base64hash2==</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

```xml
<!-- AndroidManifest.xml -->
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ...>
</application>
```

---

## Testing Strategy

### Unit Tests (Domain Layer)

```kotlin
class CreateJournalEntryUseCaseTest {

    private lateinit var useCase: CreateJournalEntryUseCase
    private lateinit var repository: WellnessRepository
    private lateinit var validator: JournalEntryValidator

    @Before
    fun setup() {
        repository = mockk()
        validator = JournalEntryValidator()
        useCase = CreateJournalEntryUseCase(repository, validator)
    }

    @Test
    fun `create journal entry with valid data returns success`() = runTest {
        // Given
        val request = CreateJournalEntryRequest(
            title = "Morning reflection",
            entryType = "mood_check_in",
            moodRating = 8,
            stressLevel = 2,
            privacyScope = "private"
        )

        val expectedEntry = JournalEntry(...)
        coEvery { repository.createJournalEntry(request) } returns flowOf(Result.Success(expectedEntry))

        // When
        val result = useCase(request).first()

        // Then
        assertTrue(result is Result.Success)
        assertEquals(expectedEntry, (result as Result.Success).data)
    }

    @Test
    fun `create journal entry with invalid mood rating returns error`() = runTest {
        // Given
        val request = CreateJournalEntryRequest(
            title = "Test",
            entryType = "mood_check_in",
            moodRating = 15,  // Invalid: must be 1-10
            privacyScope = "private"
        )

        // When
        val result = useCase(request).first()

        // Then
        assertTrue(result is Result.Error)
    }
}
```

### Integration Tests (Repository)

```kotlin
@HiltAndroidTest
class WellnessRepositoryImplTest {

    @get:Rule
    var hiltRule = HiltAndroidRule(this)

    @Inject
    lateinit var repository: WellnessRepository

    @Inject
    lateinit var database: FacilityDatabase

    @Before
    fun setup() {
        hiltRule.inject()
    }

    @Test
    fun `create journal entry saves to local DB and adds to sync queue`() = runTest {
        // Given
        val request = CreateJournalEntryRequest(...)

        // When
        val result = repository.createJournalEntry(request).first()

        // Then
        assertTrue(result is Result.Success)

        // Verify local DB
        val cachedEntry = database.journalDao().getById(result.data.id.value)
        assertNotNull(cachedEntry)
        assertEquals(SyncStatus.PENDING_SYNC.name, cachedEntry.syncStatus)

        // Verify pending operations queue
        val pendingOps = database.pendingOperationsDao().getAll()
        assertEquals(1, pendingOps.size)
        assertEquals("CREATE", pendingOps[0].operationType)
    }
}
```

### UI Tests (Compose)

```kotlin
@HiltAndroidTest
class JournalListScreenTest {

    @get:Rule(order = 0)
    var hiltRule = HiltAndroidRule(this)

    @get:Rule(order = 1)
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun `journal list displays entries`() {
        // Given
        val entries = listOf(
            JournalEntry(...),
            JournalEntry(...)
        )

        // When
        composeTestRule.setContent {
            JournalListScreen(
                onEntryClick = {},
                onCreateClick = {}
            )
        }

        // Then
        composeTestRule.onNodeWithText("My Journal").assertExists()
        composeTestRule.onNodeWithText(entries[0].title.value).assertExists()
        composeTestRule.onNodeWithText(entries[1].title.value).assertExists()
    }

    @Test
    fun `clicking entry navigates to detail screen`() {
        // ... test navigation
    }

    @Test
    fun `clicking FAB navigates to create screen`() {
        // ... test FAB click
    }
}
```

---

## Performance Optimization

### Image Loading (Coil)

```kotlin
@Composable
fun AsyncImageWithPlaceholder(url: String) {
    AsyncImage(
        model = ImageRequest.Builder(LocalContext.current)
            .data(url)
            .crossfade(true)
            .diskCachePolicy(CachePolicy.ENABLED)
            .memoryCachePolicy(CachePolicy.ENABLED)
            .build(),
        contentDescription = null,
        placeholder = painterResource(R.drawable.placeholder),
        error = painterResource(R.drawable.error)
    )
}
```

### Pagination

```kotlin
@Composable
fun PaginatedJobList(
    viewModel: JobListViewModel = hiltViewModel()
) {
    val lazyListState = rememberLazyListState()
    val jobs by viewModel.jobs.collectAsState()

    LazyColumn(state = lazyListState) {
        items(jobs) { job ->
            JobCard(job)
        }

        // Load more when reaching end
        if (lazyListState.isScrolledToEnd() && !viewModel.isLoading) {
            LaunchedEffect(Unit) {
                viewModel.loadNextPage()
            }
        }
    }
}

fun LazyListState.isScrolledToEnd(): Boolean {
    val lastVisibleIndex = layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
    return lastVisibleIndex >= layoutInfo.totalItemsCount - 5  // Preload 5 items before end
}
```

---

## Summary & Next Steps

This PRD defines a production-grade Kotlin Android application with:

✅ **Clean Architecture** (3-layer separation)
✅ **Offline-First** (cache-first, pending queue, conflict resolution)
✅ **Type-Safe** (value classes, sealed classes, compile-time verification)
✅ **Modern Stack** (Compose, Hilt, Room, Retrofit, Coroutines)
✅ **Secure** (KeyStore, certificate pinning, encrypted storage)
✅ **Testable** (dependency injection, interface-based, pure Kotlin domain)

**Implementation Phases**:
1. Setup project structure & modules
2. Generate DTOs from OpenAPI
3. Implement domain layer (entities, use cases, repository interfaces)
4. Implement data layer (repositories, remote/local data sources, mappers)
5. Setup database (Room schema, DAOs)
6. Implement presentation layer (ViewModels, Compose UI)
7. Background sync (WorkManager)
8. Testing & optimization
9. Security hardening
10. Performance tuning

**Reference Documents**:
- [API_CONTRACT_FOUNDATION.md](./API_CONTRACT_FOUNDATION.md) - Auth, errors, pagination
- [CODE_GENERATION_PLAN.md](./CODE_GENERATION_PLAN.md) - DTO generation
- [MAPPING_GUIDE.md](./MAPPING_GUIDE.md) - Data transformations
- Domain Contracts: WELLNESS, OPERATIONS, PEOPLE, ATTENDANCE, HELPDESK

---

**Document Version**: 1.0
**Last Reviewed**: October 30, 2025
**Target Audience**: Android Developers, Architects, External Contractors
