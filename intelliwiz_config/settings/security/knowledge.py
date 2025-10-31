"""
Knowledge Base Security Configuration

Allowlisted knowledge sources and security policies.

Following CLAUDE.md:
- Rule #1: No secrets in settings (use environment variables)
- Rule #7: <150 lines
- Security-first configuration

Sprint 1-2: Knowledge Management Security
"""

from django.core.exceptions import ImproperlyConfigured
import os

# =============================================================================
# ALLOWLISTED KNOWLEDGE SOURCES (SECURITY CRITICAL)
# =============================================================================

# Only these domains can be configured as knowledge sources
# Prevents arbitrary URL fetching and potential SSRF attacks
KB_ALLOWED_SOURCES = [
    # International Standards Organizations
    'iso.org',
    'www.iso.org',

    # US Government Standards
    'nist.gov',
    'www.nist.gov',
    'csrc.nist.gov',

    # Security Industry Standards
    'asis.org',
    'www.asisonline.org',

    # Indian Standards
    'bis.gov.in',
    'www.bis.gov.in',

    # Safety Standards
    'osha.gov',
    'www.osha.gov',

    # International Labor Organization
    'ilo.org',
    'www.ilo.org',

    # Internal domains (customize for deployment)
    'intranet.company.local',
    'docs.company.local',
]

# Environment-specific overrides (load from .env)
ADDITIONAL_ALLOWED_SOURCES_ENV = os.getenv('KB_ADDITIONAL_ALLOWED_SOURCES', '')
if ADDITIONAL_ALLOWED_SOURCES_ENV:
    additional_sources = [
        domain.strip()
        for domain in ADDITIONAL_ALLOWED_SOURCES_ENV.split(',')
        if domain.strip()
    ]
    KB_ALLOWED_SOURCES.extend(additional_sources)

# =============================================================================
# DOCUMENT INGESTION SECURITY
# =============================================================================

# Maximum document size (bytes) - prevents DoS via large documents
KB_MAX_DOCUMENT_SIZE_BYTES = int(os.getenv('KB_MAX_DOCUMENT_SIZE_BYTES', 50 * 1024 * 1024))  # 50 MB

# Allowed MIME types for document uploads
KB_ALLOWED_MIME_TYPES = [
    'application/pdf',
    'text/plain',
    'text/html',
    'text/markdown',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/msword',  # .doc
    'text/csv',
]

# Maximum chunks per document (prevents memory exhaustion)
KB_MAX_CHUNKS_PER_DOCUMENT = int(os.getenv('KB_MAX_CHUNKS_PER_DOCUMENT', 1000))

# Chunk size configuration
KB_DEFAULT_CHUNK_SIZE = int(os.getenv('KB_DEFAULT_CHUNK_SIZE', 1000))
KB_DEFAULT_CHUNK_OVERLAP = int(os.getenv('KB_DEFAULT_CHUNK_OVERLAP', 200))

# =============================================================================
# CONTENT SANITIZATION
# =============================================================================

# HTML sanitization - allowed tags
KB_ALLOWED_HTML_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'a', 'table', 'tr', 'td', 'th'
]

# Forbidden patterns in document content (security red flags)
# Blocks XSS, script injection, and malicious content
KB_FORBIDDEN_PATTERNS = [
    r'<script[^>]*>',  # JavaScript injection
    r'javascript:',  # JavaScript protocol
    r'on\w+\s*=',  # Event handlers (onclick, onload, etc)
    r'data:text/html',  # Data URLs that could execute code
]

# =============================================================================
# REVIEW WORKFLOW CONFIGURATION
# =============================================================================

# Require two-person approval for all knowledge sources
KB_REQUIRE_TWO_PERSON_APPROVAL = os.getenv('KB_REQUIRE_TWO_PERSON_APPROVAL', 'true').lower() == 'true'

# Minimum quality scores for publication
KB_MIN_ACCURACY_SCORE = float(os.getenv('KB_MIN_ACCURACY_SCORE', 0.7))
KB_MIN_COMPLETENESS_SCORE = float(os.getenv('KB_MIN_COMPLETENESS_SCORE', 0.7))
KB_MIN_RELEVANCE_SCORE = float(os.getenv('KB_MIN_RELEVANCE_SCORE', 0.7))

# Auto-rejection if any score below threshold
KB_AUTO_REJECT_THRESHOLD = float(os.getenv('KB_AUTO_REJECT_THRESHOLD', 0.5))

# =============================================================================
# SEARCH AND RETRIEVAL
# =============================================================================

# Maximum search results
KB_MAX_SEARCH_RESULTS = int(os.getenv('KB_MAX_SEARCH_RESULTS', 50))

# Default search mode
KB_DEFAULT_SEARCH_MODE = os.getenv('KB_DEFAULT_SEARCH_MODE', 'hybrid')  # 'semantic', 'text', 'hybrid'

# Authority level weights for ranking
KB_AUTHORITY_WEIGHTS = {
    'official': 1.0,
    'high': 0.9,
    'medium': 0.7,
    'low': 0.5,
}

# Freshness decay (documents older than N days get lower ranking)
KB_FRESHNESS_DECAY_DAYS = int(os.getenv('KB_FRESHNESS_DECAY_DAYS', 730))  # 2 years

# =============================================================================
# DATA RETENTION
# =============================================================================

# How long to keep ingestion job logs (days)
KB_INGESTION_JOB_RETENTION_DAYS = int(os.getenv('KB_INGESTION_JOB_RETENTION_DAYS', 90))

# How long to keep old document versions (days)
KB_OLD_VERSION_RETENTION_DAYS = int(os.getenv('KB_OLD_VERSION_RETENTION_DAYS', 365))

# How long to keep rejected documents (days)
KB_REJECTED_DOCUMENT_RETENTION_DAYS = int(os.getenv('KB_REJECTED_DOCUMENT_RETENTION_DAYS', 30))

# =============================================================================
# VALIDATION
# =============================================================================

def validate_knowledge_security_settings():
    """Validate knowledge security settings at startup."""
    errors = []

    # Validate at least one allowed source
    if not KB_ALLOWED_SOURCES:
        errors.append("KB_ALLOWED_SOURCES is empty - no knowledge sources can be added")

    # Validate size limits
    if KB_MAX_DOCUMENT_SIZE_BYTES < 1024 * 1024:  # Less than 1MB
        errors.append(f"KB_MAX_DOCUMENT_SIZE_BYTES too small: {KB_MAX_DOCUMENT_SIZE_BYTES}")

    # Validate quality score thresholds
    if not (0 <= KB_MIN_ACCURACY_SCORE <= 1):
        errors.append(f"KB_MIN_ACCURACY_SCORE out of range: {KB_MIN_ACCURACY_SCORE}")

    if errors:
        raise ImproperlyConfigured(
            f"Knowledge Base security configuration errors:\n" + "\n".join(errors)
        )


# Run validation on import
validate_knowledge_security_settings()
