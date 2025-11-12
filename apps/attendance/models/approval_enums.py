"""
Approval Workflow Enums (Phase 4.1)

TextChoices enums for approval workflow models.

Author: Claude Code
Created: 2025-11-05
Phase: 4.1 - Approval Enums
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class RequestType(models.TextChoices):
    """Types of approval requests"""
    VALIDATION_OVERRIDE = 'VALIDATION_OVERRIDE', _('Validation Check-in Override')
    EMERGENCY_ASSIGNMENT = 'EMERGENCY_ASSIGNMENT', _('Emergency Assignment')
    SHIFT_CHANGE = 'SHIFT_CHANGE', _('Shift Change Request')
    POST_REASSIGNMENT = 'POST_REASSIGNMENT', _('Post Reassignment')
    REST_PERIOD_WAIVER = 'REST_PERIOD_WAIVER', _('Rest Period Waiver')
    LATE_CHECKIN_APPROVAL = 'LATE_CHECKIN_APPROVAL', _('Late Check-in Approval')
    SITE_TRANSFER = 'SITE_TRANSFER', _('Site Transfer')
    COVERAGE_GAP_FILL = 'COVERAGE_GAP_FILL', _('Coverage Gap Fill')


class RequestStatus(models.TextChoices):
    """Approval request status"""
    PENDING = 'PENDING', _('Pending Review')
    AUTO_APPROVED = 'AUTO_APPROVED', _('Auto-Approved')
    MANUALLY_APPROVED = 'MANUALLY_APPROVED', _('Manually Approved')
    REJECTED = 'REJECTED', _('Rejected')
    EXPIRED = 'EXPIRED', _('Expired')
    CANCELLED = 'CANCELLED', _('Cancelled')


class RequestPriority(models.TextChoices):
    """Request priority"""
    URGENT = 'URGENT', _('Urgent')
    HIGH = 'HIGH', _('High')
    NORMAL = 'NORMAL', _('Normal')
    LOW = 'LOW', _('Low')


class ApprovalActionType(models.TextChoices):
    """Types of approval actions"""
    CREATED = 'CREATED', _('Request Created')
    APPROVED = 'APPROVED', _('Approved')
    REJECTED = 'REJECTED', _('Rejected')
    CANCELLED = 'CANCELLED', _('Cancelled')
    EXPIRED = 'EXPIRED', _('Expired')
    ESCALATED = 'ESCALATED', _('Escalated to Manager')
    COMMENT_ADDED = 'COMMENT_ADDED', _('Comment Added')
