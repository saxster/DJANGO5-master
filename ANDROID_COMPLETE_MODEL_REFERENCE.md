# Complete Model Reference for Android Team

**Purpose**: Comprehensive Django5 model definitions for Android Room entities
**Last Updated**: October 3, 2025

---

## 📦 **Model 1: Job (Template/Definition)**

See `ANDROID_REQUIREMENTS_FILLED.md` Section 1 for complete Job model.

**Quick Summary**:
- **Table**: `job`
- **Purpose**: Template for recurring work
- **Key Fields**: jobname, cron, frequency, fromdate, uptodate
- **Relationships**: 1-to-many with Jobneed

---

## 📦 **Model 2: Jobneed (Execution Instance)**

### Complete Django Model:

```python
# FILE: apps/activity/models/job_model.py

class Jobneed(BaseModel, TenantAwareModel):
    """
    Jobneed: Concrete execution instance of a Job.

    Represents ONE specific execution with actual start/end times and status.
    """

    # ===== ENUMERATIONS =====
    class Priority(models.TextChoices):
        HIGH = ("HIGH", "High")
        LOW = ("LOW", "Low")
        MEDIUM = ("MEDIUM", "Medium")

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
        ASSETAUDIT = ("ASSETAUDIT", "Asset Audit")
        ASSETMAINTENANCE = ("ASSETMAINTENANCE", "Asset Maintenance")
        POSTING_ORDER = ("POSTING_ORDER", "Posting Order")
        SITESURVEY = ("SITESURVEY", "Site Survey")

    class Scantype(models.TextChoices):
        NONE = ("NONE", "None")
        QR = ("QR", "QR")
        NFC = ("NFC", "NFC")
        SKIP = ("SKIP", "Skip")
        ENTERED = ("ENTERED", "Entered")

    class JobStatus(models.TextChoices):
        ASSIGNED = ("ASSIGNED", "Assigned")
        AUTOCLOSED = ("AUTOCLOSED", "Auto Closed")
        COMPLETED = ("COMPLETED", "Completed")
        INPROGRESS = ("INPROGRESS", "Inprogress")
        PARTIALLYCOMPLETED = ("PARTIALLYCOMPLETED", "Partially Completed")
        MAINTENANCE = ("MAINTENANCE", "Maintenance")
        STANDBY = ("STANDBY", "Standby")
        WORKING = ("WORKING", "Working")

    class JobType(models.TextChoices):
        SCHEDULE = ("SCHEDULE", "Schedule")  # Generated from Job template
        ADHOC = ("ADHOC", "Adhoc")           # Created manually (no Job template)

    class Frequency(models.TextChoices):
        NONE = ("NONE", "None")
        DAILY = ("DAILY", "Daily")
        WEEKLY = ("WEEKLY", "Weekly")
        MONTHLY = ("MONTHLY", "Monthly")
        BIMONTHLY = ("BIMONTHLY", "Bimonthly")
        QUARTERLY = ("QUARTERLY", "Quarterly")
        HALFYEARLY = ("HALFYEARLY", "Half Yearly")
        YEARLY = ("YEARLY", "Yearly")
        FORTNIGHTLY = ("FORTNIGHTLY", "Fort Nightly")

    # ===== PRIMARY KEY =====
    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)

    # ===== STRING FIELDS =====
    jobdesc = models.CharField(_("Job Description"), max_length=200)
    scantype = models.CharField(
        _("Scan type"),
        max_length=50,
        choices=Scantype.choices,
        default=Scantype.NONE.value,
    )
    identifier = models.CharField(
        _("Jobneed Type"),
        max_length=50,
        choices=Identifier.choices,
        null=True,
        db_index=True
    )
    jobstatus = models.CharField(
        "Job Status",
        choices=JobStatus.choices,
        max_length=60,
        null=True
    )
    jobtype = models.CharField(
        _("Job Type"),
        max_length=50,
        choices=JobType.choices,
        null=True
    )
    priority = models.CharField(_("Priority"), max_length=50, choices=Priority.choices)
    frequency = models.CharField(
        verbose_name=_("Frequency type"),
        null=True,
        max_length=55,
        choices=Frequency.choices,
        default=Frequency.NONE.value,
    )
    othersite = models.CharField(
        _("Other Site"),
        max_length=100,
        default=None,
        null=True
    )

    # ===== TEXT FIELDS =====
    remarks = models.TextField(_("Remark"), null=True, blank=True)

    # ===== INTEGER FIELDS =====
    gracetime = models.IntegerField(_("Grace time"))
    seqno = models.SmallIntegerField(_("Sl No."))
    attachmentcount = models.IntegerField(_("Attachment Count"), default=0)

    # ===== DECIMAL FIELDS =====
    multifactor = models.DecimalField(
        _("Multiplication Factor"),
        default=1,
        max_digits=10,
        decimal_places=6
    )

    # ===== DATETIME FIELDS =====
    plandatetime = models.DateTimeField(
        _("Plan date time"),
        auto_now=False,
        auto_now_add=False,
        null=True
    )
    expirydatetime = models.DateTimeField(
        _("Expiry date time"),
        auto_now=False,
        auto_now_add=False,
        null=True
    )
    receivedonserver = models.DateTimeField(
        _("Received on server"),
        auto_now=False,
        auto_now_add=True
    )
    starttime = models.DateTimeField(
        _("Start time"),
        auto_now=False,
        auto_now_add=False,
        null=True
    )
    endtime = models.DateTimeField(
        _("End time"),  # Note: Label says "Start time" but field is endtime
        auto_now=False,
        auto_now_add=False,
        null=True
    )

    # ===== GEOSPATIAL FIELDS =====
    gpslocation = PointField(
        _("GPS Location"),
        null=True,
        blank=True,
        geography=True,
        srid=4326
    )
    journeypath = LineStringField(geography=True, null=True, blank=True)

    # ===== BOOLEAN FIELDS =====
    alerts = models.BooleanField(_("Alerts"), default=False, null=True)
    raisedtktflag = models.BooleanField(_("RaiseTicketFlag"), default=False, null=True)
    ismailsent = models.BooleanField(_("Mail Sent"), default=False)
    deviation = models.BooleanField(_("Deviation"), default=False, null=True)

    # ===== JSON FIELDS =====
    other_info = models.JSONField(
        _("Other info"),
        default=dict,
        blank=True
    )
    geojson = models.JSONField(
        default=dict,
        blank=True,
        null=True
    )

    # ===== FOREIGN KEYS =====
    job = models.ForeignKey(
        "activity.Job",
        verbose_name=_("Job"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobs",  # Job.jobs.all() returns all Jobneeds
    )
    asset = models.ForeignKey(
        "activity.Asset",
        verbose_name=_("Asset"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobneed_assets",
    )
    qset = models.ForeignKey(
        "activity.QuestionSet",
        verbose_name=_("QuestionSet"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    performedby = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Performed by"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobneed_performedby",
    )
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("People"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    pgroup = models.ForeignKey(
        "peoples.Pgroup",
        verbose_name=_("People Group"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobneed_pgroup",
    )
    sgroup = models.ForeignKey(
        "peoples.Pgroup",
        verbose_name=_("Site Group"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobneed_sgroup",
    )
    parent = models.ForeignKey(
        "self",  # Self-referencing for checkpoint hierarchy
        verbose_name=_("Belongs to"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobneed_clients",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobneedf_bus",  # Note: Typo in original - "jobneedf_bus"
    )
    ticketcategory = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Notify Category"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    ticket = models.ForeignKey(
        "y_helpdesk.Ticket",
        verbose_name=_("Ticket"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobneed_ticket",
    )
    remarkstype = models.ForeignKey(
        "onboarding.TypeAssist",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="remark_types",
    )

    # ===== OPTIMISTIC LOCKING =====
    version = VersionField()

    # ===== INHERITED FROM BaseModel =====
    # - cdtz, mdtz, cuser_id, muser_id, ctzoffset (same as Job)

    class Meta:
        db_table = "jobneed"
        verbose_name = "Jobneed"
        verbose_name_plural = "Jobneeds"
        ordering = ['-plandatetime']  # Latest first

    def __str__(self):
        return f"{self.jobdesc} ({self.plandatetime})"
```

### Complete Field Mapping for Android:

| Django Field | Type | Nullable? | Default | Kotlin Type | Notes |
|--------------|------|-----------|---------|-------------|-------|
| **PRIMARY KEY** |
| `id` | BigAutoField | No | Auto | `Long` | Primary key |
| `uuid` | UUIDField | No | Auto | `String` | Unique identifier |
| **STRING FIELDS** |
| `jobdesc` | CharField(200) | No | - | `String` | Execution description |
| `scantype` | CharField(50) | Yes | "NONE" | `String?` | QR, NFC, SKIP, ENTERED, NONE |
| `identifier` | CharField(50) | Yes | null | `String?` | TASK, INTERNALTOUR, etc. |
| `jobstatus` | CharField(60) | Yes | null | `String?` | ASSIGNED, COMPLETED, etc. |
| `jobtype` | CharField(50) | Yes | null | `String?` | SCHEDULE or ADHOC |
| `priority` | CharField(50) | No | - | `String` | HIGH, MEDIUM, LOW |
| `frequency` | CharField(55) | Yes | "NONE" | `String?` | DAILY, WEEKLY, etc. |
| `othersite` | CharField(100) | Yes | null | `String?` | Alternative site name |
| **TEXT FIELDS** |
| `remarks` | TextField | Yes | null | `String?` | User remarks/comments |
| **INTEGER FIELDS** |
| `gracetime` | IntegerField | No | - | `Int` | Grace time (minutes) |
| `seqno` | SmallIntegerField | No | - | `Int` | Sequence number |
| `attachmentcount` | IntegerField | No | 0 | `Int` | Number of attachments |
| **DECIMAL FIELDS** |
| `multifactor` | DecimalField(10,6) | No | 1.0 | `Double` | Multiplication factor |
| **DATETIME FIELDS** |
| `plandatetime` | DateTimeField | Yes | null | `Long?` | **Planned execution time** ⭐ |
| `expirydatetime` | DateTimeField | Yes | null | `Long?` | Expiry time |
| `receivedonserver` | DateTimeField | No | Auto | `Long` | When server received |
| `starttime` | DateTimeField | Yes | null | `Long?` | **Actual start** (user action) |
| `endtime` | DateTimeField | Yes | null | `Long?` | **Actual end** (user action) |
| `cdtz` | DateTimeField | No | Auto | `Long` | Created datetime |
| `mdtz` | DateTimeField | No | Auto | `Long` | Modified datetime |
| **GEOSPATIAL FIELDS** |
| `gpslocation` | PointField | Yes | null | `String?` | GPS point (GeoJSON or "POINT(lon lat)") |
| `journeypath` | LineStringField | Yes | null | `String?` | Journey path (GeoJSON LineString) |
| **BOOLEAN FIELDS** |
| `alerts` | BooleanField | Yes | False | `Boolean` | Has alerts |
| `raisedtktflag` | BooleanField | Yes | False | `Boolean` | Ticket raised |
| `ismailsent` | BooleanField | No | False | `Boolean` | Email sent |
| `deviation` | BooleanField | Yes | False | `Boolean` | Has deviation |
| **JSON FIELDS** |
| `other_info` | JSONField | No | {} | `String` | Additional data (parse to Map) |
| `geojson` | JSONField | Yes | {} | `String?` | GeoJSON data |
| **FOREIGN KEYS** |
| `job_id` | BigInt (FK) | Yes | null | `Long?` | **FK to Job template** ⭐ |
| `asset_id` | BigInt (FK) | Yes | null | `Long?` | FK to Asset |
| `qset_id` | BigInt (FK) | Yes | null | `Long?` | FK to QuestionSet |
| `performedby_id` | BigInt (FK) | Yes | null | `Long?` | Who actually performed |
| `people_id` | BigInt (FK) | Yes | null | `Long?` | Assigned to (planned) |
| `pgroup_id` | BigInt (FK) | Yes | null | `Long?` | People group |
| `sgroup_id` | BigInt (FK) | Yes | null | `Long?` | Site group |
| `parent_id` | BigInt (FK) | Yes | null | `Long?` | Parent jobneed (checkpoints) |
| `client_id` | BigInt (FK) | Yes | null | `Long?` | Client |
| `bu_id` | BigInt (FK) | Yes | null | `Long?` | Business unit/site |
| `ticketcategory_id` | BigInt (FK) | Yes | null | `Long?` | Ticket category |
| `ticket_id` | BigInt (FK) | Yes | null | `Long?` | Associated ticket |
| `remarkstype_id` | BigInt (FK) | Yes | null | `Long?` | Remark type |
| `cuser_id` | BigInt (FK) | No | - | `Long` | Created by |
| `muser_id` | BigInt (FK) | No | - | `Long` | Modified by |
| **VERSION CONTROL** |
| `version` | IntegerField | No | 0 | `Int` | Optimistic locking |
| **TIMEZONE** |
| `ctzoffset` | IntegerField | No | 0 | `Int` | Timezone offset (minutes) |

### Android Room Entity for Jobneed:

```kotlin
@Entity(
    tableName = "jobneed",
    indices = [
        Index(value = ["uuid"], unique = true),
        Index(value = ["job_id"]),  // For latest_for_job queries
        Index(value = ["identifier"]),
        Index(value = ["jobstatus"]),
        Index(value = ["plandatetime"]),  // For ordering
        Index(value = ["client_id", "bu_id"])
    ],
    foreignKeys = [
        ForeignKey(
            entity = Job::class,
            parentColumns = ["id"],
            childColumns = ["job_id"],
            onDelete = ForeignKey.RESTRICT
        )
    ]
)
data class Jobneed(
    @PrimaryKey
    @ColumnInfo(name = "id")
    val id: Long,

    @ColumnInfo(name = "uuid")
    val uuid: String,

    // String fields
    @ColumnInfo(name = "jobdesc")
    val jobdesc: String,

    @ColumnInfo(name = "scantype")
    val scantype: String? = "NONE",

    @ColumnInfo(name = "identifier")
    val identifier: String?,

    @ColumnInfo(name = "jobstatus")
    val jobstatus: String?,

    @ColumnInfo(name = "jobtype")
    val jobtype: String?,

    @ColumnInfo(name = "priority")
    val priority: String,

    @ColumnInfo(name = "frequency")
    val frequency: String? = "NONE",

    @ColumnInfo(name = "othersite")
    val othersite: String?,

    @ColumnInfo(name = "remarks")
    val remarks: String?,

    // Integer fields
    @ColumnInfo(name = "gracetime")
    val gracetime: Int,

    @ColumnInfo(name = "seqno")
    val seqno: Int,

    @ColumnInfo(name = "attachmentcount")
    val attachmentcount: Int = 0,

    // Decimal
    @ColumnInfo(name = "multifactor")
    val multifactor: Double = 1.0,

    // Datetime fields (epoch millis)
    @ColumnInfo(name = "plandatetime")
    val plandatetime: Long?,  // ⭐ KEY FIELD for "latest" determination

    @ColumnInfo(name = "expirydatetime")
    val expirydatetime: Long?,

    @ColumnInfo(name = "receivedonserver")
    val receivedonserver: Long,

    @ColumnInfo(name = "starttime")
    val starttime: Long?,

    @ColumnInfo(name = "endtime")
    val endtime: Long?,

    @ColumnInfo(name = "cdtz")
    val cdtz: Long,

    @ColumnInfo(name = "mdtz")
    val mdtz: Long,

    // Geospatial (stored as GeoJSON string)
    @ColumnInfo(name = "gpslocation")
    val gpslocation: String?,  // "POINT(77.5946 12.9716)" or GeoJSON

    @ColumnInfo(name = "journeypath")
    val journeypath: String?,  // GeoJSON LineString

    // Boolean
    @ColumnInfo(name = "alerts")
    val alerts: Boolean = false,

    @ColumnInfo(name = "raisedtktflag")
    val raisedtktflag: Boolean = false,

    @ColumnInfo(name = "ismailsent")
    val ismailsent: Boolean = false,

    @ColumnInfo(name = "deviation")
    val deviation: Boolean = false,

    // JSON (stored as string)
    @ColumnInfo(name = "other_info")
    val otherInfo: String,

    @ColumnInfo(name = "geojson")
    val geojson: String?,

    // Foreign keys
    @ColumnInfo(name = "job_id")
    val jobId: Long?,  // ⭐ NEW: FK to Job template

    @ColumnInfo(name = "asset_id")
    val assetId: Long?,

    @ColumnInfo(name = "qset_id")
    val qsetId: Long?,

    @ColumnInfo(name = "performedby_id")
    val performedbyId: Long?,

    @ColumnInfo(name = "people_id")
    val peopleId: Long?,

    @ColumnInfo(name = "pgroup_id")
    val pgroupId: Long?,

    @ColumnInfo(name = "sgroup_id")
    val sgroupId: Long?,

    @ColumnInfo(name = "parent_id")
    val parentId: Long?,

    @ColumnInfo(name = "client_id")
    val clientId: Long?,

    @ColumnInfo(name = "bu_id")
    val buId: Long?,

    @ColumnInfo(name = "ticketcategory_id")
    val ticketcategoryId: Long?,

    @ColumnInfo(name = "ticket_id")
    val ticketId: Long?,

    @ColumnInfo(name = "remarkstype_id")
    val remarkstypeId: Long?,

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
    @Ignore
    val job: Job? = null,  // Parent Job template

    @Ignore
    val details: List<JobneedDetails>? = null  // Checklist items
)
```

---

## 📦 **Model 3: JobneedDetails (Checklist Items)**

### Complete Django Model:

```python
class JobneedDetails(BaseModel, TenantAwareModel):
    """
    JobneedDetails: Individual checklist item for a Jobneed execution.

    Each Jobneed has multiple JobneedDetails (one per question).
    """

    # ===== ENUMERATIONS =====
    class AnswerType(models.TextChoices):
        CHECKBOX = ("CHECKBOX", "Checkbox")
        DATE = ("DATE", "Date")
        DROPDOWN = ("DROPDOWN", "Dropdown")
        EMAILID = ("EMAILID", "Email Id")
        MULTILINE = ("MULTILINE", "Multiline")
        NUMERIC = ("NUMERIC", "Numeric")
        SIGNATURE = ("SIGNATURE", "Signature")
        SINGLELINE = ("SINGLELINE", "Single Line")
        TIME = ("TIME", "Time")
        RATING = ("RATING", "Rating")
        BACKCAMERA = ("BACKCAMERA", "Back Camera")
        FRONTCAMERA = ("FRONTCAMERA", "Front Camera")
        PEOPLELIST = ("PEOPLELIST", "People List")
        SITELIST = ("SITELIST", "Site List")
        NONE = ("NONE", "NONE")
        METERREADING = "METERREADING", _("Meter Reading")
        MULTISELECT = "MULTISELECT", _("Multi Select")

    class AvptType(models.TextChoices):
        BACKCAMPIC = "BACKCAMPIC", _("Back Camera Pic")
        FRONTCAMPIC = "FRONTCAMPIC", _("Front Camera Pic")
        AUDIO = "AUDIO", _("Audio")
        VIDEO = "VIDEO", _("Video")
        NONE = ("NONE", "NONE")

    # ===== PRIMARY KEY =====
    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)

    # ===== INTEGER FIELDS =====
    seqno = models.SmallIntegerField(_("SL No."))
    attachmentcount = models.IntegerField(_("Attachment count"), default=0)

    # ===== STRING FIELDS =====
    answertype = models.CharField(
        _("Answer Type"),
        max_length=50,
        choices=AnswerType.choices,
        null=True
    )
    answer = models.CharField(_("Answer"), max_length=250, default="", null=True)
    avpttype = models.CharField(
        _("Attachment Type"),
        max_length=50,
        choices=AvptType.choices,
        null=True,
        blank=True,
    )
    options = models.CharField(_("Option"), max_length=2000, null=True, blank=True)
    alerton = models.CharField(_("Alert On"), null=True, blank=True, max_length=300)

    # ===== TEXT FIELDS =====
    transcript = models.TextField(_("Audio Transcript"), null=True, blank=True)
    transcript_status = models.CharField(
        _("Transcript Status"),
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
        ],
        null=True,
        blank=True
    )
    transcript_language = models.CharField(
        _("Transcript Language"),
        max_length=10,
        default='en-US',
        null=True,
        blank=True,
    )

    # ===== DECIMAL FIELDS =====
    min = models.DecimalField(_("Min"), max_digits=18, decimal_places=4, null=True)
    max = models.DecimalField(_("Max"), max_digits=18, decimal_places=4, null=True)

    # ===== DATETIME FIELDS =====
    transcript_processed_at = models.DateTimeField(
        _("Transcript Processed At"),
        null=True,
        blank=True,
    )

    # ===== BOOLEAN FIELDS =====
    isavpt = models.BooleanField(_("Attachment Required"), default=False)
    ismandatory = models.BooleanField(_("Mandatory"), default=True)
    alerts = models.BooleanField(_("Alerts"), default=False)

    # ===== FOREIGN KEYS =====
    jobneed = models.ForeignKey(
        "activity.Jobneed",
        verbose_name=_("Jobneed"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    question = models.ForeignKey(
        "activity.Question",
        verbose_name=_("Question"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    qset = models.ForeignKey(
        QuestionSet,
        verbose_name=("Question Set"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="questions_qset",
    )

    # ===== UNIQUE CONSTRAINTS (NEW - October 2025) =====
    class Meta:
        db_table = "jobneeddetails"
        verbose_name = "JobneedDetails"
        ordering = ['seqno']  # Display order
        constraints = [
            models.UniqueConstraint(
                fields=['jobneed', 'question'],
                name='jobneeddetails_jobneed_question_uk',
            ),
            models.UniqueConstraint(
                fields=['jobneed', 'seqno'],
                name='jobneeddetails_jobneed_seqno_uk',
            ),
        ]
```

### Android Room Entity for JobneedDetails:

```kotlin
@Entity(
    tableName = "jobneeddetails",
    indices = [
        Index(value = ["uuid"], unique = true),
        Index(value = ["jobneed_id"]),
        Index(value = ["question_id"]),
        Index(value = ["seqno"])
    ],
    foreignKeys = [
        ForeignKey(
            entity = Jobneed::class,
            parentColumns = ["id"],
            childColumns = ["jobneed_id"],
            onDelete = ForeignKey.RESTRICT
        ),
        ForeignKey(
            entity = Question::class,
            parentColumns = ["id"],
            childColumns = ["question_id"],
            onDelete = ForeignKey.RESTRICT
        )
    ]
)
data class JobneedDetails(
    @PrimaryKey
    @ColumnInfo(name = "id")
    val id: Long,

    @ColumnInfo(name = "uuid")
    val uuid: String,

    @ColumnInfo(name = "seqno")
    val seqno: Int,  // ⭐ Display order in checklist

    // Answer fields
    @ColumnInfo(name = "answertype")
    val answertype: String?,

    @ColumnInfo(name = "answer")
    val answer: String?,

    @ColumnInfo(name = "min")
    val min: Double?,

    @ColumnInfo(name = "max")
    val max: Double?,

    @ColumnInfo(name = "options")
    val options: String?,  // Comma-separated or JSON

    @ColumnInfo(name = "alerton")
    val alerton: String?,

    // Attachment fields
    @ColumnInfo(name = "isavpt")
    val isavpt: Boolean = false,

    @ColumnInfo(name = "avpttype")
    val avpttype: String?,

    @ColumnInfo(name = "attachmentcount")
    val attachmentcount: Int = 0,

    // Transcript fields
    @ColumnInfo(name = "transcript")
    val transcript: String?,

    @ColumnInfo(name = "transcript_status")
    val transcriptStatus: String?,

    @ColumnInfo(name = "transcript_language")
    val transcriptLanguage: String? = "en-US",

    @ColumnInfo(name = "transcript_processed_at")
    val transcriptProcessedAt: Long?,

    // Validation
    @ColumnInfo(name = "ismandatory")
    val ismandatory: Boolean = true,

    @ColumnInfo(name = "alerts")
    val alerts: Boolean = false,

    // Foreign keys
    @ColumnInfo(name = "jobneed_id")
    val jobneedId: Long?,  // ⭐ Parent jobneed

    @ColumnInfo(name = "question_id")
    val questionId: Long?,

    @ColumnInfo(name = "qset_id")
    val qsetId: Long?,

    @ColumnInfo(name = "cuser_id")
    val cuserId: Long,

    @ColumnInfo(name = "muser_id")
    val muserId: Long,

    // Metadata
    @ColumnInfo(name = "cdtz")
    val cdtz: Long,

    @ColumnInfo(name = "mdtz")
    val mdtz: Long,

    @ColumnInfo(name = "ctzoffset")
    val ctzoffset: Int = 0,

    // Transient
    @Ignore
    val question: Question? = null  // Question details from FK
)
```

---

## 🔄 **Relationship Diagram for Android**

```
┌─────────────────────────┐
│         Job             │ (Template - NEW for Android)
│─────────────────────────│
│ PK: id                  │
│     jobname             │
│     cron                │
│     frequency           │
│     fromdate → uptodate │
└─────────────────────────┘
           │
           │ 1-to-many (job_id FK)
           ↓
┌─────────────────────────┐
│       Jobneed           │ (Execution Instance - MODIFIED)
│─────────────────────────│
│ PK: id                  │
│ FK: job_id ← NEW        │ ⭐ Points to Job template
│     uuid                │
│     jobdesc             │
│     plandatetime ← KEY  │ ⭐ Determines "latest"
│     expirydatetime      │
│     jobstatus           │
│     jobtype             │
│     starttime           │
│     endtime             │
└─────────────────────────┘
           │
           │ 1-to-many (jobneed_id FK)
           ↓
┌─────────────────────────┐
│   JobneedDetails        │ (Checklist Item - UNCHANGED)
│─────────────────────────│
│ PK: id                  │
│ FK: jobneed_id          │
│ FK: question_id         │
│     seqno ← ORDER       │ ⭐ Display order
│     answertype          │
│     answer              │
│     min, max            │
│     ismandatory         │
└─────────────────────────┘

UNIQUE (jobneed_id, question_id)  ← NEW CONSTRAINT
UNIQUE (jobneed_id, seqno)        ← NEW CONSTRAINT
```

---

## 🎯 **Android DAO Methods to Implement**

### JobDao:

```kotlin
@Dao
interface JobDao {
    @Query("SELECT * FROM job WHERE id = :jobId")
    suspend fun getById(jobId: Long): Job?

    @Query("SELECT * FROM job WHERE client_id = :clientId AND bu_id = :buId AND enable = 1")
    fun getAllActive(clientId: Long, buId: Long): Flow<List<Job>>

    @Query("SELECT * FROM job WHERE mdtz > :afterTimestamp")
    suspend fun getModifiedAfter(afterTimestamp: Long): List<Job>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOrUpdate(job: Job)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOrUpdateAll(jobs: List<Job>)

    @Query("DELETE FROM job WHERE id = :jobId")
    suspend fun delete(jobId: Long)
}
```

### JobneedDao (UPDATED):

```kotlin
@Dao
interface JobneedDao {
    // NEW: Get latest jobneed for a job
    @Query("""
        SELECT * FROM jobneed
        WHERE job_id = :jobId
        ORDER BY plandatetime DESC, id DESC
        LIMIT 1
    """)
    suspend fun getLatestForJob(jobId: Long): Jobneed?

    // NEW: Get execution history for a job
    @Query("""
        SELECT * FROM jobneed
        WHERE job_id = :jobId
        ORDER BY plandatetime DESC
        LIMIT :limit
    """)
    suspend fun getHistoryForJob(jobId: Long, limit: Int = 10): List<Jobneed>

    // Existing methods (unchanged)
    @Query("SELECT * FROM jobneed WHERE id = :jobneedId")
    suspend fun getById(jobneedId: Long): Jobneed?

    @Query("SELECT * FROM jobneed WHERE uuid = :uuid")
    suspend fun getByUuid(uuid: String): Jobneed?

    @Query("SELECT * FROM jobneed WHERE jobstatus = :status AND plandatetime_date = :date")
    fun getByStatusAndDate(status: String, date: Long): Flow<List<Jobneed>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOrUpdate(jobneed: Jobneed)

    @Update
    suspend fun update(jobneed: Jobneed)
}
```

### JobneedDetailsDao (unchanged):

```kotlin
@Dao
interface JobneedDetailsDao {
    @Query("SELECT * FROM jobneeddetails WHERE jobneed_id = :jobneedId ORDER BY seqno ASC")
    suspend fun getForJobneed(jobneedId: Long): List<JobneedDetails>

    @Query("SELECT * FROM jobneeddetails WHERE id = :id")
    suspend fun getById(id: Long): JobneedDetails?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOrUpdate(detail: JobneedDetails)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertOrUpdateAll(details: List<JobneedDetails>)

    // NEW: Check for duplicate before insert (constraint prevention)
    @Query("SELECT COUNT(*) FROM jobneeddetails WHERE jobneed_id = :jobneedId AND question_id = :questionId")
    suspend fun countDuplicates(jobneedId: Long, questionId: Long): Int
}
```

---

**Document Complete**: ✅
**Total Pages**: 3 comprehensive model definitions
**Ready for Android Implementation**: ✅

**See Also**:
- `ANDROID_REQUIREMENTS_FILLED.md` - Main requirements (5 items)
- `docs/mobile-api/JOB_JOBNEED_API_CONTRACT.md` - API migration guide
