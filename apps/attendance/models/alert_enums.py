"""
Alert & Monitoring Enums (Phase 5.1)

TextChoices enums for alert and monitoring models.

Author: Claude Code
Created: 2025-11-05
Phase: 5.1 - Alert Enums
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class AlertType(models.TextChoices):
    """Alert types"""
    NO_SHOW = 'NO_SHOW', _('No-Show Alert')
    LATE_CHECKIN = 'LATE_CHECKIN', _('Late Check-in Alert')
    WRONG_POST = 'WRONG_POST', _('Wrong Post Alert')
    MISSING_CHECKOUT = 'MISSING_CHECKOUT', _('Missing Check-out Alert')
    COVERAGE_GAP = 'COVERAGE_GAP', _('Coverage Gap Alert')
    OVERTIME_WARNING = 'OVERTIME_WARNING', _('Overtime Warning')
    REST_VIOLATION = 'REST_VIOLATION', _('Rest Period Violation')
    MULTIPLE_MISMATCH = 'MULTIPLE_MISMATCH', _('Multiple Mismatch Alert')
    GEOFENCE_BREACH = 'GEOFENCE_BREACH', _('Geofence Breach Alert')
    CERT_EXPIRY = 'CERT_EXPIRY', _('Certification Expiry Alert')
    CUSTOM = 'CUSTOM', _('Custom Alert')


class AlertSeverity(models.TextChoices):
    """Alert severity"""
    CRITICAL = 'CRITICAL', _('Critical')
    HIGH = 'HIGH', _('High')
    MEDIUM = 'MEDIUM', _('Medium')
    LOW = 'LOW', _('Low')
    INFO = 'INFO', _('Informational')


class AlertStatus(models.TextChoices):
    """Alert lifecycle status"""
    ACTIVE = 'ACTIVE', _('Active')
    ACKNOWLEDGED = 'ACKNOWLEDGED', _('Acknowledged')
    RESOLVED = 'RESOLVED', _('Resolved')
    ESCALATED = 'ESCALATED', _('Escalated')
    AUTO_RESOLVED = 'AUTO_RESOLVED', _('Auto-Resolved')
    CANCELLED = 'CANCELLED', _('Cancelled')
