# Job → Jobneed → JobneedDetails API Contract

**Version**: 2.0 (October 2025)
**Target**: Android-Kotlin Frontend
**Status**: ⚠️ **BREAKING CHANGES** in GraphQL Schema

---

## 🚨 **BREAKING CHANGES SUMMARY**

### **GraphQL Schema Changes (Enhanced Schema Only)**

| Change | Old Behavior | New Behavior | Impact |
|--------|-------------|--------------|---------|
| `Job.jobneed_details` | ❌ Wrong: Assumed 1-1 relationship | ✅ **REMOVED** | 🔴 **BREAKING** |
| `Job.jobneed` | ❌ Did not exist | ✅ **NEW**: Returns latest jobneed | 🟢 **NEW FIELD** |
| `Job.jobneeds` | ❌ Did not exist | ✅ **NEW**: Returns execution history | 🟢 **NEW FIELD** |
| `Jobneed.job` | ❌ Not exposed | ✅ **NEW**: Returns parent Job | 🟢 **NEW FIELD** |
| `Jobneed.details` | ❌ Not exposed | ✅ **NEW**: Returns JobneedDetails list | 🟢 **NEW FIELD** |

### **Migration Timeline**

- **Week 1 (Oct 3-10)**: Backend deployed with new schema
- **Week 2 (Oct 10-17)**: Android app updated and tested
- **Week 3 (Oct 17-24)**: Rollout to production
- **Backward Compatibility**: Old queries will fail after Oct 10

---

## 📋 **Domain Model Explanation**

### **The Three Models**

```kotlin
// Kotlin representation of domain model

/**
 * Job: Template/Definition (WHAT work to do, WHEN to schedule it)
 * - Recurring work definition (tasks, tours, PPM)
 * - Scheduling config (cron, frequency, dates)
 * - Generates multiple Jobneed instances over time
 */
data class Job(
    val id: Long,
    val jobname: String,
    val jobdesc: String,
    val identifier: JobIdentifier,  // TASK, INTERNALTOUR, EXTERNALTOUR, PPM
    val cron: String,
    val frequency: JobFrequency,
    val fromdate: Instant,
    val uptodate: Instant,
    // ... other fields
)

/**
 * Jobneed: Concrete Instance (ONE specific execution)
 * - Generated from Job OR created adhoc
 * - Tracks execution: assigned, in-progress, completed
 * - Has actual start/end times
 * - 1-to-many relationship with Job (via job_id foreign key)
 */
data class Jobneed(
    val id: Long,
    val jobId: Long,           // FK to Job (which template generated this)
    val jobdesc: String,
    val plandatetime: Instant,  // When to execute
    val expirydatetime: Instant,
    val jobstatus: JobStatus,   // ASSIGNED, COMPLETED, AUTOCLOSED
    val jobtype: JobType,       // SCHEDULE or ADHOC
    val starttime: Instant?,    // Actual start (user action)
    val endtime: Instant?,      // Actual end (user action)
    // ... other fields
)

/**
 * JobneedDetails: Checklist Item (ONE question in ONE execution)
 * - Tied to specific Jobneed
 * - Stores question answer, validation, alerts
 * - seqno: Display order in checklist
 */
data class JobneedDetails(
    val id: Long,
    val jobneedId: Long,        // FK to Jobneed
    val questionId: Long?,      // FK to Question
    val seqno: Int,             // Display order
    val answertype: AnswerType,
    val answer: String?,
    val ismandatory: Boolean,
    val alerts: Boolean,
    // ... other fields
)
```

### **Relationship Examples**

#### **Example 1: Daily Task Schedule**

```
Job #123: "Daily Pump Check" (fromdate=2025-01-01, uptodate=2025-12-31, cron="0 10 * * *")
  ├─ Jobneed #1001: 2025-10-01 10:00 (COMPLETED)
  │   ├─ JobneedDetails: Q1 (answer="Normal")
  │   ├─ JobneedDetails: Q2 (answer="45.5")
  │   └─ JobneedDetails: Q3 (answer="OK")
  ├─ Jobneed #1002: 2025-10-02 10:00 (COMPLETED)
  │   ├─ JobneedDetails: Q1 (answer="Normal")
  │   ├─ JobneedDetails: Q2 (answer="46.2")
  │   └─ JobneedDetails: Q3 (answer="OK")
  └─ Jobneed #1003: 2025-10-03 10:00 (ASSIGNED) ← LATEST
      ├─ JobneedDetails: Q1 (answer=null)
      ├─ JobneedDetails: Q2 (answer=null)
      └─ JobneedDetails: Q3 (answer=null)
```

**Key Insight**: Job #123 generates a NEW Jobneed every day at 10:00 AM.

---

## 🔄 **Migration Guide for Android Team**

### **Step 1: Update GraphQL Queries**

#### **Before (Old Schema - Will Break):**

```graphql
query GetJobDetails($jobId: Int!) {
  job(id: $jobId) {
    id
    jobname
    jobneed_details {  # ❌ REMOVED - This field no longer exists
      id
      jobstatus
      plandatetime
    }
  }
}
```

**Result**: `Field 'jobneed_details' doesn't exist on type 'JobType'`

#### **After (New Schema - Correct):**

```graphql
query GetJobDetails($jobId: Int!) {
  job(id: $jobId) {
    id
    jobname

    # Get LATEST jobneed (most recent execution)
    jobneed {
      id
      jobstatus
      plandatetime
      expirydatetime
      starttime
      endtime
    }

    # Get FULL HISTORY (last 10 executions)
    jobneeds(limit: 10) {
      id
      jobstatus
      plandatetime
      starttime
      endtime
    }
  }
}
```

### **Step 2: Update Kotlin Data Models**

#### **Add Relationship Fields:**

```kotlin
// OLD: Job model without jobneed relationship
data class Job(
    val id: Long,
    val jobname: String,
    // ...
)

// NEW: Job model with jobneed relationships
data class Job(
    val id: Long,
    val jobname: String,
    // ... existing fields

    // NEW: Latest jobneed execution
    val jobneed: Jobneed?,

    // NEW: Execution history
    val jobneeds: List<Jobneed>? = null
)

// Jobneed model with new fields
data class Jobneed(
    val id: Long,
    val jobId: Long,
    // ... existing fields

    // NEW: Parent Job template
    val job: Job?,

    // NEW: Checklist details
    val details: List<JobneedDetails>? = null
)
```

### **Step 3: Update API Calls**

#### **Use Case: Show Current Task Status**

```kotlin
// Query for job with latest execution
val query = """
  query GetCurrentTask(${'$'}jobId: Int!) {
    job(id: ${'$'}jobId) {
      id
      jobname
      jobneed {
        id
        jobstatus
        plandatetime
        details {
          id
          seqno
          question { quesname }
          answer
          ismandatory
        }
      }
    }
  }
"""

// Execute query
val result = apolloClient.query(GetCurrentTaskQuery(jobId = 123))

// Access data
val job = result.data?.job
val latestJobneed = job?.jobneed
val checklistItems = latestJobneed?.details

// Display in UI
checklistItems?.sortedBy { it.seqno }?.forEach { detail ->
    displayChecklistItem(detail)
}
```

#### **Use Case: Show Execution History**

```kotlin
// Query for job with execution history
val query = """
  query GetJobHistory(${'$'}jobId: Int!) {
    job(id: ${'$'}jobId) {
      jobname
      jobneeds(limit: 30) {
        id
        plandatetime
        jobstatus
        starttime
        endtime
      }
    }
  }
"""

// Execute query
val result = apolloClient.query(GetJobHistoryQuery(jobId = 123))

// Display in RecyclerView
val history = result.data?.job?.jobneeds ?: emptyList()
historyAdapter.submitList(history)
```

---

## 🔌 **REST API (No Breaking Changes)**

### **Endpoints (Unchanged)**

```
GET  /api/v1/jobs/{id}/                    # Get job details
GET  /api/v1/jobs/{id}/jobneeds/           # Get jobneeds for job (NEW)
GET  /api/v1/jobneeds/{id}/                # Get jobneed details
GET  /api/v1/jobneeds/{id}/details/        # Get checklist items
POST /api/v1/jobneeds/                     # Create adhoc jobneed
PUT  /api/v1/jobneeds/{id}/                # Update jobneed
```

### **Response Schema**

#### **GET /api/v1/jobs/{id}/ (Enhanced)**

```json
{
  "id": 123,
  "jobname": "Daily Pump Check",
  "jobdesc": "Check pump status",
  "identifier": "TASK",
  "cron": "0 10 * * *",
  "fromdate": "2025-01-01T00:00:00Z",
  "uptodate": "2025-12-31T23:59:59Z",

  // NEW: Latest jobneed (most recent execution)
  "jobneed": {
    "id": 1003,
    "jobstatus": "ASSIGNED",
    "plandatetime": "2025-10-03T10:00:00Z",
    "expirydatetime": "2025-10-03T11:30:00Z"
  },

  // NEW: Recent execution history
  "jobneeds": [
    {
      "id": 1003,
      "plandatetime": "2025-10-03T10:00:00Z",
      "jobstatus": "ASSIGNED"
    },
    {
      "id": 1002,
      "plandatetime": "2025-10-02T10:00:00Z",
      "jobstatus": "COMPLETED"
    }
  ]
}
```

#### **GET /api/v1/jobneeds/{id}/details/ (Unchanged)**

```json
[
  {
    "id": 5001,
    "jobneed": 1003,
    "question": 789,
    "seqno": 1,
    "quesname": "Pump Pressure (PSI)?",
    "answertype": "NUMERIC",
    "answer": "45.5",
    "min": 40.0,
    "max": 50.0,
    "ismandatory": true,
    "alerts": false
  },
  {
    "id": 5002,
    "jobneed": 1003,
    "question": 790,
    "seqno": 2,
    "quesname": "Visual Inspection OK?",
    "answertype": "CHECKBOX",
    "answer": "true",
    "ismandatory": true,
    "alerts": false
  }
]
```

---

## 📱 **Android Implementation Checklist**

### **Week 1: Update GraphQL Queries**

- [ ] Update all `Job.jobneed_details` references to `Job.jobneed`
- [ ] Add `Job.jobneeds` queries for history views
- [ ] Update `Jobneed` queries to include `details` field
- [ ] Test all GraphQL queries in GraphiQL/Playground

### **Week 2: Update Kotlin Models**

- [ ] Add `jobneed: Jobneed?` field to `Job` data class
- [ ] Add `jobneeds: List<Jobneed>?` field to `Job` data class
- [ ] Add `job: Job?` field to `Jobneed` data class
- [ ] Add `details: List<JobneedDetails>?` field to `Jobneed` data class
- [ ] Update Apollo codegen configuration
- [ ] Regenerate GraphQL client code

### **Week 3: Update UI Components**

- [ ] Update task list views to use `job.jobneed`
- [ ] Update tour detail views to show `jobneed.details`
- [ ] Add execution history views using `job.jobneeds`
- [ ] Test offline sync with new schema
- [ ] Update unit tests for new model structure

### **Week 4: Integration Testing**

- [ ] Test with staging backend (new schema)
- [ ] Verify checklist rendering
- [ ] Verify history views
- [ ] Performance testing (ensure < 500ms load)
- [ ] Rollout to beta testers

---

## 🔍 **Key Differences: OLD vs NEW**

### **Concept 1: Job → Jobneed is 1-to-Many**

**OLD Assumption** (Incorrect):
```
Job #123 ──one-to-one──> Jobneed #1003
```

**NEW Reality** (Correct):
```
Job #123 ──one-to-many──> Jobneed #1001 (Oct 1)
                       └──> Jobneed #1002 (Oct 2)
                       └──> Jobneed #1003 (Oct 3) ← LATEST
```

### **Concept 2: "Latest" vs "History"**

**When to use `job.jobneed` (singular)**:
- Showing current task status
- Displaying "Today's Tasks"
- Quick status checks
- Dashboard cards

**When to use `job.jobneeds` (plural)**:
- Execution history views
- Performance analytics
- Audit trails
- "Past Executions" screen

---

## 📊 **Common Query Patterns**

### **Pattern 1: Get Today's Tasks**

```graphql
query GetTodaysTasks($userId: Int!, $date: Date!) {
  jobs(people_id: $userId, plandatetime_date: $date) {
    id
    jobname
    identifier

    # Get latest jobneed for today
    jobneed {
      id
      jobstatus
      plandatetime
      expirydatetime

      # Get checklist
      details {
        id
        seqno
        question { quesname }
        answertype
        answer
        ismandatory
      }
    }
  }
}
```

**Kotlin Usage**:
```kotlin
val tasks = result.data?.jobs
tasks?.forEach { job ->
    val latestJobneed = job.jobneed
    val checklist = latestJobneed?.details?.sortedBy { it.seqno }

    // Display in UI
    TaskCard(
        jobName = job.jobname,
        status = latestJobneed?.jobstatus,
        checklistItems = checklist
    )
}
```

### **Pattern 2: Get Execution History**

```graphql
query GetTaskHistory($jobId: Int!) {
  job(id: $jobId) {
    id
    jobname

    # Get last 30 executions
    jobneeds(limit: 30) {
      id
      plandatetime
      jobstatus
      starttime
      endtime
      performedby { peoplename }
    }
  }
}
```

**Kotlin Usage**:
```kotlin
val history = result.data?.job?.jobneeds ?: emptyList()

// Display in RecyclerView
historyAdapter.submitList(
    history.map { jobneed ->
        HistoryItem(
            date = jobneed.plandatetime,
            status = jobneed.jobstatus,
            performer = jobneed.performedby?.peoplename,
            duration = calculateDuration(jobneed.starttime, jobneed.endtime)
        )
    }
)
```

### **Pattern 3: Get Job with Checklist**

```graphql
query GetJobChecklist($jobneedId: Int!) {
  jobneed(id: $jobneedId) {
    id
    jobdesc
    plandatetime
    jobstatus

    # Get parent job template
    job {
      jobname
      identifier
      qset { qsetname }
    }

    # Get checklist details
    details {
      id
      seqno
      question {
        id
        quesname
        qset { qsetname }
      }
      answertype
      answer
      min
      max
      options
      ismandatory
      alerts
    }
  }
}
```

**Kotlin Usage**:
```kotlin
val jobneed = result.data?.jobneed
val checklistItems = jobneed?.details?.sortedBy { it.seqno }

ChecklistScreen(
    jobName = jobneed?.job?.jobname,
    checklistName = jobneed?.job?.qset?.qsetname,
    items = checklistItems?.map { detail ->
        ChecklistItem(
            seqno = detail.seqno,
            question = detail.question?.quesname,
            answerType = detail.answertype,
            currentAnswer = detail.answer,
            validation = Validation(
                min = detail.min,
                max = detail.max,
                options = detail.options
            ),
            isMandatory = detail.ismandatory
        )
    }
)
```

---

## 🔒 **Data Integrity Improvements**

### **NEW Database Constraints (October 2025)**

Android app benefits from these backend improvements:

1. **Unique (jobneed, question)** ✅
   - Prevents duplicate questions in checklist
   - Android won't receive malformed data

2. **Unique (jobneed, seqno)** ✅
   - Ensures proper checklist ordering
   - Android can reliably sort by seqno

**Impact**: More reliable data, fewer edge cases to handle

---

## 📡 **Offline Sync Considerations**

### **Conflict Resolution**

#### **Scenario: User completes task offline, backend generates new jobneed**

**Problem**:
```
Device (Offline):
  Jobneed #1003 (Oct 3) → status=COMPLETED, answers filled

Backend (Meanwhile):
  Generated Jobneed #1004 (Oct 4) → status=ASSIGNED

Device Syncs:
  Sends: UPDATE Jobneed #1003
  Receives: NEW Jobneed #1004
```

**Resolution Strategy**:
```kotlin
// 1. Sync completed jobneed
syncService.updateJobneed(localJobneed)  // Success

// 2. Fetch latest from server
val latestJobneed = fetchLatestJobneed(jobId)

// 3. Merge into local DB
if (latestJobneed.id != localJobneed.id) {
    // New jobneed generated - update local state
    db.jobneedDao().insert(latestJobneed)
    notifyUser("New task scheduled for ${latestJobneed.plandatetime}")
}
```

### **Sync Algorithm Update**

```kotlin
fun syncJobneeds(jobs: List<Job>) {
    jobs.forEach { job ->
        // OLD: Assumed 1-1 relationship
        // val jobneed = job.jobneed_details  // ❌ WRONG

        // NEW: Handle 1-to-many correctly
        val latestJobneed = job.jobneed  // ✅ Most recent

        when {
            latestJobneed == null -> {
                // No executions yet - nothing to sync
            }
            latestJobneed.jobstatus == "ASSIGNED" -> {
                // Pending execution - show to user
                addToTaskList(latestJobneed)
            }
            latestJobneed.jobstatus == "COMPLETED" -> {
                // Already completed - check history
                val history = job.jobneeds ?: emptyList()
                updateHistoryView(history)
            }
        }
    }
}
```

---

## 🧪 **Testing Checklist**

### **Unit Tests**

```kotlin
@Test
fun `test Job model has jobneed relationship`() {
    val job = Job(id = 123, jobname = "Test")
    assertNotNull(job.jobneed)  // Should have latest field
    assertNotNull(job.jobneeds)  // Should have history field
}

@Test
fun `test Jobneed model has details relationship`() {
    val jobneed = Jobneed(id = 1003, jobId = 123)
    assertNotNull(jobneed.details)  // Should have checklist
    assertNotNull(jobneed.job)       // Should have parent Job
}
```

### **Integration Tests**

```kotlin
@Test
fun `test GraphQL query returns latest jobneed`() = runBlocking {
    val query = GetJobDetailsQuery(jobId = 123)
    val result = apolloClient.query(query).execute()

    assertFalse(result.hasErrors())
    assertNotNull(result.data?.job?.jobneed)

    val latest = result.data?.job?.jobneed
    assertEquals("ASSIGNED", latest?.jobstatus)
}

@Test
fun `test GraphQL query returns jobneed history`() = runBlocking {
    val query = GetJobHistoryQuery(jobId = 123)
    val result = apolloClient.query(query).execute()

    val history = result.data?.job?.jobneeds ?: emptyList()
    assertTrue(history.size <= 10)  // Respects limit
    assertTrue(history.isSortedByDescending { it.plandatetime })
}
```

---

## 🎯 **Performance Guidelines**

### **Query Optimization**

```graphql
# ❌ BAD: Over-fetching (requesting all fields)
query GetTasks {
  jobs {
    id
    jobname
    jobneed {
      id
      jobstatus
      plandatetime
      expirydatetime
      gracetime
      receivedonserver
      starttime
      endtime
      gpslocation
      remarks
      # ... 30+ fields
    }
  }
}

# ✅ GOOD: Request only needed fields
query GetTasks {
  jobs {
    id
    jobname
    jobneed {
      id
      jobstatus
      plandatetime
    }
  }
}
```

### **Pagination**

```graphql
# For large history queries, use pagination
query GetJobHistory($jobId: Int!, $page: Int!, $pageSize: Int!) {
  job(id: $jobId) {
    jobneeds(limit: $pageSize, offset: $page * $pageSize) {
      id
      plandatetime
      jobstatus
    }
  }
}
```

**Recommended Limits**:
- Task list: `limit: 50` (today's tasks)
- History view: `limit: 30` (last month)
- Infinite scroll: `limit: 20` per page

---

## 🐛 **Common Issues & Solutions**

### **Issue 1: Field doesn't exist**

**Error**: `Field 'jobneed_details' doesn't exist on type 'JobType'`

**Solution**: Update query to use `jobneed` (singular) instead of `jobneed_details`

### **Issue 2: Null jobneed when job has no executions**

**Error**: App crashes when `job.jobneed` is null

**Solution**: Handle null case in Kotlin
```kotlin
val latestJobneed = job.jobneed ?: run {
    // No executions yet - show "Not Started"
    return@run null
}
```

### **Issue 3: Duplicate questions in checklist**

**Error**: Checklist shows same question twice

**Solution**: Backend now prevents this with unique constraints. If you see duplicates, report as bug.

### **Issue 4: Incorrect seqno ordering**

**Error**: Checklist items appear in wrong order

**Solution**: Backend now enforces unique seqno. Always sort by `seqno`:
```kotlin
val orderedItems = jobneed.details?.sortedBy { it.seqno }
```

---

## 📞 **Support & Coordination**

### **Backend Team Contacts**
- API Changes: backend-team@example.com
- GraphQL Schema: graphql-team@example.com
- Data Migration: database-team@example.com

### **Testing Environment**
- Staging GraphQL: `https://staging-api.example.com/graphql/`
- GraphiQL: `https://staging-api.example.com/graphiql/`
- Swagger Docs: `https://staging-api.example.com/api/docs/`

### **Rollout Schedule**
- **Oct 3**: Backend deployed to staging
- **Oct 7**: Android team begins migration
- **Oct 14**: Android beta release
- **Oct 21**: Production rollout

---

## 🔬 **Appendix: Data Model ERD**

```
┌─────────────────────┐
│       Job           │  (Template/Definition)
│─────────────────────│
│ PK: id              │
│     jobname         │
│     cron            │
│     frequency       │
│     fromdate        │
│     uptodate        │
│ FK: asset_id        │
│ FK: qset_id         │
│ FK: parent_id       │───┐ Self-referencing
│                     │   │ (tour checkpoints)
└─────────────────────┘   │
         │                │
         │ 1-to-many      │
         ↓                ↓
┌─────────────────────┐
│     Jobneed         │  (Execution Instance)
│─────────────────────│
│ PK: id              │
│ FK: job_id          │───→ Points to Job template
│     jobdesc         │
│     plandatetime    │
│     expirydatetime  │
│     jobstatus       │
│     jobtype         │
│     starttime       │
│     endtime         │
│ FK: parent_id       │───┐ Self-referencing
│ FK: performedby_id  │   │ (checkpoint instances)
└─────────────────────┘   │
         │                │
         │ 1-to-many      │
         ↓                ↓
┌─────────────────────┐
│  JobneedDetails     │  (Checklist Item)
│─────────────────────│
│ PK: id              │
│ FK: jobneed_id      │───→ Points to Jobneed instance
│ FK: question_id     │
│     seqno           │
│     answertype      │
│     answer          │
│     min, max        │
│     ismandatory     │
│     alerts          │
└─────────────────────┘

UNIQUE (jobneed_id, question_id)  ✅ NEW
UNIQUE (jobneed_id, seqno)        ✅ NEW
```

---

## ✅ **Validation Checklist**

Before deploying Android app update:

- [ ] All GraphQL queries tested in GraphiQL
- [ ] Kotlin models updated with new fields
- [ ] Apollo codegen regenerated successfully
- [ ] Unit tests passing (100%)
- [ ] Integration tests with staging backend passing
- [ ] Offline sync tested with new schema
- [ ] Performance benchmarks met (< 500ms)
- [ ] Beta testing completed (no critical issues)
- [ ] Rollback plan documented
- [ ] User communication drafted

---

**Document Version**: 1.0
**Last Updated**: October 3, 2025
**Next Review**: October 10, 2025 (post-deployment)

**Questions?** Contact: backend-team@example.com
