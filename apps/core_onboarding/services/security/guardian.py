"""
Security Guardian - Main Security Orchestration Service
Coordinates PII redaction, rate limiting, content validation, and RBAC
"""
import hashlib
import logging
from typing import Dict, Any, List, Tuple
from urllib.parse import urlparse
from django.conf import settings
from datetime import datetime
from .pii_redaction import PIIRedactor
from .rate_limiting import RateLimiter, RateLimitExceeded
from .content_deduplication import ContentDeduplicator
from .license_validation import LicenseValidator
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)


class SecurityGuardian:
    """
    Comprehensive security orchestrator for onboarding API
    Coordinates all security services with unified interface
    """

    def __init__(self):
        self.pii_redactor = PIIRedactor()
        self.rate_limiter = RateLimiter()
        self.content_deduplicator = ContentDeduplicator()
        self.license_validator = LicenseValidator()
        self.source_allowlist = self._load_source_allowlist()

    def sanitize_prompt(self, prompt: str, user_id: str, context: str = 'prompt') -> Tuple[str, Dict[str, Any]]:
        """Sanitize prompt before sending to LLM"""
        # Redact PII
        sanitized_prompt, redaction_meta = self.pii_redactor.redact_text(prompt, context)

        # Check rate limits
        rate_allowed, rate_info = self.rate_limiter.check_rate_limit(user_id, 'llm_calls', 'requests')

        security_metadata = {
            'pii_redacted': len(redaction_meta.get('redactions', [])) > 0,
            'redaction_metadata': redaction_meta,
            'rate_limit_check': rate_info,
            'rate_limited': not rate_allowed,
            'sanitized_at': datetime.now().isoformat()
        }

        if not rate_allowed:
            raise RateLimitExceeded(f"Rate limit exceeded: {rate_info}")

        return sanitized_prompt, security_metadata

    def sanitize_response(self, response: Dict[str, Any], context: str = 'response') -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Sanitize response before returning to user"""
        sanitized_response, redaction_meta = self.pii_redactor.redact_dict(response, context)

        security_metadata = {
            'response_sanitized': True,
            'redaction_metadata': redaction_meta,
            'sanitized_at': datetime.now().isoformat()
        }

        return sanitized_response, security_metadata

    def validate_source_url(self, url: str) -> bool:
        """Validate if URL is from an allowed source"""
        if not self.source_allowlist:
            return False

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            return any(
                domain == allowed_domain or domain.endswith('.' + allowed_domain)
                for allowed_domain in self.source_allowlist
            )

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Error validating source URL {url}: {str(e)}")
            return False

    def validate_document_security(
        self,
        content: str,
        document_info: Dict[str, Any],
        source_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Comprehensive document security validation"""
        security_validation = {
            'overall_risk': 'low',
            'security_passed': True,
            'violations': [],
            'recommendations': [],
            'quarantine_required': False,
            'validation_timestamp': datetime.now().isoformat()
        }

        try:
            # 1. PII Scanning
            _, pii_scan = self.pii_redactor.redact_text(content, 'document_ingestion')

            # 2. License Validation
            license_validation = self.license_validator.validate_document_license(content, source_metadata)

            # 3. Content Deduplication
            content_hash = document_info.get('content_hash') or hashlib.sha256(content.encode()).hexdigest()
            dedup_result = self.content_deduplicator.check_duplicate_with_versioning(content_hash, document_info)

            # 4. Quarantine Decision
            quarantine_required = self.license_validator.should_quarantine_document(license_validation, pii_scan)

            # Aggregate results
            security_validation.update({
                'pii_scan_result': pii_scan,
                'license_validation': license_validation,
                'deduplication_result': dedup_result,
                'quarantine_required': quarantine_required
            })

            # Calculate overall risk
            risk_factors = []
            if pii_scan.get('redactions', []):
                risk_factors.append('pii_detected')
            if not license_validation.get('redistribution_allowed', True):
                risk_factors.append('redistribution_restricted')
            if dedup_result.get('is_duplicate', False) and not dedup_result.get('allow_duplicate', False):
                risk_factors.append('duplicate_content')

            if len(risk_factors) >= 2:
                security_validation['overall_risk'] = 'high'
                security_validation['security_passed'] = False
            elif len(risk_factors) == 1:
                security_validation['overall_risk'] = 'medium'

            # Generate recommendations
            if quarantine_required:
                security_validation['recommendations'].append('Document requires quarantine and manual review')
            if license_validation.get('attribution_required', False):
                security_validation['recommendations'].append('Attribution required for this content')
            if dedup_result.get('similar_content'):
                security_validation['recommendations'].append('Review for potential content overlap')

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error in document security validation: {str(e)}")
            security_validation.update({
                'overall_risk': 'high',
                'security_passed': False,
                'violations': [{'type': 'validation_error', 'description': str(e)}]
            })

        return security_validation

    def check_rbac_permissions(self, user, action: str, resource: str = None) -> Dict[str, Any]:
        """Check role-based access control permissions"""
        permission_result = {
            'allowed': False,
            'user_roles': [],
            'required_roles': [],
            'permission_source': 'denied'
        }

        try:
            # Get user capabilities
            user_capabilities = getattr(user, 'capabilities', {})
            is_staff = getattr(user, 'is_staff', False)

            # Determine user roles
            user_roles = []
            if is_staff:
                user_roles.append('staff')
            if user_capabilities.get('knowledge_curator', False):
                user_roles.append('knowledge_curator')
            if user_capabilities.get('admin', False):
                user_roles.append('admin')

            permission_result['user_roles'] = user_roles

            # Define required roles
            action_requirements = {
                'ingest': ['knowledge_curator', 'admin'],
                'publish': ['knowledge_curator', 'admin'],
                'review': ['knowledge_curator', 'admin', 'staff'],
                'search': ['staff'],
                'read': ['staff']
            }

            required_roles = action_requirements.get(action, ['admin'])
            permission_result['required_roles'] = required_roles

            # Check permissions
            if any(role in user_roles for role in required_roles):
                permission_result['allowed'] = True
                permission_result['permission_source'] = f"role_{action}"

            logger.info(
                f"RBAC check: user {getattr(user, 'email', 'unknown')} action {action} - "
                f"{'allowed' if permission_result['allowed'] else 'denied'}"
            )

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error checking RBAC permissions: {str(e)}")
            permission_result['error'] = str(e)

        return permission_result

    def _load_source_allowlist(self) -> List[str]:
        """Load allowed source domains"""
        default_allowlist = [
            'docs.python.org',
            'developer.mozilla.org',
            'stackoverflow.com',
            'github.com',
            'djangoproject.com'
        ]

        custom_allowlist = getattr(settings, 'ONBOARDING_SOURCE_ALLOWLIST', [])
        return default_allowlist + custom_allowlist


def get_security_guardian() -> SecurityGuardian:
    """Factory function to get security guardian"""
    return SecurityGuardian()
