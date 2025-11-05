"""
Jobneed Model - Work Execution Instance

Concrete instance generated from Job based on schedule OR created adhoc.
Tracks execution state, timing, assignments, completion.
Represents one specific execution instance with actual start/end times.
"""

import uuid
from django.conf import settings
from django.contrib.gis.db.models import LineStringField, PointField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _
from concurrency.fields import VersionField

from apps.activity.managers.job import JobneedManager
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from apps.core import utils


def other_info():
    """Default JSON structure for Jobneed.other_info field"""
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
    """Default GeoJSON structure"""
    return {"gpslocation": ""}


class Jobneed(BaseModel, TenantAwareModel):
    """
    Jobneed - Concrete execution instance

    Generated from Job based on schedule OR created adhoc.
    Parent relationships: parent=NULL means parent jobneed; parent=Jobneed means child checkpoint.
    Has 1-to-many relationship with Job (via related_name='jobs').
    """

    # Import enums locally to avoid circular imports
    from .enums import JobneedIdentifier, Priority, ScanType, Frequency, JobStatus, JobType

    # Expose enums as nested classes for backward compatibility
    Priority = Priority
    Identifier = JobneedIdentifier
    Scantype = ScanType
    JobStatus = JobStatus
    JobType = JobType
    Frequency = Frequency

    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    jobdesc = models.CharField(_("Job Description"), max_length=200)
    plandatetime = models.DateTimeField(_("Plan date time"), auto_now=False, auto_now_add=False, null=True)
    expirydatetime = models.DateTimeField(_("Expiry date time"), auto_now=False, auto_now_add=False, null=True)
    gracetime = models.IntegerField(_("Grace time"))
    receivedonserver = models.DateTimeField(_("Recived on server"), auto_now=False, auto_now_add=True)
    starttime = models.DateTimeField(_("Start time"), auto_now=False, auto_now_add=False, null=True)
    endtime = models.DateTimeField(_("Start time"), auto_now=False, auto_now_add=False, null=True)
    gpslocation = PointField(_("GPS Location"), null=True, blank=True, geography=True, srid=4326)
    journeypath = LineStringField(geography=True, null=True, blank=True)
    remarks = models.TextField(_("Remark"), null=True, blank=True)
    remarkstype = models.ForeignKey("onboarding.TypeAssist", on_delete=models.RESTRICT, null=True, blank=True, related_name="remark_types")
    asset = models.ForeignKey("activity.Asset", verbose_name=_("Asset"), on_delete=models.RESTRICT, null=True, blank=True, related_name="jobneed_assets")
    frequency = models.CharField(verbose_name=_("Frequency type"), null=True, max_length=55, choices=Frequency.choices, default=Frequency.NONE.value)
    job = models.ForeignKey("activity.Job", verbose_name=_("Job"), on_delete=models.RESTRICT, null=True, blank=True, related_name="jobs")
    jobstatus = models.CharField("Job Status", choices=JobStatus.choices, max_length=60, null=True)
    jobtype = models.CharField(_("Job Type"), max_length=50, choices=JobType.choices, null=True)
    performedby = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_("Performed by"), on_delete=models.RESTRICT, null=True, blank=True, related_name="jobneed_performedby")
    priority = models.CharField(_("Priority"), max_length=50, choices=Priority.choices)
    qset = models.ForeignKey("activity.QuestionSet", verbose_name=_("QuestionSet"), on_delete=models.RESTRICT, null=True, blank=True)
    scantype = models.CharField(_("Scan type"), max_length=50, choices=ScanType.choices, default=ScanType.NONE.value)
    people = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_("People"), on_delete=models.RESTRICT, null=True, blank=True)
    pgroup = models.ForeignKey("peoples.Pgroup", verbose_name=_("People Group"), on_delete=models.RESTRICT, null=True, blank=True, related_name="jobneed_pgroup")
    sgroup = models.ForeignKey("peoples.Pgroup", verbose_name=_("Site Group"), on_delete=models.RESTRICT, null=True, blank=True, related_name="jobneed_sgroup")
    identifier = models.CharField(_("Jobneed Type"), max_length=50, choices=JobneedIdentifier.choices, null=True, db_index=True)
    parent = models.ForeignKey("self", verbose_name=_("Belongs to"), on_delete=models.RESTRICT, null=True, blank=True)
    alerts = models.BooleanField(_("Alerts"), default=False, null=True)
    seqno = models.SmallIntegerField(_("Sl No."))
    client = models.ForeignKey("onboarding.Bt", verbose_name=_("Client"), on_delete=models.RESTRICT, null=True, blank=True, related_name="jobneed_clients")
    bu = models.ForeignKey("onboarding.Bt", verbose_name=_("Site"), on_delete=models.RESTRICT, null=True, blank=True, related_name="jobneedf_bus")
    ticketcategory = models.ForeignKey("onboarding.TypeAssist", verbose_name=_("Notify Category"), null=True, blank=True, on_delete=models.RESTRICT)
    ticket = models.ForeignKey("y_helpdesk.Ticket", verbose_name=_("Ticket"), on_delete=models.RESTRICT, null=True, blank=True, related_name="jobneed_ticket")
    othersite = models.CharField(_("Other Site"), max_length=100, default=None, null=True)
    multifactor = models.DecimalField(_("Multiplication Factor"), default=1, max_digits=10, decimal_places=6)
    raisedtktflag = models.BooleanField(_("RaiseTicketFlag"), default=False, null=True)
    ismailsent = models.BooleanField(_("Mail Sent"), default=False)
    attachmentcount = models.IntegerField(_("Attachment Count"), default=0)
    other_info = models.JSONField(_("Other info"), default=other_info, blank=True, encoder=DjangoJSONEncoder)
    geojson = models.JSONField(default=geojson_jobnjobneed, blank=True, null=True, encoder=DjangoJSONEncoder)
    deviation = models.BooleanField(_("Deviation"), default=False, null=True)
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


__all__ = ['Jobneed']
