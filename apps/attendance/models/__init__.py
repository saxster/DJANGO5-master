"""
Attendance models package.

Contains all models for the attendance app, modularized for maintainability.

This package exports all models to maintain backward compatibility with
existing imports like:
    from apps.attendance.models import PeopleEventlog, Geofence

Models are organized by domain:
- Core attendance: PeopleEventlog, Geofence
- Tracking: Tracking, TestGeo
- Audit & Compliance: AttendanceAccessLog, AuditLogRetentionPolicy
- Consent Management: ConsentPolicy, EmployeeConsentLog, ConsentRequirement
- Post Assignment: Post, PostAssignment, PostOrderAcknowledgement
- Approval Workflow: ApprovalRequest, ApprovalAction, AutoApprovalRule
- Alert & Monitoring: AlertRule, AttendanceAlert, AlertEscalation
- Fraud Detection: FraudAlert, UserBehaviorProfile
- Photo Capture: AttendancePhoto
- Conflict Resolution: SyncConflict
"""

# Core attendance models
from apps.attendance.models.people_eventlog import (
    PeopleEventlog,
    PEventLogExtras,
    PELGeoJson,
    peventlog_json,
    pel_geojson,
)
from apps.attendance.models.geofence import Geofence

# Tracking models
from apps.attendance.models.tracking import Tracking
from apps.attendance.models.test_geo import TestGeo

# Audit & compliance models
from apps.attendance.models.audit_log import (
    AttendanceAccessLog,
    AuditLogRetentionPolicy,
)

# Consent management models
from apps.attendance.models.consent import (
    ConsentPolicy,
    EmployeeConsentLog,
    ConsentRequirement,
)

# Post assignment models (Phase 2)
from apps.attendance.models.post import Post
from apps.attendance.models.post_assignment import PostAssignment
from apps.attendance.models.post_order_acknowledgement import PostOrderAcknowledgement

# Approval workflow models (Phase 4)
from apps.attendance.models.approval_workflow import (
    ApprovalRequest,
    ApprovalAction,
    AutoApprovalRule,
)

# Alert & monitoring models (Phase 5)
from apps.attendance.models.alert_monitoring import (
    AlertRule,
    AttendanceAlert,
    AlertEscalation,
)

# Fraud detection models
from apps.attendance.models.fraud_alert import FraudAlert
from apps.attendance.models.user_behavior_profile import UserBehaviorProfile

# Photo capture models (Phase 1.4)
from apps.attendance.models.attendance_photo import AttendancePhoto

# Conflict resolution models
from apps.attendance.models.sync_conflict import SyncConflict

__all__ = [
    # Core attendance models
    'PeopleEventlog',
    'PEventLogExtras',
    'PELGeoJson',
    'peventlog_json',
    'pel_geojson',
    'Geofence',

    # Tracking models
    'Tracking',
    'TestGeo',

    # Audit & compliance
    'AttendanceAccessLog',
    'AuditLogRetentionPolicy',

    # Consent management
    'ConsentPolicy',
    'EmployeeConsentLog',
    'ConsentRequirement',

    # Post assignment (Phase 2)
    'Post',
    'PostAssignment',
    'PostOrderAcknowledgement',

    # Approval workflow (Phase 4)
    'ApprovalRequest',
    'ApprovalAction',
    'AutoApprovalRule',

    # Alert & monitoring (Phase 5)
    'AlertRule',
    'AttendanceAlert',
    'AlertEscalation',

    # Fraud detection
    'FraudAlert',
    'UserBehaviorProfile',

    # Photo capture
    'AttendancePhoto',

    # Conflict resolution
    'SyncConflict',
]
