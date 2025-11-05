"""
Job Model - Work Template Definition

Represents recurring or scheduled work (tasks, tours, PPM).
Generates Jobneed instances for execution based on schedule.
"""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _
from concurrency.fields import VersionField

from apps.activity.managers.job import JobManager
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel


def other_info():
    """Default JSON structure for Job.other_info field"""
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


class Job(BaseModel, TenantAwareModel):
    """
    Job Template/Definition - What work to do, when to schedule it

    Has 1-to-many relationship with Jobneed (generates multiple execution instances).
    Parent relationships: parent=NULL means root job; parent=Job means child checkpoint.
    """

    # Import enums locally to avoid circular imports
    from .enums import JobIdentifier, Priority, ScanType, Frequency

    # Expose enums as nested classes for backward compatibility
    Identifier = JobIdentifier
    Priority = Priority
    Scantype = ScanType
    Frequency = Frequency

    jobname = models.CharField(_("Name"), max_length=200)
    jobdesc = models.CharField(_("Description"), max_length=500)
    fromdate = models.DateTimeField(_("From date"), auto_now=False, auto_now_add=False)
    uptodate = models.DateTimeField(_("To date"), auto_now=False, auto_now_add=False)
    cron = models.CharField(_("Cron Exp."), max_length=200, default="* * * * *")
    identifier = models.CharField(_("Job Type"), max_length=100, choices=JobIdentifier.choices, null=True, db_index=True)
    planduration = models.IntegerField(_("Plan duration (min)"))
    gracetime = models.IntegerField(_("Grace Time"))
    expirytime = models.IntegerField(_("Expiry Time"))
    lastgeneratedon = models.DateTimeField(_("Last generatedon"), auto_now=False, auto_now_add=True)
    asset = models.ForeignKey("activity.Asset", verbose_name=_("Asset"), on_delete=models.RESTRICT, null=True, blank=True)
    priority = models.CharField(_("Priority"), max_length=100, choices=Priority.choices)
    qset = models.ForeignKey("activity.QuestionSet", verbose_name=_("QuestionSet"), on_delete=models.RESTRICT, null=True, blank=True)
    people = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_("Aggresive auto-assign to People"), on_delete=models.RESTRICT, null=True, blank=True, related_name="job_aaatops")
    pgroup = models.ForeignKey("peoples.Pgroup", verbose_name=_("People Group"), on_delete=models.RESTRICT, null=True, blank=True, related_name="job_pgroup")
    sgroup = models.ForeignKey("peoples.Pgroup", verbose_name=_("Site Group"), on_delete=models.RESTRICT, null=True, blank=True, related_name="job_sgroup")
    geofence = models.ForeignKey("onboarding.GeofenceMaster", verbose_name=_("Geofence"), on_delete=models.RESTRICT, null=True, blank=True)
    parent = models.ForeignKey("self", verbose_name=_("Belongs to"), on_delete=models.RESTRICT, null=True, blank=True)
    seqno = models.SmallIntegerField(_("Serial No."))
    client = models.ForeignKey("onboarding.Bt", verbose_name=_("Client"), on_delete=models.RESTRICT, related_name="job_clients", null=True, blank=True)
    bu = models.ForeignKey("onboarding.Bt", verbose_name=_("Site"), on_delete=models.RESTRICT, related_name="job_bus", null=True, blank=True)
    shift = models.ForeignKey("onboarding.Shift", verbose_name=_("Shift"), on_delete=models.RESTRICT, null=True, related_name="job_shifts")
    starttime = models.TimeField(_("Start time"), auto_now=False, auto_now_add=False, null=True)
    endtime = models.TimeField(_("End time"), auto_now=False, auto_now_add=False, null=True)
    ticketcategory = models.ForeignKey("onboarding.TypeAssist", verbose_name=_("Notify Category"), on_delete=models.RESTRICT, null=True, blank=True, related_name="job_tktcategories")
    scantype = models.CharField(_("Scan Type"), max_length=50, choices=ScanType.choices)
    frequency = models.CharField(verbose_name=_("Frequency type"), null=True, max_length=55, choices=Frequency.choices, default=Frequency.NONE.value)
    other_info = models.JSONField(_("Other info"), default=other_info, blank=True, encoder=DjangoJSONEncoder)
    geojson = models.JSONField(default=geojson_jobnjobneed, blank=True, null=True, encoder=DjangoJSONEncoder)
    enable = models.BooleanField(_("Enable"), default=True)
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


__all__ = ['Job']
