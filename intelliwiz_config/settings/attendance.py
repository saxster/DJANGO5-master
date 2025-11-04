"""
Attendance System Configuration

Settings for attendance tracking, fraud detection, and compliance.

Features:
- Audit logging configuration
- Photo capture settings
- Data retention policies
- Fraud detection thresholds
- Consent management
"""

import os
from datetime import timedelta

# ============================================================================
# AUDIT LOGGING
# ============================================================================

# Enable comprehensive audit logging for all attendance access
ENABLE_ATTENDANCE_AUDIT_LOGGING = True

# Audit log retention period (days)
AUDIT_LOG_RETENTION_DAYS = 2190  # 6 years for SOC 2 / ISO 27001 compliance

# Audit log archival period (days)
AUDIT_LOG_ARCHIVE_AFTER_DAYS = 730  # 2 years

# ============================================================================
# PHOTO CAPTURE
# ============================================================================

# Photo storage (S3 or local)
ATTENDANCE_PHOTO_STORAGE = os.environ.get('ATTENDANCE_PHOTO_STORAGE', 'S3')  # 'S3' or 'LOCAL'

# Photo retention period (days)
ATTENDANCE_PHOTO_RETENTION_DAYS = 90

# Photo quality defaults (can be overridden per client)
ATTENDANCE_PHOTO_MIN_WIDTH = 480  # pixels
ATTENDANCE_PHOTO_MIN_HEIGHT = 480  # pixels
ATTENDANCE_PHOTO_MAX_SIZE_KB = 200  # kilobytes
ATTENDANCE_PHOTO_REQUIRE_FACE = True
ATTENDANCE_PHOTO_MIN_FACE_CONFIDENCE = 0.8  # 0-1 scale

# ============================================================================
# DATA RETENTION
# ============================================================================

# Active attendance data retention (days)
ATTENDANCE_ACTIVE_RETENTION_DAYS = 730  # 2 years

# Archive retention (days) - total retention = active + archive
ATTENDANCE_ARCHIVE_RETENTION_DAYS = 1825  # 5 years (7 years total for tax compliance)

# GPS location history retention (days) - privacy compliance
GPS_HISTORY_RETENTION_DAYS = 90

# Biometric data deletion after employee termination (days)
BIOMETRIC_AFTER_TERMINATION_DAYS = 30

# ============================================================================
# FRAUD DETECTION
# ============================================================================

# Minimum attendance records for fraud baseline training
FRAUD_BASELINE_MIN_RECORDS = 30

# Fraud baseline training window (days)
FRAUD_BASELINE_WINDOW_DAYS = 90

# Fraud detection risk thresholds
FRAUD_RISK_CRITICAL_THRESHOLD = 0.8  # Auto-block
FRAUD_RISK_HIGH_THRESHOLD = 0.6  # Manager review required
FRAUD_RISK_MEDIUM_THRESHOLD = 0.4  # Flag for monitoring
FRAUD_RISK_LOW_THRESHOLD = 0.2  # Normal activity

# Fraud alert auto-escalation (hours)
FRAUD_ALERT_ESCALATION_HOURS = 24  # Escalate if not resolved in 24h

# Device sharing detection window (minutes)
DEVICE_SHARING_WINDOW_MINUTES = 30

# Maximum devices per employee
MAX_DEVICES_PER_EMPLOYEE = 3

# ============================================================================
# GPS VALIDATION
# ============================================================================

# GPS accuracy thresholds
GPS_MIN_ACCURACY_METERS = 100  # Flag if worse than 100m
GPS_ACCURACY_JUMP_THRESHOLD = 50  # Flag if jumps more than 50m

# Velocity limits for spoofing detection (km/h)
MAX_WALKING_SPEED_KMH = 6
MAX_DRIVING_SPEED_KMH = 130
MAX_FLYING_SPEED_KMH = 900

# Geofence validation
DEFAULT_GEOFENCE_HYSTERESIS_METERS = 1.0  # Default buffer
GEOFENCE_HYSTERESIS_CONSTRUCTION = 5.0  # For construction sites
GEOFENCE_HYSTERESIS_WAREHOUSE = 10.0  # For large warehouses

# ============================================================================
# CONSENT MANAGEMENT
# ============================================================================

# Consent grace period (days) - time before consent becomes mandatory
CONSENT_GRACE_PERIOD_DAYS = 7

# Consent expiration reminder (days before expiration)
CONSENT_REMINDER_DAYS_BEFORE = 30

# States requiring GPS consent
GPS_CONSENT_REQUIRED_STATES = ['CA', 'LA']  # California, Louisiana

# States requiring written biometric consent
BIOMETRIC_WRITTEN_CONSENT_STATES = ['IL', 'TX']  # Illinois BIPA, Texas CUBI

# ============================================================================
# EXPENSE CALCULATION
# ============================================================================

# Default reimbursement rates (per km) if not configured per client
DEFAULT_REIMBURSEMENT_RATE_PER_KM = 0.30  # $0.30/km

# Minimum distance for reimbursement (km)
MINIMUM_REIMBURSEMENT_DISTANCE_KM = 0.0

# Maximum daily reimbursement cap (USD)
MAXIMUM_DAILY_REIMBURSEMENT = 100.00

# ============================================================================
# PERFORMANCE
# ============================================================================

# Fraud detection timeout (seconds)
FRAUD_DETECTION_TIMEOUT_SECONDS = 2.0

# Photo processing timeout (seconds)
PHOTO_PROCESSING_TIMEOUT_SECONDS = 5.0

# Batch sizes for background tasks
ARCHIVAL_BATCH_SIZE = 1000
PHOTO_DELETION_BATCH_SIZE = 100
GPS_PURGE_BATCH_SIZE = 1000

# ============================================================================
# CELERY BEAT SCHEDULE
# ============================================================================

from celery.schedules import crontab

ATTENDANCE_CELERY_BEAT_SCHEDULE = {
    # Audit log maintenance
    'cleanup-audit-logs': {
        'task': 'attendance.cleanup_old_audit_logs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'options': {'expires': 3600},  # Task expires after 1 hour
    },
    'analyze-suspicious-access': {
        'task': 'attendance.analyze_suspicious_access',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },

    # Data retention tasks
    'archive-old-records': {
        'task': 'attendance.archive_old_records',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),  # Monthly on 1st
        'kwargs': {'batch_size': ARCHIVAL_BATCH_SIZE},
    },
    'purge-gps-history': {
        'task': 'attendance.purge_gps_history',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
        'kwargs': {'batch_size': GPS_PURGE_BATCH_SIZE},
    },
    'delete-old-photos': {
        'task': 'attendance.delete_old_photos',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM
        'kwargs': {'batch_size': PHOTO_DELETION_BATCH_SIZE},
    },

    # Consent management
    'send-consent-reminders': {
        'task': 'attendance.send_consent_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'expire-old-consents': {
        'task': 'attendance.expire_old_consents',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },

    # Fraud detection
    'train-fraud-baselines': {
        'task': 'attendance.train_fraud_baselines',
        'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Weekly on Sunday at 1 AM
    },
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

ATTENDANCE_LOGGING = {
    'handlers': {
        'attendance_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(os.environ.get('LOG_DIR', '/var/log/intelliwiz'), 'attendance.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'fraud_detection_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(os.environ.get('LOG_DIR', '/var/log/intelliwiz'), 'fraud_detection.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 20,  # Keep more for investigations
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'apps.attendance': {
            'handlers': ['attendance_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.attendance.ml_models': {
            'handlers': ['fraud_detection_file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'apps.attendance.services.fraud_detection_orchestrator': {
            'handlers': ['fraud_detection_file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
