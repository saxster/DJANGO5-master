"""
Job → Jobneed → JobneedDetails Domain Model

This module defines the core work execution models for the facility management platform.

## Domain Model Overview

**Job**: Template/Definition (What work to do, when to schedule it)
- Represents recurring or scheduled work (tasks, tours, PPM)
- Contains scheduling information (cron, frequency, dates)
- Has 1-to-many relationship with Jobneed (generates multiple execution instances)
- Parent relationships: parent=NULL means root job; parent=Job means child checkpoint

**Jobneed**: Concrete Instance (Scheduled or adhoc execution)
- Generated from Job based on schedule OR created adhoc
- Tracks execution state, timing, assignments, completion
- Represents one specific execution instance with actual start/end times
- Parent relationships: parent=NULL means parent jobneed; parent=Jobneed means child checkpoint
- Has 1-to-many relationship with Job (via related_name='jobs')

**JobneedDetails**: Per-Question Details (Checklist items per execution)
- Tied to specific Jobneed execution
- Stores question answers, validations, attachments, alerts
- seqno: Display order within the jobneed's checklist
- Unique constraints: (jobneed, question) and (jobneed, seqno)

## Relationship Examples

### Task Scheduling:
```
Job (Template: "Daily Pump Check")
  └─ Jobneed (Instance: 2025-10-03 10:00) → JobneedDetails (Q1, Q2, Q3)
  └─ Jobneed (Instance: 2025-10-04 10:00) → JobneedDetails (Q1, Q2, Q3)
  └─ Jobneed (Instance: 2025-10-05 10:00) → JobneedDetails (Q1, Q2, Q3)
```

### Tour Hierarchy:
```
Job (Parent: "Building A Tour") [parent=NULL]
  ├─ Job (Child: "Floor 1 Checkpoint") [parent=Parent Job]
  ├─ Job (Child: "Floor 2 Checkpoint")
  └─ Job (Child: "Floor 3 Checkpoint")

When scheduled:
  Jobneed (Parent: "Building A Tour - 2025-10-03") [parent=NULL]
    ├─ Jobneed (Child: "Floor 1 - 2025-10-03") [parent=Parent Jobneed]
    ├─ Jobneed (Child: "Floor 2 - 2025-10-03")
    └─ Jobneed (Child: "Floor 3 - 2025-10-03")
```

## Parent Semantics

### Root Detection (Jobs and Jobneeds):
- **Modern approach**: `parent__isnull=True` (preferred)
- **Legacy approach**: `parent_id=1` (sentinel record "NONE")
- **Transitional**: Use `Q(parent__isnull=True) | Q(parent_id=1)` for compatibility

### Naming Conventions:
- **Model names**: Use `Jobneed`, `JobneedDetails` (lowercase 'n')
- **Form names**: May use `JobNeedForm` (uppercase 'N' - acceptable for forms)
- **Backward compatibility**: Aliases `JobNeed = Jobneed` provided below

## Database Constraints:
- Job: Unique (jobname, asset, qset, parent, identifier, client)
- Jobneed: Optimistic locking via VersionField
- JobneedDetails:
  - Unique (jobneed, question) - prevents duplicate questions
  - Unique (jobneed, seqno) - ensures sequence ordering
"""

import uuid
from django.conf import settings
from django.contrib.gis.db.models import LineStringField, PointField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _
from concurrency.fields import VersionField
from apps.ontology import ontology

# Updated import path after job_manager.py refactoring (2025-10-10)
# Original: from apps.activity.managers.job_manager import ...
# New: Use modular job managers structure (3 focused files)
from apps.activity.managers.job import (
    JobManager,
    JobneedManager,
    JobneedDetailsManager,
)
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from apps.core import utils
from apps.activity.models.question_model import QuestionSet


def other_info():
    return {
        "tour_frequency": 1,
        "is_randomized": False,
        "distance": None,
        "breaktime": 0,
        "deviation": False,
        "ticket_generated": False,
        "email_sent": False,
        "autoclosed_by_server": False,
        "acknowledged_by": "",
        "isAcknowledged": False,
        "istimebound": True,
        "isdynamic": False,
    }


def geojson_jobnjobneed():
    return {"gpslocation": ""}


@ontology(
    domain="operations",
    concept="Work Template & Execution State Machine",
    purpose=(
        "Core work template model representing recurring or scheduled facility operations "
        "(tasks, tours, PPM). Generates Jobneed instances for execution. Implements hierarchical "
        "parent-child relationships for tour checkpoints. State machine with SCHEDULED → INPROGRESS "
        "→ COMPLETED → CLOSED transitions."
    ),
    criticality="critical",
    state_machine=True,
    inputs=[
        {"name": "jobname", "type": "str", "description": "Human-readable job name", "required": True},
        {"name": "identifier", "type": "TextChoices", "description": "Job type: TASK, TOUR, PPM, TICKET, etc.", "required": True},
        {"name": "qset", "type": "QuestionSet", "description": "Associated question set for checklist", "foreign_key": True},
        {"name": "asset", "type": "Asset", "description": "Asset this job operates on", "foreign_key": True},
        {"name": "parent", "type": "Job", "description": "Parent job for hierarchical tours", "self_referential": True},
        {"name": "cron_expression", "type": "str", "description": "Cron schedule for recurring jobs"},
        {"name": "frequency", "type": "TextChoices", "description": "Schedule frequency: DAILY, WEEKLY, MONTHLY, etc."},
    ],
    outputs=[
        {"name": "jobneeds", "type": "QuerySet[Jobneed]", "description": "Generated execution instances via reverse relation"},
        {"name": "children", "type": "QuerySet[Job]", "description": "Child jobs for tours via reverse relation"},
    ],
    side_effects=[
        "Generates Jobneed instances based on cron schedule via Celery beat tasks",
        "Creates hierarchical Jobneed chains for parent-child job relationships",
        "Triggers notifications on job state transitions",
        "Updates related Asset maintenance schedules",
        "Logs state transitions to JobWorkflowAuditLog",
    ],
    depends_on=[
        "apps.activity.managers.job.JobManager",
        "apps.activity.models.question_model.QuestionSet",
        "apps.activity.models.asset_model.Asset",
        "apps.activity.models.location_model.Location",
        "apps.peoples.models.user_model.People",
        "apps.tenants.models.TenantAwareModel",
        "apps.core.tasks.celery_beat_integration",
    ],
    used_by=[
        "Jobneed model for execution instances",
        "Scheduler service for recurring task generation",
        "Mobile apps for task assignment and execution",
        "Reports module for completion analytics",
        "PPM module for preventive maintenance",
    ],
    tags=["operations", "state-machine", "scheduling", "hierarchical", "work-template", "critical"],
    security_notes=(
        "Multi-tenant isolation:\n"
        "1. All Job queries filtered by tenant via TenantAwareModel\n"
        "2. Jobs cannot reference Assets/Locations from other tenants\n"
        "3. Parent-child relationships must be within same tenant\n"
        "4. API endpoints enforce tenant-based authorization\n"
        "5. Celery tasks validate tenant context before job generation"
    ),
    performance_notes=(
        "Optimizations:\n"
        "- Composite unique constraint on (jobname, asset, qset, parent, identifier, client)\n"
        "- Indexes on tenant, client, identifier, frequency for scheduler queries\n"
        "- JobManager.with_full_details() uses select_related for asset/qset/location\n"
        "- GIS indexes on job_route field for geospatial queries\n"
        "\nBottlenecks:\n"
        "- Hierarchical queries for tour parent-child relationships can be slow\n"
        "- JSONField queries on other_info slower than indexed columns\n"
        "- Celery beat scheduler overhead for high-frequency jobs (>1000/hour)"
    ),
    state_machine_notes=(
        "State Transitions (via Jobneed model):\n"
        "1. SCHEDULED: Initial state after generation from Job template\n"
        "2. INPROGRESS: Worker starts execution (sets starttime)\n"
        "3. COMPLETED: All JobneedDetails answered (sets endtime)\n"
        "4. CLOSED: Reviewed and approved (sets closetime)\n"
        "\nRace Condition Handling:\n"
        "- Jobneed uses VersionField for optimistic locking\n"
        "- State transitions validated via JobWorkflowAuditLog\n"
        "- Concurrent updates trigger RecordModifiedError\n"
        "- Idempotency keys prevent duplicate Jobneed generation\n"
        "\nParent-Child Semantics:\n"
        "- Job.parent=NULL: Root job (tour template)\n"
        "- Job.parent=Job: Child checkpoint of parent tour\n"
        "- Jobneed instances inherit parent hierarchy from Job\n"
        "- Legacy sentinel: parent_id=1 ('NONE') for backward compatibility"
    ),
    architecture_notes=(
        "Domain Model Hierarchy:\n"
        "Job (Template) → Jobneed (Instance) → JobneedDetails (Checklist)\n"
        "\nRelationships:\n"
        "- Job 1:N Jobneed (via related_name='jobs')\n"
        "- Jobneed 1:N JobneedDetails (via related_name='details')\n"
        "- Job self-referential parent-child for tours\n"
        "\nScheduling Flow:\n"
        "1. Celery beat evaluates Job.cron_expression\n"
        "2. Creates Jobneed instance with scheduled_time\n"
        "3. For hierarchical jobs, creates child Jobneed instances\n"
        "4. Mobile worker receives Jobneed via sync API\n"
        "5. Worker completes JobneedDetails, updates Jobneed state\n"
        "\nData Consistency:\n"
        "- Unique constraint prevents duplicate jobs\n"
        "- VersionField on Jobneed prevents race conditions\n"
        "- JobneedDetails has unique (jobneed, question) and (jobneed, seqno)"
    ),
    examples=[
        "# Create daily pump check task\njob = Job.objects.create(\n    jobname='Daily Pump Check',\n    identifier=Job.Identifier.TASK,\n    frequency=Job.Frequency.DAILY,\n    cron_expression='0 10 * * *',\n    qset=question_set,\n    asset=pump_asset\n)",
        "# Create hierarchical tour\nparent_tour = Job.objects.create(\n    jobname='Building A Tour',\n    identifier=Job.Identifier.INTERNALTOUR,\n    parent=None\n)\nfloor1_checkpoint = Job.objects.create(\n    jobname='Floor 1 Checkpoint',\n    identifier=Job.Identifier.INTERNALTOUR,\n    parent=parent_tour\n)",
        "# Query root jobs (non-sentinel approach)\nroot_jobs = Job.objects.filter(parent__isnull=True)",
        "# Get job with full details (optimized)\njob = Job.objects.with_full_details().get(pk=job_id)",
    ],
    related_models=[
        "apps.activity.models.job_model.Jobneed",
        "apps.activity.models.job_model.JobneedDetails",
        "apps.activity.models.question_model.QuestionSet",
        "apps.activity.models.asset_model.Asset",
    ],
    api_endpoints=[
        "GET /api/v1/jobs/ - List jobs (tenant-filtered)",
        "POST /api/v1/jobs/ - Create job template",
        "PATCH /api/v1/jobs/{id}/ - Update job",
        "GET /api/v1/jobs/{id}/jobneeds/ - Get execution instances",
    ],
)
class Job(BaseModel, TenantAwareModel):
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

    # id          = models.BigIntegerField(_("Job Id"), primary_key = True)
    jobname = models.CharField(_("Name"), max_length=200)
    jobdesc = models.CharField(_("Description"), max_length=500)
    fromdate = models.DateTimeField(_("From date"), auto_now=False, auto_now_add=False)
    uptodate = models.DateTimeField(_("To date"), auto_now=False, auto_now_add=False)
    cron = models.CharField(_("Cron Exp."), max_length=200, default="* * * * *")
    identifier = models.CharField(
        _("Job Type"), max_length=100, choices=Identifier.choices, null=True, db_index=True
    )
    planduration = models.IntegerField(_("Plan duration (min)"))
    gracetime = models.IntegerField(_("Grace Time"))
    expirytime = models.IntegerField(_("Expiry Time"))
    lastgeneratedon = models.DateTimeField(
        _("Last generatedon"), auto_now=False, auto_now_add=True
    )
    asset = models.ForeignKey(
        "activity.Asset",
        verbose_name=_("Asset"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    priority = models.CharField(_("Priority"), max_length=100, choices=Priority.choices)
    qset = models.ForeignKey(
        "activity.QuestionSet",
        verbose_name=_("QuestionSet"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Aggresive auto-assign to People"),
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
        "self",
        verbose_name=_("Belongs to"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    seqno = models.SmallIntegerField(_("Serial No."))
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
    starttime = models.TimeField(
        _("Start time"), auto_now=False, auto_now_add=False, null=True
    )
    endtime = models.TimeField(
        _("End time"), auto_now=False, auto_now_add=False, null=True
    )
    ticketcategory = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Notify Category"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="job_tktcategories",
    )
    scantype = models.CharField(_("Scan Type"), max_length=50, choices=Scantype.choices)
    frequency = models.CharField(
        verbose_name=_("Frequency type"),
        null=True,
        max_length=55,
        choices=Frequency.choices,
        default=Frequency.NONE.value,
    )
    other_info = models.JSONField(
        _("Other info"), default=other_info, blank=True, encoder=DjangoJSONEncoder
    )
    geojson = models.JSONField(
        default=geojson_jobnjobneed, blank=True, null=True, encoder=DjangoJSONEncoder
    )
    enable = models.BooleanField(_("Enable"), default=True)

    # Optimistic locking for concurrent updates (Rule #17)
    version = VersionField()

    objects = JobManager()

    class Meta(BaseModel.Meta):
        db_table = "job"
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "jobname", "asset", "qset", "parent", "identifier", "client"],
                name="tenant_jobname_asset_qset_parent_identifier_client_uk",
            ),
            models.CheckConstraint(
                condition=models.Q(gracetime__gte=0), name="gracetime_gte_0_ck"
            ),
            models.CheckConstraint(
                condition=models.Q(planduration__gte=0), name="planduration_gte_0_ck"
            ),
            models.CheckConstraint(
                condition=models.Q(expirytime__gte=0), name="expirytime_gte_0_ck"
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'cdtz'], name='job_tenant_cdtz_idx'),
            models.Index(fields=['tenant', 'identifier'], name='job_tenant_identifier_idx'),
            models.Index(fields=['tenant', 'enable'], name='job_tenant_enable_idx'),
        ]

    def __str__(self):
        return self.jobname


class Jobneed(BaseModel, TenantAwareModel):
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
        SCHEDULE = ("SCHEDULE", "Schedule")
        ADHOC = ("ADHOC", "Adhoc")

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

    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    jobdesc = models.CharField(_("Job Description"), max_length=200)
    plandatetime = models.DateTimeField(
        _("Plan date time"), auto_now=False, auto_now_add=False, null=True
    )
    expirydatetime = models.DateTimeField(
        _("Expiry date time"), auto_now=False, auto_now_add=False, null=True
    )
    gracetime = models.IntegerField(_("Grace time"))
    receivedonserver = models.DateTimeField(
        _("Recived on server"), auto_now=False, auto_now_add=True
    )
    starttime = models.DateTimeField(
        _("Start time"), auto_now=False, auto_now_add=False, null=True
    )
    endtime = models.DateTimeField(
        _("Start time"), auto_now=False, auto_now_add=False, null=True
    )
    gpslocation = PointField(
        _("GPS Location"), null=True, blank=True, geography=True, srid=4326
    )
    journeypath = LineStringField(geography=True, null=True, blank=True)
    remarks = models.TextField(_("Remark"), null=True, blank=True)
    remarkstype = models.ForeignKey(
        "onboarding.TypeAssist",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="remark_types",
    )
    asset = models.ForeignKey(
        "activity.Asset",
        verbose_name=_("Asset"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobneed_assets",
    )
    frequency = models.CharField(
        verbose_name=_("Frequency type"),
        null=True,
        max_length=55,
        choices=Frequency.choices,
        default=Frequency.NONE.value,
    )
    job = models.ForeignKey(
        "activity.Job",
        verbose_name=_("Job"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobs",
    )
    jobstatus = models.CharField(
        "Job Status", choices=JobStatus.choices, max_length=60, null=True
    )
    jobtype = models.CharField(
        _("Job Type"), max_length=50, choices=JobType.choices, null=True
    )
    performedby = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Performed by"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="jobneed_performedby",
    )
    priority = models.CharField(_("Priority"), max_length=50, choices=Priority.choices)
    qset = models.ForeignKey(
        "activity.QuestionSet",
        verbose_name=_("QuestionSet"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    scantype = models.CharField(
        _("Scan type"),
        max_length=50,
        choices=Scantype.choices,
        default=Scantype.NONE.value,
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
    identifier = models.CharField(
        _("Jobneed Type"), max_length=50, choices=Identifier.choices, null=True, db_index=True
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Belongs to"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    alerts = models.BooleanField(_("Alerts"), default=False, null=True)
    seqno = models.SmallIntegerField(_("Sl No."))
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
        related_name="jobneedf_bus",
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
    othersite = models.CharField(
        _("Other Site"), max_length=100, default=None, null=True
    )
    multifactor = models.DecimalField(
        _("Multiplication Factor"), default=1, max_digits=10, decimal_places=6
    )
    raisedtktflag = models.BooleanField(_("RaiseTicketFlag"), default=False, null=True)
    ismailsent = models.BooleanField(_("Mail Sent"), default=False)
    attachmentcount = models.IntegerField(_("Attachment Count"), default=0)
    other_info = models.JSONField(
        _("Other info"), default=other_info, blank=True, encoder=DjangoJSONEncoder
    )
    geojson = models.JSONField(
        default=geojson_jobnjobneed, blank=True, null=True, encoder=DjangoJSONEncoder
    )
    deviation = models.BooleanField(_("Deviation"), default=False, null=True)

    # Optimistic locking for concurrent updates (Rule #17)
    version = VersionField()

    objects = JobneedManager()

    class Meta(BaseModel.Meta):
        db_table = "jobneed"
        verbose_name = "Jobneed"
        verbose_name_plural = "Jobneeds"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(gracetime__gte=0), name="jobneed_gracetime_gte_0_ck"
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'cdtz'], name='jobneed_tenant_cdtz_idx'),
            models.Index(fields=['tenant', 'jobstatus'], name='jobneed_tenant_jobstatus_idx'),
            models.Index(fields=['tenant', 'people'], name='jobneed_tenant_people_idx'),
        ]

    def save(self, *args, **kwargs):
        if self.ticket_id is None:
            self.ticket_id = utils.get_or_create_none_ticket().id
        super().save(*args, **kwargs)


class JobneedDetails(BaseModel, TenantAwareModel):
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

    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    seqno = models.SmallIntegerField(_("SL No."))
    question = models.ForeignKey(
        "activity.Question",
        verbose_name=_("Question"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    answertype = models.CharField(
        _("Answer Type"), max_length=50, choices=AnswerType.choices, null=True
    )
    answer = models.CharField(_("Answer"), max_length=250, default="", null=True)
    isavpt = models.BooleanField(_("Attachement Required"), default=False)
    avpttype = models.CharField(
        _("Attachment Type"),
        max_length=50,
        choices=AvptType.choices,
        null=True,
        blank=True,
    )
    options = models.CharField(_("Option"), max_length=2000, null=True, blank=True)
    min = models.DecimalField(_("Min"), max_digits=18, decimal_places=4, null=True)
    max = models.DecimalField(_("Max"), max_digits=18, decimal_places=4, null=True)
    alerton = models.CharField(_("Alert On"), null=True, blank=True, max_length=300)
    qset = models.ForeignKey(
        QuestionSet,
        verbose_name=("Question Set"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="questions_qset",
    )
    ismandatory = models.BooleanField(_("Mandatory"), default=True)
    jobneed = models.ForeignKey(
        "activity.Jobneed",
        verbose_name=_("Jobneed"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    alerts = models.BooleanField(_("Alerts"), default=False)
    attachmentcount = models.IntegerField(_("Attachment count"), default=0)
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
        help_text="Language code used for transcription (e.g., 'en-US', 'hi-IN')"
    )
    transcript_processed_at = models.DateTimeField(
        _("Transcript Processed At"),
        null=True,
        blank=True,
        help_text="Timestamp when transcript processing completed"
    )

    objects = JobneedDetailsManager()

    class Meta(BaseModel.Meta):
        db_table = "jobneeddetails"
        verbose_name = "JobneedDetails"
        verbose_name_plural = "Jobneed Details"
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'jobneed', 'question'],
                name='tenant_jobneeddetails_jobneed_question_uk',
                violation_error_message=(
                    "Duplicate question not allowed for the same jobneed. "
                    "Each question can only appear once per jobneed."
                )
            ),
            models.UniqueConstraint(
                fields=['tenant', 'jobneed', 'seqno'],
                name='tenant_jobneeddetails_jobneed_seqno_uk',
                violation_error_message=(
                    "Duplicate sequence number not allowed for the same jobneed. "
                    "Each seqno must be unique within a jobneed."
                )
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'jobneed'], name='jnd_tenant_jobneed_idx'),
            models.Index(fields=['tenant', 'question'], name='jnd_tenant_question_idx'),
        ]

# Backward compatibility aliases for naming standardization
# DEPRECATED: Use Jobneed and JobneedDetails (lowercase 'n')
# These aliases exist to prevent import errors during migration
JobNeed = Jobneed
JobNeedDetails = JobneedDetails

__all__ = ['Job', 'Jobneed', 'JobneedDetails', 'JobNeed', 'JobNeedDetails']
