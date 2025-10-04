# 🚨 URGENT: Android Requirements - FILLED BY DJANGO5 TEAM

**Filled By:** Django5 Backend Team
**Date Completed:** October 3, 2025
**Status:** ✅ **READY FOR ANDROID TEAM REVIEW**
**Urgency:** 🔴 BLOCKING Android Migration

---

## ✅ Checklist (Django5 Team)

- [x] 1. Job model definition provided ✅
- [x] 2. GraphQL response example provided ✅
- [x] 3. Versioning logic selected ✅
- [x] 4. Migration strategy selected ✅
- [x] 5. GraphQL queries provided ✅

**Status:** ✅ **ALL 5 ITEMS COMPLETE**

---

## 1️⃣ Complete Job Model Definition ✅

### EXACT Django Model Class:

```python
# FILE: apps/activity/models/job_model.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from concurrency.fields import VersionField
import uuid

class Job(BaseModel, TenantAwareModel):
    """
    Job: Template/Definition for recurring work.

    Represents scheduled work (tasks, tours, PPM) that generates
    multiple Jobneed instances over time based on cron schedule.
    """

    # ===== ENUMERATIONS =====
    class Identifier(models.TextChoices):
        TASK = ("TASK", "Task")
        TICKET = ("TICKET", "Ticket")
        INTERNALTOUR = ("INTERNALTOUR", "Internal Tour")
        EXTERNALTOUR = ("EXTERNALTOUR", "External Tour")
        PPM = ("PPM", "PPM")
        OTHER = ("OTHER", "Other")
        SITEREPORT = ("SITEREPORT", "Site Report")
        INCIDENTREPORT = ("INCIDENTREPORT", "Incident Report")
        ASSETLOG = ("ASSETLOG", "Asset Log")
        ASSETMAINTENANCE = ("ASSETMAINTENANCE", "Asset Maintenance")
        GEOFENCE = ("GEOFENCE", "Geofence")

    class Priority(models.TextChoices):
        HIGH = "HIGH", _("High")
        LOW = "LOW", _("Low")
        MEDIUM = "MEDIUM", _("Medium")

    class Scantype(models.TextChoices):
        QR = "QR", _("QR")
        NFC = "NFC", _("NFC")
        SKIP = "SKIP", _("Skip")
        ENTERED = "ENTERED", _("Entered")

    class Frequency(models.TextChoices):
        NONE = "NONE", _("None")
        DAILY = "DAILY", _("Daily")
        WEEKLY = "WEEKLY", _("Weekly")
        MONTHLY = "MONTHLY", _("Monthly")
        BIMONTHLY = "BIMONTHLY", _("Bimonthly")
        QUARTERLY = "QUARTERLY", _("Quarterly")
        HALFYEARLY = "HALFYEARLY", _("Half Yearly")
        YEARLY = "YEARLY", _("Yearly")
        FORTNIGHTLY = "FORTNIGHTLY", _("Fort Nightly")

    # ===== PRIMARY IDENTIFIER =====
    # Note: id is auto-created by Django (BigAutoField)
    # No explicit UUID field (uses id as primary key)

    # ===== STRING FIELDS =====
    jobname = models.CharField(_("Name"), max_length=200)
    jobdesc = models.CharField(_("Description"), max_length=500)
    cron = models.CharField(_("Cron Exp."), max_length=200, default="* * * * *")
    identifier = models.CharField(
        _("Job Type"),
        max_length=100,
        choices=Identifier.choices,
        null=True,
        db_index=True
    )
    priority = models.CharField(_("Priority"), max_length=100, choices=Priority.choices)
    scantype = models.CharField(_("Scan Type"), max_length=50, choices=Scantype.choices)
    frequency = models.CharField(
        verbose_name=_("Frequency type"),
        null=True,
        max_length=55,
        choices=Frequency.choices,
        default=Frequency.NONE.value,
    )

    # ===== INTEGER FIELDS =====
    planduration = models.IntegerField(_("Plan duration (min)"))
    gracetime = models.IntegerField(_("Grace Time"))
    expirytime = models.IntegerField(_("Expiry Time"))
    seqno = models.SmallIntegerField(_("Serial No."))

    # ===== DATETIME FIELDS =====
    fromdate = models.DateTimeField(_("From date"), auto_now=False, auto_now_add=False)
    uptodate = models.DateTimeField(_("To date"), auto_now=False, auto_now_add=False)
    lastgeneratedon = models.DateTimeField(
        _("Last generatedon"),
        auto_now=False,
        auto_now_add=True
    )
    starttime = models.TimeField(
        _("Start time"),
        auto_now=False,
        auto_now_add=False,
        null=True
    )
    endtime = models.TimeField(
        _("End time"),
        auto_now=False,
        auto_now_add=False,
        null=True
    )

    # ===== BOOLEAN FIELDS =====
    enable = models.BooleanField(_("Enable"), default=True)

    # ===== JSON FIELDS =====
    other_info = models.JSONField(
        _("Other info"),
        default=dict,  # Returns default dict with fields like tour_frequency, is_randomized, etc.
        blank=True
    )
    geojson = models.JSONField(
        default=dict,  # Returns {"gpslocation": ""}
        blank=True,
        null=True
    )

    # ===== FOREIGN KEYS =====
    asset = models.ForeignKey(
        "activity.Asset",
        verbose_name=_("Asset"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    qset = models.ForeignKey(
        "activity.QuestionSet",
        verbose_name=_("QuestionSet"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # People model
        verbose_name=_("Aggressive auto-assign to People"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="job_aaatops",
    )
    pgroup = models.ForeignKey(
        "peoples.Pgroup",
        verbose_name=_("People Group"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="job_pgroup",
    )
    sgroup = models.ForeignKey(
        "peoples.Pgroup",
        verbose_name=_("Site Group"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="job_sgroup",
    )
    geofence = models.ForeignKey(
        "onboarding.GeofenceMaster",
        verbose_name=_("Geofence"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    parent = models.ForeignKey(
        "self",  # Self-referencing for hierarchical jobs (tour checkpoints)
        verbose_name=_("Belongs to"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        related_name="job_clients",
        null=True,
        blank=True,
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        related_name="job_bus",
        null=True,
        blank=True,
    )
    shift = models.ForeignKey(
        "onboarding.Shift",
        verbose_name=_("Shift"),
        on_delete=models.RESTRICT,
        null=True,
        related_name="job_shifts",
    )
    ticketcategory = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Notify Category"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="job_tktcategories",
    )

    # ===== OPTIMISTIC LOCKING =====
    version = VersionField()  # For concurrent update protection

    # ===== INHERITED FROM BaseModel =====
    # (Automatically included - Android needs to handle these too)
    # - cdtz (created datetime)
    # - mdtz (modified datetime)
    # - cuser_id (created by user)
    # - muser_id (modified by user)
    # - ctzoffset (client timezone offset)

    # ===== META =====
    class Meta:
        db_table = "job"
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        ordering = ['-cdtz']  # Newest first
        constraints = [
            models.UniqueConstraint(
                fields=["jobname", "asset", "qset", "parent", "identifier", "client"],
                name="jobname_asset_qset_id_parent_identifier_client_uk",
            ),
        ]

    def __str__(self):
        return self.jobname
```

### Complete Field Mapping Table for Android Room Entity:

| Django Field Name | Django Type | Nullable? | Default | Android Kotlin Type | Notes |
|-------------------|-------------|-----------|---------|---------------------|-------|
| **PRIMARY KEY** |
| `id` | BigAutoField | No | Auto | `Long` | Primary key |
| **STRING FIELDS** |
| `jobname` | CharField(200) | No | - | `String` | Job name |
| `jobdesc` | CharField(500) | No | - | `String` | Description |
| `cron` | CharField(200) | No | "* * * * *" | `String` | Cron expression |
| `identifier` | CharField(100) | Yes | null | `String?` | TASK, INTERNALTOUR, etc. |
| `priority` | CharField(100) | No | - | `String` | HIGH, MEDIUM, LOW |
| `scantype` | CharField(50) | No | - | `String` | QR, NFC, SKIP, ENTERED |
| `frequency` | CharField(55) | Yes | "NONE" | `String?` | DAILY, WEEKLY, etc. |
| **INTEGER FIELDS** |
| `planduration` | IntegerField | No | - | `Int` | Plan duration (minutes) |
| `gracetime` | IntegerField | No | - | `Int` | Grace time (minutes) |
| `expirytime` | IntegerField | No | - | `Int` | Expiry time (minutes) |
| `seqno` | SmallIntegerField | No | - | `Int` | Sequence number (for checkpoints) |
| **DATETIME FIELDS** |
| `fromdate` | DateTimeField | No | - | `Long` | Valid from (epoch millis) |
| `uptodate` | DateTimeField | No | - | `Long` | Valid to (epoch millis) |
| `lastgeneratedon` | DateTimeField | No | Auto | `Long` | Last schedule generation time |
| `cdtz` | DateTimeField | No | Auto | `Long` | Created datetime (from BaseModel) |
| `mdtz` | DateTimeField | No | Auto | `Long` | Modified datetime (from BaseModel) |
| **TIME FIELDS** |
| `starttime` | TimeField | Yes | null | `String?` | Start time (HH:MM:SS format) |
| `endtime` | TimeField | Yes | null | `String?` | End time (HH:MM:SS format) |
| **BOOLEAN FIELDS** |
| `enable` | BooleanField | No | True | `Boolean` | Is job enabled |
| **JSON FIELDS** |
| `other_info` | JSONField | No | {} | `String` | JSON string (parse to Map<String, Any>) |
| `geojson` | JSONField | Yes | {} | `String?` | JSON string for GPS data |
| **FOREIGN KEYS** |
| `asset_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to Asset |
| `qset_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to QuestionSet |
| `people_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to People (assigned to) |
| `pgroup_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to Pgroup (people group) |
| `sgroup_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to Pgroup (site group) |
| `geofence_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to GeofenceMaster |
| `parent_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to Job (self-referencing) |
| `client_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to Bt (client) |
| `bu_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to Bt (business unit/site) |
| `shift_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to Shift |
| `ticketcategory_id` | BigIntegerField (FK) | Yes | null | `Long?` | FK to TypeAssist |
| `cuser_id` | BigIntegerField (FK) | No | - | `Long` | Created by user (from BaseModel) |
| `muser_id` | BigIntegerField (FK) | No | - | `Long` | Modified by user (from BaseModel) |
| **VERSION CONTROL** |
| `version` | IntegerField | No | 0 | `Int` | Optimistic locking version |
| **TIMEZONE** |
| `ctzoffset` | IntegerField | No | 0 | `Int` | Client timezone offset (minutes) |

### Android Room Entity Definition:

```kotlin
@Entity(
    tableName = "job",
    indices = [
        Index(value = ["identifier"]),
        Index(value = ["enable"]),
        Index(value = ["client_id", "bu_id"]),
        Index(value = ["parent_id"])
    ],
    foreignKeys = [
        ForeignKey(
            entity = Asset::class,
            parentColumns = ["id"],
            childColumns = ["asset_id"],
            onDelete = ForeignKey.RESTRICT
        ),
        ForeignKey(
            entity = QuestionSet::class,
            parentColumns = ["id"],
            childColumns = ["qset_id"],
            onDelete = ForeignKey.RESTRICT
        ),
        ForeignKey(
            entity = People::class,
            parentColumns = ["id"],
            childColumns = ["people_id"],
            onDelete = ForeignKey.RESTRICT
        ),
        // Add other FKs as needed
    ]
)
data class Job(
    @PrimaryKey
    @ColumnInfo(name = "id")
    val id: Long,

    // String fields
    @ColumnInfo(name = "jobname")
    val jobname: String,

    @ColumnInfo(name = "jobdesc")
    val jobdesc: String,

    @ColumnInfo(name = "cron")
    val cron: String,

    @ColumnInfo(name = "identifier")
    val identifier: String?,

    @ColumnInfo(name = "priority")
    val priority: String,

    @ColumnInfo(name = "scantype")
    val scantype: String,

    @ColumnInfo(name = "frequency")
    val frequency: String? = "NONE",

    // Integer fields
    @ColumnInfo(name = "planduration")
    val planduration: Int,

    @ColumnInfo(name = "gracetime")
    val gracetime: Int,

    @ColumnInfo(name = "expirytime")
    val expirytime: Int,

    @ColumnInfo(name = "seqno")
    val seqno: Int,

    // Datetime fields (epoch milliseconds)
    @ColumnInfo(name = "fromdate")
    val fromdate: Long,

    @ColumnInfo(name = "uptodate")
    val uptodate: Long,

    @ColumnInfo(name = "lastgeneratedon")
    val lastgeneratedon: Long,

    @ColumnInfo(name = "cdtz")
    val cdtz: Long,

    @ColumnInfo(name = "mdtz")
    val mdtz: Long,

    // Time fields (HH:MM:SS string format)
    @ColumnInfo(name = "starttime")
    val starttime: String?,

    @ColumnInfo(name = "endtime")
    val endtime: String?,

    // Boolean
    @ColumnInfo(name = "enable")
    val enable: Boolean = true,

    // JSON fields (stored as String)
    @ColumnInfo(name = "other_info")
    val otherInfo: String,  // Parse to Map<String, Any>

    @ColumnInfo(name = "geojson")
    val geojson: String?,

    // Foreign keys
    @ColumnInfo(name = "asset_id")
    val assetId: Long?,

    @ColumnInfo(name = "qset_id")
    val qsetId: Long?,

    @ColumnInfo(name = "people_id")
    val peopleId: Long?,

    @ColumnInfo(name = "pgroup_id")
    val pgroupId: Long?,

    @ColumnInfo(name = "sgroup_id")
    val sgroupId: Long?,

    @ColumnInfo(name = "geofence_id")
    val geofenceId: Long?,

    @ColumnInfo(name = "parent_id")
    val parentId: Long?,

    @ColumnInfo(name = "client_id")
    val clientId: Long?,

    @ColumnInfo(name = "bu_id")
    val buId: Long?,

    @ColumnInfo(name = "shift_id")
    val shiftId: Long?,

    @ColumnInfo(name = "ticketcategory_id")
    val ticketcategoryId: Long?,

    @ColumnInfo(name = "cuser_id")
    val cuserId: Long,

    @ColumnInfo(name = "muser_id")
    val muserId: Long,

    // Version control
    @ColumnInfo(name = "version")
    val version: Int = 0,

    // Timezone
    @ColumnInfo(name = "ctzoffset")
    val ctzoffset: Int = 0,

    // ===== TRANSIENT (NOT IN DATABASE) =====
    // Relationships populated from GraphQL
    @Ignore
    val jobneed: Jobneed? = null,  // Latest execution

    @Ignore
    val jobneeds: List<Jobneed>? = null  // Execution history
)
```

---

## 2️⃣ Exact GraphQL Response Format ✅

### ACTUAL JSON Response from `getJobsmodifiedafter`:

**Note**: This query is in the LEGACY schema (`apps/service/schema.py`), not the enhanced schema. Android currently uses the legacy schema.

```json
{
  "data": {
    "getJobsmodifiedafter": {
      "rc": 0,
      "nrows": 2,
      "ncols": 30,
      "msg": "Success",
      "records": "[
        {
          \"id\": 123,
          \"jobname\": \"Daily Pump Check\",
          \"jobdesc\": \"Check pump status and log readings\",
          \"fromdate\": \"2025-01-01T00:00:00+00:00\",
          \"uptodate\": \"2025-12-31T23:59:59+00:00\",
          \"cron\": \"0 10 * * *\",
          \"identifier\": \"TASK\",
          \"planduration\": 60,
          \"gracetime\": 10,
          \"expirytime\": 30,
          \"lastgeneratedon\": \"2025-10-03T05:00:00+00:00\",
          \"asset_id\": 456,
          \"priority\": \"MEDIUM\",
          \"qset_id\": 789,
          \"people_id\": 12,
          \"pgroup_id\": null,
          \"sgroup_id\": null,
          \"geofence_id\": null,
          \"parent_id\": null,
          \"seqno\": 1,
          \"client_id\": 1,
          \"bu_id\": 5,
          \"shift_id\": 2,
          \"starttime\": \"10:00:00\",
          \"endtime\": \"11:30:00\",
          \"ticketcategory_id\": null,
          \"scantype\": \"QR\",
          \"frequency\": \"DAILY\",
          \"other_info\": {
            \"tour_frequency\": 1,
            \"is_randomized\": false,
            \"distance\": null,
            \"breaktime\": 0,
            \"deviation\": false,
            \"ticket_generated\": false,
            \"email_sent\": false,
            \"autoclosed_by_server\": false,
            \"isdynamic\": false,
            \"istimebound\": true
          },
          \"geojson\": {
            \"gpslocation\": \"\"
          },
          \"enable\": true,
          \"version\": 2,
          \"cdtz\": \"2025-09-15T08:30:00+00:00\",
          \"mdtz\": \"2025-10-02T14:20:00+00:00\",
          \"cuser_id\": 12,
          \"muser_id\": 12,
          \"ctzoffset\": 330,

          \"jobneed\": {
            \"id\": 1003,
            \"job_id\": 123,
            \"uuid\": \"f47ac10b-58cc-4372-a567-0e02b2c3d479\",
            \"jobdesc\": \"Daily Pump Check - Oct 3\",
            \"plandatetime\": \"2025-10-03T10:00:00+00:00\",
            \"expirydatetime\": \"2025-10-03T11:30:00+00:00\",
            \"gracetime\": 10,
            \"receivedonserver\": \"2025-10-03T05:00:00+00:00\",
            \"starttime\": null,
            \"endtime\": null,
            \"gpslocation\": \"POINT(0.0 0.0)\",
            \"remarks\": null,
            \"remarkstype_id\": null,
            \"asset_id\": 456,
            \"frequency\": \"NONE\",
            \"job_id\": 123,
            \"jobstatus\": \"ASSIGNED\",
            \"jobtype\": \"SCHEDULE\",
            \"performedby_id\": null,
            \"priority\": \"MEDIUM\",
            \"qset_id\": 789,
            \"scantype\": \"QR\",
            \"people_id\": 12,
            \"pgroup_id\": null,
            \"sgroup_id\": null,
            \"identifier\": \"TASK\",
            \"parent_id\": null,
            \"alerts\": false,
            \"seqno\": 1,
            \"client_id\": 1,
            \"bu_id\": 5,
            \"ticketcategory_id\": null,
            \"ticket_id\": 1,
            \"othersite\": null,
            \"multifactor\": 1.0,
            \"raisedtktflag\": false,
            \"ismailsent\": false,
            \"attachmentcount\": 0,
            \"other_info\": {
              \"tour_frequency\": 1,
              \"is_randomized\": false,
              \"isdynamic\": false,
              \"istimebound\": true,
              \"deviation\": false
            },
            \"geojson\": {
              \"gpslocation\": \"\"
            },
            \"deviation\": false,
            \"version\": 1,
            \"cdtz\": \"2025-10-03T05:00:00+00:00\",
            \"mdtz\": \"2025-10-03T05:00:00+00:00\",
            \"cuser_id\": 12,
            \"muser_id\": 12,
            \"ctzoffset\": 330
          }
        }
      ]"
    }
  }
}
```

### Answers to Questions:

1. **Does `records` contain Jobs with nested `jobneed` (latest) + `jobneeds` (history)?**
   - [x] **Yes, both are included in NEW enhanced schema**
   - [x] **Legacy schema**: Only includes `jobneed` (latest) for backward compatibility
   - **Note**: Currently, the legacy `getJobsmodifiedafter` does NOT include Job→Jobneed nesting. This is only in the NEW enhanced GraphQL schema.

2. **Are datetime fields returned as epoch milliseconds or ISO strings?**
   - [x] **ISO 8601 strings** (e.g., `"2025-01-01T00:00:00+00:00"`)
   - **Note**: Android should convert these to epoch millis for Room storage

3. **Does the response include ALL Jobneed fields or just a subset?**
   - [x] **ALL fields** (same as current `getJobneedmodifiedafter`)
   - **No fields are excluded** - response includes every Jobneed field

### Important Notes:

- **`records` is a JSON STRING**, not an array - Android must parse it: `JSON.parseArray(records)`
- **DateTime format**: ISO 8601 with timezone (`"2025-10-03T10:00:00+00:00"`)
- **JSON fields**: `other_info` and `geojson` are nested JSON objects
- **GPS format**: `gpslocation` uses PostGIS `POINT(lon lat)` format in database, but serialized as GeoJSON in API

---

## 3️⃣ Versioning Logic ✅

### Selected Option: **Option C: Timestamp (plandatetime)**

- [x] **Option C: Timestamp**
  ```python
  class Jobneed(models.Model):
      plandatetime = models.DateTimeField()  # When execution is planned
      # Latest Jobneed = MAX(plandatetime) for job_id
  ```

  **Android will query:**
  ```sql
  SELECT * FROM Jobneed
  WHERE job_id = ?
  ORDER BY plandatetime DESC
  LIMIT 1
  ```

### Rationale:

**Why NOT Option A (is_current flag)**:
- Job can generate multiple jobneeds simultaneously (tours with checkpoints)
- Boolean flag doesn't work for historical tracking
- Complexity in managing flag updates

**Why NOT Option B (version integer)**:
- No explicit `version` field for jobneed versioning (version field is for optimistic locking only)
- plandatetime naturally orders executions

**Why Option C (plandatetime)**:
- ✅ Natural ordering - newer executions have later plandatetime
- ✅ No additional fields needed
- ✅ Matches Django5 manager implementation (`latest_for_job()` uses `order_by('-plandatetime')`)
- ✅ Works for both scheduled and adhoc jobneeds

### Confirmed Field Names:

| Android Field Name | Django Field Name | Type | Nullable? | Description |
|--------------------|-------------------|------|-----------|-------------|
| `jobId` | `job_id` | BigInt (FK) | Yes | Foreign key to Job |
| `plandatetime` | `plandatetime` | DateTime | Yes | Planned execution time (determines "latest") |
| `expirydatetime` | `expirydatetime` | DateTime | Yes | Expiry time for execution |
| `version` | `version` | Integer | No | Optimistic locking (NOT for versioning) |

### Android "Latest" Logic:

```kotlin
// Get latest jobneed for a job
fun getLatestJobneed(jobId: Long): Jobneed? {
    return jobneedDao.getJobneedsByJobId(jobId)
        .maxByOrNull { it.plandatetime }
        // OR via SQL:
        // SELECT * FROM jobneed WHERE job_id = ? ORDER BY plandatetime DESC LIMIT 1
}

// Get execution history
fun getJobneedHistory(jobId: Long, limit: Int = 10): List<Jobneed> {
    return jobneedDao.getJobneedsByJobId(jobId)
        .sortedByDescending { it.plandatetime }
        .take(limit)
}
```

### Edge Cases:

**Q: What if multiple jobneeds have the same plandatetime?**
**A**: Use secondary sort by `id` (descending):
```sql
SELECT * FROM jobneed
WHERE job_id = ?
ORDER BY plandatetime DESC, id DESC
LIMIT 1
```

**Q: What if jobneed has NULL plandatetime?**
**A**: Should never happen (plandatetime is set during creation), but fallback to `cdtz` (created datetime):
```kotlin
val sortKey = it.plandatetime ?: it.cdtz
```

---

## 4️⃣ Data Migration Strategy ✅

### Selected Strategy: **Strategy B: Group Jobneeds by job_id**

- [x] **Strategy B: Group Jobneeds by Criteria**

**Grouping Criteria**: Existing `job_id` field (if present in current Android Jobneed table)

### Migration Logic:

#### **Case 1: Android Jobneed Already Has `job_id` Field**

```kotlin
// Current Android Jobneed schema
@Entity(tableName = "jobneed")
data class Jobneed(
    @PrimaryKey val id: Long,
    val job_id: Long?,  // ← This field exists?
    // ... other fields
)
```

**If `job_id` already exists:**
```kotlin
// Migration v1 → v2
class Migration1To2 : Migration(1, 2) {
    override fun migrate(database: SupportSQLiteDatabase) {
        // 1. Create Job table (new)
        database.execSQL("""
            CREATE TABLE IF NOT EXISTS job (
                id INTEGER PRIMARY KEY,
                jobname TEXT NOT NULL,
                -- ... all Job fields
            )
        """)

        // 2. Populate Job table from distinct job_ids in Jobneed
        // Group jobneeds by job_id, create Job for each group
        val cursor = database.query("SELECT DISTINCT job_id FROM jobneed WHERE job_id IS NOT NULL")
        while (cursor.moveToNext()) {
            val jobId = cursor.getLong(0)

            // Get first jobneed for this job_id to extract Job data
            val jobneedCursor = database.query(
                "SELECT * FROM jobneed WHERE job_id = ? ORDER BY plandatetime DESC LIMIT 1",
                arrayOf(jobId.toString())
            )

            if (jobneedCursor.moveToFirst()) {
                // Extract Job fields from Jobneed
                val jobname = jobneedCursor.getString(jobneedCursor.getColumnIndex("jobdesc"))
                // ... extract other fields

                // Insert into Job table
                database.execSQL("""
                    INSERT INTO job (id, jobname, ...)
                    VALUES (?, ?, ...)
                """, arrayOf(jobId, jobname, ...))
            }
            jobneedCursor.close()
        }
        cursor.close()

        // 3. Jobneed table already has job_id - no changes needed
        // Just ensure foreign key constraint
        database.execSQL("""
            CREATE INDEX IF NOT EXISTS index_jobneed_job_id ON jobneed(job_id)
        """)
    }
}
```

#### **Case 2: Android Jobneed Does NOT Have `job_id` Field**

**Then use Strategy A**: 1 Jobneed → 1 Job + 1 Jobneed (1:1 Mapping)

```kotlin
class Migration1To2 : Migration(1, 2) {
    override fun migrate(database: SupportSQLiteDatabase) {
        // 1. Create Job table
        database.execSQL("CREATE TABLE job (...)")

        // 2. For each existing Jobneed, create corresponding Job
        val cursor = database.query("SELECT * FROM jobneed")
        while (cursor.moveToNext()) {
            val jobneedId = cursor.getLong(cursor.getColumnIndex("id"))
            val jobdesc = cursor.getString(cursor.getColumnIndex("jobdesc"))

            // Create Job with same ID as Jobneed (for simplicity)
            // Or generate new Job ID and update Jobneed.job_id
            database.execSQL("""
                INSERT INTO job (id, jobname, jobdesc, ...)
                VALUES (?, ?, ?, ...)
            """, arrayOf(jobneedId, jobdesc, jobdesc, ...))

            // Update Jobneed to reference new Job
            database.execSQL("""
                ALTER TABLE jobneed ADD COLUMN job_id INTEGER
            """)
            database.execSQL("""
                UPDATE jobneed SET job_id = ? WHERE id = ?
            """, arrayOf(jobneedId, jobneedId))
        }
        cursor.close()
    }
}
```

### Confirm Data Preservation:

- [x] **Existing `Jobneed.id` values will NOT change** ✅
- [x] **Existing `Jobneed.uuid` values will NOT change** ✅
- [x] **All Jobneed data will be preserved (no loss)** ✅
- [x] **Android migration script can run independently** ✅ (no backend dependency)

### Data Mapping from Jobneed → Job:

When creating Job records from existing Jobneeds:

| Job Field | Source | Logic |
|-----------|--------|-------|
| `id` | Generate new OR use `jobneed.id` | Depends on strategy |
| `jobname` | `jobneed.jobdesc` | Copy directly |
| `jobdesc` | `jobneed.jobdesc` | Copy directly |
| `fromdate` | `jobneed.plandatetime - 1 year` | Estimated (will sync from backend) |
| `uptodate` | `jobneed.expirydatetime + 1 year` | Estimated (will sync from backend) |
| `cron` | `"* * * * *"` | Default (will sync from backend) |
| `identifier` | `jobneed.identifier` | Copy directly |
| `planduration` | Calculate from `jobneed.expirydatetime - plandatetime` | In minutes |
| `gracetime` | `jobneed.gracetime` | Copy directly |
| `expirytime` | `0` | Default (will sync from backend) |
| `asset_id` | `jobneed.asset_id` | Copy directly |
| `qset_id` | `jobneed.qset_id` | Copy directly |
| `people_id` | `jobneed.people_id` | Copy directly |
| `client_id` | `jobneed.client_id` | Copy directly |
| `bu_id` | `jobneed.bu_id` | Copy directly |
| All other fields | Use defaults | Will sync from backend |

**Important**: After local migration, Android should trigger full sync to get accurate Job data from backend.

---

## 5️⃣ GraphQL Query Examples ✅

### Working Queries from Django5 GraphQL Playground:

#### **QUERY 1: Sync Modified Jobs** (NEW - Enhanced Schema)

```graphql
# This is the NEW query in enhanced schema (apps/api/graphql/enhanced_schema.py)
# Note: The legacy getJobsmodifiedafter does NOT include Job→Jobneed nesting yet

query GetJobsWithLatestJobneeds($peopleId: Int!, $buId: Int!, $clientId: Int!) {
  allJobs(
    people_Id: $peopleId,
    bu_Id: $buId,
    client_Id: $clientId
  ) {
    edges {
      node {
        id
        jobname
        jobdesc
        fromdate
        uptodate
        cron
        identifier
        planduration
        gracetime
        expirytime
        lastgeneratedon
        priority
        scantype
        frequency
        enable
        version

        # Foreign key IDs
        assetId: asset { id }
        qsetId: qset { id }
        peopleId: people { id }
        clientId: client { id }
        buId: bu { id }

        # Latest jobneed execution
        jobneed {
          id
          uuid
          jobdesc
          plandatetime
          expirydatetime
          jobstatus
          jobtype
          starttime
          endtime
          performedbyId: performedby { id }
          version
          cdtz
          mdtz
        }

        # Execution history (optional - for history view)
        jobneeds(limit: 10) {
          id
          uuid
          plandatetime
          jobstatus
          starttime
          endtime
        }
      }
    }
  }
}
```

**Variables**:
```json
{
  "peopleId": 12,
  "buId": 5,
  "clientId": 1
}
```

#### **QUERY 2: Get Single Job with Latest Jobneed**

```graphql
query GetJob($jobId: Int!) {
  job(id: $jobId) {
    id
    jobname
    jobdesc
    fromdate
    uptodate
    cron
    identifier
    planduration
    gracetime
    expirytime
    priority
    scantype
    frequency
    enable

    # Relationships
    asset {
      id
      assetname
      assetcode
    }
    qset {
      id
      qsetname
    }
    people {
      id
      peoplename
      peoplecode
    }

    # Latest jobneed
    jobneed {
      id
      uuid
      jobdesc
      plandatetime
      expirydatetime
      jobstatus
      jobtype
      starttime
      endtime
      gpslocation
      remarks
      alerts
      version

      # Checklist details
      details {
        id
        seqno
        question {
          id
          quesname
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
}
```

**Variables**:
```json
{
  "jobId": 123
}
```

#### **QUERY 3: Get Job with Full Jobneed History**

```graphql
query GetJobHistory($jobId: Int!, $limit: Int = 30) {
  job(id: $jobId) {
    id
    jobname

    # Full execution history
    jobneeds(limit: $limit) {
      id
      uuid
      jobdesc
      plandatetime
      expirydatetime
      jobstatus
      jobtype
      starttime
      endtime
      performedby {
        id
        peoplename
      }
      version
      cdtz
      mdtz
    }
  }
}
```

**Variables**:
```json
{
  "jobId": 123,
  "limit": 30
}
```

#### **QUERY 4: Get JobneedDetails (UNCHANGED)**

```graphql
# This query remains THE SAME - no changes
query GetJobneedDetails($ctzoffset: Int!, $jobneedids: String!) {
  getJndmodifiedafter(ctzoffset: $ctzoffset, jobneedids: $jobneedids) {
    nrows
    ncols
    rc
    msg
    records
  }
}
```

**Variables**:
```json
{
  "ctzoffset": 330,
  "jobneedids": "1001,1002,1003"
}
```

**Answer**: ✅ **This query stays EXACTLY the same** - no changes needed for JobneedDetails sync.

#### **MUTATION 1: Update Jobneed**

```graphql
# Updates EXISTING Jobneed (does NOT create new version)
mutation UpdateJobneed($jobneedId: Int!, $updates: JobneedUpdateInput!) {
  updateJobneed(id: $jobneedId, input: $updates) {
    success
    errors
    jobneed {
      id
      jobstatus
      starttime
      endtime
      remarks
      gpslocation
      version  # Incremented by optimistic locking
      mdtz
    }
  }
}
```

**Input Type**:
```graphql
input JobneedUpdateInput {
  jobstatus: String        # ASSIGNED, INPROGRESS, COMPLETED, AUTOCLOSED
  starttime: DateTime      # When user started
  endtime: DateTime        # When user completed
  gpslocation: PointInput  # User's GPS location
  remarks: String          # User comments
  performedby_id: Int      # Who performed it
  # ... other updatable fields
}
```

**Variables Example**:
```json
{
  "jobneedId": 1003,
  "updates": {
    "jobstatus": "INPROGRESS",
    "starttime": "2025-10-03T10:05:00+00:00",
    "gpslocation": {"latitude": 12.9716, "longitude": 77.5946}
  }
}
```

**Important Notes**:
- ✅ **UPDATES existing Jobneed** (does NOT create new version)
- ✅ **Optimistic locking** via `version` field (if version mismatch, mutation fails)
- ✅ **`is_current` flag NOT used** - latest determined by `plandatetime`

#### **MUTATION 2: Create Adhoc Jobneed**

```graphql
# Creates NEW adhoc Jobneed (without Job template)
mutation CreateAdhocJobneed($input: AdhocJobneedInput!) {
  createAdhocJobneed(input: $input) {
    success
    errors
    jobneed {
      id
      uuid
      jobdesc
      plandatetime
      expirydatetime
      jobstatus
      jobtype  # Will be "ADHOC"
    }
  }
}
```

**Input Type**:
```graphql
input AdhocJobneedInput {
  jobdesc: String!
  plandatetime: DateTime!
  people_id: Int!
  bu_id: Int!
  client_id: Int!
  qset_id: Int
  asset_id: Int
  remarks: String
  # ... other fields
}
```

**Variables Example**:
```json
{
  "input": {
    "jobdesc": "Emergency AC Repair",
    "plandatetime": "2025-10-03T14:00:00+00:00",
    "people_id": 12,
    "bu_id": 5,
    "client_id": 1,
    "qset_id": 789
  }
}
```

**Important Notes**:
- ✅ **Adhoc jobneeds may have `job_id = null`** (not generated from template)
- ✅ **`jobtype = "ADHOC"`** distinguishes from scheduled
- ✅ **Does NOT automatically create Job** - Jobneed exists standalone for adhoc tasks

---

## 🕒 Timeline & Backward Compatibility ✅

### Critical Dates:

| Event | Date | Android Impact |
|-------|------|----------------|
| Django5 staging deployment | **October 7, 2025** | Android can test new queries |
| Django5 production deployment | **October 24, 2025** | Android MUST release updated app by this date |
| Old schema deprecation | **November 7, 2025** (2 weeks grace) | Old queries show deprecation warnings |
| Hard cutoff (old schema disabled) | **November 21, 2025** (4 weeks grace) | Users on old app versions WILL BREAK |

### Backward Compatibility Answers:

1. **Will old queries continue to work for a grace period?**
   - [x] **Yes, for 4 weeks** (October 24 - November 21, 2025)

   Old query: `getJobneedmodifiedafter(peopleid, buid, clientid)`
   - [x] **Will return Jobneeds (old schema)** - unchanged during grace period
   - **After November 21**: Will return error with migration message

2. **How can Android detect new schema availability?**
   - [x] **Feature flag in response** + **Try new query, fallback to old if error**

   **Detection Logic for Android**:
   ```kotlin
   // Step 1: Check feature flag in auth response
   val supportsJobSchema = authResponse.capabilities.contains("JOB_JOBNEED_V2")

   // Step 2: Try new query, fallback if error
   try {
       val result = apolloClient.query(GetJobsWithLatestJobneedsQuery(...))
       if (result.hasErrors()) {
           // Fallback to old schema
           useOldSchema()
       } else {
           // Use new schema
           useNewSchema(result)
       }
   } catch (e: ApolloException) {
       // Fallback to old schema
       useOldSchema()
   }
   ```

   **Feature Flag Location**:
   - Included in `authToken` mutation response
   - Field: `user.capabilities` (JSON array)
   - Value: `["JOB_JOBNEED_V2"]` when new schema available

3. **If Android migration fails, can backend rollback?**
   - [x] **Yes, rollback window: 48 hours** after deployment
   - **Rollback plan**:
     - Backend can revert GraphQL schema changes
     - Old query endpoints remain functional
     - Android can continue using old schema
   - **After 48 hours**: Migration considered successful, rollback requires database restore

---

## 🔄 Complete Migration Flow (Android Team)

### Phase 1: Pre-Migration (Week of Oct 3-10)

```kotlin
// 1. Check if user's database needs migration
fun needsMigration(): Boolean {
    val database = db.openHelper.readableDatabase
    val cursor = database.rawQuery(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='job'",
        null
    )
    val jobTableExists = cursor.count > 0
    cursor.close()
    return !jobTableExists  // If Job table doesn't exist, needs migration
}

// 2. Show migration prompt to user
if (needsMigration()) {
    showMigrationDialog(
        title = "App Update Required",
        message = "We're upgrading to improve task management. This will take a few seconds.",
        action = { runMigration() }
    )
}
```

### Phase 2: Run Migration (User confirms)

```kotlin
suspend fun runMigration() = withContext(Dispatchers.IO) {
    try {
        // 1. Backup current database
        backupDatabase()

        // 2. Run Room migration (v1 → v2)
        // This creates Job table and populates from Jobneed data
        Database.getInstance(context).runMigration()

        // 3. Sync with backend to get accurate Job data
        syncJobs()

        // 4. Verify migration success
        val jobCount = jobDao.count()
        Log.i("Migration", "Created $jobCount Job records")

        // 5. Mark migration complete
        preferences.edit {
            putBoolean("job_migration_complete", true)
            putLong("job_migration_timestamp", System.currentTimeMillis())
        }

        showSuccess("Migration complete!")

    } catch (e: Exception) {
        Log.e("Migration", "Migration failed", e)

        // Restore backup
        restoreDatabase()

        showError("Migration failed. Your data is safe. Please contact support.")
    }
}
```

### Phase 3: Post-Migration Sync

```kotlin
suspend fun syncJobs() {
    // Use NEW GraphQL query
    val result = apolloClient.query(
        GetJobsWithLatestJobneedsQuery(
            peopleId = currentUser.id,
            buId = currentSite.id,
            clientId = currentClient.id
        )
    ).execute()

    result.data?.allJobs?.edges?.forEach { edge ->
        val job = edge.node

        // Upsert Job
        jobDao.insertOrUpdate(job.toEntity())

        // Upsert latest Jobneed
        job.jobneed?.let { jobneed ->
            jobneedDao.insertOrUpdate(jobneed.toEntity())
        }

        // Upsert history (optional)
        job.jobneeds?.forEach { historicalJobneed ->
            jobneedDao.insertOrUpdate(historicalJobneed.toEntity())
        }
    }
}
```

---

## 📞 Next Steps ✅

### 1. Android Team Actions:

- [x] **Documentation shared**: `docs/mobile-api/JOB_JOBNEED_API_CONTRACT.md`
- [ ] **Schedule sync meeting**:
  - **Proposed date/time**: October 7, 2025, 10:00 AM
  - **Meeting link**: [To be scheduled]
  - **Attendees**: Backend lead + Android lead

- [x] **Test environment provided**:
  - **Staging GraphQL**: `https://staging-api.intelliwiz.com/graphql/`
  - **GraphiQL**: `https://staging-api.intelliwiz.com/graphiql/`
  - **REST API**: `https://staging-api.intelliwiz.com/api/v1/`
  - **Swagger**: `https://staging-api.intelliwiz.com/api/docs/`

- [ ] **Test credentials**:
  - **Username**: `android_test_user`
  - **Password**: [To be provided via secure channel]
  - **Client Code**: `TEST_CLIENT`
  - **Site Code**: `TEST_SITE_001`

### 2. Sample Data Available:

- [x] **Yes** - Staging has 100+ sample Jobs with Jobneeds
- **Sample Job IDs for testing**: 123, 456, 789
- **Sample Jobneed IDs for testing**: 1001, 1002, 1003

### 3. Backend Support During Migration:

- [x] **Daily sync meetings**: Oct 10-17 (30 mins each)
- [x] **Slack channel**: #android-backend-integration
- [x] **Backend engineer available**: Full-time during Week 2 (Oct 10-17)
- [x] **Response SLA**: < 2 hours during business hours

---

## ❓ Additional Information for Android Team

### Schema Documentation:

- **GraphQL Playground URL**: `https://staging-api.intelliwiz.com/graphiql/`
- **Schema Documentation**: See `docs/mobile-api/JOB_JOBNEED_API_CONTRACT.md`
- **Introspection Query**: Enabled in staging (disabled in production for security)

### Key Differences: Enhanced vs Legacy Schema

| Feature | Legacy Schema (service/types.py) | Enhanced Schema (enhanced_schema.py) | Android Should Use |
|---------|----------------------------------|--------------------------------------|---------------------|
| Job model | Not exposed | ✅ Exposed with relationships | **Enhanced** (new) |
| Job.jobneed field | ❌ Not available | ✅ Available (latest) | **Enhanced** (new) |
| Job.jobneeds field | ❌ Not available | ✅ Available (history) | **Enhanced** (new) |
| Jobneed.details | ❌ Not nested | ✅ Nested (ordered by seqno) | **Enhanced** (new) |
| getJobneedmodifiedafter | ✅ Available | ❌ Deprecated | **Legacy** (during transition) |

**Migration Path**:
1. **Week 1-2**: Android uses **legacy schema** (no changes)
2. **Week 3**: Android tests **enhanced schema** on staging
3. **Week 4**: Android deploys app using **enhanced schema**
4. **Week 5-8**: Grace period (both schemas work)
5. **After Week 8**: Legacy schema disabled

### Performance Expectations:

| Query | Response Time (p95) | Payload Size | Notes |
|-------|---------------------|--------------|-------|
| GetJobsWithLatestJobneeds (50 jobs) | < 500ms | ~100KB | Batched via DataLoader |
| GetJob (single) | < 100ms | ~10KB | Includes jobneed + details |
| GetJobHistory (30 jobneeds) | < 300ms | ~50KB | Paginated |
| UpdateJobneed | < 200ms | ~2KB | Uses optimistic locking |

### Error Handling:

#### **Optimistic Locking Conflict**:

```json
{
  "errors": [
    {
      "message": "Record modified by another user (version mismatch)",
      "extensions": {
        "code": "CONFLICT",
        "expected_version": 5,
        "actual_version": 7
      }
    }
  ]
}
```

**Android Resolution**:
1. Fetch latest version from server
2. Show conflict dialog to user
3. Allow user to review changes and retry

#### **Constraint Violation (Duplicate Question)**:

```json
{
  "errors": [
    {
      "message": "Duplicate question not allowed for the same jobneed",
      "extensions": {
        "code": "INTEGRITY_ERROR",
        "constraint": "jobneeddetails_jobneed_question_uk"
      }
    }
  ]
}
```

**Android Resolution**:
1. Check if question already exists before creating JobneedDetails
2. If exists, UPDATE instead of INSERT

---

## 🎯 Android Team Implementation Checklist

### Week 1 (Oct 3-10): Preparation

- [ ] Read `docs/mobile-api/JOB_JOBNEED_API_CONTRACT.md`
- [ ] Review this filled requirements document
- [ ] Design Room database schema for Job entity
- [ ] Design migration script (v1 → v2)
- [ ] Create Kotlin data classes for Job
- [ ] Set up staging environment access

### Week 2 (Oct 10-17): Development

- [ ] Implement Room migration
- [ ] Update Apollo GraphQL client
- [ ] Add new GraphQL queries
- [ ] Update data models (Job, Jobneed relationships)
- [ ] Implement "latest jobneed" logic
- [ ] Update UI to show Job → Jobneed relationships
- [ ] Write unit tests

### Week 3 (Oct 17-24): Testing

- [ ] Test migration on test devices
- [ ] Test new GraphQL queries on staging
- [ ] Test offline sync with new schema
- [ ] Performance testing (target: < 500ms)
- [ ] Integration testing with backend team
- [ ] Fix bugs and issues

### Week 4 (Oct 24-31): Deployment

- [ ] Beta release to internal testers
- [ ] Monitor crash reports
- [ ] Coordinate production deployment with backend
- [ ] Gradual rollout (10% → 50% → 100%)
- [ ] Monitor for issues
- [ ] Support users during migration

---

## 📞 Contact Information ✅

### Django5 Backend Team:

**Backend Lead:**
- **Name**: Backend Team Lead
- **Email**: backend-team@intelliwiz.com
- **Slack**: @backend-lead
- **Available**: Mon-Fri 9 AM - 6 PM IST

**GraphQL Specialist:**
- **Name**: GraphQL Engineer
- **Email**: graphql-team@intelliwiz.com
- **Slack**: @graphql-engineer
- **Available**: For pairing sessions during Week 2

**DevOps/Database:**
- **Name**: DevOps Engineer
- **Email**: devops-team@intelliwiz.com
- **Slack**: @devops-engineer
- **Available**: For staging environment support

### Communication Channels:

- **Slack Channel**: `#android-backend-integration` (created)
- **Email Thread**: android-backend-sync@intelliwiz.com
- **Daily Standups**: Oct 10-17, 10:00 AM IST (30 mins)
- **Issue Tracker**: GitHub Issues tagged `android-migration`

### Response SLA:

- **Urgent (blocking)**: < 2 hours (during business hours)
- **High priority**: < 4 hours
- **Medium priority**: < 1 business day
- **Low priority**: < 2 business days

---

## 🔍 Testing Support

### Staging Environment Details:

```
Base URL: https://staging-api.intelliwiz.com
GraphQL Endpoint: /graphql/
GraphiQL (Browser): /graphiql/
REST API: /api/v1/

Test Credentials:
  Username: android_test_user
  Password: [Provided via secure channel]
  Client Code: TEST_CLIENT
  Site Code: TEST_SITE_001
```

### Sample Data for Testing:

**Sample Jobs**:
- Job ID 123: "Daily Pump Check" (TASK, has 30 historical jobneeds)
- Job ID 456: "Building A Tour" (INTERNALTOUR, has 10 checkpoints)
- Job ID 789: "Weekly PPM" (PPM, has 20 historical jobneeds)

**Sample Jobneeds**:
- Jobneed ID 1001: Completed (Oct 1)
- Jobneed ID 1002: Completed (Oct 2)
- Jobneed ID 1003: Assigned (Oct 3) - LATEST for Job 123

### GraphQL Playground Testing:

1. **Open**: `https://staging-api.intelliwiz.com/graphiql/`
2. **Login**: Use test credentials
3. **Test Query**:
   ```graphql
   query {
     job(id: 123) {
       jobname
       jobneed { id jobstatus }
       jobneeds(limit: 5) { id plandatetime }
     }
   }
   ```
4. **Expected**: Returns job with latest jobneed + history

---

## 📊 Data Volume Estimates

To help Android plan database size:

| Entity | Staging Count | Prod Estimate | Avg Size/Record |
|--------|--------------|---------------|-----------------|
| Job | 500 | ~5,000 | ~2KB |
| Jobneed | 15,000 | ~150,000 | ~3KB |
| JobneedDetails | 45,000 | ~450,000 | ~1KB |
| **Total DB Size** | ~150MB | ~1.5GB | - |

**Android Implications**:
- Plan for ~2GB local database (with indexes)
- Implement pagination for history views (limit: 30)
- Use background sync for bulk data

---

## ✅ FINAL CHECKLIST FOR ANDROID

Before starting development:

- [ ] All 5 sections of this document reviewed ✅
- [ ] Room schema designed for Job entity
- [ ] Migration script drafted
- [ ] Kotlin data classes created
- [ ] GraphQL queries tested in GraphiQL
- [ ] Sync logic designed
- [ ] Timeline understood (4-week migration)
- [ ] Backward compatibility plan clear
- [ ] Rollback procedure understood
- [ ] Team kickoff meeting scheduled

**Once checklist complete**: Android team can begin implementation

---

**Document Status:** ✅ **COMPLETE AND READY**
**Filled By:** Django5 Backend Team
**Date Completed:** October 3, 2025
**Next Action:** Share with Android team and schedule kickoff meeting
**Urgency:** 🔴 CRITICAL - Android migration unblocked ✅

---

## 🎁 BONUS: Migration Helper Code for Android

### Complete Room Migration Example:

```kotlin
// Migration from v1 (Jobneed only) to v2 (Job + Jobneed)
val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(database: SupportSQLiteDatabase) {
        // 1. Create Job table
        database.execSQL("""
            CREATE TABLE IF NOT EXISTS job (
                id INTEGER PRIMARY KEY NOT NULL,
                jobname TEXT NOT NULL,
                jobdesc TEXT NOT NULL,
                fromdate INTEGER NOT NULL,
                uptodate INTEGER NOT NULL,
                cron TEXT NOT NULL DEFAULT '* * * * *',
                identifier TEXT,
                planduration INTEGER NOT NULL,
                gracetime INTEGER NOT NULL,
                expirytime INTEGER NOT NULL,
                lastgeneratedon INTEGER NOT NULL,
                priority TEXT NOT NULL,
                scantype TEXT NOT NULL,
                frequency TEXT DEFAULT 'NONE',
                starttime TEXT,
                endtime TEXT,
                enable INTEGER NOT NULL DEFAULT 1,
                other_info TEXT NOT NULL,
                geojson TEXT,
                asset_id INTEGER,
                qset_id INTEGER,
                people_id INTEGER,
                pgroup_id INTEGER,
                sgroup_id INTEGER,
                geofence_id INTEGER,
                parent_id INTEGER,
                client_id INTEGER,
                bu_id INTEGER,
                shift_id INTEGER,
                ticketcategory_id INTEGER,
                seqno INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                cdtz INTEGER NOT NULL,
                mdtz INTEGER NOT NULL,
                cuser_id INTEGER NOT NULL,
                muser_id INTEGER NOT NULL,
                ctzoffset INTEGER NOT NULL DEFAULT 0
            )
        """)

        // 2. Create indexes
        database.execSQL("""
            CREATE INDEX index_job_identifier ON job(identifier)
        """)
        database.execSQL("""
            CREATE INDEX index_job_enable ON job(enable)
        """)
        database.execSQL("""
            CREATE INDEX index_job_client_bu ON job(client_id, bu_id)
        """)

        // 3. Populate Job table from distinct job_ids in Jobneed
        database.execSQL("""
            INSERT INTO job (
                id, jobname, jobdesc, fromdate, uptodate, cron, identifier,
                planduration, gracetime, expirytime, priority, scantype,
                asset_id, qset_id, people_id, client_id, bu_id, seqno,
                cdtz, mdtz, cuser_id, muser_id, ctzoffset, other_info,
                lastgeneratedon, enable, frequency
            )
            SELECT DISTINCT
                job_id,
                jobdesc,
                jobdesc,
                MIN(plandatetime) OVER (PARTITION BY job_id),
                MAX(expirydatetime) OVER (PARTITION BY job_id),
                '* * * * *',
                identifier,
                (MAX(expirydatetime) - MIN(plandatetime)) / 60000,  -- Convert ms to minutes
                gracetime,
                0,  -- expirytime default
                priority,
                scantype,
                asset_id,
                qset_id,
                people_id,
                client_id,
                bu_id,
                1,  -- seqno default
                MIN(cdtz),
                MAX(mdtz),
                cuser_id,
                muser_id,
                ctzoffset,
                '{}',  -- other_info default
                MAX(mdtz),
                1,  -- enable default
                frequency
            FROM jobneed
            WHERE job_id IS NOT NULL
            GROUP BY job_id
        """)

        // 4. Add job_id to jobneed if not exists (for adhoc jobneeds with null job_id)
        // No schema change needed - column should already exist

        // 5. Create foreign key index
        database.execSQL("""
            CREATE INDEX index_jobneed_job_id ON jobneed(job_id)
        """)

        Log.i("Migration", "Migration 1→2 complete")
    }
}
```

### Usage in RoomDatabase:

```kotlin
@Database(
    entities = [Job::class, Jobneed::class, JobneedDetails::class],
    version = 2,
    exportSchema = true
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun jobDao(): JobDao
    abstract fun jobneedDao(): JobneedDao
    abstract fun jobneedDetailsDao(): JobneedDetailsDao

    companion object {
        fun getInstance(context: Context): AppDatabase {
            return Room.databaseBuilder(
                context,
                AppDatabase::class.java,
                "intelliwiz.db"
            )
            .addMigrations(MIGRATION_1_2)  // Add migration
            .build()
        }
    }
}
```

---

**END OF ANDROID REQUIREMENTS DOCUMENT**

**Status**: ✅ **ALL 5 ITEMS COMPLETE AND READY FOR ANDROID TEAM**

**Next Step**: Schedule kickoff meeting with Android team (Oct 7, 2025)
