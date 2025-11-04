"""
Onboarding File Upload Security Configuration

Defines rate limiting and security controls specific to onboarding module
file uploads (photos, documents, voice recordings).

Following .claude/rules.md Rule #14: File Upload Security
Addresses Phase 1.2 requirement for onboarding-specific upload throttling.

Author: Claude Code
Date: 2025-10-01
"""

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

# =============================================================================
# ONBOARDING FILE UPLOAD LIMITS
# =============================================================================

ONBOARDING_FILE_UPLOAD_LIMITS = {
    # Maximum number of photos per onboarding session
    'MAX_PHOTOS_PER_SESSION': 50,

    # Maximum number of documents per onboarding session
    'MAX_DOCUMENTS_PER_SESSION': 20,

    # Maximum total upload size per session (100MB)
    'MAX_TOTAL_SIZE_PER_SESSION': 100 * 1024 * 1024,

    # Upload rate limiting window (minutes)
    'UPLOAD_WINDOW_MINUTES': 15,

    # Maximum photos per minute (burst protection)
    'MAX_PHOTOS_PER_MINUTE': 10,

    # Maximum file size for individual uploads (10MB per file)
    'MAX_FILE_SIZE_BYTES': 10 * 1024 * 1024,

    # Voice recording limits
    'MAX_VOICE_RECORDINGS_PER_SESSION': 100,
    'MAX_VOICE_RECORDING_DURATION_SECONDS': 180,  # 3 minutes max
    'MAX_VOICE_RECORDING_SIZE_BYTES': 5 * 1024 * 1024,  # 5MB

    # Concurrent upload limits
    'MAX_CONCURRENT_UPLOADS': 3,
}

# =============================================================================
# ALLOWED FILE TYPES BY UPLOAD CATEGORY
# =============================================================================

ONBOARDING_ALLOWED_FILE_TYPES = {
    'photos': [
        'image/jpeg',
        'image/jpg',
        'image/png',
        'image/heic',  # iOS photos
        'image/webp'
    ],

    'documents': [
        'application/pdf',
        'image/jpeg',  # Scanned documents
        'image/png',   # Scanned documents
    ],

    'voice': [
        'audio/mpeg',  # MP3
        'audio/wav',
        'audio/webm',  # Web recordings
        'audio/ogg',
        'audio/m4a',   # iOS recordings
    ]
}

# =============================================================================
# UPLOAD SECURITY POLICIES
# =============================================================================

# Require EXIF validation for photos (detect tampered images)
ONBOARDING_REQUIRE_EXIF_VALIDATION = True

# Require virus scanning for document uploads (if available)
ONBOARDING_REQUIRE_VIRUS_SCAN = True

# Automatic photo compression for large files
ONBOARDING_AUTO_COMPRESS_PHOTOS = True
ONBOARDING_COMPRESSION_QUALITY = 85  # JPEG quality 0-100

# Geolocation requirements for site audit photos
ONBOARDING_REQUIRE_PHOTO_GEOLOCATION = True
ONBOARDING_MAX_PHOTO_AGE_HOURS = 24  # Photos must be recent

# =============================================================================
# RATE LIMITING CONFIGURATION
# =============================================================================

# Rate limiter settings for onboarding file uploads
RATE_LIMITER_CRITICAL_RESOURCES = [
    'llm_calls',
    'translations',
    'knowledge_ingestion',
    'onboarding_photo_uploads',  # NEW: Critical resource
]

# Circuit breaker threshold for upload failures
RATE_LIMITER_CIRCUIT_BREAKER_THRESHOLD = 5

# =============================================================================
# CACHE KEYS
# =============================================================================

ONBOARDING_UPLOAD_CACHE_KEYS = {
    'photo_count': 'onboarding:upload:photo_count:{session_id}',
    'document_count': 'onboarding:upload:document_count:{session_id}',
    'total_size': 'onboarding:upload:total_size:{session_id}',
    'burst_protection': 'onboarding:upload:burst:{user_id}',
    'concurrent_uploads': 'onboarding:upload:concurrent:{user_id}',
}

# Cache TTL (matches session duration)
ONBOARDING_UPLOAD_CACHE_TTL = SECONDS_IN_HOUR  # 1 hour

# =============================================================================
# ERROR MESSAGES
# =============================================================================

ONBOARDING_UPLOAD_ERROR_MESSAGES = {
    'session_photo_limit': 'Maximum of {limit} photos per session exceeded. Please complete current session first.',
    'session_document_limit': 'Maximum of {limit} documents per session exceeded.',
    'session_size_limit': 'Total upload size limit ({limit} MB) exceeded for this session.',
    'burst_limit': 'Upload rate too high. Please wait {retry_after} seconds before uploading more.',
    'file_size_limit': 'File size ({size} MB) exceeds maximum allowed ({limit} MB).',
    'file_type_invalid': 'File type {file_type} not allowed. Allowed types: {allowed_types}',
    'geolocation_missing': 'Photo geolocation required for site audits. Please enable location services.',
    'photo_age_invalid': 'Photo is too old ({age} hours). Photos must be taken within {max_age} hours.',
    'concurrent_limit': 'Too many concurrent uploads. Maximum {limit} uploads allowed simultaneously.',
}

__all__ = [
    'ONBOARDING_FILE_UPLOAD_LIMITS',
    'ONBOARDING_ALLOWED_FILE_TYPES',
    'ONBOARDING_REQUIRE_EXIF_VALIDATION',
    'ONBOARDING_REQUIRE_VIRUS_SCAN',
    'ONBOARDING_AUTO_COMPRESS_PHOTOS',
    'ONBOARDING_COMPRESSION_QUALITY',
    'ONBOARDING_REQUIRE_PHOTO_GEOLOCATION',
    'ONBOARDING_MAX_PHOTO_AGE_HOURS',
    'ONBOARDING_UPLOAD_CACHE_KEYS',
    'ONBOARDING_UPLOAD_CACHE_TTL',
    'ONBOARDING_UPLOAD_ERROR_MESSAGES',
    'RATE_LIMITER_CRITICAL_RESOURCES',
]
