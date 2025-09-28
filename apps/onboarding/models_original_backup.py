from django.conf import settings
from django.urls import reverse
from django.contrib.gis.db.models import PolygonField
from django.db import models
from apps.tenants.models import TenantAwareModel
from apps.peoples.models import BaseModel
from .managers import (
    BtManager,
    TypeAssistManager,
    GeofenceManager,
    ShiftManager,
    DeviceManager,
    SubscriptionManger,
)
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext_lazy as _
from django.contrib.gis.db.models import PointField
from django.contrib.postgres.fields import ArrayField
import uuid
from django.utils import timezone

# Create your models here.


def bu_defaults():
    return {
        "mobilecapability": [],
        "validimei": "",
        "webcapability": [],
        "portletcapability": [],
        "validip": "",
        "reliveronpeoplecount": 0,
        "reportcapability": [],
        "usereliver": False,
        "pvideolength": 10,
        "guardstrenth": 0,
        "malestrength": 0,
        "femalestrength": 0,
        "siteclosetime": "",
        "tag": "",
        "siteopentime": "",
        "nearbyemergencycontacts": [],
        "maxadmins": 5,
        "address": "",
        "address2": None,
        "permissibledistance": 0,
        "controlroom": [],
        "ispermitneeded": False,
        "no_of_devices_allowed": 0,
        "no_of_users_allowed_mob": 0,
        "no_of_users_allowed_web": 0,
        "no_of_users_allowed_both": 0,
        "devices_currently_added": 0,
        "startdate": "",
        "enddate": "",
        "onstop": "",
        "onstopmessage": "",
        "clienttimezone": "",
        "billingtype": "",
        "total_people_count": 0,
        "contract_designcount": {},
        "posted_people": [],
    }


class Bt(BaseModel, TenantAwareModel):
    uuid = models.UUIDField(default=uuid.uuid4, null=True)
    bucode = models.CharField(_("Code"), max_length=30)
    solid = models.CharField(
        max_length=30, null=True, blank=True, verbose_name="Sol ID"
    )
    siteincharge = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Site Incharge",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="siteincharge",
    )
    bupreferences = models.JSONField(
        _("bupreferences"),
        null=True,
        default=bu_defaults,
        encoder=DjangoJSONEncoder,
        blank=True,
    )
    identifier = models.ForeignKey(
        "TypeAssist",
        verbose_name="Identifier",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="bu_idfs",
    )
    buname = models.CharField(_("Name"), max_length=200)
    butree = models.CharField(
        _("Bu Path"), null=True, blank=True, max_length=300, default=""
    )
    butype = models.ForeignKey(
        "TypeAssist",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="bu_butypes",
        verbose_name="Type",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="children",
        verbose_name="Belongs To",
    )
    enable = models.BooleanField(_("Enable"), default=True)
    iswarehouse = models.BooleanField(_("Warehouse"), default=False)
    gpsenable = models.BooleanField(_("GPS Enable"), default=False)
    enablesleepingguard = models.BooleanField(_("Enable SleepingGuard"), default=False)
    skipsiteaudit = models.BooleanField(_("Skip SiteAudit"), default=False)
    siincludes = ArrayField(
        models.CharField(max_length=50, blank=True),
        verbose_name=_("Site Inclides"),
        null=True,
        blank=True,
    )
    deviceevent = models.BooleanField(_("Device Event"), default=False)
    pdist = models.FloatField(
        _("Permissible Distance"), default=0.0, blank=True, null=True
    )
    gpslocation = PointField(
        _("GPS Location"), null=True, blank=True, geography=True, srid=4326
    )
    isvendor = models.BooleanField(_("Vendor"), default=False)
    isserviceprovider = models.BooleanField(_("ServiceProvider"), default=False)

    # Conversational Onboarding Fields (Phase 1 MVP)
    onboarding_context = models.JSONField(
        _("Onboarding Context"),
        default=dict,
        blank=True,
        help_text="Context data for conversational onboarding process"
    )
    setup_confidence_score = models.FloatField(
        _("Setup Confidence Score"),
        null=True,
        blank=True,
        help_text="AI confidence score for the setup recommendations"
    )

    objects = BtManager()

    class Meta(BaseModel.Meta):
        db_table = "bt"
        verbose_name = "Buisiness Unit"
        verbose_name_plural = "Buisiness Units"
        constraints = [
            models.UniqueConstraint(
                fields=["bucode", "parent", "identifier"],
                name="bu_bucode_parent_identifier_uk",
            )
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self) -> str:
        return f"{self.buname} ({self.bucode})"

    def get_absolute_wizard_url(self):
        return reverse("onboarding:wiz_bu_update", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        # Check if this is a new instance or update
        is_new = self.pk is None
        
        # Get the old parent_id if this is an update
        old_parent_id = None
        if not is_new:
            try:
                old_instance = Bt.objects.get(pk=self.pk)
                old_parent_id = old_instance.parent_id
            except Bt.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        from apps.core import utils

        if self.siteincharge is None:
            self.siteincharge = utils.get_or_create_none_people()
        if self.butype is None:
            self.butype = utils.get_none_typeassist()
        
        # Clear cache after save
        self._clear_bu_cache(old_parent_id)
    
    def delete(self, *args, **kwargs):
        # Store parent_id before deletion
        parent_id = self.parent_id
        
        # Call parent delete
        super().delete(*args, **kwargs)
        
        # Clear cache after deletion
        self._clear_bu_cache(parent_id)
    
    def _clear_bu_cache(self, old_parent_id=None):
        """Clear BU tree cache for affected clients"""
        from django.core.cache import cache
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Clear cache for current parent
        if self.parent_id:
            # Clear all cache patterns for this parent and its ancestors
            self._clear_cache_for_bu_tree(self.parent_id)
        
        # Clear cache for old parent if it changed
        if old_parent_id and old_parent_id != self.parent_id:
            self._clear_cache_for_bu_tree(old_parent_id)
        
        # Clear cache for self if it's a parent node
        self._clear_cache_for_bu_tree(self.id)
        
        logger.info(f"Cache cleared for BU {self.bucode} (ID: {self.id})")
    
    def _clear_cache_for_bu_tree(self, bu_id):
        """Clear all cache keys related to a BU tree"""
        from django.core.cache import cache
        
        # Clear all possible cache key patterns for this BU
        cache_patterns = [
            f"bulist_{bu_id}_True_True_array",
            f"bulist_{bu_id}_True_True_text",
            f"bulist_{bu_id}_True_True_jsonb",
            f"bulist_{bu_id}_True_False_array",
            f"bulist_{bu_id}_True_False_text",
            f"bulist_{bu_id}_True_False_jsonb",
            f"bulist_{bu_id}_False_True_array",
            f"bulist_{bu_id}_False_True_text",
            f"bulist_{bu_id}_False_True_jsonb",
            f"bulist_{bu_id}_False_False_array",
            f"bulist_{bu_id}_False_False_text",
            f"bulist_{bu_id}_False_False_jsonb",
            f"bulist_idnf_{bu_id}_True_True",
            f"bulist_idnf_{bu_id}_True_False",
            f"bulist_idnf_{bu_id}_False_True",
            f"bulist_idnf_{bu_id}_False_False",
        ]
        
        for pattern in cache_patterns:
            cache.delete(pattern)


def shiftdata_json():
    return {}


class Shift(BaseModel, TenantAwareModel):
    bu = models.ForeignKey(
        "Bt",
        verbose_name="Buisiness View",
        null=True,
        on_delete=models.RESTRICT,
        related_name="shift_bu",
    )
    client = models.ForeignKey(
        "Bt",
        verbose_name="Buisiness View",
        null=True,
        on_delete=models.RESTRICT,
        related_name="shift_client",
    )
    shiftname = models.CharField(max_length=50, verbose_name="Name")
    shiftduration = models.IntegerField(null=True, verbose_name="Shift Duration")
    designation = models.ForeignKey(
        "TypeAssist",
        verbose_name="Buisiness View",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    peoplecount = models.IntegerField(
        null=True, blank=True, verbose_name="People Count"
    )
    starttime = models.TimeField(verbose_name="Start time")
    endtime = models.TimeField(verbose_name="End time")
    nightshiftappicable = models.BooleanField(
        default=True, verbose_name="Night Shift Applicable"
    )
    captchafreq = models.IntegerField(default=10, null=True)
    enable = models.BooleanField(verbose_name="Enable", default=True)
    shift_data = models.JSONField(
        encoder=DjangoJSONEncoder, blank=True, null=True, default=shiftdata_json
    )

    objects = ShiftManager()

    class Meta(BaseModel.Meta):
        db_table = "shift"
        constraints = [
            models.UniqueConstraint(
                fields=["shiftname", "bu", "designation", "client"],
                name="shiftname_bu_desgn_client_uk",
            )
        ]
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self):
        return f"{self.shiftname} ({self.starttime} - {self.endtime})"

    def get_absolute_wizard_url(self):
        return reverse("onboarding:wiz_shift_update", kwargs={"pk": self.pk})


class TypeAssist(BaseModel, TenantAwareModel):
    id = models.BigAutoField(primary_key=True)
    tacode = models.CharField(_("tacode"), max_length=50)
    taname = models.CharField(_("taname"), max_length=100)
    tatype = models.ForeignKey(
        "self",
        verbose_name="TypeAssist",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="children",
    )
    bu = models.ForeignKey(
        "Bt",
        verbose_name="Buisiness View",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="ta_bus",
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name="Client",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="ta_clients",
    )
    enable = models.BooleanField(_("Enable"), default=True)

    objects = TypeAssistManager()

    class Meta(BaseModel.Meta):
        db_table = "typeassist"
        constraints = [
            models.UniqueConstraint(
                fields=["tacode", "tatype", "client"], name="code_unique"
            ),
        ]

    def __str__(self):
        return f"{self.taname} ({self.tacode})"

    def get_absolute_url(self):
        return reverse("onboarding:ta_update", kwargs={"pk": self.pk})

    def get_all_children(self):
        if self.pk is None:
            return []
        children = [self]
        try:
            child_list = self.children.all()
        except AttributeError:
            return children
        for child in child_list:
            children.extend(child.get_all_children())
        return children

    def get_all_parents(self):
        parents = [self]
        if self.tatype is not None:
            parent = self.tatype
            parents.extend(parent.get_all_parents())
        return parents

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.tatype in self.get_all_children():
            raise ValidationError(
                "A user cannot have itself \
                    or one of its' children as parent."
            )


def wizard_default():
    return {"wizard_data": {}}


def formData_default():
    return {"form_id": {}}


class GeofenceMaster(BaseModel):
    # id= models.BigIntegerField(primary_key = True)
    gfcode = models.CharField(_("Code"), max_length=100)
    gfname = models.CharField(_("Name"), max_length=100)
    alerttext = models.CharField(_("Alert Text"), max_length=100)
    geofence = PolygonField(
        _("GeoFence"),
        srid=4326,
        geography=True,
        null=True,
    )
    alerttogroup = models.ForeignKey(
        "peoples.Pgroup",
        null=True,
        verbose_name=_("Alert to Group"),
        on_delete=models.RESTRICT,
    )
    alerttopeople = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        verbose_name=_(""),
        on_delete=models.RESTRICT,
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        related_name="for_clients",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        related_name="for_sites",
    )
    enable = models.BooleanField(_("Enable"), default=True)

    objects = GeofenceManager()

    class Meta(BaseModel.Meta):
        db_table = "geofencemaster"
        constraints = [
            models.UniqueConstraint(fields=["gfcode", "bu"], name="gfcode_bu_uk")
        ]
        get_latest_by = ["mdtz"]

    def __str__(self):
        return f"{self.gfname} ({self.gfname})"


class DownTimeHistory(BaseModel):
    reason = models.TextField(_("Downtime Reason"))
    starttime = models.DateTimeField(_("Start"), default=timezone.now)
    endtime = models.DateTimeField(_("End"), default=timezone.now)
    client = models.ForeignKey(
        "onboarding.Bt", null=True, verbose_name=_("Client"), on_delete=models.RESTRICT
    )

    class Meta(BaseModel.Meta):
        db_table = "downtime_history"
        get_latest_by = ["mdtz"]

    def __str__(self):
        return self.reason


class Device(BaseModel, TenantAwareModel):
    # id     = models.BigIntegerField(_("Device Id"), primary_key = True)
    handsetname = models.CharField(_("Handset Name"), max_length=100)
    modelname = models.CharField(_("Model"), max_length=50)
    dateregistered = models.DateField(_("Date Registered"), default=timezone.now)
    lastcommunication = models.DateTimeField(
        _("Last Communication"), auto_now=False, auto_now_add=False
    )
    imeino = models.CharField(
        _("IMEI No"), max_length=15, null=True, blank=True, unique=True
    )
    lastloggedinuser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Last Logged In User"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    phoneno = models.CharField(_("Phone No"), max_length=15, null=True, blank=True)
    isdeviceon = models.BooleanField(_("Is Device On"), default=True)
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )

    objects = DeviceManager()

    class Meta(BaseModel.Meta):
        db_table = "device"
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self):
        return self.handsetname


class Subscription(BaseModel, TenantAwareModel):
    class StatusChoices(models.TextChoices):
        A = ("Active", "Active")
        IA = ("In Active", "In Active")

    startdate = models.DateField(_("Start Date"), auto_now=False, auto_now_add=False)
    enddate = models.DateField(_("End Date"), auto_now=False, auto_now_add=False)
    terminateddate = models.DateField(
        _("Terminated Date"), auto_now=False, null=True, auto_now_add=False
    )
    reason = models.TextField(_("Reason"), null=True, blank=True)
    status = models.CharField(
        _("Status"),
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.A.value,
    )
    assignedhandset = models.ForeignKey(
        Device,
        verbose_name=_("Assigned Handset"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
    )
    istemporary = models.BooleanField(_("Is Temporary"), default=False)

    objects = SubscriptionManger()

    class Meta(BaseModel.Meta):
        db_table = "subscription"
        constraints = [
            models.UniqueConstraint(
                fields=["startdate", "enddate", "client"],
                name="startdate_enddate_client_uk",
            )
        ]


# =============================================================================
# CONVERSATIONAL ONBOARDING AI MODELS (Phase 1 MVP)
# =============================================================================


class ConversationSession(BaseModel, TenantAwareModel):
    """
    Tracks conversational onboarding sessions with users.
    """
    class ConversationTypeChoices(models.TextChoices):
        INITIAL_SETUP = "initial_setup", _("Initial Setup")
        CONFIGURATION_UPDATE = "config_update", _("Configuration Update")
        TROUBLESHOOTING = "troubleshooting", _("Troubleshooting")
        FEATURE_REQUEST = "feature_request", _("Feature Request")

    class StateChoices(models.TextChoices):
        STARTED = "started", _("Started")
        IN_PROGRESS = "in_progress", _("In Progress")
        GENERATING_RECOMMENDATIONS = "generating", _("Generating Recommendations")
        AWAITING_USER_APPROVAL = "awaiting_approval", _("Awaiting User Approval")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")
        ERROR = "error", _("Error")

    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_sessions",
        verbose_name=_("User")
    )
    client = models.ForeignKey(
        "Bt",
        on_delete=models.CASCADE,
        related_name="conversation_sessions",
        verbose_name=_("Client")
    )
    language = models.CharField(
        _("Language"),
        max_length=10,
        default="en",
        help_text="ISO language code for the conversation"
    )
    conversation_type = models.CharField(
        _("Conversation Type"),
        max_length=50,
        choices=ConversationTypeChoices.choices,
        default=ConversationTypeChoices.INITIAL_SETUP
    )
    context_data = models.JSONField(
        _("Context Data"),
        default=dict,
        blank=True,
        help_text="Initial context and environment data"
    )
    current_state = models.CharField(
        _("Current State"),
        max_length=50,
        choices=StateChoices.choices,
        default=StateChoices.STARTED
    )
    collected_data = models.JSONField(
        _("Collected Data"),
        default=dict,
        blank=True,
        help_text="Data collected during the conversation"
    )
    error_message = models.TextField(
        _("Error Message"),
        blank=True,
        null=True,
        help_text="Error details if session failed"
    )

    class Meta(BaseModel.Meta):
        db_table = "conversation_session"
        verbose_name = "Conversation Session"
        verbose_name_plural = "Conversation Sessions"
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self):
        return f"Session {self.session_id} - {self.user.email} ({self.conversation_type})"


class LLMRecommendation(BaseModel, TenantAwareModel):
    """
    Stores LLM-generated recommendations with maker-checker pattern.
    """
    class UserDecisionChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        MODIFIED = "modified", _("Modified")

    # Phase 2: Enhanced status tracking
    class StatusChoices(models.TextChoices):
        QUEUED = "queued", _("Queued")
        PROCESSING = "processing", _("Processing")
        VALIDATED = "validated", _("Validated")
        NEEDS_REVIEW = "needs_review", _("Needs Review")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")

    recommendation_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    session = models.ForeignKey(
        ConversationSession,
        on_delete=models.CASCADE,
        related_name="recommendations",
        verbose_name=_("Session")
    )
    maker_output = models.JSONField(
        _("Maker Output"),
        help_text="Raw output from the maker LLM"
    )
    checker_output = models.JSONField(
        _("Checker Output"),
        null=True,
        blank=True,
        help_text="Validation output from checker LLM"
    )
    consensus = models.JSONField(
        _("Consensus"),
        default=dict,
        blank=True,
        help_text="Final consensus between maker and checker"
    )
    authoritative_sources = models.JSONField(
        _("Authoritative Sources"),
        default=list,
        blank=True,
        help_text="References to authoritative knowledge sources"
    )
    confidence_score = models.FloatField(
        _("Confidence Score"),
        help_text="Overall confidence score (0.0 to 1.0)"
    )
    user_decision = models.CharField(
        _("User Decision"),
        max_length=20,
        choices=UserDecisionChoices.choices,
        default=UserDecisionChoices.PENDING
    )
    rejection_reason = models.TextField(
        _("Rejection Reason"),
        blank=True,
        null=True,
        help_text="Why the user rejected the recommendation"
    )
    modifications = models.JSONField(
        _("Modifications"),
        default=dict,
        blank=True,
        help_text="User modifications to the recommendation"
    )

    # Phase 2: Enhanced tracking and observability
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.QUEUED,
        help_text="Current processing status of the recommendation"
    )
    latency_ms = models.IntegerField(
        _("Latency (ms)"),
        null=True,
        blank=True,
        help_text="Total processing time in milliseconds"
    )
    provider_cost_cents = models.IntegerField(
        _("Provider Cost (cents)"),
        null=True,
        blank=True,
        help_text="Cost of LLM provider calls in cents"
    )
    eval_scores = models.JSONField(
        _("Evaluation Scores"),
        default=dict,
        blank=True,
        help_text="Quality evaluation scores and metrics"
    )
    trace_id = models.CharField(
        _("Trace ID"),
        max_length=50,
        blank=True,
        help_text="Distributed tracing ID for request correlation"
    )

    class Meta(BaseModel.Meta):
        db_table = "llm_recommendation"
        verbose_name = "LLM Recommendation"
        verbose_name_plural = "LLM Recommendations"
        get_latest_by = ["mdtz", "cdtz"]
        indexes = [
            models.Index(fields=['session', 'status'], name='llm_rec_session_status_idx'),
            models.Index(fields=['confidence_score'], name='llm_rec_confidence_idx'),
            models.Index(fields=['trace_id'], name='llm_rec_trace_id_idx'),
            models.Index(fields=['status', 'cdtz'], name='llm_rec_status_created_idx'),
        ]

    def __str__(self):
        return f"Recommendation {self.recommendation_id} - {self.status} - {self.user_decision}"


class AuthoritativeKnowledge(BaseModel, TenantAwareModel):
    """
    Stores authoritative knowledge for LLM grounding and validation.
    """
    class AuthorityLevelChoices(models.TextChoices):
        LOW = "low", _("Low")
        MEDIUM = "medium", _("Medium")
        HIGH = "high", _("High")
        OFFICIAL = "official", _("Official")

    knowledge_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    source_organization = models.CharField(
        _("Source Organization"),
        max_length=200,
        help_text="Organization that published this knowledge"
    )
    document_title = models.CharField(
        _("Document Title"),
        max_length=500,
        help_text="Title of the source document"
    )
    document_version = models.CharField(
        _("Document Version"),
        max_length=50,
        blank=True,
        help_text="Version of the document"
    )
    authority_level = models.CharField(
        _("Authority Level"),
        max_length=20,
        choices=AuthorityLevelChoices.choices,
        default=AuthorityLevelChoices.MEDIUM
    )
    content_vector = ArrayField(
        models.FloatField(),
        verbose_name=_("Content Vector"),
        help_text="Vector embedding of the content",
        null=True,
        blank=True
    )
    content_summary = models.TextField(
        _("Content Summary"),
        help_text="Summary of the knowledge content"
    )
    publication_date = models.DateTimeField(
        _("Publication Date"),
        help_text="When this knowledge was published"
    )
    last_verified = models.DateTimeField(
        _("Last Verified"),
        auto_now=True,
        help_text="When this knowledge was last verified"
    )
    is_current = models.BooleanField(
        _("Is Current"),
        default=True,
        help_text="Whether this knowledge is still current"
    )

    # Enhanced fields from production-grade specification
    source_url = models.URLField(
        _("Source URL"),
        max_length=1000,
        blank=True,
        null=True,
        help_text="Original URL where document was fetched from"
    )
    doc_checksum = models.CharField(
        _("Document Checksum"),
        max_length=64,
        blank=True,
        help_text="SHA-256 checksum of the document content"
    )
    jurisdiction = models.CharField(
        _("Jurisdiction"),
        max_length=100,
        blank=True,
        help_text="Legal or geographical jurisdiction (e.g., 'US', 'EU', 'Global')"
    )
    industry = models.CharField(
        _("Industry"),
        max_length=100,
        blank=True,
        help_text="Industry sector (e.g., 'healthcare', 'finance', 'manufacturing')"
    )
    language = models.CharField(
        _("Language"),
        max_length=10,
        default="en",
        help_text="ISO language code (e.g., 'en', 'es', 'fr')"
    )
    tags = models.JSONField(
        _("Tags"),
        default=dict,
        blank=True,
        help_text="Flexible metadata tags for categorization and filtering"
    )
    ingestion_version = models.IntegerField(
        _("Ingestion Version"),
        default=1,
        help_text="Version of the ingestion pipeline that processed this document"
    )

    class Meta(BaseModel.Meta):
        db_table = "authoritative_knowledge"
        verbose_name = "Authoritative Knowledge"
        verbose_name_plural = "Authoritative Knowledge"
        get_latest_by = ["publication_date", "mdtz"]

    def __str__(self):
        return f"{self.document_title} - {self.source_organization}"


class UserFeedbackLearning(BaseModel, TenantAwareModel):
    """
    Captures user feedback for continuous learning and model improvement.
    """
    class FeedbackTypeChoices(models.TextChoices):
        RECOMMENDATION_QUALITY = "rec_quality", _("Recommendation Quality")
        CONVERSATION_FLOW = "conv_flow", _("Conversation Flow")
        ACCURACY = "accuracy", _("Accuracy")
        COMPLETENESS = "completeness", _("Completeness")
        USABILITY = "usability", _("Usability")
        OTHER = "other", _("Other")

    feedback_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    recommendation = models.ForeignKey(
        LLMRecommendation,
        on_delete=models.CASCADE,
        related_name="feedback",
        verbose_name=_("Recommendation")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedback_given",
        verbose_name=_("User")
    )
    client = models.ForeignKey(
        "Bt",
        on_delete=models.CASCADE,
        related_name="feedback_received",
        verbose_name=_("Client")
    )
    feedback_type = models.CharField(
        _("Feedback Type"),
        max_length=50,
        choices=FeedbackTypeChoices.choices
    )
    feedback_data = models.JSONField(
        _("Feedback Data"),
        help_text="Structured feedback data"
    )
    learning_extracted = models.JSONField(
        _("Learning Extracted"),
        default=dict,
        blank=True,
        help_text="Learning patterns extracted from this feedback"
    )
    applied_to_model = models.BooleanField(
        _("Applied to Model"),
        default=False,
        help_text="Whether this feedback has been applied to improve the model"
    )

    class Meta(BaseModel.Meta):
        db_table = "user_feedback_learning"
        verbose_name = "User Feedback Learning"
        verbose_name_plural = "User Feedback Learning"
        get_latest_by = ["mdtz", "cdtz"]

    def __str__(self):
        return f"Feedback {self.feedback_id} - {self.feedback_type}"


class AuthoritativeKnowledgeChunk(BaseModel, TenantAwareModel):
    """
    Chunked knowledge content for RAG retrieval (Phase 2)
    """
    chunk_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    knowledge = models.ForeignKey(
        AuthoritativeKnowledge,
        on_delete=models.CASCADE,
        related_name="chunks",
        verbose_name=_("Knowledge Document")
    )
    chunk_index = models.IntegerField(
        _("Chunk Index"),
        help_text="Sequential chunk number within the document"
    )
    content_text = models.TextField(
        _("Content Text"),
        help_text="Text content of this chunk"
    )
    content_vector = ArrayField(
        models.FloatField(),
        verbose_name=_("Content Vector"),
        help_text="Vector embedding of the chunk content",
        null=True,
        blank=True
    )
    tags = models.JSONField(
        _("Tags"),
        default=dict,
        blank=True,
        help_text="Metadata tags for filtering and categorization"
    )
    last_verified = models.DateTimeField(
        _("Last Verified"),
        auto_now=True,
        help_text="When this chunk was last verified for accuracy"
    )
    is_current = models.BooleanField(
        _("Is Current"),
        default=True,
        help_text="Whether this chunk is still current and valid"
    )
    # Derived fields for efficient querying
    authority_level = models.CharField(
        _("Authority Level"),
        max_length=20,
        blank=True,
        help_text="Cached authority level from parent knowledge"
    )
    source_organization = models.CharField(
        _("Source Organization"),
        max_length=200,
        blank=True,
        help_text="Cached source organization from parent knowledge"
    )

    class Meta(BaseModel.Meta):
        db_table = "authoritative_knowledge_chunk"
        verbose_name = "Knowledge Chunk"
        verbose_name_plural = "Knowledge Chunks"
        get_latest_by = ["last_verified", "mdtz"]
        indexes = [
            models.Index(fields=['knowledge', 'chunk_index'], name='knowledge_chunk_idx'),
            models.Index(fields=['is_current'], name='chunk_current_idx'),
            models.Index(fields=['authority_level'], name='chunk_authority_idx'),
            models.Index(fields=['source_organization'], name='chunk_source_idx'),
            models.Index(fields=['is_current', 'authority_level'], name='chunk_current_auth_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['knowledge', 'chunk_index'],
                name='knowledge_chunk_unique'
            )
        ]

    def save(self, *args, **kwargs):
        # Cache parent knowledge fields for efficient querying
        if self.knowledge_id:
            self.authority_level = self.knowledge.authority_level
            self.source_organization = self.knowledge.source_organization
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.knowledge.document_title}"

    def get_similarity_score(self, query_vector):
        """Calculate cosine similarity with query vector"""
        if not self.content_vector or not query_vector:
            return 0.0

        import numpy as np
        try:
            chunk_vector = np.array(self.content_vector)
            query_vector_np = np.array(query_vector)

            # Calculate cosine similarity
            dot_product = np.dot(chunk_vector, query_vector_np)
            norm1 = np.linalg.norm(chunk_vector)
            norm2 = np.linalg.norm(query_vector_np)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(dot_product / (norm1 * norm2))
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError):
            return 0.0


# =============================================================================
# PRODUCTION-GRADE KNOWLEDGE BASE MODELS
# =============================================================================


class KnowledgeSource(BaseModel, TenantAwareModel):
    """
    Configurable knowledge sources for document ingestion
    """
    class SourceTypeChoices(models.TextChoices):
        ISO = "iso", _("ISO Standards")
        ASIS = "asis", _("ASIS Guidelines")
        NIST = "nist", _("NIST Framework")
        INTERNAL = "internal", _("Internal SOPs")
        EXTERNAL = "external", _("External Documentation")

    class FetchPolicyChoices(models.TextChoices):
        MANUAL = "manual", _("Manual Upload Only")
        SCHEDULED = "scheduled", _("Scheduled Fetch")
        ON_DEMAND = "on_demand", _("On-Demand Fetch")
        WEBHOOK = "webhook", _("Webhook Triggered")

    source_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(
        _("Source Name"),
        max_length=200,
        help_text="Human-readable name for this knowledge source"
    )
    source_type = models.CharField(
        _("Source Type"),
        max_length=20,
        choices=SourceTypeChoices.choices,
        default=SourceTypeChoices.EXTERNAL
    )
    base_url = models.URLField(
        _("Base URL"),
        max_length=1000,
        blank=True,
        null=True,
        help_text="Base URL for fetching documents from this source"
    )
    auth_config = models.JSONField(
        _("Authentication Configuration"),
        default=dict,
        blank=True,
        help_text="Authentication configuration (API keys, tokens, etc.)"
    )
    jurisdiction = models.CharField(
        _("Jurisdiction"),
        max_length=100,
        blank=True,
        help_text="Legal or geographical jurisdiction coverage"
    )
    industry_tags = models.JSONField(
        _("Industry Tags"),
        default=list,
        blank=True,
        help_text="List of industry sectors this source covers"
    )
    language = models.CharField(
        _("Language"),
        max_length=10,
        default="en",
        help_text="Primary language of documents from this source"
    )
    fetch_policy = models.CharField(
        _("Fetch Policy"),
        max_length=20,
        choices=FetchPolicyChoices.choices,
        default=FetchPolicyChoices.MANUAL
    )
    is_active = models.BooleanField(
        _("Is Active"),
        default=True,
        help_text="Whether this source is active for ingestion"
    )

    # Metadata for monitoring and management
    last_fetch_attempt = models.DateTimeField(
        _("Last Fetch Attempt"),
        null=True,
        blank=True,
        help_text="Timestamp of last fetch attempt"
    )
    last_successful_fetch = models.DateTimeField(
        _("Last Successful Fetch"),
        null=True,
        blank=True,
        help_text="Timestamp of last successful fetch"
    )
    total_documents_fetched = models.IntegerField(
        _("Total Documents Fetched"),
        default=0,
        help_text="Total number of documents successfully fetched"
    )
    fetch_error_count = models.IntegerField(
        _("Fetch Error Count"),
        default=0,
        help_text="Number of consecutive fetch errors"
    )

    class Meta(BaseModel.Meta):
        db_table = "knowledge_source"
        verbose_name = "Knowledge Source"
        verbose_name_plural = "Knowledge Sources"
        get_latest_by = ["mdtz", "cdtz"]
        indexes = [
            models.Index(fields=['source_type', 'is_active'], name='kb_source_type_active_idx'),
            models.Index(fields=['jurisdiction'], name='kb_source_jurisdiction_idx'),
            models.Index(fields=['language'], name='kb_source_language_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.source_type})"


class KnowledgeIngestionJob(BaseModel, TenantAwareModel):
    """
    Tracks document ingestion jobs for async processing pipeline
    """
    class StatusChoices(models.TextChoices):
        QUEUED = "queued", _("Queued")
        FETCHING = "fetching", _("Fetching")
        PARSING = "parsing", _("Parsing")
        CHUNKING = "chunking", _("Chunking")
        EMBEDDING = "embedding", _("Embedding")
        READY = "ready", _("Ready")
        FAILED = "failed", _("Failed")

    job_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    source = models.ForeignKey(
        KnowledgeSource,
        on_delete=models.CASCADE,
        related_name="ingestion_jobs",
        verbose_name=_("Knowledge Source")
    )
    document = models.ForeignKey(
        AuthoritativeKnowledge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingestion_jobs",
        verbose_name=_("Document"),
        help_text="Created document reference (null until document is created)"
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.QUEUED
    )
    source_url = models.URLField(
        _("Source URL"),
        max_length=1000,
        help_text="Specific URL being processed"
    )
    error_log = models.TextField(
        _("Error Log"),
        blank=True,
        help_text="Detailed error information if job failed"
    )

    # Processing metrics and timings
    timings = models.JSONField(
        _("Processing Timings"),
        default=dict,
        blank=True,
        help_text="Timing data for each processing stage"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="initiated_ingestion_jobs",
        verbose_name=_("Created By")
    )

    # Pipeline configuration
    processing_config = models.JSONField(
        _("Processing Configuration"),
        default=dict,
        blank=True,
        help_text="Configuration overrides for this specific job"
    )

    # Results and metrics
    chunks_created = models.IntegerField(
        _("Chunks Created"),
        default=0,
        help_text="Number of chunks created from this document"
    )
    embeddings_generated = models.IntegerField(
        _("Embeddings Generated"),
        default=0,
        help_text="Number of embeddings generated"
    )
    processing_duration_ms = models.IntegerField(
        _("Processing Duration (ms)"),
        null=True,
        blank=True,
        help_text="Total processing time in milliseconds"
    )

    class Meta(BaseModel.Meta):
        db_table = "knowledge_ingestion_job"
        verbose_name = "Knowledge Ingestion Job"
        verbose_name_plural = "Knowledge Ingestion Jobs"
        get_latest_by = ["cdtz"]
        indexes = [
            models.Index(fields=['status', 'cdtz'], name='kb_job_status_created_idx'),
            models.Index(fields=['source', 'status'], name='kb_job_source_status_idx'),
            models.Index(fields=['created_by'], name='kb_job_created_by_idx'),
        ]

    def __str__(self):
        return f"Ingestion Job {self.job_id} - {self.status}"

    def update_status(self, new_status: str, error_message: str = None):
        """Update job status with optional error logging"""
        self.status = new_status
        if error_message:
            self.error_log = error_message
        self.save()

    def record_timing(self, stage: str, duration_ms: int):
        """Record timing for a specific processing stage"""
        if not self.timings:
            self.timings = {}
        self.timings[stage] = duration_ms
        self.save()


class KnowledgeReview(BaseModel, TenantAwareModel):
    """
    Manual review and approval workflow for knowledge documents
    """
    class StatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending Review")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        REQUIRES_CHANGES = "requires_changes", _("Requires Changes")

    review_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    document = models.ForeignKey(
        AuthoritativeKnowledge,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name=_("Document")
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_reviews",
        verbose_name=_("Reviewer")
    )
    status = models.CharField(
        _("Review Status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )
    notes = models.TextField(
        _("Review Notes"),
        blank=True,
        help_text="Reviewer's notes and feedback"
    )
    reviewed_at = models.DateTimeField(
        _("Reviewed At"),
        null=True,
        blank=True,
        help_text="When the review was completed"
    )

    # Review criteria and scores
    accuracy_score = models.FloatField(
        _("Accuracy Score"),
        null=True,
        blank=True,
        help_text="Reviewer's accuracy assessment (0.0-1.0)"
    )
    completeness_score = models.FloatField(
        _("Completeness Score"),
        null=True,
        blank=True,
        help_text="Reviewer's completeness assessment (0.0-1.0)"
    )
    relevance_score = models.FloatField(
        _("Relevance Score"),
        null=True,
        blank=True,
        help_text="Reviewer's relevance assessment (0.0-1.0)"
    )

    # Detailed feedback
    feedback_data = models.JSONField(
        _("Detailed Feedback"),
        default=dict,
        blank=True,
        help_text="Structured feedback data"
    )

    # Approval metadata
    approved_for_publication = models.BooleanField(
        _("Approved for Publication"),
        default=False,
        help_text="Whether document is approved for use in RAG pipeline"
    )
    approval_conditions = models.TextField(
        _("Approval Conditions"),
        blank=True,
        help_text="Any conditions or limitations on the approval"
    )

    class Meta(BaseModel.Meta):
        db_table = "knowledge_review"
        verbose_name = "Knowledge Review"
        verbose_name_plural = "Knowledge Reviews"
        get_latest_by = ["reviewed_at", "mdtz"]
        indexes = [
            models.Index(fields=['document', 'status'], name='kb_review_doc_status_idx'),
            models.Index(fields=['reviewer'], name='kb_review_reviewer_idx'),
            models.Index(fields=['status', 'reviewed_at'], name='kb_review_status_date_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'reviewer'],
                name='kb_review_unique_per_reviewer',
                condition=models.Q(status__in=['pending', 'approved'])
            )
        ]

    def __str__(self):
        return f"Review of {self.document.document_title} by {self.reviewer.email} - {self.status}"

    def approve(self, notes: str = "", conditions: str = ""):
        """Mark review as approved"""
        self.status = self.StatusChoices.APPROVED
        self.approved_for_publication = True
        self.reviewed_at = timezone.now()
        if notes:
            self.notes = notes
        if conditions:
            self.approval_conditions = conditions
        self.save()

    def reject(self, notes: str):
        """Mark review as rejected"""
        self.status = self.StatusChoices.REJECTED
        self.reviewed_at = timezone.now()
        self.notes = notes
        self.approved_for_publication = False
        self.save()


# Update AuthoritativeKnowledgeChunk model with additional fields for enhanced chunking
class AuthoritativeKnowledgeChunkEnhanced(AuthoritativeKnowledgeChunk):
    """
    Extended chunk model with additional Phase 2+ enhancements
    """
    # Additional fields for Phase 2+
    section_heading = models.CharField(
        _("Section Heading"),
        max_length=500,
        blank=True,
        help_text="Section or chapter heading this chunk belongs to"
    )
    page_start = models.IntegerField(
        _("Page Start"),
        null=True,
        blank=True,
        help_text="Starting page number of this chunk"
    )
    page_end = models.IntegerField(
        _("Page End"),
        null=True,
        blank=True,
        help_text="Ending page number of this chunk"
    )
    chunk_checksum = models.CharField(
        _("Chunk Checksum"),
        max_length=64,
        blank=True,
        help_text="SHA-256 checksum of chunk content for deduplication"
    )

    class Meta:
        proxy = True
        verbose_name = "Enhanced Knowledge Chunk"
        verbose_name_plural = "Enhanced Knowledge Chunks"


# =============================================================================
# AI RECOMMENDATION CHANGE TRACKING AND ROLLBACK MODELS
# =============================================================================


class AIChangeSet(BaseModel, TenantAwareModel):
    """
    Tracks all changes applied by AI recommendations for rollback capabilities.

    This model provides a comprehensive audit trail and rollback mechanism
    for all AI-generated changes to business-critical data.
    """

    class StatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPLIED = "applied", _("Applied")
        ROLLED_BACK = "rolled_back", _("Rolled Back")
        FAILED = "failed", _("Failed")
        PARTIALLY_APPLIED = "partially_applied", _("Partially Applied")

    # Primary identification
    changeset_id = models.UUIDField(primary_key=True, default=uuid.uuid4)

    # Link to conversation session
    conversation_session = models.ForeignKey(
        ConversationSession,
        on_delete=models.CASCADE,
        related_name="changesets",
        verbose_name=_("Conversation Session")
    )

    # User who approved the changes
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_changesets",
        verbose_name=_("Approved By")
    )

    # User who rolled back (if applicable)
    rolled_back_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="rolled_back_changesets",
        verbose_name=_("Rolled Back By")
    )

    # Status and timestamps
    status = models.CharField(
        _("Status"),
        max_length=50,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )

    applied_at = models.DateTimeField(
        _("Applied At"),
        null=True,
        blank=True
    )

    rolled_back_at = models.DateTimeField(
        _("Rolled Back At"),
        null=True,
        blank=True
    )

    # Change metadata
    description = models.TextField(
        _("Description"),
        help_text="Human-readable description of changes"
    )

    total_changes = models.PositiveIntegerField(
        _("Total Changes"),
        default=0
    )

    successful_changes = models.PositiveIntegerField(
        _("Successful Changes"),
        default=0
    )

    failed_changes = models.PositiveIntegerField(
        _("Failed Changes"),
        default=0
    )

    # Rollback metadata
    rollback_reason = models.TextField(
        _("Rollback Reason"),
        null=True,
        blank=True,
        help_text="Reason for rolling back changes"
    )

    # Extended metadata
    metadata = models.JSONField(
        _("Additional Metadata"),
        default=dict,
        blank=True,
        help_text="Additional contextual information"
    )

    def can_rollback(self):
        """Check if changeset can be rolled back"""
        return (
            self.status in [self.StatusChoices.APPLIED, self.StatusChoices.PARTIALLY_APPLIED] and
            self.rolled_back_at is None
        )

    def get_rollback_complexity(self):
        """Assess rollback complexity"""
        if not self.can_rollback():
            return "not_available"

        # Count dependent changes
        dependent_count = AIChangeRecord.objects.filter(
            changeset=self,
            has_dependencies=True
        ).count()

        if dependent_count == 0:
            return "simple"
        elif dependent_count <= 5:
            return "moderate"
        else:
            return "complex"

    def calculate_risk_score(self):
        """
        Calculate risk score for this changeset to determine if two-person approval is needed.

        Risk factors:
        - Number of changes (high volume = higher risk)
        - Types of entities being modified
        - Critical system configurations
        - User permissions being modified

        Returns:
            float: Risk score from 0.0 (low risk) to 1.0 (high risk)
        """
        risk_score = 0.0

        # Factor 1: Volume of changes (0.0 - 0.3)
        if self.total_changes > 20:
            risk_score += 0.3
        elif self.total_changes > 10:
            risk_score += 0.2
        elif self.total_changes > 5:
            risk_score += 0.1

        # Factor 2: Failed changes indicate complexity (0.0 - 0.2)
        if self.total_changes > 0:
            failure_rate = self.failed_changes / self.total_changes
            risk_score += failure_rate * 0.2

        # Factor 3: Entity-specific risk scoring (0.0 - 0.3)
        entity_risks = self.get_entity_risk_breakdown()
        max_entity_risk = max(entity_risks.values()) if entity_risks else 0.0
        risk_score += max_entity_risk * 0.3

        # Factor 4: System-wide impact (0.0 - 0.2)
        if self.affects_system_wide_settings():
            risk_score += 0.2
        elif self.affects_multiple_tenants():
            risk_score += 0.1

        return min(1.0, risk_score)  # Cap at 1.0

    def get_entity_risk_breakdown(self):
        """Get risk scores by entity type"""
        from django.db.models import Count

        # Define risk levels for different entity types
        ENTITY_RISK_LEVELS = {
            'bt': 0.8,  # High risk - affects business units
            'shift': 0.6,  # Medium-high risk - affects scheduling
            'typeassist': 0.4,  # Medium risk - affects categorization
            'device': 0.3,  # Low-medium risk
            'subscription': 0.2,  # Low risk
        }

        entity_counts = self.change_records.values('model_name').annotate(
            count=Count('id')
        )

        entity_risks = {}
        for entity in entity_counts:
            model_name = entity['model_name'].lower()
            count = entity['count']
            base_risk = ENTITY_RISK_LEVELS.get(model_name, 0.1)

            # Scale risk by count (more changes = higher risk)
            scaled_risk = min(1.0, base_risk + (count - 1) * 0.1)
            entity_risks[model_name] = scaled_risk

        return entity_risks

    def affects_system_wide_settings(self):
        """Check if changeset affects system-wide settings"""
        # Check for changes to critical system entities
        critical_changes = self.change_records.filter(
            model_name__in=['bt'],  # Business units can be system-wide
            object_id='1'  # Often root/system objects have ID 1
        )
        return critical_changes.exists()

    def affects_multiple_tenants(self):
        """Check if changeset affects multiple tenants"""
        # Count distinct clients affected by the changes
        try:
            # This would need to be implemented based on your specific tenant model structure
            # For now, return False as a safe default
            return False
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError):
            return False

    def requires_two_person_approval(self):
        """Determine if this changeset requires two-person approval"""
        from django.conf import settings

        # Get risk threshold from settings (default 0.7)
        risk_threshold = getattr(settings, 'ONBOARDING_TWO_PERSON_THRESHOLD', 0.7)

        risk_score = self.calculate_risk_score()
        return risk_score >= risk_threshold

    def get_required_approvers_count(self):
        """Get the number of approvers required for this changeset"""
        if self.requires_two_person_approval():
            return 2
        return 1

    def get_approval_status(self):
        """
        Get current approval status for this changeset.

        Returns:
            dict: Approval status information
        """
        required_approvers = self.get_required_approvers_count()
        approved_count = self.approvals.filter(
            status=ChangeSetApproval.StatusChoices.APPROVED
        ).count()
        rejected_count = self.approvals.filter(
            status=ChangeSetApproval.StatusChoices.REJECTED
        ).count()
        pending_count = self.approvals.filter(
            status=ChangeSetApproval.StatusChoices.PENDING
        ).count()

        is_fully_approved = approved_count >= required_approvers
        is_rejected = rejected_count > 0
        needs_more_approvals = approved_count < required_approvers and not is_rejected

        return {
            'required_approvers': required_approvers,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'pending_count': pending_count,
            'is_fully_approved': is_fully_approved,
            'is_rejected': is_rejected,
            'needs_more_approvals': needs_more_approvals,
            'risk_score': self.calculate_risk_score(),
            'requires_two_person': self.requires_two_person_approval()
        }

    def can_be_applied(self):
        """Check if changeset has sufficient approvals to be applied"""
        approval_status = self.get_approval_status()
        return (
            approval_status['is_fully_approved'] and
            not approval_status['is_rejected'] and
            self.status == self.StatusChoices.PENDING
        )

    def create_approval_request(self, approver, approval_level=None, request_meta=None):
        """
        Create an approval request for this changeset.

        Args:
            approver: User who will approve
            approval_level: Level of approval (primary/secondary/escalated)
            request_meta: Request metadata for audit trail

        Returns:
            ChangeSetApproval: Created approval object
        """
        if approval_level is None:
            # Determine approval level based on existing approvals
            existing_approvals = self.approvals.count()
            if existing_approvals == 0:
                approval_level = ChangeSetApproval.ApprovalLevelChoices.PRIMARY
            else:
                approval_level = ChangeSetApproval.ApprovalLevelChoices.SECONDARY

        # Check if approval already exists for this user
        existing_approval = self.approvals.filter(approver=approver).first()
        if existing_approval:
            return existing_approval

        approval = ChangeSetApproval.objects.create(
            changeset=self,
            approver=approver,
            approval_level=approval_level,
            ip_address=request_meta.get('ip_address') if request_meta else None,
            user_agent=request_meta.get('user_agent') if request_meta else None,
            correlation_id=request_meta.get('correlation_id') if request_meta else None
        )

        return approval

    def get_next_required_approver_level(self):
        """Get the next required approval level"""
        approval_status = self.get_approval_status()

        if approval_status['approved_count'] == 0:
            return ChangeSetApproval.ApprovalLevelChoices.PRIMARY
        elif approval_status['needs_more_approvals']:
            return ChangeSetApproval.ApprovalLevelChoices.SECONDARY
        else:
            return None  # No more approvals needed

    def get_eligible_secondary_approvers(self, primary_approver):
        """
        Get users eligible to be secondary approvers.

        Args:
            primary_approver: The primary approver (to exclude from secondary)

        Returns:
            QuerySet: Users eligible for secondary approval
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Get users with approval permissions, excluding the primary approver
        eligible_approvers = User.objects.filter(
            capabilities__can_approve_ai_recommendations=True,
            client=self.conversation_session.client
        ).exclude(id=primary_approver.id)

        return eligible_approvers

    def auto_assign_secondary_approver(self, primary_approver, request_meta=None):
        """
        Automatically assign a secondary approver for high-risk changesets.

        Args:
            primary_approver: The primary approver
            request_meta: Request metadata for audit

        Returns:
            ChangeSetApproval or None: Created secondary approval if successful
        """
        if not self.requires_two_person_approval():
            return None

        eligible_approvers = self.get_eligible_secondary_approvers(primary_approver)

        if not eligible_approvers.exists():
            # Log warning - no eligible secondary approvers available
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"No eligible secondary approvers found for changeset {self.changeset_id}"
            )
            return None

        # Select the first available secondary approver
        # In a production system, you might implement more sophisticated logic
        secondary_approver = eligible_approvers.first()

        return self.create_approval_request(
            approver=secondary_approver,
            approval_level=ChangeSetApproval.ApprovalLevelChoices.SECONDARY,
            request_meta=request_meta
        )

    def __str__(self):
        return f"ChangeSet {self.changeset_id} - {self.status} ({self.total_changes} changes)"

    class Meta:
        verbose_name = "AI Change Set"
        verbose_name_plural = "AI Change Sets"
        db_table = "onboarding_ai_changeset"
        ordering = ['-cdtz']


class ChangeSetApproval(BaseModel):
    """
    Tracks individual approvals for changesets implementing two-person rule.

    For high-risk changesets, multiple approvals are required before changes
    can be applied to production systems.
    """

    class StatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        ESCALATED = "escalated", _("Escalated")

    class ApprovalLevelChoices(models.TextChoices):
        PRIMARY = "primary", _("Primary Approver")
        SECONDARY = "secondary", _("Secondary Approver")
        ESCALATED = "escalated", _("Escalated Approver")

    # Link to changeset
    changeset = models.ForeignKey(
        AIChangeSet,
        on_delete=models.CASCADE,
        related_name="approvals",
        verbose_name=_("Change Set")
    )

    # Approver details
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="changeset_approvals",
        verbose_name=_("Approver")
    )

    # Approval metadata
    approval_level = models.CharField(
        _("Approval Level"),
        max_length=20,
        choices=ApprovalLevelChoices.choices,
        default=ApprovalLevelChoices.PRIMARY
    )

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )

    # Decision details
    decision_at = models.DateTimeField(
        _("Decision At"),
        null=True,
        blank=True
    )

    decision_reason = models.TextField(
        _("Decision Reason"),
        blank=True,
        help_text="Reason for approval, rejection, or escalation"
    )

    # Risk assessment
    risk_assessment = models.JSONField(
        _("Risk Assessment"),
        default=dict,
        blank=True,
        help_text="Approver's risk assessment and concerns"
    )

    # Conditions and modifications
    approval_conditions = models.TextField(
        _("Approval Conditions"),
        blank=True,
        help_text="Any conditions or limitations on the approval"
    )

    requested_modifications = models.JSONField(
        _("Requested Modifications"),
        default=dict,
        blank=True,
        help_text="Modifications requested by the approver"
    )

    # Audit trail
    ip_address = models.GenericIPAddressField(
        _("IP Address"),
        null=True,
        blank=True
    )

    user_agent = models.TextField(
        _("User Agent"),
        blank=True
    )

    correlation_id = models.CharField(
        _("Correlation ID"),
        max_length=50,
        blank=True,
        help_text="Request correlation ID for audit purposes"
    )

    def is_approved(self):
        """Check if this approval is approved"""
        return self.status == self.StatusChoices.APPROVED

    def is_rejected(self):
        """Check if this approval is rejected"""
        return self.status == self.StatusChoices.REJECTED

    def is_pending(self):
        """Check if this approval is still pending"""
        return self.status == self.StatusChoices.PENDING

    def approve(self, reason="", conditions="", modifications=None):
        """Mark this approval as approved"""
        self.status = self.StatusChoices.APPROVED
        self.decision_at = timezone.now()
        self.decision_reason = reason
        self.approval_conditions = conditions
        if modifications:
            self.requested_modifications = modifications
        self.save()

    def reject(self, reason=""):
        """Mark this approval as rejected"""
        self.status = self.StatusChoices.REJECTED
        self.decision_at = timezone.now()
        self.decision_reason = reason
        self.save()

    def escalate(self, reason=""):
        """Mark this approval as escalated"""
        self.status = self.StatusChoices.ESCALATED
        self.decision_at = timezone.now()
        self.decision_reason = reason
        self.save()

    def __str__(self):
        return f"Approval {self.id} - {self.approver.email} - {self.status}"

    class Meta:
        verbose_name = "ChangeSet Approval"
        verbose_name_plural = "ChangeSet Approvals"
        db_table = "onboarding_changeset_approval"
        ordering = ['-cdtz']
        constraints = [
            models.UniqueConstraint(
                fields=['changeset', 'approver'],
                name='unique_approval_per_user_changeset'
            )
        ]


class AIChangeRecord(BaseModel):
    """
    Individual change record within a changeset.

    Stores detailed before/after state for each modified object,
    enabling granular rollback operations.
    """

    class ActionChoices(models.TextChoices):
        CREATE = "create", _("Create")
        UPDATE = "update", _("Update")
        DELETE = "delete", _("Delete")

    class StatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending")
        SUCCESS = "success", _("Success")
        FAILED = "failed", _("Failed")
        ROLLED_BACK = "rolled_back", _("Rolled Back")

    # Link to parent changeset
    changeset = models.ForeignKey(
        AIChangeSet,
        on_delete=models.CASCADE,
        related_name="change_records",
        verbose_name=_("Change Set")
    )

    # Record identification
    record_id = models.UUIDField(default=uuid.uuid4, unique=True)
    sequence_order = models.PositiveIntegerField(_("Sequence Order"))

    # Target model information
    model_name = models.CharField(_("Model Name"), max_length=100)
    app_label = models.CharField(_("App Label"), max_length=100)
    object_id = models.CharField(_("Object ID"), max_length=100)

    # Change details
    action = models.CharField(
        _("Action"),
        max_length=20,
        choices=ActionChoices.choices
    )

    # State tracking
    before_state = models.JSONField(
        _("Before State"),
        null=True,
        blank=True,
        help_text="Object state before change (for UPDATE/DELETE)"
    )

    after_state = models.JSONField(
        _("After State"),
        null=True,
        blank=True,
        help_text="Object state after change (for CREATE/UPDATE)"
    )

    # Change metadata
    field_changes = models.JSONField(
        _("Field Changes"),
        default=dict,
        help_text="Specific field-level changes"
    )

    # Status and error handling
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING
    )

    error_message = models.TextField(
        _("Error Message"),
        null=True,
        blank=True
    )

    # Dependencies and relationships
    has_dependencies = models.BooleanField(
        _("Has Dependencies"),
        default=False,
        help_text="Whether this change affects related objects"
    )

    dependency_info = models.JSONField(
        _("Dependency Information"),
        default=dict,
        blank=True
    )

    # Rollback tracking
    rollback_attempted_at = models.DateTimeField(
        _("Rollback Attempted At"),
        null=True,
        blank=True
    )

    rollback_success = models.BooleanField(
        _("Rollback Success"),
        null=True,
        blank=True
    )

    rollback_error = models.TextField(
        _("Rollback Error"),
        null=True,
        blank=True
    )

    def can_rollback(self):
        """Check if this individual record can be rolled back"""
        return (
            self.status == self.StatusChoices.SUCCESS and
            self.changeset.can_rollback() and
            self.rollback_attempted_at is None
        )

    def get_target_model(self):
        """Get the Django model class for this record"""
        try:
            from django.apps import apps
            return apps.get_model(self.app_label, self.model_name)
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError):
            return None

    def get_target_object(self):
        """Get the actual object instance (if it exists)"""
        model_class = self.get_target_model()
        if not model_class:
            return None

        try:
            return model_class.objects.get(pk=self.object_id)
        except model_class.DoesNotExist:
            return None

    def __str__(self):
        return f"Change {self.record_id}: {self.action} {self.model_name}({self.object_id})"

    class Meta:
        verbose_name = "AI Change Record"
        verbose_name_plural = "AI Change Records"
        db_table = "onboarding_ai_change_record"
        ordering = ['changeset', 'sequence_order']
        unique_together = [['changeset', 'sequence_order']]


# =============================================================================
# PERSONALIZATION AND EXPERIMENTATION MODELS
# =============================================================================


class PreferenceProfile(BaseModel, TenantAwareModel):
    """
    User/tenant preference modeling for personalized recommendations
    """
    profile_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="preference_profiles",
        verbose_name=_("User"),
        help_text="User this profile belongs to (null for tenant-wide profiles)"
    )
    client = models.ForeignKey(
        "Bt",
        on_delete=models.CASCADE,
        related_name="preference_profiles",
        verbose_name=_("Client"),
        help_text="Tenant/client this profile belongs to"
    )

    # Preference vector for ML-based personalization
    preference_vector = ArrayField(
        models.FloatField(),
        verbose_name=_("Preference Vector"),
        help_text="Vector embedding of user preferences",
        null=True,
        blank=True,
        size=128  # Standard embedding dimension
    )

    # Structured preference weights
    weights = models.JSONField(
        _("Preference Weights"),
        default=dict,
        blank=True,
        help_text="Structured preference weights and settings"
    )

    # Learning statistics
    stats = models.JSONField(
        _("Learning Statistics"),
        default=dict,
        blank=True,
        help_text="Approval rates, rejection reasons, timing stats, etc."
    )

    last_updated = models.DateTimeField(
        _("Last Updated"),
        auto_now=True,
        help_text="When preferences were last updated"
    )

    class Meta(BaseModel.Meta):
        db_table = "preference_profile"
        verbose_name = "Preference Profile"
        verbose_name_plural = "Preference Profiles"
        get_latest_by = ["last_updated", "mdtz"]
        indexes = [
            models.Index(fields=['client', 'user'], name='pref_client_user_idx'),
            models.Index(fields=['last_updated'], name='pref_last_updated_idx'),
            models.Index(fields=['client', 'last_updated'], name='pref_client_updated_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['client', 'user'],
                name='unique_preference_per_user_client'
            )
        ]

    def __str__(self):
        user_str = self.user.email if self.user else "Tenant-wide"
        return f"Preferences: {user_str} - {self.client.bucode}"

    def get_preference_weight(self, key: str, default: float = 0.5) -> float:
        """Get a preference weight with fallback to default"""
        return self.weights.get(key, default)

    def update_stats(self, event_type: str, metadata: dict = None):
        """Update learning statistics"""
        if not self.stats:
            self.stats = {}

        # Initialize counters
        for stat in ['approvals', 'rejections', 'modifications', 'escalations']:
            if stat not in self.stats:
                self.stats[stat] = 0

        # Update counter
        if event_type in self.stats:
            self.stats[event_type] += 1

        # Update detailed stats
        if metadata:
            if 'details' not in self.stats:
                self.stats['details'] = {}
            self.stats['details'][event_type] = self.stats['details'].get(event_type, [])
            self.stats['details'][event_type].append({
                'timestamp': timezone.now().isoformat(),
                'metadata': metadata
            })
            # Keep only last 10 entries per event type
            self.stats['details'][event_type] = self.stats['details'][event_type][-10:]

        self.save()

    def calculate_acceptance_rate(self) -> float:
        """Calculate overall acceptance rate"""
        if not self.stats:
            return 0.0

        approvals = self.stats.get('approvals', 0)
        total = sum([
            approvals,
            self.stats.get('rejections', 0),
            self.stats.get('modifications', 0)
        ])

        return approvals / total if total > 0 else 0.0


class RecommendationInteraction(BaseModel, TenantAwareModel):
    """
    Captures raw learning signals from user interactions with recommendations
    """
    class EventTypeChoices(models.TextChoices):
        VIEWED = "viewed", _("Viewed")
        CLICKED_DETAIL = "clicked_detail", _("Clicked Detail")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        MODIFIED = "modified", _("Modified")
        ESCALATED = "escalated", _("Escalated")
        TIME_OUT = "timeout", _("Timed Out")
        ABANDONED = "abandoned", _("Abandoned")

    interaction_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    session = models.ForeignKey(
        ConversationSession,
        on_delete=models.CASCADE,
        related_name="interactions",
        verbose_name=_("Session")
    )
    recommendation = models.ForeignKey(
        LLMRecommendation,
        on_delete=models.CASCADE,
        related_name="interactions",
        verbose_name=_("Recommendation")
    )
    event_type = models.CharField(
        _("Event Type"),
        max_length=20,
        choices=EventTypeChoices.choices
    )

    # Rich interaction metadata
    metadata = models.JSONField(
        _("Interaction Metadata"),
        default=dict,
        blank=True,
        help_text="Time on item, scroll depth, reason codes, token usage, etc."
    )

    occurred_at = models.DateTimeField(
        _("Occurred At"),
        auto_now_add=True,
        help_text="When the interaction occurred"
    )

    class Meta(BaseModel.Meta):
        db_table = "recommendation_interaction"
        verbose_name = "Recommendation Interaction"
        verbose_name_plural = "Recommendation Interactions"
        get_latest_by = ["occurred_at"]
        indexes = [
            models.Index(fields=['session', 'event_type'], name='interact_session_event_idx'),
            models.Index(fields=['recommendation', 'event_type'], name='interact_rec_event_idx'),
            models.Index(fields=['occurred_at'], name='interact_occurred_idx'),
            models.Index(fields=['event_type', 'occurred_at'], name='interact_event_time_idx'),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.recommendation.recommendation_id} at {self.occurred_at}"

    def get_time_to_decision(self) -> float:
        """Get time from recommendation creation to this interaction in seconds"""
        if self.event_type in ['approved', 'rejected', 'modified', 'escalated']:
            time_diff = self.occurred_at - self.recommendation.cdtz
            return time_diff.total_seconds()
        return 0.0

    def extract_features(self) -> dict:
        """Extract features for ML learning"""
        features = {
            'event_type': self.event_type,
            'time_to_decision': self.get_time_to_decision(),
            'session_type': self.session.conversation_type,
            'user_is_staff': self.session.user.is_staff if self.session.user else False,
        }

        # Add metadata features
        if self.metadata:
            features.update({
                'time_on_item': self.metadata.get('time_on_item', 0),
                'scroll_depth': self.metadata.get('scroll_depth', 0.0),
                'token_usage': self.metadata.get('token_usage', 0),
                'cost_estimate': self.metadata.get('cost_estimate', 0.0),
            })

        return features


class Experiment(BaseModel, TenantAwareModel):
    """
    A/B testing and multi-armed bandit experiments for personalization
    """
    class StatusChoices(models.TextChoices):
        DRAFT = "draft", _("Draft")
        RUNNING = "running", _("Running")
        PAUSED = "paused", _("Paused")
        COMPLETED = "completed", _("Completed")
        ARCHIVED = "archived", _("Archived")

    class ScopeChoices(models.TextChoices):
        GLOBAL = "global", _("Global")
        TENANT = "tenant", _("Tenant")
        USER_SEGMENT = "user_segment", _("User Segment")

    experiment_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(
        _("Experiment Name"),
        max_length=200,
        help_text="Human-readable experiment name"
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text="Detailed experiment description and objectives"
    )
    scope = models.CharField(
        _("Scope"),
        max_length=20,
        choices=ScopeChoices.choices,
        default=ScopeChoices.TENANT
    )

    # Experiment arms configuration
    arms = models.JSONField(
        _("Experiment Arms"),
        help_text="Configuration for each experiment arm (A/B variants)"
    )

    # Metrics and evaluation
    primary_metric = models.CharField(
        _("Primary Metric"),
        max_length=50,
        default="acceptance_rate",
        help_text="Primary metric to optimize (acceptance_rate, time_to_approval, cost_per_accepted)"
    )
    secondary_metrics = models.JSONField(
        _("Secondary Metrics"),
        default=list,
        blank=True,
        help_text="Additional metrics to track"
    )

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT
    )

    # Traffic allocation
    holdback_pct = models.FloatField(
        _("Holdback Percentage"),
        default=10.0,
        help_text="Percentage of traffic to hold back as control group"
    )

    # Ownership and governance
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_experiments",
        verbose_name=_("Owner")
    )

    # Experiment lifecycle
    started_at = models.DateTimeField(
        _("Started At"),
        null=True,
        blank=True,
        help_text="When experiment was started"
    )
    ended_at = models.DateTimeField(
        _("Ended At"),
        null=True,
        blank=True,
        help_text="When experiment was ended"
    )

    # Safety constraints
    safety_constraints = models.JSONField(
        _("Safety Constraints"),
        default=dict,
        blank=True,
        help_text="Safety thresholds and constraints"
    )

    # Results and analysis
    results = models.JSONField(
        _("Experiment Results"),
        default=dict,
        blank=True,
        help_text="Statistical analysis and results"
    )

    class Meta(BaseModel.Meta):
        db_table = "experiment"
        verbose_name = "Experiment"
        verbose_name_plural = "Experiments"
        get_latest_by = ["started_at", "cdtz"]
        indexes = [
            models.Index(fields=['status', 'scope'], name='exp_status_scope_idx'),
            models.Index(fields=['owner'], name='exp_owner_idx'),
            models.Index(fields=['started_at'], name='exp_started_idx'),
            models.Index(fields=['primary_metric', 'status'], name='exp_metric_status_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"

    def is_active(self) -> bool:
        """Check if experiment is currently active"""
        return self.status == self.StatusChoices.RUNNING

    def get_arm_count(self) -> int:
        """Get number of experiment arms"""
        return len(self.arms) if self.arms else 0

    def get_traffic_allocation(self) -> dict:
        """Get current traffic allocation across arms"""
        if not self.arms:
            return {}

        arm_count = len(self.arms)
        available_traffic = 100.0 - self.holdback_pct
        per_arm_traffic = available_traffic / arm_count

        allocation = {'control': self.holdback_pct}
        for i, arm in enumerate(self.arms):
            allocation[f"arm_{i}"] = per_arm_traffic

        return allocation

    def check_safety_constraints(self, arm_performance: dict) -> list:
        """Check if any safety constraints are violated"""
        violations = []

        if not self.safety_constraints:
            return violations

        # Check error rate constraints
        max_error_rate = self.safety_constraints.get('max_error_rate', 0.1)
        for arm, perf in arm_performance.items():
            if perf.get('error_rate', 0) > max_error_rate:
                violations.append(f"Arm {arm} error rate {perf['error_rate']:.2%} exceeds limit {max_error_rate:.2%}")

        # Check complaint rate constraints
        max_complaint_rate = self.safety_constraints.get('max_complaint_rate', 0.05)
        for arm, perf in arm_performance.items():
            if perf.get('complaint_rate', 0) > max_complaint_rate:
                violations.append(f"Arm {arm} complaint rate {perf['complaint_rate']:.2%} exceeds limit {max_complaint_rate:.2%}")

        # Check daily spend constraints
        max_daily_spend = self.safety_constraints.get('max_daily_spend_cents', 10000)
        for arm, perf in arm_performance.items():
            if perf.get('daily_spend_cents', 0) > max_daily_spend:
                violations.append(f"Arm {arm} daily spend ${perf['daily_spend_cents']/100:.2f} exceeds limit ${max_daily_spend/100:.2f}")

        return violations

    def update_results(self, new_results: dict):
        """Update experiment results with new data"""
        if not self.results:
            self.results = {}

        self.results.update({
            'last_updated': timezone.now().isoformat(),
            'metrics': new_results,
            'statistical_significance': new_results.get('statistical_significance', False)
        })
        self.save()


class ExperimentAssignment(BaseModel, TenantAwareModel):
    """
    Tracks experiment arm assignments for users/clients
    """
    assignment_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name=_("Experiment")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="experiment_assignments",
        verbose_name=_("User"),
        help_text="User assigned to experiment arm (null for client-level assignment)"
    )
    client = models.ForeignKey(
        "Bt",
        on_delete=models.CASCADE,
        related_name="experiment_assignments",
        verbose_name=_("Client")
    )
    arm = models.CharField(
        _("Experiment Arm"),
        max_length=50,
        help_text="Which arm/variant this user/client is assigned to"
    )
    assigned_at = models.DateTimeField(
        _("Assigned At"),
        auto_now_add=True,
        help_text="When assignment was made"
    )
    expires_at = models.DateTimeField(
        _("Expires At"),
        null=True,
        blank=True,
        help_text="When assignment expires (null = never expires)"
    )

    # Assignment metadata
    assignment_context = models.JSONField(
        _("Assignment Context"),
        default=dict,
        blank=True,
        help_text="Context data used for assignment decision"
    )

    class Meta(BaseModel.Meta):
        db_table = "experiment_assignment"
        verbose_name = "Experiment Assignment"
        verbose_name_plural = "Experiment Assignments"
        get_latest_by = ["assigned_at"]
        indexes = [
            models.Index(fields=['experiment', 'user'], name='exp_assign_exp_user_idx'),
            models.Index(fields=['experiment', 'client'], name='exp_assign_exp_client_idx'),
            models.Index(fields=['user', 'assigned_at'], name='exp_assign_user_date_idx'),
            models.Index(fields=['client', 'assigned_at'], name='exp_assign_client_date_idx'),
            models.Index(fields=['expires_at'], name='exp_assign_expires_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['experiment', 'user', 'client'],
                name='unique_experiment_assignment_per_user',
                condition=models.Q(user__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['experiment', 'client'],
                name='unique_experiment_assignment_per_client',
                condition=models.Q(user__isnull=True)
            )
        ]

    def __str__(self):
        user_str = self.user.email if self.user else f"Client {self.client.bucode}"
        return f"{self.experiment.name} - {user_str} -> {self.arm}"

    def is_active(self) -> bool:
        """Check if assignment is still active"""
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return self.experiment.is_active()

    def get_arm_config(self) -> dict:
        """Get configuration for assigned arm"""
        if not self.experiment.arms:
            return {}

        for arm_config in self.experiment.arms:
            if arm_config.get('name') == self.arm:
                return arm_config

        return {}


# Enhanced LLMRecommendation fields for personalization tracking
# Add these fields to existing LLMRecommendation model via migration

def add_personalization_fields_to_llm_recommendation():
    """
    Migration helper to add personalization fields to existing LLMRecommendation model
    These fields should be added via Django migration:

    provider_used = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="LLM provider used for this recommendation"
    )

    token_usage = models.JSONField(
        default=dict,
        blank=True,
        help_text="Token usage breakdown by provider and stage"
    )

    applied_policy_version = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Version of policy template applied"
    )

    experiment_arm = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Experiment arm this recommendation was generated under"
    )
    """
    pass
