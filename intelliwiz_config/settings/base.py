"""
Base Django settings for intelliwiz_config project.

Master configuration file that orchestrates all settings modules:
- base_common.py: Shared settings (paths, auth, dates, templates)
- base_apps.py: INSTALLED_APPS (single source of truth)
- middleware.py: Middleware stack
- integrations/: External service configurations
- Other domain-specific configs (security, logging, etc.)

DO NOT define settings inline here. Always import from specialized modules.
"""

# ============================================================================
# IMPORT ALL SETTINGS FROM SPECIALIZED MODULES
# ============================================================================

# Common settings (SECRET_KEY, BASE_DIR, authentication, etc.)
from .base_common import *  # noqa: F401, F403

# INSTALLED_APPS - Single source of truth
from .base_apps import INSTALLED_APPS  # noqa: F401

# Middleware configuration
from .middleware import MIDDLEWARE  # noqa: F401

# ============================================================================
# CELERY & THIRD-PARTY INTEGRATION CONFIGURATION
# ============================================================================
# All external service integrations (Celery, AWS, GCP, LLM, Notifications)
# are imported from specialized modules

from .integrations import (  # noqa: F401, F405
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_SERIALIZER,
    CELERY_TASK_QUEUES,
    CELERY_TASK_ROUTES,
    EMAIL_BACKEND,
    EMAIL_HOST,
    DEFAULT_FROM_EMAIL,
    BUCKET,
    GCS_ENABLED,
    GOOGLE_API_KEY,
    LLM_PROVIDERS_ENABLED,
    MQTT_CONFIG,
    NOTIFICATION_PROVIDERS,
    CLIENT_DOMAINS,
    CACHES,
    CHANNEL_LAYERS,
)

# ============================================================================
# KNOWLEDGE BASE SECURITY CONFIGURATION
# ============================================================================

from .security.knowledge import (
    KB_ALLOWED_SOURCES,
    KB_MAX_DOCUMENT_SIZE_BYTES,
    KB_ALLOWED_MIME_TYPES,
    KB_MAX_CHUNKS_PER_DOCUMENT,
    KB_DEFAULT_CHUNK_SIZE,
    KB_DEFAULT_CHUNK_OVERLAP,
    KB_ALLOWED_HTML_TAGS,
    KB_FORBIDDEN_PATTERNS,
    KB_REQUIRE_TWO_PERSON_APPROVAL,
    KB_MIN_ACCURACY_SCORE,
    KB_MIN_COMPLETENESS_SCORE,
    KB_MIN_RELEVANCE_SCORE,
    KB_AUTO_REJECT_THRESHOLD,
    KB_MAX_SEARCH_RESULTS,
    KB_DEFAULT_SEARCH_MODE,
    KB_AUTHORITY_WEIGHTS,
    KB_FRESHNESS_DECAY_DAYS,
    KB_INGESTION_JOB_RETENTION_DAYS,
    KB_OLD_VERSION_RETENTION_DAYS,
    KB_REJECTED_DOCUMENT_RETENTION_DAYS,
)  # noqa: F401

# ============================================================================
# WEBSOCKET CONFIGURATION
# ============================================================================

from .websocket import (
    WEBSOCKET_JWT_AUTH_ENABLED,
    WEBSOCKET_JWT_COOKIE_NAME,
    WEBSOCKET_JWT_CACHE_TIMEOUT,
    WEBSOCKET_THROTTLE_LIMITS,
    WEBSOCKET_CONNECTION_TIMEOUT,
    WEBSOCKET_HEARTBEAT_INTERVAL,
    WEBSOCKET_PRESENCE_TIMEOUT,
    WEBSOCKET_AUTO_RECONNECT_ENABLED,
    WEBSOCKET_MAX_RECONNECT_ATTEMPTS,
    WEBSOCKET_RECONNECT_BASE_DELAY,
    WEBSOCKET_ORIGIN_VALIDATION_ENABLED,
    WEBSOCKET_ALLOWED_ORIGINS,
    WEBSOCKET_TOKEN_BINDING_ENABLED,
    WEBSOCKET_TOKEN_BINDING_STRICT,
    WEBSOCKET_LOG_AUTH_ATTEMPTS,
    WEBSOCKET_LOG_AUTH_FAILURES,
    WEBSOCKET_STREAM_TESTBENCH_ENABLED,
)  # noqa: F401

# ============================================================================
# HELPBOT CONFIGURATION
# ============================================================================

# HelpBot core settings
HELPBOT_ENABLED = True
HELPBOT_AUTO_INDEX_ON_STARTUP = False  # Set to True for auto-indexing on startup
HELPBOT_VOICE_ENABLED = True  # Enable voice interactions
HELPBOT_MAX_MESSAGE_LENGTH = 2000  # Maximum message length in characters
HELPBOT_SESSION_TIMEOUT_MINUTES = 60  # Session timeout in minutes
HELPBOT_MAX_CONTEXT_MESSAGES = 10  # Max messages to include in conversation context
HELPBOT_CACHE_TIMEOUT = 3600  # Cache timeout in seconds (1 hour)
HELPBOT_ANALYTICS_CACHE_TIMEOUT = 1800  # Analytics cache timeout (30 minutes)

# HelpBot knowledge base settings
HELPBOT_KNOWLEDGE_AUTO_UPDATE = True  # Auto-update knowledge base from docs
HELPBOT_MAX_KNOWLEDGE_RESULTS = 10  # Maximum search results to return
HELPBOT_KNOWLEDGE_EFFECTIVENESS_THRESHOLD = 0.3  # Min effectiveness to show results

# HelpBot supported languages (integrates with existing localization)
HELPBOT_LANGUAGES = ['en', 'hi', 'es', 'fr']  # Add more as needed

# HelpBot integration with existing AI services
HELPBOT_TXTAI_INTEGRATION = True  # Enable txtai semantic search integration
HELPBOT_LLM_INTEGRATION = True  # Enable LLM service integration
HELPBOT_VOICE_INTEGRATION = True  # Enable voice service integration

# HelpBot performance settings
HELPBOT_ANALYTICS_BATCH_SIZE = 100  # Batch size for analytics processing
HELPBOT_CONTEXT_TIMEOUT_MINUTES = 30  # Context tracking timeout
HELPBOT_MAX_JOURNEY_LENGTH = 20  # Maximum user journey entries to track

# HelpBot UI settings
HELPBOT_WIDGET_POSITION = 'bottom-right'  # Widget position on page
HELPBOT_WIDGET_THEME = 'modern'  # UI theme (modern, classic, minimal)
HELPBOT_SHOW_TYPING_INDICATOR = True  # Show typing indicator during AI response
HELPBOT_ENABLE_QUICK_SUGGESTIONS = True  # Show quick suggestion buttons

# ============================================================================
# NOC INTELLIGENCE SYSTEM CONFIGURATION
# ============================================================================

# NOC Operational Intelligence Settings
NOC_CONFIG = {
    # Telemetry & API
    'TELEMETRY_CACHE_TTL': 60,  # seconds - Cache telemetry data
    'CORRELATION_WINDOW_MINUTES': 15,  # Time window for signal-to-alert correlation

    # Fraud Detection & ML
    'FRAUD_SCORE_TICKET_THRESHOLD': 0.80,  # Auto-create ticket if fraud score >= 80%
    'ML_MODEL_MIN_TRAINING_SAMPLES': 500,  # Minimum labeled samples for model training
    'ML_MODEL_VALIDATION_THRESHOLDS': {
        'precision': 0.85,  # Minimum precision to accept model
        'recall': 0.75,     # Minimum recall to accept model
        'f1': 0.80          # Minimum F1 score to accept model
    },
    'FRAUD_DEDUPLICATION_HOURS': 24,  # Max 1 fraud ticket per person per 24h

    # Audit & Escalation
    'AUDIT_FINDING_TICKET_SEVERITIES': ['CRITICAL', 'HIGH'],  # Auto-escalate these severities
    'TICKET_DEDUPLICATION_HOURS': 4,  # Max 1 ticket per finding type per 4h

    # Baseline Learning & Threshold Tuning
    'BASELINE_FP_THRESHOLD': 0.3,  # High false positive rate threshold (30%)
    'BASELINE_STABLE_SAMPLE_COUNT': 100,  # Sample count for "stable" baseline
    'BASELINE_DEFAULT_THRESHOLD': 3.0,  # Default z-score threshold
    'BASELINE_SENSITIVE_THRESHOLD': 2.5,  # Threshold for stable baselines (more sensitive)
    'BASELINE_CONSERVATIVE_THRESHOLD': 4.0,  # Threshold for high FP rate (less sensitive)

    # WebSocket & Real-Time
    'WEBSOCKET_RATE_LIMIT': 100,  # Max events per minute per tenant
    'WEBSOCKET_BROADCAST_TIMEOUT': 5,  # Seconds before broadcast times out
    'EVENT_LOG_RETENTION_DAYS': 90,  # Keep event logs for 90 days
}

# ============================================================================
# ML CONFIGURATION (PHASE 2)
# ============================================================================
# Machine Learning drift monitoring and auto-retraining configuration
# Feature flags, thresholds, and safeguards for automated ML operations
# ============================================================================

from .ml_config import ML_CONFIG

# ============================================================================
# ATTENDANCE SYSTEM CONFIGURATION (Enhanced Nov 2025)
# ============================================================================
# Comprehensive attendance configuration including audit logging, fraud detection,
# consent management, photo capture, and data retention policies
# ============================================================================

from .attendance import *

# ============================================================================
# UNFOLD ADMIN THEME CONFIGURATION
# ============================================================================
# Modern admin interface with organized model grouping and enhanced UX
# Configuration centralized in settings/unfold.py
# ============================================================================

from .unfold import UNFOLD
