"""
Logging Security Configuration.

This module defines security policies for logging including:
- Sensitive data patterns to sanitize
- Log retention policies
- Access control requirements
- Compliance configurations (GDPR, HIPAA)

CRITICAL: Addresses Rule #15 - Logging Data Sanitization
"""

from typing import Dict, List, Set

LOG_RETENTION_DAYS_PRODUCTION = 90
LOG_RETENTION_DAYS_DEVELOPMENT = 7
LOG_RETENTION_DAYS_SECURITY = 365

LOG_ROTATION_SCHEDULE = {
    'application': 'midnight',
    'security': 'midnight',
    'errors': 'midnight',
    'audit': 'midnight'
}

LOG_MAX_FILE_SIZE_MB = 100
LOG_BACKUP_COUNT_PRODUCTION = 90
LOG_BACKUP_COUNT_DEVELOPMENT = 3

SENSITIVE_FIELD_PATTERNS = {
    'password', 'passwd', 'pwd', 'secret', 'token', 'key', 'api_key',
    'access_token', 'refresh_token', 'auth_token', 'session_key',
    'private_key', 'public_key', 'certificate', 'cert', 'credential',
    'email', 'email_address', 'mail', 'e_mail', 'mobno', 'mobile',
    'mobile_number', 'phone', 'phone_number', 'telephone', 'ssn',
    'social_security_number', 'credit_card', 'cc_number', 'card_number',
    'cvv', 'security_code', 'expiry_date', 'card_expiry',
    'oauth_token', 'bearer_token', 'jwt_token', 'csrf_token',
    'encryption_key', 'decrypt_key', 'hmac_secret', 'signing_key'
}

SENSITIVE_DATA_REPLACEMENT = '[SANITIZED]'
PII_FIELD_REPLACEMENT = '[PII-REDACTED]'

LOG_ACCESS_ROLES = {
    'security_logs': ['superuser', 'security_admin'],
    'application_logs': ['superuser', 'admin', 'developer'],
    'error_logs': ['superuser', 'admin', 'developer'],
    'audit_logs': ['superuser', 'compliance_officer']
}

COMPLIANCE_SETTINGS = {
    'gdpr': {
        'enabled': True,
        'log_user_consent': True,
        'right_to_erasure_logs': True,
        'data_minimization': True,
        'retention_policy_days': 90,
    },
    'hipaa': {
        'enabled': True,
        'encrypt_logs_at_rest': True,
        'audit_log_access': True,
        'minimum_retention_days': 365,
        'secure_transmission': True,
    },
    'soc2': {
        'enabled': True,
        'continuous_monitoring': True,
        'change_tracking': True,
        'incident_response_logging': True,
    },
    'pci_dss': {
        'enabled': True,
        'mask_payment_data': True,
        'quarterly_log_review': True,
        'retention_policy_days': 365,
    }
}

SECURITY_MONITORING_THRESHOLDS = {
    'max_failed_authentications_per_ip': 10,
    'max_failed_authentications_per_user': 5,
    'time_window_minutes': 15,
    'max_sensitive_data_detections': 3,
    'alert_on_password_log_attempt': True,
    'alert_on_credit_card_log_attempt': True,
}

LOG_SANITIZATION_PATTERNS = {
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'phone_us': r'(?:\+?1[-.\s]?)?(?:\(?[0-9]{3}\)?[-.\s]?)?[0-9]{3}[-.\s]?[0-9]{4}',
    'credit_card': r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b',
    'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
    'ipv4': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
}

STRUCTURED_LOGGING_FIELDS = {
    'required': [
        'timestamp',
        'level',
        'logger_name',
        'correlation_id',
    ],
    'optional': [
        'user_id',
        'ip_address',
        'request_path',
        'http_method',
        'status_code',
        'response_time_ms',
    ],
    'forbidden': [
        'password',
        'token',
        'secret',
        'credit_card',
        'ssn',
        'full_email',
    ]
}

LOGGING_SECURITY_ALERTS = {
    'enable_real_time_scanning': True,
    'alert_on_sensitive_data_detection': True,
    'alert_channels': ['email', 'slack'],
    'alert_email_recipients': ['security@youtility.in'],
    'alert_threshold_critical': 1,
    'alert_threshold_high': 5,
    'alert_threshold_medium': 10,
}

LOG_ENCRYPTION_SETTINGS = {
    'encrypt_security_logs': True,
    'encrypt_audit_logs': True,
    'encryption_algorithm': 'AES-256-GCM',
    'key_rotation_days': 90,
}

SECURE_LOG_STORAGE_PATHS = {
    'production': '/var/log/youtility4',
    'development': '/tmp/youtility4_logs',
    'test': '/tmp',
}

LOG_TRANSMISSION_SECURITY = {
    'use_tls': True,
    'verify_certificates': True,
    'allowed_aggregators': ['elasticsearch', 'datadog', 'splunk'],
    'sanitize_before_transmission': True,
}

def get_logging_security_settings(environment='development') -> Dict:
    """Get environment-specific logging security settings."""
    base_settings = {
        'LOG_RETENTION_DAYS': LOG_RETENTION_DAYS_DEVELOPMENT if environment == 'development' else LOG_RETENTION_DAYS_PRODUCTION,
        'LOG_MAX_FILE_SIZE_MB': LOG_MAX_FILE_SIZE_MB,
        'SENSITIVE_DATA_REPLACEMENT': SENSITIVE_DATA_REPLACEMENT,
        'LOG_ACCESS_ROLES': LOG_ACCESS_ROLES,
        'COMPLIANCE_SETTINGS': COMPLIANCE_SETTINGS,
        'SECURITY_MONITORING_THRESHOLDS': SECURITY_MONITORING_THRESHOLDS,
    }

    if environment == 'production':
        base_settings.update({
            'LOG_ENCRYPTION_ENABLED': True,
            'LOG_TRANSMISSION_TLS': True,
            'REAL_TIME_SCANNING_ENABLED': True,
            'ALERT_ON_SENSITIVE_DATA': True,
        })
    else:
        base_settings.update({
            'LOG_ENCRYPTION_ENABLED': False,
            'LOG_TRANSMISSION_TLS': False,
            'REAL_TIME_SCANNING_ENABLED': False,
            'ALERT_ON_SENSITIVE_DATA': False,
        })

    return base_settings