"""
File upload security configuration (CVSS 8.1 vulnerability fix).
File upload restrictions, monitoring, and content security settings.
"""

import environ

env = environ.Env()

# FILE UPLOAD SECURITY CONFIGURATION (CVSS 8.1 vulnerability fix)

# File upload rate limiting (more restrictive than general API rate limits)
FILE_UPLOAD_RATE_LIMITING = {
    'ENABLE': True,
    'WINDOW_MINUTES': 5,     # Shorter window for file uploads
    'MAX_ATTEMPTS': 10,      # Lower max attempts
    'MAX_SIZE_PER_WINDOW': 50 * 1024 * 1024,  # 50MB total per window
}

# File upload paths that require additional security
FILE_UPLOAD_PATHS = [
    '/api/upload/att_file/',
    '/api/upload/',
    # Conversational Onboarding - Voice input (Rule #14 compliance)
    '/api/v1/onboarding/conversation/',  # Voice uploads for transcription
    # Site Audit - Image and document uploads (Rule #14 compliance)
    '/api/v1/onboarding/site-audit/',     # Image uploads for analysis
    '/api/v1/onboarding/documents/',      # Document uploads for OCR
    # Admin onboarding uploads
    '/admin/onboarding/',                  # Admin file uploads
    '/admin/onboarding_api/',              # Admin API file uploads
]

# File upload CSRF protection
FILE_UPLOAD_CSRF_PROTECTION = {
    'ENABLE': True,
    'REQUIRE_CSRF_TOKEN': True,
    'ALLOWED_CONTENT_TYPES': [
        'multipart/form-data',
        'application/octet-stream',
        # Audio formats for voice input (conversational onboarding)
        'audio/webm',
        'audio/wav',
        'audio/mp3',
        'audio/ogg',
        'audio/m4a',
        'audio/aac',
        'audio/flac',
    ]
}

# File upload monitoring and alerting
FILE_UPLOAD_MONITORING = {
    'ENABLE_UPLOAD_LOGGING': True,
    'ENABLE_SECURITY_ALERTING': True,
    'LOG_VALIDATION_FAILURES': True,
    'LOG_PATH_TRAVERSAL_ATTEMPTS': True,
    'LOG_OVERSIZED_UPLOADS': True,
    'ALERT_ON_SUSPICIOUS_UPLOADS': True,
    'MAX_FAILED_UPLOADS_PER_USER': 5,
    'FAILED_UPLOAD_WINDOW_MINUTES': 10,
}

# File upload content security
FILE_UPLOAD_CONTENT_SECURITY = {
    'ENABLE_MAGIC_NUMBER_VALIDATION': True,
    'ENABLE_FILENAME_SANITIZATION': True,
    'ENABLE_PATH_TRAVERSAL_PROTECTION': True,
    'ENABLE_MALWARE_SCANNING': env.bool('ENABLE_MALWARE_SCANNING', default=True),
    'QUARANTINE_SUSPICIOUS_FILES': True,
}

# Virus Scanning Configuration (CVSS 8.6 - Malware distribution prevention)
FILE_UPLOAD_VIRUS_SCANNING = env.bool('FILE_UPLOAD_VIRUS_SCANNING', default=True)

VIRUS_SCANNER_CONFIG = {
    'ENABLE': FILE_UPLOAD_VIRUS_SCANNING,
    'ENGINE': 'clamav',  # or 'virustotal', 'aws_s3_scan' (future)
    'CLAMAV_SOCKET': '/var/run/clamav/clamd.ctl',  # Unix socket path
    'MAX_FILE_SIZE_MB': 50,  # Files larger than this logged but scanned
    'QUARANTINE_DIR': env.str('QUARANTINE_DIR', default='/tmp/claude/quarantine/uploads/'),
    'FAIL_OPEN': True,  # Allow uploads if scanner unavailable (vs FAIL_CLOSED)
}

CLAMAV_SETTINGS = {
    'ENABLED': env.bool('CLAMAV_ENABLED', default=True),
    'SCAN_TIMEOUT': env.int('CLAMAV_SCAN_TIMEOUT', default=30),
    'QUARANTINE_DIR': env.str('QUARANTINE_DIR', default='/tmp/claude/quarantine/uploads/'),
    'ALERT_ON_INFECTION': True,
    'BLOCK_ON_SCAN_FAILURE': env.bool('BLOCK_ON_SCAN_FAILURE', default=False),
    'MAX_FILE_SIZE': 100 * 1024 * 1024,
    'SCAN_ON_UPLOAD': True,
    'ASYNC_SCAN_THRESHOLD': 5 * 1024 * 1024,
}

# File upload size and type restrictions per user role
FILE_UPLOAD_RESTRICTIONS = {
    'admin': {
        'max_file_size': 100 * 1024 * 1024,  # 100MB
        'allowed_types': ['image', 'pdf', 'document', 'archive'],
        'max_files_per_day': 1000,
    },
    'staff': {
        'max_file_size': 50 * 1024 * 1024,   # 50MB
        'allowed_types': ['image', 'pdf', 'document'],
        'max_files_per_day': 500,
    },
    'user': {
        'max_file_size': 10 * 1024 * 1024,   # 10MB
        'allowed_types': ['image', 'pdf'],
        'max_files_per_day': 100,
    }
}