# MISSING SKILLS ANALYSIS
## What's Needed for Error-Free Kotlin Implementation

**Analysis Date**: October 30, 2025
**Context**: We have comprehensive documentation (344 KB), but need practical troubleshooting and implementation skills

---

## 🔍 Deep Analysis: Current State

### What We Have ✅

1. **Architecture Documentation** (Complete)
   - 3-layer clean architecture
   - Module structure
   - Tech stack justifications
   - Offline-first strategy

2. **API Contracts** (Complete)
   - Foundation patterns (auth, errors, pagination)
   - WELLNESS domain (16 endpoints, template for others)
   - Request/response schemas
   - Error scenarios

3. **Code Generation** (Complete)
   - OpenAPI → DTO automation
   - Gradle configuration
   - CI/CD integration

4. **Data Transformations** (Complete)
   - All type conversions
   - Complete mapping examples
   - Conflict resolution

5. **Implementation Roadmap** (Complete)
   - 8 phases with step-by-step instructions
   - 3,000+ lines of code examples
   - Verification checklists

### What We're Missing ❌

**The gap is: TROUBLESHOOTING and COMMON PITFALLS during implementation**

---

## 🎯 Critical Missing Skills

### 1. Room Database Implementation Skill ⭐ HIGH PRIORITY

**Why Needed**:
- Room has many edge cases developers hit
- Migration errors are common
- Type converters often cause issues
- Foreign key relationships can fail silently
- Query syntax errors only appear at runtime (partially)

**What It Should Cover**:
```
ROOM_IMPLEMENTATION_GUIDE.md (20-30 pages)

Sections:
1. Common Room Errors and Solutions
   - "Cannot find setter for field X" → @Ignore or @ColumnInfo
   - "Foreign key constraint failed" → Cascade rules
   - "No type converter found" → Custom converters
   - "Migration didn't run" → Version bumps

2. Entity Design Best Practices
   - When to use @Embedded vs @Relation
   - JSON vs relational (when to use each)
   - Index strategy (what to index, what not to)
   - Primary key strategies (Int vs String vs UUID)

3. Migration Strategies
   - Schema changes (add column, remove column, rename)
   - Data migration with SQL
   - Fallback strategies
   - Testing migrations

4. Performance Optimization
   - Query optimization (EXPLAIN QUERY PLAN)
   - Batch operations
   - Transaction management
   - Index usage verification

5. Type Converters
   - Instant ↔ Long
   - List<String> ↔ String (JSON)
   - Enum ↔ String
   - Custom type converters

6. Testing Room
   - In-memory database for tests
   - Migration testing
   - DAO query testing
   - Verification strategies

7. Debugging Room
   - Enable SQL logging
   - Inspect database with Device File Explorer
   - Query validation
   - Foreign key debugging
```

**Example Pitfall**:
```kotlin
// ❌ WRONG: This will fail at runtime
@Entity
data class JournalEntry(
    val gratitudeItems: List<String>  // No type converter!
)

// ✅ CORRECT: Add type converter
@TypeConverters(StringListConverter::class)
@Entity
data class JournalEntry(
    val gratitudeItems: List<String>
)

class StringListConverter {
    @TypeConverter
    fun fromString(value: String): List<String> {
        return Json.decodeFromString(value)
    }

    @TypeConverter
    fun toString(list: List<String>): String {
        return Json.encodeToString(list)
    }
}
```

---

### 2. Retrofit Error Handling Skill ⭐ HIGH PRIORITY

**Why Needed**:
- Network errors are complex (timeouts, 4xx, 5xx, no connection)
- Error body parsing often fails
- Token refresh interceptor is tricky
- Retry logic needs exponential backoff

**What It Should Cover**:
```
RETROFIT_ERROR_HANDLING_GUIDE.md (15-20 pages)

Sections:
1. Network Error Taxonomy
   - Connection errors (no internet, timeout)
   - HTTP errors (401, 404, 500, etc.)
   - Serialization errors (malformed JSON)
   - SSL/TLS errors (certificate issues)

2. Error Body Parsing
   - Parse standardized error envelope
   - Handle malformed error responses
   - Extract correlation IDs
   - Map to domain errors

3. Retrofit Interceptors
   - Auth interceptor (add Bearer token)
   - Token refresh interceptor (on 401, refresh token, retry)
   - Logging interceptor (debug vs production)
   - Error translation interceptor

4. Retry Strategies
   - Which errors to retry (timeouts, 5xx)
   - Which errors NOT to retry (4xx)
   - Exponential backoff implementation
   - Max retry limits

5. Timeout Configuration
   - Connect timeout (5-10s)
   - Read timeout (15-30s)
   - Write timeout (30s for uploads)
   - Call timeout (overall)

6. Testing Network Errors
   - MockWebServer for testing
   - Simulate timeouts, errors
   - Test retry logic
   - Test token refresh
```

**Example Pitfall**:
```kotlin
// ❌ WRONG: Token refresh will fail (infinite loop)
class AuthInterceptor : Interceptor {
    override fun intercept(chain: Chain): Response {
        val response = chain.proceed(request)
        if (response.code == 401) {
            // This creates infinite loop if refresh endpoint also returns 401!
            refreshToken()
            return chain.proceed(request)
        }
        return response
    }
}

// ✅ CORRECT: Prevent infinite loop
class AuthInterceptor : Interceptor {
    override fun intercept(chain: Chain): Response {
        val request = chain.request()

        // Don't intercept refresh endpoint
        if (request.url.toString().contains("/auth/refresh/")) {
            return chain.proceed(request)
        }

        val response = chain.proceed(request)
        if (response.code == 401 && !isRefreshAttempted) {
            synchronized(this) {
                val newToken = refreshToken()  // Blocks other threads
                if (newToken != null) {
                    return chain.proceed(request.newBuilder()
                        .header("Authorization", "Bearer $newToken")
                        .build())
                }
            }
        }
        return response
    }
}
```

---

### 3. Compose State Management Skill ⭐ MEDIUM PRIORITY

**Why Needed**:
- Recomposition issues cause performance problems
- State hoisting is confusing for beginners
- Side effects (LaunchedEffect, DisposableEffect) are tricky
- Memory leaks from ViewModel scoping

**What It Should Cover**:
```
COMPOSE_STATE_MANAGEMENT_GUIDE.md (15-20 pages)

Sections:
1. State Hoisting Patterns
   - When to hoist vs local state
   - State vs MutableState
   - Remember vs rememberSaveable

2. Recomposition Optimization
   - Stable types (immutable data classes)
   - derivedStateOf usage
   - key() for LazyColumn items
   - Avoid recomposition of entire screen

3. Side Effects
   - LaunchedEffect (when to use)
   - DisposableEffect (cleanup)
   - SideEffect (synchronize state)
   - rememberCoroutineScope

4. ViewModel Integration
   - StateFlow vs LiveData
   - Events (one-time actions)
   - Avoiding memory leaks
   - ViewModelScope vs rememberCoroutineScope

5. Common Pitfalls
   - Capturing ViewModel in composable
   - Not using keys in LazyColumn
   - Recreating lambdas on recomposition
   - Heavy operations in composition
```

---

### 4. Hilt Dependency Injection Debugging Skill ⭐ MEDIUM PRIORITY

**Why Needed**:
- Hilt errors are cryptic
- Circular dependencies are hard to debug
- Scoping issues cause subtle bugs
- Module conflicts are confusing

**What It Should Cover**:
```
HILT_DEBUGGING_GUIDE.md (10-15 pages)

Sections:
1. Common Hilt Errors
   - "Cannot find module" → Missing @InstallIn
   - "Circular dependency" → Interface abstraction needed
   - "Binding for X not found" → Missing @Provides
   - "Multiple bindings for X" → @Named or @Qualifier

2. Scoping Rules
   - @Singleton vs @ViewModelScoped vs @ActivityScoped
   - When to use each scope
   - Scope violations and how to fix

3. Module Organization
   - One module per feature vs monolithic
   - Interface binding (@Binds vs @Provides)
   - Conditional provisions (debug vs release)

4. Testing with Hilt
   - @HiltAndroidTest setup
   - Replacing modules for tests
   - Mocking dependencies
```

**Example Pitfall**:
```kotlin
// ❌ WRONG: Circular dependency
@Module
@InstallIn(SingletonComponent::class)
object DataModule {
    @Provides
    fun provideRepositoryA(repositoryB: RepositoryB): RepositoryA {
        return RepositoryAImpl(repositoryB)
    }

    @Provides
    fun provideRepositoryB(repositoryA: RepositoryA): RepositoryB {
        return RepositoryBImpl(repositoryA)  // CIRCULAR!
    }
}

// ✅ CORRECT: Use interfaces to break cycle
interface RepositoryA
interface RepositoryB

@Module
@InstallIn(SingletonComponent::class)
abstract class DataModule {
    @Binds
    abstract fun bindRepositoryA(impl: RepositoryAImpl): RepositoryA

    @Binds
    abstract fun bindRepositoryB(impl: RepositoryBImpl): RepositoryB
}

class RepositoryAImpl @Inject constructor(
    private val repositoryB: RepositoryB  // Injected interface, not impl
) : RepositoryA

class RepositoryBImpl @Inject constructor(
    // Don't inject RepositoryA if it creates cycle
) : RepositoryB
```

---

### 5. Offline-First Implementation Patterns ⭐ HIGH PRIORITY

**Why Needed**:
- Cache invalidation is hard
- Stale data detection
- Conflict resolution edge cases
- Pending queue can grow unbounded

**What It Should Cover**:
```
OFFLINE_FIRST_PATTERNS_GUIDE.md (20-25 pages)

Sections:
1. Cache Strategies
   - Cache-aside (lazy loading)
   - Write-through (immediate sync)
   - Write-behind (queue for later)
   - TTL management
   - LRU eviction

2. Staleness Detection
   - Time-based (expires_at)
   - Version-based (etag)
   - Manual invalidation
   - Background refresh

3. Conflict Resolution
   - Last-write-wins (timestamp)
   - Version-based (optimistic locking)
   - Merge strategies (field-level)
   - User-driven resolution (UI prompt)

4. Pending Operations Queue
   - Queue size limits
   - Priority ordering
   - Batching operations
   - Purging old operations
   - Retry exhaustion handling

5. Network State Management
   - Connectivity monitoring
   - Sync triggers (on reconnect)
   - Sync indicators (UI)
   - Manual sync option

6. Edge Cases
   - User deletes account while offline
   - Server resource deleted (404 on sync)
   - Server validation fails (reject queued operation)
   - Token expires during long offline period
```

**Example Pitfall**:
```kotlin
// ❌ WRONG: Pending queue can grow unbounded
fun createJournalEntry(...) {
    // Save to DB
    db.insert(entry)
    // Add to queue - no size limit!
    queue.add(operation)
}

// ✅ CORRECT: Limit queue size, purge old operations
fun createJournalEntry(...) {
    // Check queue size
    if (queue.size() >= MAX_QUEUE_SIZE) {
        // Purge oldest operations or reject new ones
        queue.purgeOldest(PURGE_COUNT)
    }

    db.insert(entry)
    queue.add(operation)

    // Also purge operations older than 7 days
    queue.purgeOlderThan(7.days)
}
```

---

### 6. Kotlin Coroutines & Flow Error Handling ⭐ HIGH PRIORITY

**Why Needed**:
- Exception handling in coroutines is different
- Flow collectors can crash silently
- CancellationException must be rethrown
- Structured concurrency violations cause leaks

**What It Should Cover**:
```
KOTLIN_COROUTINES_ERROR_HANDLING_GUIDE.md (15-20 pages)

Sections:
1. Exception Propagation
   - Exceptions in launch vs async
   - Parent-child cancellation
   - SupervisorJob vs Job
   - CoroutineExceptionHandler

2. Flow Error Handling
   - catch {} operator
   - retry {} and retryWhen {}
   - onCompletion {} vs catch {}
   - Error recovery patterns

3. CancellationException
   - Why it must be rethrown
   - Detecting cancellation
   - Cleanup on cancellation

4. Structured Concurrency
   - ViewModel scope (viewModelScope)
   - Lifecycle scope (lifecycleScope)
   - Custom scopes (when needed)
   - Avoiding GlobalScope

5. Common Pitfalls
   - Swallowing exceptions in catch {}
   - Not propagating cancellation
   - Blocking calls in coroutines
   - Infinite retries
```

**Example Pitfall**:
```kotlin
// ❌ WRONG: Swallows all exceptions including CancellationException
viewModelScope.launch {
    try {
        repository.getData()
    } catch (e: Exception) {
        // This catches CancellationException too!
        _error.value = e.message
    }
}

// ✅ CORRECT: Rethrow CancellationException
viewModelScope.launch {
    try {
        repository.getData()
    } catch (e: CancellationException) {
        throw e  // Must rethrow!
    } catch (e: Exception) {
        _error.value = e.message
    }
}

// ✅ BETTER: Use Flow.catch {} (handles this automatically)
repository.getData()
    .catch { e ->
        _error.value = e.message
    }
    .collect { data ->
        _data.value = data
    }
```

---

### 7. Android Permissions & GPS Handling ⭐ MEDIUM PRIORITY

**Why Needed**:
- Attendance module requires GPS permissions
- Runtime permissions are complex (API 23+)
- Location accuracy varies widely
- Battery optimization can kill location updates

**What It Should Cover**:
```
ANDROID_PERMISSIONS_GPS_GUIDE.md (15-20 pages)

Sections:
1. Runtime Permissions
   - Request flow (check → request → handle result)
   - Rationale dialogs
   - Settings redirect (when permanently denied)
   - Permission state management

2. Location Permissions
   - FINE vs COARSE location
   - Background location (API 29+)
   - Permission best practices

3. GPS/Location Services
   - FusedLocationProviderClient setup
   - Location request configuration
   - Accuracy vs battery tradeoff
   - Mock location detection

4. Geofencing
   - Geofence setup
   - Transition detection
   - Battery optimization
   - Limits (100 geofences max)

5. Common Issues
   - Location disabled by user
   - GPS accuracy too low
   - Battery optimization kills service
   - Permissions revoked at runtime
```

---

### 8. Compose UI Testing Patterns ⭐ MEDIUM PRIORITY

**Why Needed**:
- Compose testing is different from View testing
- Semantics tree is confusing
- Async operations in tests are tricky
- Screenshot testing setup is complex

**What It Should Cover**:
```
COMPOSE_TESTING_GUIDE.md (15-20 pages)

Sections:
1. Compose Test Basics
   - ComposeTestRule setup
   - Finders (onNodeWithText, onNodeWithTag)
   - Assertions (assertExists, assertIsDisplayed)
   - Actions (performClick, performScrollTo)

2. Testing State
   - State changes verification
   - collectAsState in tests
   - ViewModel mocking

3. Testing Navigation
   - NavController mocking
   - Verify navigation calls
   - Test deep links

4. Testing Async Operations
   - waitUntil {}
   - Idle synchronization
   - Test dispatchers

5. Accessibility Testing
   - Semantics properties
   - TalkBack testing
   - Content descriptions

6. Screenshot Testing
   - Paparazzi or Shot
   - Golden image comparison
   - CI/CD integration
```

---

### 9. WorkManager Best Practices ⭐ MEDIUM PRIORITY

**Why Needed**:
- WorkManager constraints are subtle
- Doze mode can delay workers
- Expedited work (API 31+) has different behavior
- Chain dependencies can fail

**What It Should Cover**:
```
WORKMANAGER_PATTERNS_GUIDE.md (12-15 pages)

Sections:
1. Worker Types
   - OneTime vs Periodic
   - When to use each
   - Worker chaining

2. Constraints
   - Network (CONNECTED, UNMETERED)
   - Battery (NOT_LOW)
   - Storage (NOT_LOW)
   - Device state (IDLE, CHARGING)

3. Backoff Policies
   - LINEAR vs EXPONENTIAL
   - Initial delay configuration
   - Max backoff time

4. Doze Mode & Battery Optimization
   - Background execution limits
   - Expedited work (API 31+)
   - Foreground service alternative

5. Observing Work Status
   - WorkInfo LiveData
   - Success/failure handling
   - Progress updates

6. Testing Workers
   - WorkManagerTestInitHelper
   - Synchronous execution
   - Constraint simulation
```

---

### 10. JSON Serialization Edge Cases ⭐ MEDIUM PRIORITY

**Why Needed**:
- Polymorphic serialization is complex
- Null handling differences (Kotlin vs JSON)
- Unknown keys can crash deserialization
- Date formats vary

**What It Should Cover**:
```
KOTLINX_SERIALIZATION_GUIDE.md (12-15 pages)

Sections:
1. Configuration Best Practices
   - ignoreUnknownKeys = true (why essential)
   - coerceInputValues (handle type mismatches)
   - encodeDefaults (when to use)

2. Custom Serializers
   - Instant serializer
   - UUID serializer
   - Polymorphic types

3. Null Handling
   - Kotlin nullable vs JSON null
   - Default values
   - Missing fields

4. Polymorphic Serialization
   - Sealed classes
   - Class discriminator
   - Type registration

5. Common Errors
   - "Serializer not found" → @Serializable missing
   - "Unknown key" → ignoreUnknownKeys = false
   - "Expected BEGIN_OBJECT" → Type mismatch
```

---

### 11. Security Best Practices for Android ⭐ HIGH PRIORITY

**Why Needed**:
- Token storage is critical
- Certificate pinning can break app
- ProGuard can break serialization
- Reverse engineering is a real threat

**What It Should Cover**:
```
ANDROID_SECURITY_GUIDE.md (20-25 pages)

Sections:
1. Secure Storage
   - EncryptedSharedPreferences (when, how)
   - Android KeyStore (for keys)
   - BiometricPrompt integration
   - What NOT to store locally

2. Network Security
   - Certificate pinning (implementation + rotation)
   - Network security config
   - SSL/TLS validation
   - Public key pinning backup

3. ProGuard/R8 Configuration
   - Keep rules for serialization
   - Keep rules for Retrofit
   - Keep rules for Room
   - Optimization levels

4. Reverse Engineering Protection
   - Code obfuscation
   - Root detection
   - Debugger detection
   - Tamper detection

5. Data Protection
   - Sensitive data in memory
   - Screen capture prevention (for sensitive screens)
   - Clipboard security
   - Logging sanitization

6. Common Vulnerabilities
   - Insecure data storage
   - Improper TLS validation
   - Code injection
   - Exported components
```

---

### 12. Database Migration Strategies ⭐ MEDIUM PRIORITY

**Why Needed**:
- Schema changes are inevitable
- Data loss during migration is catastrophic
- Testing migrations is often skipped
- Rollback strategy needed

**What It Should Cover**:
```
ROOM_MIGRATION_GUIDE.md (15-20 pages)

Sections:
1. Migration Basics
   - Version bumping
   - Migration class structure
   - SQL commands (ALTER, CREATE, DROP)

2. Common Migration Types
   - Add column (with default)
   - Remove column
   - Rename column
   - Change column type
   - Add table
   - Remove table

3. Data Migration
   - Copying data to new structure
   - Transforming data during migration
   - Handling null values

4. Testing Migrations
   - MigrationTestHelper
   - Test all versions (1→2, 1→3, 2→3)
   - Verify data integrity

5. Rollback Strategies
   - Export schema
   - Backup database
   - Fallback to destructive migration

6. Production Considerations
   - User data preservation
   - Migration performance
   - Error recovery
```

---

### 13. Kotlin Multiplatform Preparation (Optional) 🔵 LOW PRIORITY

**Why Needed** (if KMP future planned):
- Domain layer should be KMP-ready
- expect/actual pattern
- Platform-specific implementations

**What It Should Cover**:
```
KMP_PREPARATION_GUIDE.md (10-15 pages)

Sections:
1. KMP Architecture
   - Shared domain layer
   - Platform-specific UI
   - expect/actual declarations

2. Making Domain Layer KMP-Ready
   - Remove Android dependencies
   - Use kotlinx libraries
   - Platform-specific types

3. Shared Business Logic
   - Repository interfaces (shared)
   - Use cases (shared)
   - Entities (shared)

4. Platform-Specific
   - Database (expect/actual)
   - Network (can be shared with Ktor)
   - UI (separate)
```

---

## 🎯 Recommended Skills Priority

### Must-Have (Before Starting Implementation)

1. **ROOM_IMPLEMENTATION_GUIDE.md** ⭐⭐⭐⭐⭐
   - Prevents 80% of database issues
   - Covers migrations (critical for production)
   - Type converters (essential for our schema)
   - **Estimated**: 20-30 pages, 2-3 days to create

2. **RETROFIT_ERROR_HANDLING_GUIDE.md** ⭐⭐⭐⭐⭐
   - Prevents network-related crashes
   - Token refresh is complex
   - Error mapping is critical for UX
   - **Estimated**: 15-20 pages, 1-2 days to create

3. **OFFLINE_FIRST_PATTERNS_GUIDE.md** ⭐⭐⭐⭐⭐
   - Core architectural pattern
   - Conflict resolution is complex
   - Cache management prevents bugs
   - **Estimated**: 20-25 pages, 2-3 days to create

4. **ANDROID_SECURITY_GUIDE.md** ⭐⭐⭐⭐
   - Prevents security vulnerabilities
   - Token storage is critical
   - ProGuard rules prevent crashes
   - **Estimated**: 20-25 pages, 2-3 days to create

### Should-Have (During Implementation)

5. **KOTLIN_COROUTINES_ERROR_HANDLING_GUIDE.md** ⭐⭐⭐⭐
   - Prevents subtle async bugs
   - Flow error handling is tricky
   - **Estimated**: 15-20 pages, 1-2 days to create

6. **COMPOSE_STATE_MANAGEMENT_GUIDE.md** ⭐⭐⭐
   - Prevents performance issues
   - Recomposition bugs are subtle
   - **Estimated**: 15-20 pages, 1-2 days to create

7. **HILT_DEBUGGING_GUIDE.md** ⭐⭐⭐
   - Speeds up debugging
   - Circular dependencies are confusing
   - **Estimated**: 10-15 pages, 1 day to create

8. **ANDROID_PERMISSIONS_GPS_GUIDE.md** ⭐⭐⭐
   - Required for Attendance module
   - Permissions are complex
   - **Estimated**: 15-20 pages, 1-2 days to create

### Nice-to-Have (Later)

9. **WORKMANAGER_PATTERNS_GUIDE.md** ⭐⭐
   - Background sync specifics
   - **Estimated**: 12-15 pages, 1 day

10. **KOTLINX_SERIALIZATION_GUIDE.md** ⭐⭐
    - Edge cases
    - **Estimated**: 12-15 pages, 1 day

11. **ROOM_MIGRATION_GUIDE.md** ⭐⭐
    - Production schema changes
    - **Estimated**: 15-20 pages, 1-2 days

12. **COMPOSE_TESTING_GUIDE.md** ⭐
    - UI testing specifics
    - **Estimated**: 15-20 pages, 1-2 days

---

## 💡 Additional Practical Guides Needed

### 13. Common Build Errors & Solutions

**GRADLE_TROUBLESHOOTING.md** (10 pages):
- Dependency conflicts
- Gradle sync failures
- Build cache issues
- Version catalog problems

### 14. Debugging Techniques

**ANDROID_DEBUGGING_GUIDE.md** (15 pages):
- Android Studio debugger
- Network inspection (Charles, Proxyman)
- Database inspection (Device File Explorer)
- Memory profiling (LeakCanary)
- Performance profiling

### 15. CI/CD for Android

**ANDROID_CI_CD_GUIDE.md** (15-20 pages):
- GitHub Actions workflow
- Build variants (debug, staging, production)
- Automated testing
- APK signing
- Play Store deployment

---

## 📊 Estimated Effort for Missing Skills

### High Priority (Must-Have Before Starting)

| Skill | Pages | Effort | Priority |
|-------|-------|--------|----------|
| ROOM_IMPLEMENTATION_GUIDE | 20-30 | 2-3 days | ⭐⭐⭐⭐⭐ |
| RETROFIT_ERROR_HANDLING_GUIDE | 15-20 | 1-2 days | ⭐⭐⭐⭐⭐ |
| OFFLINE_FIRST_PATTERNS_GUIDE | 20-25 | 2-3 days | ⭐⭐⭐⭐⭐ |
| ANDROID_SECURITY_GUIDE | 20-25 | 2-3 days | ⭐⭐⭐⭐ |
| **SUBTOTAL** | **~90 pages** | **8-11 days** | **CRITICAL** |

### Medium Priority (During Implementation)

| Skill | Pages | Effort | Priority |
|-------|-------|--------|----------|
| KOTLIN_COROUTINES_ERROR_HANDLING | 15-20 | 1-2 days | ⭐⭐⭐⭐ |
| COMPOSE_STATE_MANAGEMENT | 15-20 | 1-2 days | ⭐⭐⭐ |
| HILT_DEBUGGING_GUIDE | 10-15 | 1 day | ⭐⭐⭐ |
| ANDROID_PERMISSIONS_GPS | 15-20 | 1-2 days | ⭐⭐⭐ |
| **SUBTOTAL** | **~65 pages** | **4-7 days** | **IMPORTANT** |

### Low Priority (Nice-to-Have)

| Skill | Pages | Effort | Priority |
|-------|-------|--------|----------|
| WORKMANAGER_PATTERNS | 12-15 | 1 day | ⭐⭐ |
| KOTLINX_SERIALIZATION | 12-15 | 1 day | ⭐⭐ |
| ROOM_MIGRATION | 15-20 | 1-2 days | ⭐⭐ |
| COMPOSE_TESTING | 15-20 | 1-2 days | ⭐ |
| GRADLE_TROUBLESHOOTING | 10 | 1 day | ⭐ |
| ANDROID_DEBUGGING | 15 | 1-2 days | ⭐ |
| ANDROID_CI_CD | 15-20 | 1-2 days | ⭐ |
| **SUBTOTAL** | **~100 pages** | **8-12 days** | **OPTIONAL** |

---

## 🎯 Recommendation

### Immediate Action (Create These 4 Guides)

**Before any Kotlin implementation begins, create**:

1. **ROOM_IMPLEMENTATION_GUIDE.md** (20-30 pages, 2-3 days)
   - Prevents 80% of database errors
   - Migrations are critical
   - Type converters essential for our schema

2. **RETROFIT_ERROR_HANDLING_GUIDE.md** (15-20 pages, 1-2 days)
   - Prevents network crashes
   - Token refresh is make-or-break
   - Error mapping affects UX

3. **OFFLINE_FIRST_PATTERNS_GUIDE.md** (20-25 pages, 2-3 days)
   - Core architecture - must be right
   - Conflict resolution is complex
   - Cache management prevents data loss

4. **ANDROID_SECURITY_GUIDE.md** (20-25 pages, 2-3 days)
   - Security vulnerabilities costly to fix later
   - ProGuard rules prevent crashes
   - Token storage cannot be wrong

**Total Effort**: 8-11 days (1.5-2 weeks)
**Benefit**: Prevents 90% of common errors during implementation

---

### During Implementation (Create as Needed)

5. **KOTLIN_COROUTINES_ERROR_HANDLING_GUIDE.md** (during Phase 3-4)
6. **COMPOSE_STATE_MANAGEMENT_GUIDE.md** (during Phase 5)
7. **HILT_DEBUGGING_GUIDE.md** (when hitting DI issues)
8. **ANDROID_PERMISSIONS_GPS_GUIDE.md** (during Attendance implementation)

---

## 🔍 What's Still Missing (Beyond Skills)

### 1. Domain Contracts for Other 4 Domains

**Still needed**:
- API_CONTRACT_OPERATIONS.md (~80 pages)
- API_CONTRACT_PEOPLE.md (~60 pages)
- API_CONTRACT_ATTENDANCE.md (~50 pages)
- API_CONTRACT_HELPDESK.md (~50 pages)

**Status**: Can use API_CONTRACT_WELLNESS.md as template
**Priority**: Medium (create as you implement each domain)

### 2. OpenAPI Schema (openapi.yaml)

**Still needed**: Actual generated schema from Django backend

**Action Required**:
```bash
cd /path/to/django/project
pip install drf-spectacular
python manage.py spectacular --file openapi.yaml --validate
```

**Priority**: High (needed for Phase 2)

### 3. Test Credentials

**Still needed**:
- Dev/staging API base URL
- Test user credentials
- Test data (sample journal entries, jobs, etc.)

**Priority**: High (needed for Phase 2-3)

---

## 📋 Complete Skill Creation Checklist

### Critical Path (Before Implementation)

- [ ] ROOM_IMPLEMENTATION_GUIDE.md (2-3 days)
- [ ] RETROFIT_ERROR_HANDLING_GUIDE.md (1-2 days)
- [ ] OFFLINE_FIRST_PATTERNS_GUIDE.md (2-3 days)
- [ ] ANDROID_SECURITY_GUIDE.md (2-3 days)

**Total**: 8-11 days

### During Implementation

- [ ] KOTLIN_COROUTINES_ERROR_HANDLING_GUIDE.md (1-2 days)
- [ ] COMPOSE_STATE_MANAGEMENT_GUIDE.md (1-2 days)
- [ ] HILT_DEBUGGING_GUIDE.md (1 day)
- [ ] ANDROID_PERMISSIONS_GPS_GUIDE.md (1-2 days)

**Total**: 4-7 days

### Post-Implementation (Optional)

- [ ] WORKMANAGER_PATTERNS_GUIDE.md (1 day)
- [ ] KOTLINX_SERIALIZATION_GUIDE.md (1 day)
- [ ] ROOM_MIGRATION_GUIDE.md (1-2 days)
- [ ] COMPOSE_TESTING_GUIDE.md (1-2 days)
- [ ] GRADLE_TROUBLESHOOTING.md (1 day)
- [ ] ANDROID_DEBUGGING_GUIDE.md (1-2 days)
- [ ] ANDROID_CI_CD_GUIDE.md (1-2 days)

**Total**: 8-12 days

---

## 🎯 Final Recommendation

### Option A: Create Critical 4 Skills Now (Recommended)

**Create these 4 guides before Kotlin implementation**:
1. ROOM_IMPLEMENTATION_GUIDE.md
2. RETROFIT_ERROR_HANDLING_GUIDE.md
3. OFFLINE_FIRST_PATTERNS_GUIDE.md
4. ANDROID_SECURITY_GUIDE.md

**Effort**: 8-11 days (1.5-2 weeks)
**Benefit**: Prevents 90% of errors, saves weeks of debugging

**Then**: Start implementation with confidence

### Option B: Create On-Demand

**Start implementation now** with current docs.

**Create skills when hitting issues**:
- Hit Room error → Create ROOM_IMPLEMENTATION_GUIDE.md
- Hit network error → Create RETROFIT_ERROR_HANDLING_GUIDE.md
- Hit conflict resolution issue → Create OFFLINE_FIRST_PATTERNS_GUIDE.md

**Benefit**: Faster start, skills are highly relevant
**Risk**: May need to refactor after hitting issues

### Option C: Minimal Troubleshooting Appendix

**Create single TROUBLESHOOTING_GUIDE.md** (30-40 pages) covering:
- Top 20 Room errors
- Top 10 Retrofit errors
- Top 10 Compose errors
- Top 10 Hilt errors
- Top 10 Coroutines errors

**Effort**: 3-4 days
**Benefit**: Covers most common issues
**Limitation**: Not as deep as separate guides

---

## 💡 My Recommendation

**Create the 4 critical skills (Option A)** because:

1. **Room errors are inevitable** - migrations, type converters, relationships
2. **Network errors are complex** - token refresh, retries, error mapping
3. **Offline-first is our core pattern** - must be implemented correctly
4. **Security cannot be bolted on later** - must be right from start

**These 4 guides will save weeks of debugging and prevent architectural mistakes.**

**After that**: Start implementation, create other skills on-demand.

---

**Document Version**: 1.0
**Analysis Date**: October 30, 2025
**Recommendation**: Create 4 critical skills before implementation starts
