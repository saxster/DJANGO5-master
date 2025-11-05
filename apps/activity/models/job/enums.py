"""
Job Domain Enums

All TextChoices enums used across Job, Jobneed, and JobneedDetails models.
Centralized to avoid duplication and ensure consistency.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class JobIdentifier(models.TextChoices):
    """Job template types"""
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


class JobneedIdentifier(models.TextChoices):
    """Jobneed instance types (superset of Job types)"""
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


class Priority(models.TextChoices):
    """Priority levels for jobs and jobneeds"""
    HIGH = "HIGH", _("High")
    LOW = "LOW", _("Low")
    MEDIUM = "MEDIUM", _("Medium")


class ScanType(models.TextChoices):
    """Asset scanning methods"""
    NONE = ("NONE", "None")
    QR = "QR", _("QR")
    NFC = "NFC", _("NFC")
    SKIP = "SKIP", _("Skip")
    ENTERED = "ENTERED", _("Entered")


class Frequency(models.TextChoices):
    """Scheduling frequency options"""
    NONE = "NONE", _("None")
    DAILY = "DAILY", _("Daily")
    WEEKLY = "WEEKLY", _("Weekly")
    MONTHLY = "MONTHLY", _("Monthly")
    BIMONTHLY = "BIMONTHLY", _("Bimonthly")
    QUARTERLY = "QUARTERLY", _("Quarterly")
    HALFYEARLY = "HALFYEARLY", _("Half Yearly")
    YEARLY = "YEARLY", _("Yearly")
    FORTNIGHTLY = "FORTNIGHTLY", _("Fort Nightly")


class JobStatus(models.TextChoices):
    """Jobneed execution state machine"""
    ASSIGNED = ("ASSIGNED", "Assigned")
    AUTOCLOSED = ("AUTOCLOSED", "Auto Closed")
    COMPLETED = ("COMPLETED", "Completed")
    INPROGRESS = ("INPROGRESS", "Inprogress")
    PARTIALLYCOMPLETED = ("PARTIALLYCOMPLETED", "Partially Completed")
    MAINTENANCE = ("MAINTENANCE", "Maintenance")
    STANDBY = ("STANDBY", "Standby")
    WORKING = ("WORKING", "Working")


class JobType(models.TextChoices):
    """Jobneed origin classification"""
    SCHEDULE = ("SCHEDULE", "Schedule")
    ADHOC = ("ADHOC", "Adhoc")


class AnswerType(models.TextChoices):
    """Question answer input types for JobneedDetails"""
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
    """Attachment types for JobneedDetails"""
    BACKCAMPIC = "BACKCAMPIC", _("Back Camera Pic")
    FRONTCAMPIC = "FRONTCAMPIC", _("Front Camera Pic")
    AUDIO = "AUDIO", _("Audio")
    VIDEO = "VIDEO", _("Video")
    NONE = ("NONE", "NONE")


__all__ = [
    'JobIdentifier',
    'JobneedIdentifier',
    'Priority',
    'ScanType',
    'Frequency',
    'JobStatus',
    'JobType',
    'AnswerType',
    'AvptType',
]
