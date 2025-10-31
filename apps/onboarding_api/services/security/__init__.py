"""
Security Services Package
Provides PII redaction, rate limiting, content validation, and security orchestration

Refactored from monolithic security.py (1,629 lines) to 6 focused modules:
- pii_redaction.py: PII detection and redaction
- rate_limiting.py: Rate limiting with budget controls
- circuit_breaker.py: Resilience patterns for rate limiting
- content_deduplication.py: Duplicate detection with versioning
- license_validation.py: License compliance and redistribution
- guardian.py: Security orchestration and RBAC
"""

# Core security services
from .pii_redaction import PIIRedactor, get_pii_redactor
from .rate_limiting import RateLimiter, RateLimitExceeded, get_rate_limiter
from .circuit_breaker import CircuitBreaker
from .content_deduplication import ContentDeduplicator, get_content_deduplicator
from .license_validation import LicenseValidator, get_license_validator
from .guardian import SecurityGuardian, get_security_guardian

# Backward compatibility exports
__all__ = [
    # Classes
    'PIIRedactor',
    'RateLimiter',
    'RateLimitExceeded',
    'CircuitBreaker',
    'ContentDeduplicator',
    'LicenseValidator',
    'SecurityGuardian',
    # Factory functions
    'get_pii_redactor',
    'get_rate_limiter',
    'get_content_deduplicator',
    'get_license_validator',
    'get_security_guardian',
]

# Module metadata
__version__ = '2.0.0'
__refactored__ = '2025-10-11'
__original_size__ = '1629 lines'
__modules__ = 6
