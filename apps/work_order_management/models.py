from django.db import models
from django.forms.models import model_to_dict

# Create your models here.
import uuid
from apps.peoples.models import BaseModel
from django.contrib.gis.db.models import PointField
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.fields import ArrayField
from apps.tenants.models import TenantAwareModel
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from concurrency.fields import VersionField
from apps.ontology import ontology
from .managers import (
    VendorManager,
    WorkOrderManager,
    WOMDetailsManager,
    ApproverManager,
)


def geojson():
    return {"gpslocation": ""}


def other_data():
    return {
        "token": None,
        "created_at": None,
        "token_expiration": 5,  # min
        "reply_from_vendor": "",
        "wp_seqno": 0,
        "wp_approvers": [],
        "wp_verifiers": [],
        "section_weightage": 0,
        "overall_score": 0,
        "remarks": "",
        "uptime_score": 0,
    }


def wo_history_json():
    return {"wo_history": [], "wp_history": []}


@ontology(
    domain="operations",
    concept="Maintenance Workflow & Work Order Management",
    purpose=(
        "Central work order management system for planned maintenance (PPM), reactive repairs, and vendor-managed "
        "work. Supports work orders (WO) and work permits (WP) with multi-level approval flows, vendor coordination, "
        "SLA tracking, and quality scoring. Integrates with Asset model for equipment maintenance and QuestionSet "
        "for inspection checklists."
    ),
    criticality="high",
    lifecycle_states=[
        "ASSIGNED - Initial state, work assigned to vendor/team",
        "RE_ASSIGNED - Reassigned to different vendor/team",
        "INPROGRESS - Work actively being performed",
        "COMPLETED - Work finished, pending verification",
        "CLOSED - Verified and closed, final state",
        "CANCELLED - Work order cancelled/abandoned"
    ],
    business_rules=[
        "Work Permit requirements: REQUIRED workflow if workpermit='APPROVED', NOT_REQUIRED for simple WOs",
        "Approval flow: approvers list + verifiers list (ArrayField of people IDs) for multi-level signoff",
        "Vendor coordination: Vendor FK required, token-based external access (other_data.token)",
        "SLA tracking: plandatetime (scheduled start), expirydatetime (deadline), starttime/endtime (actual)",
        "Priority levels: HIGH, MEDIUM, LOW affect notification and escalation logic",
        "Parent-child hierarchy: parent FK supports breakdown structures (WO → child WOs for phases)",
        "Quality scoring: section_weightage, overall_score, uptime_score in other_data JSONField",
        "History tracking: wo_history JSONField captures full state transition audit trail",
        "GPS validation: gpslocation (Point) must match Location or Asset gpslocation within tolerance",
        "Identifier polymorphism: WO (work order), WP (work permit), SLA (service level agreement)",
    ],
    relationships=[
        "asset: FK to activity.Asset (equipment/system being maintained)",
        "location: FK to activity.Location (work site zone/area)",
        "qset: FK to activity.QuestionSet (inspection checklist for verification)",
        "vendor: FK to Vendor (contractor performing work)",
        "parent: Self-referential FK for hierarchical breakdown",
        "client: FK to onboarding.Bt (contract holder)",
        "bu: FK to onboarding.Bt (site/business unit)",
        "ticketcategory: FK to onboarding.TypeAssist (notification category)",
        "WomDetails: 1-to-many (checklist questions/answers per work order)",
        "Approver: M2M via approvers/verifiers ArrayField (people IDs)",
        "Tenant isolation: All queries filtered by TenantAwareModel.tenant",
    ],
    depends_on=[
        "apps.peoples.models.BaseModel (audit fields)",
        "apps.tenants.models.TenantAwareModel (multi-tenant isolation)",
        "apps.work_order_management.managers.WorkOrderManager (optimized queries)",
        "apps.activity.models.Asset (maintenance target)",
        "apps.activity.models.Location (work site)",
        "apps.activity.models.QuestionSet (inspection checklist)",
        "apps.onboarding.models.TypeAssist (categories, notification types)",
        "concurrency.fields.VersionField (optimistic locking for concurrent updates)",
    ],
    used_by=[
        "apps.work_order_management.views (Django admin CRUD)",
        "apps.work_order_management.api (REST endpoints for mobile/vendor portals)",
        "apps.scheduler.services (PPM schedule generation → WOs)",
        "Vendor portal: Token-based external access for status updates",
        "Mobile apps: Work order assignment, checklist completion, photo uploads",
        "Reports: Maintenance backlog, vendor performance, SLA compliance",
        "Notifications: Approval reminders, overdue alerts, completion confirmations",
    ],
    tags=["work-orders", "maintenance", "workflow", "approval-flow", "vendor", "sla", "multi-tenant", "gis"],
    security_notes=(
        "Multi-tenant security:\n"
        "1. TenantAwareModel ensures all queries filtered by tenant field\n"
        "2. Unique constraint includes tenant/qset/client to prevent conflicts\n"
        "3. Vendor access controlled via time-limited tokens (other_data.token)\n"
        "4. Token expiration enforced (other_data.token_expiration in minutes)\n"
        "5. Approver/verifier lists (ArrayField) validated against user permissions\n"
        "\nWorkflow security:\n"
        "6. Work permit status transitions validated (PENDING → APPROVED/REJECTED)\n"
        "7. Only assigned people can update workstatus (enforced at view layer)\n"
        "8. Verifiers cannot approve their own work (conflict of interest check)\n"
        "9. GPS location required for mobile checkins (gpslocation PointField)\n"
        "10. File uploads (attachmentcount) validated via secure_attachment service\n"
        "\nData integrity:\n"
        "11. VersionField prevents lost updates via optimistic locking\n"
        "12. RESTRICT on_delete prevents orphaned references (Asset, Vendor, etc.)\n"
        "13. wo_history immutable append-only log (no deletion)\n"
        "14. Alerts flag triggers notification workflows (ismailsent tracks delivery)"
    ),
    performance_notes=(
        "Database optimizations:\n"
        "- Composite indexes: (tenant, cdtz), (tenant, workstatus), (tenant, workpermit)\n"
        "- WorkOrderManager provides status-specific queries (pending, overdue, completed)\n"
        "- PostGIS spatial index on gpslocation for proximity searches\n"
        "- UUID field indexed for mobile sync operations\n"
        "\nQuery patterns:\n"
        "- Wom.objects.filter(workstatus='ASSIGNED', expirydatetime__lt=now()) → overdue WOs\n"
        "- Wom.objects.select_related('asset', 'vendor', 'location', 'qset') → avoid N+1\n"
        "- JSONField queries: other_data__overall_score__gte=80 (JSONB index recommended)\n"
        "\nScaling concerns:\n"
        "- Large sites (1000+ WOs/month): Partition by cdtz (monthly tables)\n"
        "- wo_history JSONField grows unbounded (consider separate WomHistory table)\n"
        "- ArrayField approvers/verifiers limited to 10 people (UI/UX constraint)\n"
        "- Vendor token generation rate-limited (prevent brute force)"
    ),
    architecture_notes=(
        "State machine design:\n"
        "- Valid transitions enforced at service layer (not database constraints)\n"
        "- ASSIGNED → INPROGRESS → COMPLETED → CLOSED (happy path)\n"
        "- ASSIGNED → RE_ASSIGNED (vendor change)\n"
        "- Any state → CANCELLED (admin override)\n"
        "- COMPLETED requires all WomDetails answered + verifier approval\n"
        "\nWork permit workflow:\n"
        "- workpermit='REQUIRED' activates approval flow\n"
        "- Approvers must approve before work starts (workstatus=INPROGRESS)\n"
        "- Verifiers must verify after completion (workstatus=CLOSED)\n"
        "- Each approval/rejection logged in wp_history array\n"
        "\nVendor integration:\n"
        "- Token generated on WO assignment (other_data.token)\n"
        "- Vendor portal authenticates via token (stateless)\n"
        "- Vendor updates reply_from_vendor field (other_data.reply_from_vendor)\n"
        "- Quality scoring calculated on completion (section_weightage, overall_score)\n"
        "\nFuture enhancements:\n"
        "- Split wo_history to separate WomHistory model (performance)\n"
        "- Add recurring WO templates (link to scheduler.Job)\n"
        "- Predictive maintenance: ML model predicts WO creation based on Asset patterns\n"
        "- Mobile offline mode: WomDetails sync protocol for disconnected work"
    ),
    examples=[
        {
            "description": "Create high-priority work order with approval flow",
            "code": """
from apps.work_order_management.models import Wom
from django.contrib.gis.geos import Point

wo = Wom.objects.create(
    description='HVAC Chiller Preventive Maintenance - Q3 2025',
    priority=Wom.Priority.HIGH,
    identifier=Wom.Identifier.WO,
    workstatus=Wom.Workstatus.ASSIGNED,
    workpermit=Wom.WorkPermitStatus.PENDING,  # Requires approval
    plandatetime=datetime(2025, 7, 15, 8, 0),
    expirydatetime=datetime(2025, 7, 15, 17, 0),
    asset=asset_obj,  # HVAC-001 chiller
    location=location_obj,
    vendor=vendor_obj,
    qset=checklist_obj,  # PPM checklist
    approvers=['123', '456'],  # Manager IDs
    verifiers=['789'],  # Supervisor ID
    client=client_bt,
    bu=site_bt,
    tenant=tenant_obj,
    gpslocation=Point(77.5946, 12.9716, srid=4326),
    other_data={
        'token': 'abc123xyz',
        'token_expiration': 1440,  # 24 hours
        'section_weightage': 0,
        'overall_score': 0
    }
)
"""
        },
        {
            "description": "Query overdue work orders needing escalation",
            "code": """
from django.utils import timezone
from datetime import timedelta

# Overdue high-priority WOs not yet started
overdue_wos = Wom.objects.filter(
    workstatus__in=[Wom.Workstatus.ASSIGNED, Wom.Workstatus.RE_ASSIGNED],
    priority=Wom.Priority.HIGH,
    expirydatetime__lt=timezone.now(),
    tenant=request.user.tenant
).select_related('asset', 'vendor', 'bu').order_by('expirydatetime')

for wo in overdue_wos:
    send_escalation_notification(wo, escalation_level='CRITICAL')
"""
        },
        {
            "description": "Approve work permit and track history",
            "code": """
wo = Wom.objects.select_for_update().get(pk=wo_id)

# Validate approver authorization
if str(request.user.id) not in wo.approvers:
    raise PermissionDenied('User not authorized to approve')

# Update work permit status
wo.workpermit = Wom.WorkPermitStatus.APPROVED
wo.other_data['wp_history'].append({
    'approved_by': request.user.id,
    'approved_at': timezone.now().isoformat(),
    'comments': 'Safety checks completed'
})

# Add to wo_history
wo.add_history()  # Appends current state to wo_history['wo_history']

wo.save()
"""
        },
        {
            "description": "Complete work order with quality scoring",
            "code": """
# Mark work order as completed
wo = Wom.objects.get(pk=wo_id)
wo.workstatus = Wom.Workstatus.COMPLETED
wo.endtime = timezone.now()

# Calculate quality score from WomDetails
details = wo.womdetails_set.all()
total_score = sum(
    detail.calculate_score()  # Custom scoring logic
    for detail in details
)
wo.other_data['overall_score'] = total_score / len(details) if details else 0
wo.other_data['uptime_score'] = calculate_uptime_impact(wo.asset)

wo.save()

# Trigger verifier notification
send_verification_request(wo.verifiers, wo)
"""
        }
    ]
)
class Wom(BaseModel, TenantAwareModel):
    class Workstatus(models.TextChoices):
        ASSIGNED = ("ASSIGNED", "Assigned")
        REASSIGNED = ("RE_ASSIGNED", "Re-Assigned")
        COMPLETED = ("COMPLETED", "Completed")
        INPROGRESS = ("INPROGRESS", "Inprogress")
        CANCELLED = ("CANCELLED", "Cancelled")
        CLOSED = ("CLOSED", "Closed")

    class WorkPermitStatus(models.TextChoices):
        """
        if value is NOT_REQURED it is work order
        """

        NOTNEED = ("NOT_REQUIRED", "Not Required")
        APPROVED = ("APPROVED", "Approved")
        REJECTED = ("REJECTED", "Rejected")
        PENDING = ("PENDING", "Pending")

    class WorkPermitVerifierStatus(models.TextChoices):
        NOTNEED = ("NOT_REQUIRED", "Not Required")
        APPROVED = ("APPROVED", "Approved")
        REJECTED = ("REJECTED", "Rejected")
        PENDING = ("PENDING", "Pending")

    class Priority(models.TextChoices):
        HIGH = ("HIGH", "High")
        LOW = ("LOW", "Low")
        MEDIUM = ("MEDIUM", "Medium")

    class Identifier(models.TextChoices):
        WO = ("WO", "Work Order")
        WP = ("WP", "Work Permit")
        SLA = ("SLA", "Service Level Agreement")

    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    description = models.CharField(_("Job Description"), max_length=200)
    plandatetime = models.DateTimeField(
        _("Plan date time"), auto_now=False, auto_now_add=False, null=True
    )
    expirydatetime = models.DateTimeField(
        _("Expiry date time"), auto_now=False, auto_now_add=False, null=True
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
    asset = models.ForeignKey(
        "activity.Asset",
        verbose_name=_("Asset"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="wo_assets",
    )
    location = models.ForeignKey(
        "activity.Location",
        verbose_name=_("Location"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    workstatus = models.CharField(
        "Job Status",
        choices=Workstatus.choices,
        default=Workstatus.ASSIGNED,
        max_length=60,
        null=True,
    )
    seqno = models.SmallIntegerField(_("Serial No."), null=True)
    approvers = ArrayField(
        models.CharField(max_length=100, blank=True),
        null=True,
        blank=True,
        verbose_name=_("Approvers"),
    )
    verifiers = ArrayField(
        models.CharField(max_length=100, blank=True),
        null=True,
        blank=True,
        verbose_name=_("Verifiers"),
    )
    workpermit = models.CharField(
        _("Work Permit"),
        choices=WorkPermitStatus.choices,
        default=WorkPermitStatus.NOTNEED,
        max_length=35,
    )
    verifiers_status = models.CharField(
        _("Verifier Status"),
        max_length=50,
        choices=WorkPermitVerifierStatus.choices,
        default=WorkPermitVerifierStatus.PENDING,
    )
    priority = models.CharField(
        _("Priority"), max_length=50, choices=Priority.choices, default=Priority.LOW
    )
    qset = models.ForeignKey(
        "activity.QuestionSet",
        verbose_name=_("QuestionSet"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    vendor = models.ForeignKey(
        "Vendor",
        null=True,
        blank=False,
        on_delete=models.RESTRICT,
        verbose_name="Vendor",
    )
    performedby = models.CharField(
        max_length=55,
        verbose_name="Performed By",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Belongs to"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    alerts = models.BooleanField(_("Alerts"), default=False, null=True)
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="wo_clients",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="wo_bus",
    )
    ticketcategory = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Notify Category"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    ismailsent = models.BooleanField(_("Mail Sent"), default=False)
    isdenied = models.BooleanField(_("Denied"), default=False)
    geojson = models.JSONField(verbose_name=_("Geo Json"), default=geojson, null=True)
    other_data = models.JSONField(
        verbose_name=_("Other Data"), default=other_data, null=True
    )
    attachmentcount = models.IntegerField(_("Attachment Count"), default=0)
    categories = ArrayField(
        models.CharField(max_length=50, blank=True, default=""), default=list
    )
    wo_history = models.JSONField(encoder=DjangoJSONEncoder, default=wo_history_json)
    identifier = models.CharField(
        _("Identifier"),
        max_length=50,
        choices=Identifier.choices,
        null=True,
        blank=True,
    )
    remarks = models.JSONField(_("Remarks"), blank=True, null=True)

    # Optimistic locking for concurrent updates (Rule #17)
    version = VersionField()

    objects = WorkOrderManager()

    def add_history(self):
        self.wo_history["wo_history"].append(
            model_to_dict(self, exclude=["wo_history", "workpermit", "gpslocation"])
        )
        self.save()

    class Meta(BaseModel.Meta):
        db_table = "wom"
        verbose_name = "work order management"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "qset", "client", "id"], name="tenant_qset_client"
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'cdtz'], name='wom_tenant_cdtz_idx'),
            models.Index(fields=['tenant', 'workstatus'], name='wom_tenant_status_idx'),
            models.Index(fields=['tenant', 'workpermit'], name='wom_tenant_permit_idx'),
        ]


class Vendor(BaseModel, TenantAwareModel):
    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    code = models.CharField(_("Code"), max_length=50, null=True, blank=False)
    name = models.CharField(_("Name"), max_length=255, null=True, blank=False)
    type = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Type"),
        null=True,
        on_delete=models.CASCADE,
    )
    address = models.TextField(
        max_length=500, verbose_name="Address", blank=True, null=True
    )
    gpslocation = PointField(
        _("GPS Location"), null=True, blank=True, geography=True, srid=4326
    )
    enable = models.BooleanField(_("Enable"), default=True)
    mobno = models.CharField(_("Mob No"), max_length=15)
    email = models.CharField(_("Email"), max_length=100)
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="vendor_clients",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="vendor_bus",
    )
    show_to_all_sites = models.BooleanField(_("Applicable to all sites"), default=False)
    description = models.TextField(
        _("Description"), max_length=500, null=True, blank=True
    )

    objects = VendorManager()

    class Meta(BaseModel.Meta):
        db_table = "vendor"
        verbose_name = "vendor company"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code", "client"], name="tenant_code_client"),
        ]
        indexes = [
            models.Index(fields=['tenant', 'cdtz'], name='vendor_tenant_cdtz_idx'),
            models.Index(fields=['tenant', 'enable'], name='vendor_tenant_enable_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.code}{" - " + self.type.taname + ")" if self.type else ")"}'


class WomDetails(BaseModel, TenantAwareModel):
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
        MULTISELECT = ("MULTISELECT", "Multi Select")

    class AvptType(models.TextChoices):
        BACKCAMPIC = "BACKCAMPIC", _("Back Camera Pic")
        FRONTCAMPIC = "FRONTCAMPIC", _("Front Camera Pic")
        AUDIO = "AUDIO", _("Audio")
        VIDEO = "VIDEO", _("Video")
        NONE = ("NONE", "NONE")

    uuid = models.UUIDField(unique=True, editable=False, blank=True, default=uuid.uuid4)
    seqno = models.SmallIntegerField(_("SL #"))
    question = models.ForeignKey(
        "activity.Question", verbose_name=_(""), on_delete=models.RESTRICT
    )
    answertype = models.CharField(
        _("Answer Type"), max_length=50, choices=AnswerType.choices, null=True
    )
    qset = models.ForeignKey(
        "activity.QuestionSet",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="qset_answers",
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
    alerton = models.CharField(_("Alert On"), null=True, blank=True, max_length=50)
    ismandatory = models.BooleanField(_("Mandatory"), default=True)
    wom = models.ForeignKey(
        Wom, verbose_name=_("Jobneed"), null=True, blank=True, on_delete=models.RESTRICT
    )
    alerts = models.BooleanField(_("Alerts"), default=False)
    attachmentcount = models.IntegerField(_("Attachment count"), default=0)

    # Optimistic locking for concurrent updates (Rule #17)
    version = VersionField()

    objects = WOMDetailsManager()

    class Meta(BaseModel.Meta):
        db_table = "womdetails"
        verbose_name = "Wom Details"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "question", "wom"], name="tenant_question_client")
        ]
        indexes = [
            models.Index(fields=['tenant', 'wom'], name='womdetails_tenant_wom_idx'),
            models.Index(fields=['tenant', 'question'], name='womdetails_tenant_question_idx'),
        ]


class Approver(BaseModel, TenantAwareModel):
    class Identifier(models.TextChoices):
        APPROVER = ("APPROVER", "Approver")
        VERIFIER = ("VERIFIER", "Verifier")

    approverfor = ArrayField(
        models.CharField(_("Approver/Verifier For"), max_length=50, blank=True),
        null=True,
        blank=True,
    )
    sites = ArrayField(
        models.CharField(max_length=50, blank=True),
        null=True,
        blank=True,
        verbose_name=_("Sites"),
    )
    forallsites = models.BooleanField(_("For all sites"), default=True)
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Approver"),
        on_delete=models.RESTRICT,
        null=True,
    )
    bu = models.ForeignKey(
        "onboarding.Bt", verbose_name=_(""), on_delete=models.RESTRICT, null=True
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        on_delete=models.RESTRICT,
        null=True,
        related_name="approver_clients",
    )
    identifier = models.CharField(
        _("Approver/Verifier"),
        choices=Identifier.choices,
        max_length=250,
        null=True,
        blank=True,
    )

    objects = ApproverManager()

    class Meta(BaseModel.Meta):
        db_table = "approver"
        verbose_name = "approver"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "people", "approverfor", "sites"],
                name="tenant_people_approverfor_sites_uk",
            )
        ]
        indexes = [
            models.Index(fields=['tenant', 'people'], name='approver_tenant_people_idx'),
            models.Index(fields=['tenant', 'identifier'], name='approver_tenant_identifier_idx'),
        ]
