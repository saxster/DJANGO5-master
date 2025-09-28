"""
Conversational Onboarding and Personalization settings.
Feature flags, consensus engine, knowledge base, and experimental settings.
"""

import os
import environ

env = environ.Env()

# CONVERSATIONAL ONBOARDING SETTINGS (Phase 1 MVP)

# Main feature flag
ENABLE_CONVERSATIONAL_ONBOARDING = env.bool('ENABLE_CONVERSATIONAL_ONBOARDING', default=False)

# Phase 2 Enhanced Features (Feature Flags)
ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER = (
    env.bool('ENABLE_CONVERSATIONAL_ONBOARDING_CHECKER', default=False) or
    env.bool('ENABLE_LLM_CHECKER', default=False)
)
ENABLE_ONBOARDING_KB = env.bool('ENABLE_ONBOARDING_KB', default=False)
ENABLE_ONBOARDING_SSE = env.bool('ENABLE_ONBOARDING_SSE', default=False)

# CONSENSUS ENGINE CONFIGURATION

ONBOARDING_APPROVE_THRESHOLD = env.float('ONBOARDING_APPROVE_THRESHOLD', default=0.7)
ONBOARDING_ESCALATE_THRESHOLD = env.float('ONBOARDING_ESCALATE_THRESHOLD', default=0.4)

# TRANSLATION CONFIGURATION

TRANSLATION_PROVIDER = env('TRANSLATION_PROVIDER', default='noop')  # 'google', 'noop'
ENABLE_TRANSLATION_CACHING = env.bool('ENABLE_TRANSLATION_CACHING', default=True)
TRANSLATION_CACHE_TIMEOUT = env.int('TRANSLATION_CACHE_TIMEOUT', default=3600)
TRANSLATION_DAILY_CHAR_LIMIT = env.int('TRANSLATION_DAILY_CHAR_LIMIT', default=100000)
TRANSLATION_REQUEST_CHAR_LIMIT = env.int('TRANSLATION_REQUEST_CHAR_LIMIT', default=5000)

# Google Translate API Configuration (when provider=google)
GOOGLE_TRANSLATE_API_KEY = env('GOOGLE_TRANSLATE_API_KEY', default='')
GOOGLE_CLOUD_PROJECT_ID = env('GOOGLE_CLOUD_PROJECT_ID', default='')

# KNOWLEDGE BASE CONFIGURATION

EMBEDDING_CACHE_TIMEOUT = env.int('EMBEDDING_CACHE_TIMEOUT', default=3600)
KNOWLEDGE_CHUNK_SIZE = env.int('KNOWLEDGE_CHUNK_SIZE', default=1000)
KNOWLEDGE_CHUNK_OVERLAP = env.int('KNOWLEDGE_CHUNK_OVERLAP', default=200)

# Production-grade Knowledge Base Settings
ONBOARDING_VECTOR_BACKEND = env('ONBOARDING_VECTOR_BACKEND', default='postgres_array')  # postgres_array|pgvector|chroma
KB_MAX_CHUNK_TOKENS = env.int('KB_MAX_CHUNK_TOKENS', default=512)
KB_TOP_K = env.int('KB_TOP_K', default=10)
KB_DAILY_EMBED_LIMIT = env.int('KB_DAILY_EMBED_LIMIT', default=100000)  # chars per tenant per day
KB_MAX_FILE_SIZE = env.int('KB_MAX_FILE_SIZE', default=50 * 1024 * 1024)  # 50MB
KB_MAX_TEXT_LENGTH = env.int('KB_MAX_TEXT_LENGTH', default=1_000_000)  # 1MB of text
KB_FETCH_TIMEOUT = env.int('KB_FETCH_TIMEOUT', default=30)  # seconds
KB_RATE_LIMIT_DELAY = env.float('KB_RATE_LIMIT_DELAY', default=1.0)  # seconds between requests

# Knowledge Base Security Settings
KB_ALLOWED_SOURCES = env.list('KB_ALLOWED_SOURCES', default=[
    'iso.org', 'nist.gov', 'asis.org', 'wikipedia.org', 'example.com',
    'docs.python.org', 'developer.mozilla.org', 'djangoproject.com', 'github.com'
])

# ChromaDB Configuration (when ONBOARDING_VECTOR_BACKEND=chroma)
CHROMA_HOST = env('CHROMA_HOST', default='localhost')
CHROMA_PORT = env.int('CHROMA_PORT', default=8000)
CHROMA_COLLECTION_NAME = env('CHROMA_COLLECTION_NAME', default='intelliwiz_knowledge')

# Budget, Security and Rate Limiting Configuration
KB_DAILY_BUDGET_LIMITS = {
    'embedding_tokens': env.int('KB_DAILY_EMBED_TOKEN_LIMIT', default=1_000_000),
    'embedding_chars': env.int('KB_DAILY_EMBED_CHAR_LIMIT', default=KB_DAILY_EMBED_LIMIT),
    'fetch_requests': env.int('KB_DAILY_FETCH_LIMIT', default=1000),
    'parse_requests': env.int('KB_DAILY_PARSE_LIMIT', default=1000)
}

KB_BLOCKED_LICENSE_PATTERNS = [r'proprietary', r'internal use only', r'confidential', r'trade secret']
KB_ATTRIBUTION_PATTERNS = [r'creative commons', r'attribution required', r'cite as', r'cc by']

ONBOARDING_API_RATE_LIMIT_WINDOW = env.int('ONBOARDING_API_RATE_LIMIT_WINDOW', default=60)
ONBOARDING_API_MAX_REQUESTS = env.int('ONBOARDING_API_MAX_REQUESTS', default=30)
ONBOARDING_SOURCE_ALLOWLIST = ['docs.python.org', 'developer.mozilla.org', 'djangoproject.com', 'github.com']

ONBOARDING_ALERT_THRESHOLDS = {
    'daily_cost_cents': env.int('ALERT_DAILY_COST_CENTS', default=10000),
    'avg_latency_ms': env.int('ALERT_AVG_LATENCY_MS', default=30000),
    'error_rate_percent': env.float('ALERT_ERROR_RATE_PERCENT', default=10.0),
}

# PERSONALIZATION AND EXPERIMENTATION SETTINGS

# Enable/Disable Personalization Features
ENABLE_ONBOARDING_LEARNING = env.bool('ENABLE_ONBOARDING_LEARNING', default=True)
ENABLE_ONBOARDING_EXPERIMENTS = env.bool('ENABLE_ONBOARDING_EXPERIMENTS', default=True)
ENABLE_ONBOARDING_PERSONALIZATION = env.bool('ENABLE_ONBOARDING_PERSONALIZATION', default=True)

# Learning System Configuration
LEARNING_ASYNC_PROCESSING = env.bool('LEARNING_ASYNC_PROCESSING', default=True)
LEARNING_BATCH_SIZE = env.int('LEARNING_BATCH_SIZE', default=100)
LEARNING_IMPLICIT_SIGNALS = env.bool('LEARNING_IMPLICIT_SIGNALS', default=True)
LEARNING_COST_TRACKING = env.bool('LEARNING_COST_TRACKING', default=True)
LEARNING_UPDATE_THRESHOLD = env.int('LEARNING_UPDATE_THRESHOLD', default=5)
LEARNING_FEATURE_CACHE_TIMEOUT = env.int('LEARNING_FEATURE_CACHE_TIMEOUT', default=300)

# Personalization Parameters
ONBOARDING_MAX_RECOMMENDATIONS = env.int('ONBOARDING_MAX_RECOMMENDATIONS', default=5)
ONBOARDING_DEFAULT_BUDGET_CENTS = env.int('ONBOARDING_DEFAULT_BUDGET_CENTS', default=1000)  # $10
ONBOARDING_ADAPTIVE_BUDGETING = env.bool('ONBOARDING_ADAPTIVE_BUDGETING', default=True)
ONBOARDING_MIN_CONFIDENCE_THRESHOLD = env.float('ONBOARDING_MIN_CONFIDENCE_THRESHOLD', default=0.3)

# Holdback and A/B Testing
ONBOARDING_LEARNING_HOLDBACK_PCT = env.float('ONBOARDING_LEARNING_HOLDBACK_PCT', default=10.0)
ONBOARDING_EXPERIMENT_HOLDBACK_PCT = env.float('ONBOARDING_EXPERIMENT_HOLDBACK_PCT', default=5.0)

# Token Budget Limits
TOKEN_BUDGET_MAKER_SIMPLE = env.int('TOKEN_BUDGET_MAKER_SIMPLE', default=500)
TOKEN_BUDGET_MAKER_COMPLEX = env.int('TOKEN_BUDGET_MAKER_COMPLEX', default=1500)
TOKEN_BUDGET_CHECKER = env.int('TOKEN_BUDGET_CHECKER', default=800)
MAX_CITATIONS_PER_REC = env.int('MAX_CITATIONS_PER_REC', default=5)

# Cost and Performance Limits
ONBOARDING_MAX_TOKENS_PER_REC = env.int('ONBOARDING_MAX_TOKENS_PER_REC', default=2000)
ONBOARDING_MIN_CONFIDENCE_FOR_CHECKER = env.float('ONBOARDING_MIN_CONFIDENCE_FOR_CHECKER', default=0.6)
ONBOARDING_DAILY_COST_CAP = env.int('ONBOARDING_DAILY_COST_CAP', default=10000)  # $100

# Two-person approval threshold (risk score 0.0-1.0)
ONBOARDING_TWO_PERSON_THRESHOLD = env.float('ONBOARDING_TWO_PERSON_THRESHOLD', default=0.7)
USER_HOURLY_BUDGET_CENTS = env.int('USER_HOURLY_BUDGET_CENTS', default=1000)  # $10/hour per user

# Reranking Weights
RERANK_PERSONALIZATION_WEIGHT = env.float('RERANK_PERSONALIZATION_WEIGHT', default=0.4)
RERANK_CONSENSUS_WEIGHT = env.float('RERANK_CONSENSUS_WEIGHT', default=0.3)
RERANK_CITATION_WEIGHT = env.float('RERANK_CITATION_WEIGHT', default=0.2)
RERANK_COST_WEIGHT = env.float('RERANK_COST_WEIGHT', default=0.1)
RERANK_CACHE_TIMEOUT = env.int('RERANK_CACHE_TIMEOUT', default=300)

# Experiment Analysis Configuration
EXPERIMENT_ALPHA = env.float('EXPERIMENT_ALPHA', default=0.05)  # Significance level
EXPERIMENT_MIN_SAMPLE_SIZE = env.int('EXPERIMENT_MIN_SAMPLE_SIZE', default=30)
EXPERIMENT_MIN_EFFECT_SIZE = env.float('EXPERIMENT_MIN_EFFECT_SIZE', default=0.02)  # 2%
EXPERIMENT_MIN_POWER = env.float('EXPERIMENT_MIN_POWER', default=0.8)
EXPERIMENT_MIN_RUNTIME_HOURS = env.int('EXPERIMENT_MIN_RUNTIME_HOURS', default=48)
EXPERIMENT_BONFERRONI_CORRECTION = env.bool('EXPERIMENT_BONFERRONI_CORRECTION', default=True)

# Multi-Armed Bandit Configuration
BANDIT_EPSILON = env.float('BANDIT_EPSILON', default=0.1)  # Exploration rate
BANDIT_MIN_SAMPLES = env.int('BANDIT_MIN_SAMPLES', default=10)

# Security and Anomaly Detection
ENABLE_PII_REDACTION = env.bool('ENABLE_PII_REDACTION', default=True)
PII_REDACTION_PATTERNS = {}  # Custom patterns can be defined here
PII_ALLOWLISTED_FIELDS = {}  # Custom allowlisted fields
PII_HASH_SALT = env('PII_HASH_SALT', default='change_me_in_production')
MAX_INTERACTIONS_PER_HOUR = env.int('MAX_INTERACTIONS_PER_HOUR', default=100)
MAX_EXPERIMENTS_PER_DAY = env.int('MAX_EXPERIMENTS_PER_DAY', default=10)

# Metrics and Monitoring
METRICS_FLUSH_INTERVAL = env.int('METRICS_FLUSH_INTERVAL', default=60)  # seconds
METRICS_BUFFER_SIZE = env.int('METRICS_BUFFER_SIZE', default=1000)

# Service Level Objectives (SLOs)
SLO_REC_LATENCY_P95 = env.int('SLO_REC_LATENCY_P95', default=5000)  # ms
SLO_REC_LATENCY_P50 = env.int('SLO_REC_LATENCY_P50', default=2000)  # ms
SLO_ACCEPTANCE_RATE_MIN = env.float('SLO_ACCEPTANCE_RATE_MIN', default=0.6)
SLO_ERROR_RATE_MAX = env.float('SLO_ERROR_RATE_MAX', default=0.05)
SLO_AVAILABILITY_MIN = env.float('SLO_AVAILABILITY_MIN', default=0.995)

# API Rate Limiting for Personalization Endpoints
INTERACTION_THROTTLE_RATE = env('INTERACTION_THROTTLE_RATE', default='100/hour')
EXPERIMENT_THROTTLE_RATE = env('EXPERIMENT_THROTTLE_RATE', default='50/hour')

# Feature Flags for Gradual Rollout
PERSONALIZATION_FEATURE_FLAGS = {
    'enable_preference_learning': env.bool('FF_PREFERENCE_LEARNING', default=True),
    'enable_cost_optimization': env.bool('FF_COST_OPTIMIZATION', default=True),
    'enable_experiment_assignments': env.bool('FF_EXPERIMENT_ASSIGNMENTS', default=True),
    'enable_smart_caching': env.bool('FF_SMART_CACHING', default=True),
    'enable_adaptive_budgeting': env.bool('FF_ADAPTIVE_BUDGETING', default=True),
    'enable_provider_routing': env.bool('FF_PROVIDER_ROUTING', default=True),
    'enable_hot_path_precompute': env.bool('FF_HOT_PATH_PRECOMPUTE', default=False),
    'enable_streaming_responses': env.bool('FF_STREAMING_RESPONSES', default=False),
    'enable_anomaly_detection': env.bool('FF_ANOMALY_DETECTION', default=True),
    'enable_audit_logging': env.bool('FF_AUDIT_LOGGING', default=True)
}

# Tenant-specific Overrides (if needed)
TENANT_PERSONALIZATION_OVERRIDES = env.json('TENANT_PERSONALIZATION_OVERRIDES', default={})