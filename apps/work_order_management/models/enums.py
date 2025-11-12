"""
Work Order Management - Enumeration Choices

This module contains all enumeration classes used across work order models.
Centralized for consistency and reusability.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class Workstatus(models.TextChoices):
    """Work order status states"""
    ASSIGNED = ("ASSIGNED", "Assigned")
    REASSIGNED = ("RE_ASSIGNED", "Re-Assigned")
    COMPLETED = ("COMPLETED", "Completed")
    INPROGRESS = ("INPROGRESS", "Inprogress")
    CANCELLED = ("CANCELLED", "Cancelled")
    CLOSED = ("CLOSED", "Closed")


class WorkPermitStatus(models.TextChoices):
    """
    Work permit approval status.
    If value is NOT_REQUIRED, it is a work order (not requiring permit).
    """
    NOTNEED = ("NOT_REQUIRED", "Not Required")
    APPROVED = ("APPROVED", "Approved")
    REJECTED = ("REJECTED", "Rejected")
    PENDING = ("PENDING", "Pending")


class WorkPermitVerifierStatus(models.TextChoices):
    """Work permit verifier approval status"""
    NOTNEED = ("NOT_REQUIRED", "Not Required")
    APPROVED = ("APPROVED", "Approved")
    REJECTED = ("REJECTED", "Rejected")
    PENDING = ("PENDING", "Pending")


class Priority(models.TextChoices):
    """Work order priority levels"""
    HIGH = ("HIGH", "High")
    LOW = ("LOW", "Low")
    MEDIUM = ("MEDIUM", "Medium")


class Identifier(models.TextChoices):
    """Work order type identifiers"""
    WO = ("WO", "Work Order")
    WP = ("WP", "Work Permit")
    SLA = ("SLA", "Service Level Agreement")


class AnswerType(models.TextChoices):
    """Answer types for work order detail questions"""
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
    """Attachment types for work order details"""
    BACKCAMPIC = "BACKCAMPIC", _("Back Camera Pic")
    FRONTCAMPIC = "FRONTCAMPIC", _("Front Camera Pic")
    AUDIO = "AUDIO", _("Audio")
    VIDEO = "VIDEO", _("Video")
    NONE = ("NONE", "NONE")


class ApproverIdentifier(models.TextChoices):
    """Approver role identifiers"""
    APPROVER = ("APPROVER", "Approver")
    VERIFIER = ("VERIFIER", "Verifier")
