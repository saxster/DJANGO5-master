# Complete Sync Flow Guide for Android Team

**Purpose**: Step-by-step sync implementation for Job → Jobneed schema migration
**Last Updated**: October 3, 2025

---

## 🔄 **Sync Flow Overview**

```
┌─────────────┐
│   Android   │
│   Device    │
└──────┬──────┘
       │
       │ 1. Auth + Check Schema Version
       ↓
┌─────────────┐
│  Backend    │───→ Returns: capabilities: ["JOB_JOBNEED_V2"]
│   Django5   │
└──────┬──────┘
       │
       │ 2. Decide: Use Old or New Schema
       ↓
   ┌───────┴───────┐
   │               │
   ↓ (Old)    ↓ (New)
┌──────────┐ ┌──────────┐
│ Legacy   │ │ Enhanced │
│ Schema   │ │ Schema   │
└──────────┘ └──────────┘
```

---

## 📋 **Complete Sync Implementation**

### Step 1: Authentication & Schema Detection

```kotlin
// SyncManager.kt
class SyncManager(
    private val apolloClient: ApolloClient,
    private val database: AppDatabase,
    private val preferences: SharedPreferences
) {
    companion object {
        private const val PREF_SCHEMA_VERSION = "schema_version"
        private const val PREF_LAST_SYNC = "last_sync_timestamp"
    }

    suspend fun performSync(): SyncResult {
        return withContext(Dispatchers.IO) {
            try {
                // 1. Authenticate and get capabilities
                val authResult = authenticate()

                // 2. Detect schema version
                val schemaVersion = detectSchemaVersion(authResult)

                // 3. Run appropriate sync
                when (schemaVersion) {
                    SchemaVersion.V1_LEGACY -> syncLegacySchema()
                    SchemaVersion.V2_ENHANCED -> syncEnhancedSchema()
                }

                // 4. Update last sync timestamp
                preferences.edit {
                    putLong(PREF_LAST_SYNC, System.currentTimeMillis())
                }

                SyncResult.Success

            } catch (e: Exception) {
                Log.e("Sync", "Sync failed", e)
                SyncResult.Failure(e.message ?: "Unknown error")
            }
        }
    }

    private fun detectSchemaVersion(authResult: AuthResponse): SchemaVersion {
        // Check feature flag in auth response
        val capabilities = authResult.user?.capabilities ?: emptyList()

        return when {
            capabilities.contains("JOB_JOBNEED_V2") -> {
                Log.i("Sync", "Using enhanced schema (v2)")
                preferences.edit {
                    putString(PREF_SCHEMA_VERSION, "v2")
                }
                SchemaVersion.V2_ENHANCED
            }
            else -> {
                Log.i("Sync", "Using legacy schema (v1)")
                preferences.edit {
                    putString(PREF_SCHEMA_VERSION, "v1")
                }
                SchemaVersion.V1_LEGACY
            }
        }
    }

    private suspend fun syncLegacySchema(): SyncResult {
        Log.i("Sync", "Syncing with legacy schema (Jobneed-only)")

        // Use existing sync logic (unchanged)
        val lastSync = preferences.getLong(PREF_LAST_SYNC, 0)
        val mdtzFormatted = formatTimestampForBackend(lastSync)

        val result = apolloClient.query(
            GetJobneedModifiedAfterQuery(
                mdtz = mdtzFormatted,
                peopleid = currentUser.id,
                siteid = currentSite.id
            )
        ).execute()

        // Parse and insert jobneeds (existing logic)
        result.data?.getJobneedmodifiedafter?.records?.let { recordsJson ->
            val jobneeds = JSON.decodeFromString<List<Jobneed>>(recordsJson)
            database.jobneedDao().insertOrUpdateAll(jobneeds)
        }

        return SyncResult.Success
    }

    private suspend fun syncEnhancedSchema(): SyncResult {
        Log.i("Sync", "Syncing with enhanced schema (Job + Jobneed)")

        // NEW sync logic for v2 schema
        val result = apolloClient.query(
            GetJobsWithLatestJobneedsQuery(
                peopleId = currentUser.id,
                buId = currentSite.id,
                clientId = currentClient.id
            )
        ).execute()

        if (result.hasErrors()) {
            Log.e("Sync", "GraphQL errors: ${result.errors}")
            return SyncResult.Failure("GraphQL query failed")
        }

        // Process Jobs
        result.data?.allJobs?.edges?.forEach { edge ->
            val job = edge.node

            // 1. Insert/Update Job
            database.jobDao().insertOrUpdate(job.toEntity())

            // 2. Insert/Update latest Jobneed
            job.jobneed?.let { latestJobneed ->
                database.jobneedDao().insertOrUpdate(latestJobneed.toEntity())

                // 3. Sync JobneedDetails for latest jobneed
                latestJobneed.details?.forEach { detail ->
                    database.jobneedDetailsDao().insertOrUpdate(detail.toEntity())
                }
            }

            // 4. Optional: Insert historical jobneeds
            job.jobneeds?.forEach { historicalJobneed ->
                database.jobneedDao().insertOrUpdate(historicalJobneed.toEntity())
            }
        }

        return SyncResult.Success
    }
}

enum class SchemaVersion {
    V1_LEGACY,
    V2_ENHANCED
}

sealed class SyncResult {
    object Success : SyncResult()
    data class Failure(val message: String) : SyncResult()
}
```

---

## 📊 **Sync Scenario Examples**

### Scenario 1: First Sync After Migration

**Initial State (Android)**:
- User upgraded app v1 → v2
- Local migration complete (Job table created)
- Job table populated from Jobneed data (estimated values)
- Need accurate Job data from backend

**Sync Flow**:
```
1. Android → Backend: GetJobsWithLatestJobneeds(peopleId, buId, clientId)

2. Backend → Android: Returns 50 Jobs with:
   - Accurate Job data (cron, frequency, dates)
   - Latest Jobneed for each Job
   - NO history (save bandwidth on first sync)

3. Android:
   - REPLACE Job records (overwrite estimated data)
   - MERGE Jobneed records (keep local changes if modified)
   - Resolve conflicts if any

4. Result: Local database has accurate Job templates
```

**Code**:
```kotlin
suspend fun firstSyncAfterMigration() {
    // Query without history to save bandwidth
    val result = apolloClient.query(
        GetJobsWithLatestJobneedsQuery(
            peopleId = currentUser.id,
            buId = currentSite.id,
            clientId = currentClient.id
        )
    ).execute()

    result.data?.allJobs?.edges?.forEach { edge ->
        val job = edge.node

        // Overwrite estimated Job data with accurate backend data
        database.jobDao().insertOrUpdate(
            job.toEntity().copy(
                // Ensure we don't overwrite local changes
                version = job.version,
                mdtz = maxOf(job.mdtz, getLocalJob(job.id)?.mdtz ?: 0)
            )
        )

        // Merge latest jobneed (conflict resolution)
        job.jobneed?.let { remoteJobneed ->
            val localJobneed = database.jobneedDao().getById(remoteJobneed.id)

            when {
                localJobneed == null -> {
                    // New from server - insert
                    database.jobneedDao().insertOrUpdate(remoteJobneed.toEntity())
                }
                localJobneed.mdtz > remoteJobneed.mdtz -> {
                    // Local newer - keep local, sync to server later
                    Log.i("Sync", "Local jobneed newer - keeping local version")
                }
                else -> {
                    // Remote newer - update local
                    database.jobneedDao().insertOrUpdate(remoteJobneed.toEntity())
                }
            }
        }
    }

    // Mark first sync complete
    preferences.edit {
        putBoolean("first_sync_v2_complete", true)
    }
}
```

---

### Scenario 2: Daily Incremental Sync

**Ongoing State**:
- App has been using v2 schema for 1 week
- User completes tasks daily
- Need to sync changes both ways

**Sync Flow**:
```
1. Android → Backend: Upload local changes (completed jobneeds)
   - UpdateJobneed mutation for each modified jobneed

2. Backend → Android: Download server changes
   - New Jobs added by admin
   - New Jobneeds generated by scheduler
   - Other users' updates

3. Conflict Resolution:
   - If same jobneed modified on both sides:
     - Check version field (optimistic locking)
     - Show conflict UI to user
     - Let user choose which version to keep

4. Result: Both sides synchronized
```

**Code**:
```kotlin
suspend fun incrementalSync() {
    // PHASE 1: Upload local changes
    val localChanges = database.jobneedDao().getModifiedAfter(lastSyncTime)

    localChanges.forEach { jobneed ->
        try {
            val result = apolloClient.mutate(
                UpdateJobneedMutation(
                    jobneedId = jobneed.id,
                    updates = jobneed.toUpdateInput()
                )
            ).execute()

            if (result.hasErrors()) {
                // Check for version conflict
                val error = result.errors?.firstOrNull()
                if (error?.extensions?.get("code") == "CONFLICT") {
                    handleVersionConflict(jobneed, error)
                } else {
                    Log.e("Sync", "Update failed: ${error?.message}")
                }
            } else {
                // Mark as synced
                database.jobneedDao().markAsSynced(jobneed.id)
            }
        } catch (e: ApolloException) {
            Log.e("Sync", "Network error uploading jobneed ${jobneed.id}", e)
            // Will retry on next sync
        }
    }

    // PHASE 2: Download server changes
    val lastMdtz = preferences.getLong(PREF_LAST_SYNC, 0)

    val result = apolloClient.query(
        GetJobsWithLatestJobneedsQuery(
            peopleId = currentUser.id,
            buId = currentSite.id,
            clientId = currentClient.id,
            modifiedAfter = lastMdtz  // Only get changes
        )
    ).execute()

    result.data?.allJobs?.edges?.forEach { edge ->
        val job = edge.node

        // Check if Job is new or updated
        val localJob = database.jobDao().getById(job.id)

        when {
            localJob == null -> {
                // New Job from server
                database.jobDao().insertOrUpdate(job.toEntity())
                Log.i("Sync", "New Job: ${job.jobname}")
            }
            job.mdtz > localJob.mdtz -> {
                // Server has newer version
                database.jobDao().insertOrUpdate(job.toEntity())
                Log.i("Sync", "Updated Job: ${job.jobname}")
            }
            else -> {
                // Local is current or newer - skip
                Log.d("Sync", "Job ${job.jobname} already up to date")
            }
        }

        // Sync latest jobneed
        job.jobneed?.let { remoteJobneed ->
            mergeJobneed(remoteJobneed.toEntity())
        }
    }

    // Update last sync time
    preferences.edit {
        putLong(PREF_LAST_SYNC, System.currentTimeMillis())
    }
}

private suspend fun mergeJobneed(remoteJobneed: Jobneed) {
    val localJobneed = database.jobneedDao().getById(remoteJobneed.id)

    when {
        localJobneed == null -> {
            // New jobneed - insert
            database.jobneedDao().insertOrUpdate(remoteJobneed)
        }
        localJobneed.version > remoteJobneed.version -> {
            // Local has higher version - keep local
            Log.i("Sync", "Local jobneed version higher - syncing to server")
            uploadJobneed(localJobneed)
        }
        remoteJobneed.version > localJobneed.version -> {
            // Server has higher version - take remote
            database.jobneedDao().insertOrUpdate(remoteJobneed)
        }
        else -> {
            // Same version - check mdtz
            if (remoteJobneed.mdtz > localJobneed.mdtz) {
                database.jobneedDao().insertOrUpdate(remoteJobneed)
            }
        }
    }
}

private suspend fun handleVersionConflict(
    localJobneed: Jobneed,
    error: Error
) {
    // Show conflict dialog to user
    val expectedVersion = error.extensions["expected_version"] as? Int ?: 0
    val actualVersion = error.extensions["actual_version"] as? Int ?: 0

    val choice = showConflictDialog(
        title = "Data Conflict",
        message = "This task was modified on another device. Choose which version to keep:",
        localData = "Your version (modified ${formatTime(localJobneed.mdtz)})",
        remoteData = "Server version (version $actualVersion)"
    )

    when (choice) {
        ConflictChoice.KEEP_LOCAL -> {
            // Fetch latest from server, merge local changes
            val latest = fetchLatestJobneed(localJobneed.id)
            val merged = mergeJobneedData(local = localJobneed, remote = latest)
            database.jobneedDao().insertOrUpdate(merged)
        }
        ConflictChoice.KEEP_REMOTE -> {
            // Discard local, fetch server version
            val latest = fetchLatestJobneed(localJobneed.id)
            database.jobneedDao().insertOrUpdate(latest)
        }
        ConflictChoice.REVIEW -> {
            // Show side-by-side comparison
            showConflictReviewScreen(localJobneed, fetchLatestJobneed(localJobneed.id))
        }
    }
}
```

---

## 🎯 **Scenario-Based Sync Patterns**

### Pattern 1: User Completes Task Offline

**Timeline**:
```
T0: User opens app, loads task (Jobneed #1003, status=ASSIGNED)
T1: User goes offline
T2: User completes task, fills checklist
T3: App saves locally (status=COMPLETED, answers filled)
T4: Meanwhile, backend generates NEW jobneed #1004 for tomorrow
T5: User comes online, sync runs
```

**Conflict**:
- Device has: Jobneed #1003 (COMPLETED, mdtz=T3)
- Server has: Jobneed #1003 (ASSIGNED, mdtz=T0) + NEW Jobneed #1004 (ASSIGNED)

**Resolution**:
```kotlin
suspend fun syncOfflineCompletedTask() {
    // 1. Upload completed jobneed
    val localJobneed = database.jobneedDao().getById(1003)

    if (localJobneed.jobstatus == "COMPLETED") {
        // Upload to server
        val result = apolloClient.mutate(
            UpdateJobneedMutation(
                jobneedId = localJobneed.id,
                updates = JobneedUpdateInput(
                    jobstatus = "COMPLETED",
                    starttime = localJobneed.starttime,
                    endtime = localJobneed.endtime,
                    gpslocation = localJobneed.gpslocation,
                    remarks = localJobneed.remarks,
                    version = localJobneed.version  // For optimistic locking
                )
            )
        ).execute()

        if (result.data?.updateJobneed?.success == true) {
            Log.i("Sync", "Uploaded completed jobneed #1003")

            // Mark as synced
            database.jobneedDao().markAsSynced(1003)
        }
    }

    // 2. Download new jobneeds from server
    val job = database.jobDao().getById(localJobneed.jobId)

    val latestJobneedResult = apolloClient.query(
        GetJobQuery(jobId = job.id)
    ).execute()

    latestJobneedResult.data?.job?.jobneed?.let { latestFromServer ->
        if (latestFromServer.id != localJobneed.id) {
            // NEW jobneed generated (tomorrow's task)
            database.jobneedDao().insertOrUpdate(latestFromServer.toEntity())

            // Notify user
            showNotification(
                title = "New Task Scheduled",
                message = "Tomorrow's ${job.jobname} is ready"
            )
        }
    }
}
```

---

### Pattern 2: Admin Creates New Job (Server-Side)

**Timeline**:
```
T0: Admin creates new Job #999 "Weekly Fire Drill" on web dashboard
T1: Backend generates first Jobneed #2001 for this Job
T2: User's app runs sync
T3: App receives NEW Job + Jobneed
```

**Sync Flow**:
```kotlin
suspend fun syncNewJobsFromServer() {
    val result = apolloClient.query(
        GetJobsWithLatestJobneedsQuery(
            peopleId = currentUser.id,
            buId = currentSite.id,
            clientId = currentClient.id
        )
    ).execute()

    result.data?.allJobs?.edges?.forEach { edge ->
        val job = edge.node

        // Check if Job exists locally
        val existsLocally = database.jobDao().getById(job.id) != null

        if (!existsLocally) {
            // NEW Job from server
            Log.i("Sync", "Received new Job: ${job.jobname}")

            // Insert Job
            database.jobDao().insertOrUpdate(job.toEntity())

            // Insert latest Jobneed
            job.jobneed?.let { jobneed ->
                database.jobneedDao().insertOrUpdate(jobneed.toEntity())

                // Insert JobneedDetails
                jobneed.details?.forEach { detail ->
                    database.jobneedDetailsDao().insertOrUpdate(detail.toEntity())
                }
            }

            // Show notification to user
            showNotification(
                title = "New Task Assigned",
                message = "${job.jobname} - due ${formatDate(job.jobneed?.plandatetime)}"
            )
        }
    }
}
```

---

### Pattern 3: User Updates Task, Another User Updates Same Task

**Timeline**:
```
T0: User A loads Jobneed #1003 (version=5, status=ASSIGNED)
T1: User A marks task INPROGRESS (offline)
T2: User B marks same task COMPLETED (online, version=6 saved to server)
T3: User A comes online, tries to sync
```

**Conflict Detection**:
```kotlin
suspend fun syncWithConflictDetection() {
    val localJobneed = database.jobneedDao().getById(1003)

    // Try to upload local changes
    val result = apolloClient.mutate(
        UpdateJobneedMutation(
            jobneedId = localJobneed.id,
            updates = JobneedUpdateInput(
                jobstatus = "INPROGRESS",  // User A's change
                version = 5  // User A's version
            )
        )
    ).execute()

    // Check for conflict
    if (result.hasErrors()) {
        val error = result.errors?.firstOrNull()

        if (error?.extensions?.get("code") == "CONFLICT") {
            // Version mismatch detected
            val expectedVersion = error.extensions["expected_version"] as Int  // 5
            val actualVersion = error.extensions["actual_version"] as Int      // 6

            Log.w("Sync", "Conflict: Expected v$expectedVersion, server has v$actualVersion")

            // Fetch latest from server
            val latestFromServer = fetchLatestJobneed(1003)

            // Show conflict UI
            val choice = showConflictDialog(
                localVersion = localJobneed,
                remoteVersion = latestFromServer
            )

            when (choice) {
                ConflictChoice.KEEP_LOCAL -> {
                    // Re-upload with latest version
                    apolloClient.mutate(
                        UpdateJobneedMutation(
                            jobneedId = localJobneed.id,
                            updates = JobneedUpdateInput(
                                jobstatus = "INPROGRESS",
                                version = actualVersion  // Use server version
                            )
                        )
                    ).execute()
                }
                ConflictChoice.KEEP_REMOTE -> {
                    // Accept server version
                    database.jobneedDao().insertOrUpdate(latestFromServer)
                }
            }
        }
    } else {
        // Success - mark as synced
        database.jobneedDao().markAsSynced(localJobneed.id)
    }
}
```

---

### Pattern 4: Scheduler Generates Multiple Jobneeds for Same Job

**Timeline**:
```
T0: Job #123 "Daily Pump Check" (cron: "0 10 * * *")
T1: Backend scheduler runs at 5:00 AM
T2: Scheduler generates:
    - Jobneed #1003 for Oct 3 10:00 AM
    - Jobneed #1004 for Oct 4 10:00 AM  (next day)
T3: User's app syncs at 9:00 AM
```

**Sync Logic**:
```kotlin
suspend fun syncSchedulerGeneratedJobneeds() {
    val result = apolloClient.query(
        GetJobQuery(jobId = 123)
    ).execute()

    val job = result.data?.job ?: return

    // Server returns latest + history
    val latestJobneed = job.jobneed  // #1004 (Oct 4)
    val history = job.jobneeds       // [#1004, #1003]

    // Insert all jobneeds
    history?.forEach { jobneed ->
        val existsLocally = database.jobneedDao().getById(jobneed.id) != null

        if (!existsLocally) {
            database.jobneedDao().insertOrUpdate(jobneed.toEntity())
            Log.i("Sync", "New jobneed: ${jobneed.jobdesc} at ${jobneed.plandatetime}")
        }
    }

    // Update UI to show today's tasks
    val today = DateTime.now().withTimeAtStartOfDay()
    val todaysJobneeds = database.jobneedDao().getByDate(
        date = today.millis,
        status = "ASSIGNED"
    )

    // Refresh task list
    _tasksFlow.emit(todaysJobneeds)
}
```

---

## 🔍 **Debugging & Validation**

### Validation Queries (Android SQLite):

```kotlin
// Check if Job table has correct foreign key relationships
suspend fun validateJobneedJobRelationship() {
    val jobneedsWithInvalidJobId = database.query(
        SimpleSQLiteQuery("""
            SELECT j.id, j.job_id, j.jobdesc
            FROM jobneed j
            LEFT JOIN job ON j.job_id = job.id
            WHERE j.job_id IS NOT NULL AND job.id IS NULL
        """)
    )

    if (jobneedsWithInvalidJobId.count > 0) {
        Log.e("Validation", "Found jobneeds with invalid job_id FK")
        // These jobneeds point to Jobs that don't exist locally
        // Solution: Sync these Jobs from server
    }
}

// Check for duplicate questions in checklist
suspend fun validateJobneedDetailsConstraints() {
    val duplicates = database.query(
        SimpleSQLiteQuery("""
            SELECT jobneed_id, question_id, COUNT(*) as count
            FROM jobneeddetails
            GROUP BY jobneed_id, question_id
            HAVING COUNT(*) > 1
        """)
    )

    if (duplicates.count > 0) {
        Log.e("Validation", "Found duplicate questions in checklist - data integrity issue!")
        // Should NEVER happen due to backend constraints
        // If found, report as critical bug
    }
}

// Check "latest" logic is correct
suspend fun validateLatestJobneedLogic() {
    val jobId = 123L

    // Get latest using helper method
    val latestViaHelper = database.jobneedDao().getLatestForJob(jobId)

    // Get latest manually (verification)
    val latestManual = database.jobneedDao()
        .getHistoryForJob(jobId, limit = 1)
        .firstOrNull()

    // Should be same
    assert(latestViaHelper?.id == latestManual?.id) {
        "Latest jobneed mismatch!"
    }

    Log.i("Validation", "Latest jobneed for Job $jobId: ${latestViaHelper?.id}")
}
```

---

## ⚡ **Performance Optimization Tips**

### Batch Inserts:

```kotlin
// BAD: Insert one at a time (slow)
jobneeds.forEach { jobneed ->
    database.jobneedDao().insertOrUpdate(jobneed)  // 100 transactions!
}

// GOOD: Batch insert (fast)
database.withTransaction {
    database.jobneedDao().insertOrUpdateAll(jobneeds)  // 1 transaction
}
```

### Index Usage:

```kotlin
// Ensure these indexes exist for fast queries
@Database(...)
abstract class AppDatabase : RoomDatabase() {
    // Migration should create these indexes
    companion object {
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(database: SupportSQLiteDatabase) {
                // ... create tables ...

                // CRITICAL: Index for "latest" queries
                database.execSQL("""
                    CREATE INDEX index_jobneed_job_plandatetime
                    ON jobneed(job_id, plandatetime DESC)
                """)

                // CRITICAL: Index for status filtering
                database.execSQL("""
                    CREATE INDEX index_jobneed_status_date
                    ON jobneed(jobstatus, plandatetime)
                """)
            }
        }
    }
}
```

### Query Optimization:

```kotlin
// Get today's tasks (optimized)
@Query("""
    SELECT j.*
    FROM jobneed j
    INNER JOIN job ON j.job_id = job.id
    WHERE j.jobstatus = :status
      AND DATE(j.plandatetime / 1000, 'unixepoch') = DATE(:today / 1000, 'unixepoch')
      AND job.enable = 1
    ORDER BY j.plandatetime ASC
""")
fun getTodaysTasks(
    status: String = "ASSIGNED",
    today: Long = System.currentTimeMillis()
): Flow<List<Jobneed>>
```

---

## 🧪 **Testing Checklist for Android**

### Unit Tests:

```kotlin
class SyncManagerTest {
    @Test
    fun `test schema detection uses capabilities flag`() = runTest {
        val authResponse = AuthResponse(
            user = User(
                capabilities = listOf("JOB_JOBNEED_V2")
            )
        )

        val schemaVersion = syncManager.detectSchemaVersion(authResponse)

        assertEquals(SchemaVersion.V2_ENHANCED, schemaVersion)
    }

    @Test
    fun `test latest jobneed selected by plandatetime`() = runTest {
        // Insert 3 jobneeds for same job
        val job = createTestJob(id = 123)
        database.jobDao().insertOrUpdate(job)

        val jobneed1 = createTestJobneed(id = 1001, jobId = 123, plandatetime = oct1)
        val jobneed2 = createTestJobneed(id = 1002, jobId = 123, plandatetime = oct2)
        val jobneed3 = createTestJobneed(id = 1003, jobId = 123, plandatetime = oct3)

        database.jobneedDao().insertOrUpdateAll(listOf(jobneed1, jobneed2, jobneed3))

        // Get latest
        val latest = database.jobneedDao().getLatestForJob(123)

        // Should be jobneed3 (most recent plandatetime)
        assertEquals(1003, latest?.id)
    }

    @Test
    fun `test version conflict triggers conflict handler`() = runTest {
        val localJobneed = createTestJobneed(id = 1003, version = 5)

        // Mock server response with version conflict
        val mockResponse = mockUpdateJobneedError(
            code = "CONFLICT",
            expectedVersion = 5,
            actualVersion = 7
        )

        // Should trigger conflict dialog
        val handled = syncManager.handleVersionConflict(localJobneed, mockResponse)

        assertTrue(handled)
    }
}
```

### Integration Tests:

```kotlin
@Test
fun `test complete sync flow with real staging backend`() = runTest {
    // 1. Authenticate
    val authResult = apolloClient.mutate(AuthMutation(...)).execute()
    assertTrue(authResult.data?.auth?.success == true)

    // 2. Perform sync
    val syncResult = syncManager.performSync()

    // 3. Verify data synced
    val jobs = database.jobDao().getAllActive(clientId, buId).first()
    assertTrue(jobs.isNotEmpty())

    val jobneeds = database.jobneedDao().getAllActive().first()
    assertTrue(jobneeds.isNotEmpty())

    // 4. Verify latest jobneed logic
    val firstJob = jobs.first()
    val latestJobneed = database.jobneedDao().getLatestForJob(firstJob.id)
    assertNotNull(latestJobneed)

    // 5. Verify checklist details
    val details = database.jobneedDetailsDao().getForJobneed(latestJobneed.id)
    assertTrue(details.isNotEmpty())
    assertEquals(details, details.sortedBy { it.seqno })  // Verify ordering
}
```

---

## 📊 **Monitoring & Analytics**

### Sync Metrics to Track:

```kotlin
data class SyncMetrics(
    val startTime: Long,
    val endTime: Long,
    val durationMs: Long,

    // Counts
    val jobsDownloaded: Int,
    val jobneedsDownloaded: Int,
    val jobneedsUploaded: Int,

    // Errors
    val networkErrors: Int,
    val conflictErrors: Int,
    val validationErrors: Int,

    // Performance
    val avgQueryTimeMs: Long,
    val totalPayloadSizeKB: Int
)

class SyncMetricsCollector {
    fun recordSync(metrics: SyncMetrics) {
        // Log to analytics
        Analytics.track("sync_complete", mapOf(
            "duration_ms" to metrics.durationMs,
            "jobs_downloaded" to metrics.jobsDownloaded,
            "jobneeds_downloaded" to metrics.jobneedsDownloaded,
            "errors" to metrics.networkErrors + metrics.conflictErrors
        ))

        // Log to Crashlytics for debugging
        Crashlytics.log("Sync completed in ${metrics.durationMs}ms")

        // Alert if slow
        if (metrics.durationMs > 5000) {
            Log.w("Sync", "Slow sync detected: ${metrics.durationMs}ms")
        }
    }
}
```

---

## 🚨 **Error Scenarios & Handling**

### Error 1: Network Timeout During Sync

```kotlin
suspend fun syncWithRetry() {
    var attempt = 0
    val maxRetries = 3

    while (attempt < maxRetries) {
        try {
            val result = apolloClient.query(
                GetJobsWithLatestJobneedsQuery(...),
                timeout = 30.seconds
            ).execute()

            // Success
            return processSyncResult(result)

        } catch (e: ApolloNetworkException) {
            attempt++
            Log.w("Sync", "Network error (attempt $attempt/$maxRetries)", e)

            if (attempt >= maxRetries) {
                throw SyncException("Network error after $maxRetries attempts", e)
            }

            // Exponential backoff
            delay(1000L * attempt)
        }
    }
}
```

### Error 2: Constraint Violation (Duplicate Question)

```kotlin
suspend fun insertJobneedDetail(detail: JobneedDetails) {
    try {
        // Check for duplicate before inserting (prevent constraint error)
        val duplicateCount = database.jobneedDetailsDao().countDuplicates(
            jobneedId = detail.jobneedId,
            questionId = detail.questionId
        )

        if (duplicateCount > 0) {
            Log.w("Sync", "Question ${detail.questionId} already exists in jobneed ${detail.jobneedId}")

            // UPDATE instead of INSERT
            database.jobneedDetailsDao().updateAnswer(
                jobneedId = detail.jobneedId,
                questionId = detail.questionId,
                answer = detail.answer
            )
        } else {
            // Safe to insert
            database.jobneedDetailsDao().insertOrUpdate(detail)
        }

    } catch (e: SQLiteConstraintException) {
        Log.e("Sync", "Constraint violation inserting detail", e)

        if (e.message?.contains("jobneeddetails_jobneed_question_uk") == true) {
            // Duplicate question - update existing
            database.jobneedDetailsDao().updateExisting(detail)
        } else {
            throw e
        }
    }
}
```

### Error 3: Missing Job (Jobneed References Non-Existent Job)

```kotlin
suspend fun syncJobneedWithOrphanCheck() {
    result.data?.jobneeds?.forEach { jobneed ->
        // Check if parent Job exists
        val jobExists = jobneed.jobId?.let { jobId ->
            database.jobDao().getById(jobId) != null
        } ?: false

        if (!jobExists && jobneed.jobId != null) {
            Log.w("Sync", "Jobneed ${jobneed.id} references missing Job ${jobneed.jobId}")

            // Fetch missing Job from server
            val jobResult = apolloClient.query(
                GetJobQuery(jobId = jobneed.jobId)
            ).execute()

            jobResult.data?.job?.let { missingJob ->
                database.jobDao().insertOrUpdate(missingJob.toEntity())
                Log.i("Sync", "Fetched missing Job: ${missingJob.jobname}")
            }
        }

        // Now insert jobneed (FK constraint satisfied)
        database.jobneedDao().insertOrUpdate(jobneed.toEntity())
    }
}
```

---

## ✅ **Android Team Final Checklist**

Before going to production:

### Code Completion:
- [ ] Room database schema updated (Job entity added)
- [ ] Migration script implemented and tested
- [ ] DAO methods for Job implemented
- [ ] DAO methods for Jobneed updated (latest_for_job, history_for_job)
- [ ] GraphQL queries updated (Job.jobneed, Job.jobneeds)
- [ ] Kotlin data classes updated (relationships added)
- [ ] Sync logic implemented (upload + download)
- [ ] Conflict resolution implemented
- [ ] Error handling implemented (network, constraint, orphan)

### Testing:
- [ ] Unit tests pass (100%)
- [ ] Integration tests with staging pass
- [ ] Migration tested on 10+ test devices
- [ ] Offline sync tested (complete task offline → sync)
- [ ] Conflict resolution tested (two users, same task)
- [ ] Performance tested (sync < 5 seconds for 100 jobs)
- [ ] Constraint handling tested (duplicate prevention)

### UI/UX:
- [ ] Task list shows Job.jobname (not Jobneed.jobdesc)
- [ ] Checklist items ordered by seqno
- [ ] Execution history view implemented (optional)
- [ ] Conflict resolution dialog designed
- [ ] Migration progress dialog designed
- [ ] Error messages user-friendly

### Documentation:
- [ ] Code documented (KDoc for new methods)
- [ ] Migration script documented
- [ ] Sync flow documented in codebase
- [ ] Troubleshooting guide created

---

**Sync Flow Documentation Complete**: ✅
**Ready for Android Implementation**: ✅
**Contact for Questions**: backend-team@intelliwiz.com
