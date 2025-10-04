# Android Migration Visual Guide: OLD vs NEW

**Purpose**: Side-by-side comparison to show EXACTLY what changed
**For**: Android developers implementing the migration

---

## 📱 **Database Schema: OLD vs NEW**

### OLD Schema (Before Migration):

```
┌─────────────────────────┐
│      Jobneed (only)     │  ← Top-level entity
│─────────────────────────│
│ id                      │
│ uuid                    │
│ jobdesc                 │
│ jobstatus               │
│ plandatetime            │
│ starttime               │
│ endtime                 │
│ ... 40+ fields          │
└─────────────────────────┘
          │
          │ 1-to-many
          ↓
┌─────────────────────────┐
│   JobneedDetails        │  ← Checklist items
│─────────────────────────│
│ id                      │
│ jobneed_id (FK)         │
│ question_id             │
│ seqno                   │
│ answer                  │
└─────────────────────────┘
```

**Problem**: No Job template - can't distinguish recurring vs adhoc

---

### NEW Schema (After Migration):

```
┌─────────────────────────┐
│      Job (NEW!)         │  ← Template/Definition
│─────────────────────────│
│ id                      │
│ jobname                 │
│ cron                    │
│ frequency               │
│ fromdate                │
│ uptodate                │
│ ... scheduling fields   │
└─────────────────────────┘
          │
          │ 1-to-many (job_id FK)
          ↓
┌─────────────────────────┐
│      Jobneed            │  ← Execution Instance
│─────────────────────────│
│ id                      │
│ job_id (NEW FK!)        │  ⭐ Points to Job
│ uuid                    │
│ jobdesc                 │
│ plandatetime ← KEY      │  ⭐ Determines "latest"
│ jobstatus               │
│ starttime               │
│ endtime                 │
│ ... execution fields    │
└─────────────────────────┘
          │
          │ 1-to-many
          ↓
┌─────────────────────────┐
│   JobneedDetails        │  ← Checklist items (unchanged)
│─────────────────────────│
│ id                      │
│ jobneed_id (FK)         │
│ question_id             │
│ seqno                   │
│ answer                  │
│ + UNIQUE constraints    │  ⭐ NEW: Prevents duplicates
└─────────────────────────┘
```

**Benefit**: Clear template vs instance separation

---

## 🔌 **GraphQL Queries: OLD vs NEW**

### Query 1: Get Task Details

#### ❌ OLD (Will Break After Nov 21):

```graphql
# OLD query (flat Jobneed only)
query GetTasks($peopleid: Int!) {
  getJobneedmodifiedafter(
    mdtz: "2025-10-01 00:00:00",
    peopleid: $peopleid,
    siteid: 5,
    clientid: 1
  ) {
    nrows
    rc
    msg
    records  # JSON string of Jobneed array
  }
}
```

**Response**:
```json
{
  "getJobneedmodifiedafter": {
    "nrows": 50,
    "records": "[{\"id\": 1003, \"jobdesc\": \"Pump Check\", ...}]"
  }
}
```

**Android Code**:
```kotlin
// OLD: Parse Jobneed directly
val jobneeds = JSON.decodeFromString<List<Jobneed>>(response.records)
database.jobneedDao().insertOrUpdateAll(jobneeds)
```

---

#### ✅ NEW (Enhanced Schema):

```graphql
# NEW query (Job with nested Jobneed)
query GetJobsWithLatestJobneeds($peopleId: Int!, $buId: Int!, $clientId: Int!) {
  allJobs(people_Id: $peopleId, bu_Id: $buId, client_Id: $clientId) {
    edges {
      node {
        id
        jobname
        cron
        frequency

        # Latest jobneed (singular)
        jobneed {
          id
          uuid
          jobstatus
          plandatetime

          # Checklist (nested)
          details {
            seqno
            question { quesname }
            answer
          }
        }

        # History (optional)
        jobneeds(limit: 10) {
          id
          plandatetime
          jobstatus
        }
      }
    }
  }
}
```

**Response**:
```json
{
  "allJobs": {
    "edges": [
      {
        "node": {
          "id": 123,
          "jobname": "Daily Pump Check",
          "jobneed": {
            "id": 1003,
            "jobstatus": "ASSIGNED",
            "details": [
              {"seqno": 1, "answer": null},
              {"seqno": 2, "answer": null}
            ]
          }
        }
      }
    ]
  }
}
```

**Android Code**:
```kotlin
// NEW: Parse Job with nested Jobneed
response.allJobs.edges.forEach { edge ->
    val job = edge.node

    // Insert Job
    database.jobDao().insertOrUpdate(job.toEntity())

    // Insert latest Jobneed
    job.jobneed?.let { jobneed ->
        database.jobneedDao().insertOrUpdate(jobneed.toEntity())

        // Insert details
        jobneed.details?.forEach { detail ->
            database.jobneedDetailsDao().insertOrUpdate(detail.toEntity())
        }
    }
}
```

---

## 🎨 **UI Changes: OLD vs NEW**

### Task List Screen:

#### ❌ OLD UI (Jobneed-centric):

```
┌─────────────────────────────────────┐
│ Today's Tasks                       │
├─────────────────────────────────────┤
│ ✓ Fix AC Unit - Building A          │  ← Jobneed.jobdesc
│   10:00 AM - 11:30 AM                │
│   Status: ASSIGNED                   │
├─────────────────────────────────────┤
│ ✓ Pump Check - Area 5                │
│   11:00 AM - 12:00 PM                │
│   Status: COMPLETED                  │
└─────────────────────────────────────┘
```

**Data Source**: Query Jobneed WHERE plandatetime_date = today

**Problem**: No context - can't see if recurring or adhoc

---

#### ✅ NEW UI (Job-aware):

```
┌─────────────────────────────────────┐
│ Today's Tasks                       │
├─────────────────────────────────────┤
│ 🔄 Daily Pump Check                 │  ← Job.jobname (shows recurring)
│    └─ Area 5 - Oct 3                │  ← Jobneed.jobdesc (instance)
│    10:00 AM - 11:30 AM               │
│    Status: ASSIGNED                  │
│    📅 Scheduled: Daily at 10:00 AM   │  ← Job.frequency + Job.cron
├─────────────────────────────────────┤
│ ⚡ Emergency AC Repair               │  ← Job.jobname (adhoc)
│    └─ Building A - Urgent           │
│    11:00 AM - 12:00 PM               │
│    Status: COMPLETED ✓               │
│    📌 Adhoc Task                     │  ← Jobneed.jobtype = ADHOC
└─────────────────────────────────────┘
```

**Data Source**:
```kotlin
// Join Job and Jobneed
@Query("""
    SELECT j.*, jobneed.*
    FROM jobneed
    INNER JOIN job j ON jobneed.job_id = j.id
    WHERE DATE(jobneed.plandatetime/1000, 'unixepoch') = DATE(:today/1000, 'unixepoch')
      AND jobneed.jobstatus = 'ASSIGNED'
    ORDER BY jobneed.plandatetime ASC
""")
fun getTodaysTasksWithJob(today: Long): Flow<List<JobWithJobneed>>

data class JobWithJobneed(
    @Embedded val job: Job,
    @Embedded(prefix = "jobneed_") val jobneed: Jobneed
)
```

**Benefit**: User sees context (recurring vs adhoc)

---

### Task Detail Screen:

#### ❌ OLD:

```
┌─────────────────────────────────────┐
│ ← Pump Check - Area 5               │
├─────────────────────────────────────┤
│ Due: Oct 3, 10:00 AM                 │
│ Status: ASSIGNED                     │
│                                      │
│ Checklist:                           │
│ 1. Pump Pressure (PSI)?  [____]      │
│ 2. Visual Inspection OK? [ ]         │
│ 3. Leaks detected?       [ ]         │
│                                      │
│ [Start Task]                         │
└─────────────────────────────────────┘
```

**Problem**: No history, no schedule info

---

#### ✅ NEW:

```
┌─────────────────────────────────────┐
│ ← Daily Pump Check                  │  ← Job.jobname
├─────────────────────────────────────┤
│ 🔄 Recurring: Daily at 10:00 AM      │  ← Job.frequency + Job.cron
│ 📅 Schedule: Jan 1 - Dec 31, 2025    │  ← Job.fromdate - uptodate
│                                      │
│ Today's Execution:                   │  ← Latest Jobneed
│ Due: Oct 3, 10:00 AM                 │
│ Status: ASSIGNED                     │
│                                      │
│ Checklist:                           │
│ 1. Pump Pressure (PSI)?  [____]      │
│ 2. Visual Inspection OK? [ ]         │
│ 3. Leaks detected?       [ ]         │
│                                      │
│ [View History] [Start Task]          │  ← NEW: History button
└─────────────────────────────────────┘

Tap [View History]:
┌─────────────────────────────────────┐
│ Execution History                    │
├─────────────────────────────────────┤
│ Oct 3, 2025 - ASSIGNED (today)       │
│ Oct 2, 2025 - COMPLETED ✓            │
│ Oct 1, 2025 - COMPLETED ✓            │
│ Sep 30, 2025 - COMPLETED ✓           │
│ Sep 29, 2025 - AUTOCLOSED            │
│ [Load More...]                       │
└─────────────────────────────────────┘
```

**Data Source**:
```kotlin
// Get Job with latest + history
viewModelScope.launch {
    val job = database.jobDao().getById(jobId)
    val latestJobneed = database.jobneedDao().getLatestForJob(jobId)
    val history = database.jobneedDao().getHistoryForJob(jobId, limit = 30)

    _uiState.emit(
        TaskDetailState(
            job = job,
            currentExecution = latestJobneed,
            history = history
        )
    )
}
```

---

## 📊 **Data Flow: OLD vs NEW**

### OLD Flow (Jobneed-centric):

```
Backend Scheduler
      ↓
  Jobneed created
      ↓
  Sync API call
      ↓
Android receives Jobneed
      ↓
  Insert into jobneed table
      ↓
  UI shows in task list
```

**Code**:
```kotlin
// OLD: Single entity sync
val jobneeds = syncApi.getJobneedModifiedAfter(lastSync)
database.jobneedDao().insertAll(jobneeds)
```

---

### NEW Flow (Job + Jobneed hierarchy):

```
Backend Scheduler
      ↓
  Job template exists
      ↓
  Jobneed generated from Job
      ↓
  Sync API call
      ↓
Android receives Job + Jobneed
      ↓
  Insert into job table
      ↓
  Insert into jobneed table (with job_id FK)
      ↓
  UI shows Job with execution status
```

**Code**:
```kotlin
// NEW: Hierarchical sync
val jobs = syncApi.getJobsWithLatestJobneeds(userId, siteId)
jobs.forEach { job ->
    // 1. Insert Job template
    database.jobDao().insertOrUpdate(job)

    // 2. Insert latest Jobneed instance
    job.jobneed?.let { jobneed ->
        database.jobneedDao().insertOrUpdate(jobneed.copy(jobId = job.id))
    }
}
```

---

## 🔄 **Sync Logic: OLD vs NEW**

### Periodic Sync (Every 15 minutes):

#### ❌ OLD:

```kotlin
fun syncJobneeds() {
    val lastSync = prefs.getLong("last_sync", 0)
    val mdtzFormatted = formatForBackend(lastSync)

    // Single query - get modified jobneeds
    val result = apolloClient.query(
        GetJobneedModifiedAfterQuery(
            mdtz = mdtzFormatted,
            peopleid = userId,
            siteid = siteId,
            clientid = clientId
        )
    )

    // Parse and insert
    val jobneeds = parseJobneeds(result.data.records)
    database.jobneedDao().insertAll(jobneeds)

    // Update last sync
    prefs.edit { putLong("last_sync", now()) }
}
```

---

#### ✅ NEW:

```kotlin
suspend fun syncJobsAndJobneeds() {
    val lastSync = prefs.getLong("last_sync", 0)

    // 1. Query Jobs with latest Jobneeds
    val result = apolloClient.query(
        GetJobsWithLatestJobneedsQuery(
            peopleId = userId,
            buId = siteId,
            clientId = clientId,
            modifiedAfter = lastSync  // Optional: Only get changes
        )
    ).execute()

    // 2. Process hierarchically
    result.data?.allJobs?.edges?.forEach { edge ->
        val job = edge.node

        // Insert Job
        database.jobDao().insertOrUpdate(job.toEntity())

        // Insert latest Jobneed (if exists)
        job.jobneed?.let { latestJobneed ->
            database.jobneedDao().insertOrUpdate(
                latestJobneed.toEntity().copy(
                    jobId = job.id  // Ensure FK is set
                )
            )

            // Insert checklist details
            latestJobneed.details?.forEach { detail ->
                // Check for duplicates before inserting (constraint prevention)
                val exists = database.jobneedDetailsDao().countDuplicates(
                    jobneedId = latestJobneed.id,
                    questionId = detail.questionId
                ) > 0

                if (!exists) {
                    database.jobneedDetailsDao().insertOrUpdate(detail.toEntity())
                }
            }
        }
    }

    // 3. Update last sync
    prefs.edit { putLong("last_sync", System.currentTimeMillis()) }
}
```

---

## 🎯 **"Latest" Logic: OLD vs NEW**

### Get Today's Active Task:

#### ❌ OLD:

```kotlin
// Query jobneed directly
@Query("""
    SELECT * FROM jobneed
    WHERE people_id = :userId
      AND jobstatus = 'ASSIGNED'
      AND DATE(plandatetime/1000, 'unixepoch') = DATE(:today/1000, 'unixepoch')
    ORDER BY plandatetime ASC
""")
fun getTodaysTasks(userId: Long, today: Long): Flow<List<Jobneed>>
```

**Usage**:
```kotlin
val tasks = database.jobneedDao().getTodaysTasks(userId, today).collect()
// Returns: List of Jobneeds
```

---

#### ✅ NEW:

```kotlin
// Query with Job context
@Query("""
    SELECT jobneed.*, job.jobname, job.frequency, job.cron
    FROM jobneed
    INNER JOIN job ON jobneed.job_id = job.id
    WHERE jobneed.people_id = :userId
      AND jobneed.jobstatus = 'ASSIGNED'
      AND DATE(jobneed.plandatetime/1000, 'unixepoch') = DATE(:today/1000, 'unixepoch')
    ORDER BY jobneed.plandatetime ASC
""")
fun getTodaysTasksWithJob(userId: Long, today: Long): Flow<List<JobneedWithJob>>

data class JobneedWithJob(
    @Embedded val jobneed: Jobneed,
    @Embedded(prefix = "job_") val job: Job
)
```

**Usage**:
```kotlin
val tasks = database.jobneedDao().getTodaysTasksWithJob(userId, today).collect()
// Returns: List of (Jobneed + Job) pairs

tasks.forEach { task ->
    println("Template: ${task.job.jobname}")  // ✅ NEW: Show job name
    println("Instance: ${task.jobneed.jobdesc}")
    println("Recurring: ${task.job.frequency}")  // ✅ NEW: Show if recurring
}
```

---

## 💾 **Data Insertion: OLD vs NEW**

### Insert New Jobneed:

#### ❌ OLD:

```kotlin
// Receive from server
val jobneed = Jobneed(
    id = 1003,
    uuid = "abc-123",
    jobdesc = "Pump Check - Oct 3",
    jobstatus = "ASSIGNED",
    plandatetime = oct3_10am,
    // ... all fields
)

// Insert directly
database.jobneedDao().insertOrUpdate(jobneed)
```

**Problem**: No job_id - can't determine if recurring

---

#### ✅ NEW:

```kotlin
// Receive from server (with Job context)
val job = Job(
    id = 123,
    jobname = "Daily Pump Check",
    cron = "0 10 * * *",
    frequency = "DAILY"
    // ... all fields
)

val jobneed = Jobneed(
    id = 1003,
    jobId = 123,  // ⭐ NEW: FK to Job
    uuid = "abc-123",
    jobdesc = "Pump Check - Oct 3",
    jobstatus = "ASSIGNED",
    plandatetime = oct3_10am,
    // ... all fields
)

// Insert hierarchically
database.withTransaction {
    // 1. Insert Job first (FK constraint)
    database.jobDao().insertOrUpdate(job)

    // 2. Then insert Jobneed
    database.jobneedDao().insertOrUpdate(jobneed)
}
```

**Benefit**: FK relationship enforced, referential integrity maintained

---

## 🧩 **Extension Functions for Easy Migration**

### GraphQL Response Converters:

```kotlin
// Convert GraphQL Job to Room entity
fun com.example.GetJobQuery.Job.toEntity(): Job {
    return Job(
        id = this.id.toLong(),
        jobname = this.jobname,
        jobdesc = this.jobdesc,
        fromdate = parseDateTime(this.fromdate),
        uptodate = parseDateTime(this.uptodate),
        cron = this.cron,
        identifier = this.identifier,
        planduration = this.planduration,
        gracetime = this.gracetime,
        expirytime = this.expirytime,
        priority = this.priority,
        scantype = this.scantype,
        frequency = this.frequency ?: "NONE",
        enable = this.enable,
        assetId = this.asset?.id?.toLong(),
        qsetId = this.qset?.id?.toLong(),
        peopleId = this.people?.id?.toLong(),
        clientId = this.client?.id?.toLong(),
        buId = this.bu?.id?.toLong(),
        // ... map all fields
        otherInfo = this.other_info?.toString() ?: "{}",
        version = this.version,
        cdtz = parseDateTime(this.cdtz),
        mdtz = parseDateTime(this.mdtz),
        cuserId = this.cuser?.id?.toLong() ?: 0,
        muserId = this.muser?.id?.toLong() ?: 0,
        ctzoffset = this.ctzoffset ?: 0
    )
}

// Convert GraphQL Jobneed to Room entity
fun com.example.GetJobQuery.Jobneed.toEntity(): Jobneed {
    return Jobneed(
        id = this.id.toLong(),
        jobId = this.jobId?.toLong(),  // ⭐ NEW field
        uuid = this.uuid,
        jobdesc = this.jobdesc,
        plandatetime = parseDateTime(this.plandatetime),
        expirydatetime = parseDateTime(this.expirydatetime),
        jobstatus = this.jobstatus,
        jobtype = this.jobtype,
        starttime = this.starttime?.let { parseDateTime(it) },
        endtime = this.endtime?.let { parseDateTime(it) },
        gpslocation = this.gpslocation?.toString(),
        // ... map all fields
        version = this.version,
        cdtz = parseDateTime(this.cdtz),
        mdtz = parseDateTime(this.mdtz),
        ctzoffset = this.ctzoffset ?: 0
    )
}

// Helper: Parse Django datetime to epoch millis
fun parseDateTime(isoString: String?): Long {
    if (isoString == null) return 0

    // Django returns: "2025-10-03T10:00:00+00:00"
    return try {
        Instant.parse(isoString).toEpochMilli()
    } catch (e: Exception) {
        Log.e("Parser", "Failed to parse datetime: $isoString", e)
        0
    }
}
```

---

## 📈 **Performance Comparison**

### Sync 100 Jobs with Jobneeds:

| Metric | OLD (Jobneed-only) | NEW (Job + Jobneed) | Change |
|--------|-------------------|---------------------|---------|
| **API Calls** | 1 (getJobneedmodifiedafter) | 1 (GetJobsWithLatestJobneeds) | ✅ Same |
| **Payload Size** | ~300KB (100 jobneeds) | ~500KB (100 jobs + 100 jobneeds) | +67% (acceptable) |
| **Parse Time** | ~50ms | ~80ms | +30ms (acceptable) |
| **Database Inserts** | 100 (jobneeds) | 200 (100 jobs + 100 jobneeds) | 2x (but batched) |
| **Total Sync Time** | ~500ms | ~700ms | +200ms (acceptable) |
| **UI Value** | Low (no context) | High (full context) | ✅ **Much better UX** |

**Verdict**: Slightly slower, but **much better user experience**

---

## 🎓 **Training Examples for Android Team**

### Example 1: Display Job with Latest Execution

```kotlin
@Composable
fun TaskCard(jobWithJobneed: JobWithJobneed) {
    Card {
        Column {
            // Job template info
            Text(
                text = jobWithJobneed.job.jobname,
                style = MaterialTheme.typography.h6
            )

            Row {
                Icon(Icons.Recurring)
                Text("${jobWithJobneed.job.frequency} at ${formatTime(jobWithJobneed.job.starttime)}")
            }

            Divider()

            // Latest execution info
            Text(
                text = jobWithJobneed.jobneed.jobdesc,
                style = MaterialTheme.typography.body1
            )

            Row {
                StatusChip(status = jobWithJobneed.jobneed.jobstatus)
                Text("Due: ${formatDateTime(jobWithJobneed.jobneed.plandatetime)}")
            }

            // Action button
            Button(onClick = { openTask(jobWithJobneed.jobneed.id) }) {
                Text("Start Task")
            }
        }
    }
}
```

### Example 2: Handle Adhoc vs Scheduled Tasks

```kotlin
fun displayTaskType(job: Job, jobneed: Jobneed): String {
    return when (jobneed.jobtype) {
        "SCHEDULE" -> {
            // Scheduled from Job template
            "📅 ${job.frequency} - ${job.jobname}"
        }
        "ADHOC" -> {
            // Created manually (job_id may be null)
            "⚡ Adhoc Task"
        }
        else -> "Unknown"
    }
}
```

### Example 3: Prevent Duplicate Questions (Constraint Handling)

```kotlin
suspend fun addAnswerToChecklist(
    jobneedId: Long,
    questionId: Long,
    answer: String
) {
    // Check for existing answer (prevent constraint violation)
    val existing = database.jobneedDetailsDao().getByJobneedAndQuestion(
        jobneedId = jobneedId,
        questionId = questionId
    )

    if (existing != null) {
        // UPDATE existing answer
        database.jobneedDetailsDao().updateAnswer(
            id = existing.id,
            answer = answer,
            mdtz = System.currentTimeMillis()
        )
        Log.i("Checklist", "Updated answer for question $questionId")
    } else {
        // INSERT new answer
        val detail = JobneedDetails(
            id = generateTempId(),  // Will be replaced by server ID on sync
            jobneedId = jobneedId,
            questionId = questionId,
            seqno = getNextSeqno(jobneedId),  // Calculate next sequence
            answer = answer,
            // ... other fields
        )
        database.jobneedDetailsDao().insertOrUpdate(detail)
        Log.i("Checklist", "Added new answer for question $questionId")
    }
}

suspend fun getNextSeqno(jobneedId: Long): Int {
    // Get max seqno for this jobneed
    val maxSeqno = database.jobneedDetailsDao().getMaxSeqno(jobneedId) ?: 0
    return maxSeqno + 1
}
```

---

## ✅ **Migration Verification Checklist**

After implementing migration, verify:

### Database Verification:

```kotlin
suspend fun verifyMigration(): MigrationVerificationResult {
    val issues = mutableListOf<String>()

    // 1. Check Job table exists
    val jobTableExists = database.query(
        SimpleSQLiteQuery("SELECT name FROM sqlite_master WHERE type='table' AND name='job'")
    ).use { it.count > 0 }

    if (!jobTableExists) {
        issues.add("Job table not created")
    }

    // 2. Check all Jobneeds have job_id
    val orphanJobneeds = database.query(
        SimpleSQLiteQuery("SELECT COUNT(*) FROM jobneed WHERE job_id IS NULL AND jobtype = 'SCHEDULE'")
    ).use { cursor ->
        cursor.moveToFirst()
        cursor.getInt(0)
    }

    if (orphanJobneeds > 0) {
        issues.add("Found $orphanJobneeds scheduled jobneeds without job_id")
    }

    // 3. Check foreign key integrity
    val invalidFKs = database.query(
        SimpleSQLiteQuery("""
            SELECT COUNT(*) FROM jobneed j
            LEFT JOIN job ON j.job_id = job.id
            WHERE j.job_id IS NOT NULL AND job.id IS NULL
        """)
    ).use { cursor ->
        cursor.moveToFirst()
        cursor.getInt(0)
    }

    if (invalidFKs > 0) {
        issues.add("Found $invalidFKs jobneeds with invalid job_id FK")
    }

    // 4. Check constraints exist
    val constraintCheck = database.query(
        SimpleSQLiteQuery("SELECT sql FROM sqlite_master WHERE type='index' AND name LIKE '%jobneeddetails%'")
    ).use { it.count >= 2 }  // Should have 2 unique indexes

    if (!constraintCheck) {
        issues.add("JobneedDetails unique constraints not created")
    }

    return when {
        issues.isEmpty() -> MigrationVerificationResult.Success
        else -> MigrationVerificationResult.Failure(issues)
    }
}

sealed class MigrationVerificationResult {
    object Success : MigrationVerificationResult()
    data class Failure(val issues: List<String>) : MigrationVerificationResult()
}
```

---

## 🔔 **User Communication**

### In-App Messages:

#### Before Migration:

```
┌─────────────────────────────────────┐
│  App Update Available               │
├─────────────────────────────────────┤
│  We're improving task management!   │
│                                     │
│  What's new:                        │
│  • Better task organization         │
│  • See recurring vs one-time tasks  │
│  • View execution history           │
│                                     │
│  This update includes database      │
│  changes (takes ~30 seconds).       │
│                                     │
│  [Update Now] [Later]               │
└─────────────────────────────────────┘
```

#### During Migration:

```
┌─────────────────────────────────────┐
│  Upgrading Database...              │
├─────────────────────────────────────┤
│  ⏳ Please wait...                   │
│                                     │
│  [████████░░] 80%                   │
│                                     │
│  Creating task templates...         │
│                                     │
│  Do not close the app.              │
└─────────────────────────────────────┘
```

#### After Migration:

```
┌─────────────────────────────────────┐
│  ✅ Update Complete!                 │
├─────────────────────────────────────┤
│  Your tasks now have:               │
│  • Full schedule information        │
│  • Recurring task tracking          │
│  • Execution history                │
│                                     │
│  [Explore New Features]             │
└─────────────────────────────────────┘
```

---

## 📝 **Code Review Checklist for Android PR**

Before merging Android migration PR:

- [ ] **Database Schema**
  - [ ] Job entity created with all fields
  - [ ] Jobneed entity updated (job_id FK added)
  - [ ] Migration script creates Job table
  - [ ] Migration script populates Job from Jobneed
  - [ ] Foreign key constraints created
  - [ ] Unique constraints for JobneedDetails created
  - [ ] All indexes created

- [ ] **DAO Methods**
  - [ ] JobDao implements all CRUD operations
  - [ ] JobneedDao.getLatestForJob() implemented
  - [ ] JobneedDao.getHistoryForJob() implemented
  - [ ] JobneedDetailsDao handles duplicates gracefully

- [ ] **GraphQL Integration**
  - [ ] Schema detection logic implemented
  - [ ] Legacy schema support maintained (grace period)
  - [ ] Enhanced schema queries implemented
  - [ ] Query response converters (toEntity()) implemented
  - [ ] Error handling for both schemas

- [ ] **Sync Logic**
  - [ ] Hierarchical sync (Job → Jobneed) implemented
  - [ ] Conflict resolution implemented
  - [ ] Optimistic locking handled
  - [ ] Orphan jobneed handling
  - [ ] Constraint violation prevention

- [ ] **UI Updates**
  - [ ] Task list shows Job context
  - [ ] Detail screen shows schedule info
  - [ ] History view implemented (optional)
  - [ ] Recurring vs adhoc indicators
  - [ ] Migration progress dialog

- [ ] **Testing**
  - [ ] Unit tests pass (100%)
  - [ ] Integration tests with staging pass
  - [ ] Migration tested on 10+ devices
  - [ ] Offline sync tested
  - [ ] Conflict resolution tested
  - [ ] Performance tested (< 5s sync)

- [ ] **Documentation**
  - [ ] Code comments added (KDoc)
  - [ ] Migration guide in README
  - [ ] Troubleshooting section added

---

**Visual Guide Complete**: ✅
**Ready for Android Implementation**: ✅

**See Also**:
- `ANDROID_REQUIREMENTS_FILLED.md` - Complete requirements (5 items)
- `ANDROID_COMPLETE_MODEL_REFERENCE.md` - All 3 model definitions
- `ANDROID_SYNC_FLOW_COMPLETE.md` - Sync implementation guide
- `docs/mobile-api/JOB_JOBNEED_API_CONTRACT.md` - API contract
