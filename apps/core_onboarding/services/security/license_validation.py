"""
License and Redistribution Validation Service
Validates document licenses and determines redistribution rights
"""
import re
import uuid
import logging
from typing import Dict, Any, List
from django.conf import settings
from django.core.cache import cache
from datetime import datetime
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS


logger = logging.getLogger(__name__)


class LicenseValidator:
    """
    License compliance and redistribution validation
    Merges pattern detection and attribution management
    """

    def __init__(self):
        self.restricted_licenses = {
            'copyright_reserved': {
                'patterns': [r'all rights reserved', r'copyright.*reserved', r'proprietary'],
                'redistribution_allowed': False,
                'attribution_required': True
            },
            'creative_commons_nc': {
                'patterns': [r'creative commons.*non-commercial', r'cc.*nc'],
                'redistribution_allowed': False,
                'attribution_required': True
            },
            'confidential': {
                'patterns': [r'confidential', r'internal use only', r'proprietary'],
                'redistribution_allowed': False,
                'attribution_required': True
            }
        }

        self.permissive_licenses = {
            'public_domain': {
                'patterns': [r'public domain', r'no rights reserved'],
                'redistribution_allowed': True,
                'attribution_required': False
            },
            'creative_commons_open': {
                'patterns': [r'creative commons.*attribution', r'cc.*by'],
                'redistribution_allowed': True,
                'attribution_required': True
            },
            'government_work': {
                'patterns': [r'government work', r'official.*document', r'nist\.gov', r'uscis\.gov'],
                'redistribution_allowed': True,
                'attribution_required': True
            }
        }

        self.blocked_patterns = getattr(settings, 'KB_BLOCKED_LICENSE_PATTERNS', [
            r'proprietary', r'internal use only', r'confidential', r'trade secret'
        ])

        self.attribution_patterns = getattr(settings, 'KB_ATTRIBUTION_PATTERNS', [
            r'creative commons', r'attribution required', r'cite as', r'reference as'
        ])

    def validate_document_license(self, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate document license and redistribution rights"""
        validation_result = {
            'license_detected': None,
            'redistribution_allowed': False,
            'attribution_required': True,
            'restrictions': [],
            'warnings': [],
            'license_metadata': {}
        }

        try:
            content_lower = content.lower()

            # Check restricted licenses
            for license_name, license_info in self.restricted_licenses.items():
                for pattern in license_info['patterns']:
                    if re.search(pattern, content_lower):
                        validation_result.update({
                            'license_detected': license_name,
                            'redistribution_allowed': license_info['redistribution_allowed'],
                            'attribution_required': license_info['attribution_required']
                        })

                        if not license_info['redistribution_allowed']:
                            validation_result['restrictions'].append({
                                'type': 'redistribution_prohibited',
                                'description': f'License {license_name} prohibits redistribution',
                                'detected_pattern': pattern
                            })

                        logger.info(f"Detected restricted license: {license_name}")
                        return validation_result

            # Check permissive licenses
            for license_name, license_info in self.permissive_licenses.items():
                for pattern in license_info['patterns']:
                    if re.search(pattern, content_lower):
                        validation_result.update({
                            'license_detected': license_name,
                            'redistribution_allowed': license_info['redistribution_allowed'],
                            'attribution_required': license_info['attribution_required']
                        })

                        logger.info(f"Detected permissive license: {license_name}")
                        return validation_result

            # No license detected - conservative approach
            validation_result['warnings'].append({
                'type': 'no_license_detected',
                'description': 'No explicit license information found',
                'recommendation': 'Verify redistribution rights with source'
            })

            validation_result.update({
                'license_detected': 'unknown',
                'redistribution_allowed': False,
                'attribution_required': True
            })

        except CACHE_EXCEPTIONS as e:
            logger.error(f"Error validating license: {str(e)}")
            validation_result['warnings'].append({
                'type': 'validation_error',
                'description': f'License validation failed: {str(e)}'
            })

        return validation_result

    def validate_redistribution_rights(self, content: str, source_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate if content can be redistributed in knowledge base"""
        validation = {
            'redistribution_allowed': True,
            'attribution_required': False,
            'license_restrictions': [],
            'compliance_requirements': [],
            'risk_assessment': 'low'
        }

        try:
            content_lower = content.lower()

            # Check blocked patterns
            for pattern in self.blocked_patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    validation.update({
                        'redistribution_allowed': False,
                        'risk_assessment': 'high'
                    })
                    validation['license_restrictions'].append({
                        'type': 'blocked_license',
                        'pattern': pattern,
                        'description': f'Content contains blocked license pattern: {pattern}'
                    })

            # Check attribution requirements
            for pattern in self.attribution_patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    validation['attribution_required'] = True
                    validation['compliance_requirements'].append({
                        'type': 'attribution_required',
                        'pattern': pattern,
                        'description': f'Content requires attribution: {pattern}'
                    })

            # Check source restrictions
            if source_metadata:
                source_restrictions = self._check_source_restrictions(source_metadata)
                validation['license_restrictions'].extend(source_restrictions)

            # Update risk assessment
            if validation['license_restrictions']:
                validation['risk_assessment'] = 'medium' if validation['redistribution_allowed'] else 'high'

        except CACHE_EXCEPTIONS as e:
            logger.error(f"Error validating redistribution rights: {str(e)}")
            validation.update({
                'redistribution_allowed': False,
                'risk_assessment': 'high',
                'license_restrictions': [{'type': 'validation_error', 'description': str(e)}]
            })

        return validation

    def should_quarantine_document(self, license_validation: Dict[str, Any], pii_scan_result: Dict[str, Any]) -> bool:
        """Determine if document should be quarantined"""
        if not license_validation.get('redistribution_allowed', False):
            logger.info("Quarantining document: redistribution prohibited")
            return True

        pii_redactions = pii_scan_result.get('redactions', [])
        high_sensitivity_pii = [r for r in pii_redactions if r.get('sensitivity') == 'high']

        if high_sensitivity_pii:
            logger.info(f"Quarantining document: {len(high_sensitivity_pii)} high-sensitivity PII items")
            return True

        if len(pii_redactions) > 5:
            logger.info(f"Quarantining document: excessive PII ({len(pii_redactions)} items)")
            return True

        return False

    def create_quarantine_record(self, document_info: Dict[str, Any], quarantine_reason: str) -> Dict[str, Any]:
        """Create quarantine record for blocked document"""
        quarantine_record = {
            'quarantine_id': str(uuid.uuid4()),
            'document_title': document_info.get('title', 'Unknown'),
            'source_url': document_info.get('source_url', ''),
            'content_hash': document_info.get('content_hash', ''),
            'quarantine_reason': quarantine_reason,
            'quarantined_at': datetime.now().isoformat(),
            'requires_manual_review': True,
            'auto_release_eligible': False
        }

        cache_key = f"quarantine:{quarantine_record['quarantine_id']}"
        cache.set(cache_key, quarantine_record, 86400 * 7)  # 7 days

        logger.warning(f"Document quarantined: {quarantine_reason}")
        return quarantine_record

    def create_attribution_record(self, document_info: Dict[str, Any], license_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create attribution record for compliant use"""
        attribution = {
            'attribution_id': str(uuid.uuid4()),
            'document_title': document_info.get('title', ''),
            'source_organization': document_info.get('source_organization', ''),
            'source_url': document_info.get('source_url', ''),
            'license_type': license_info.get('license_detected', 'unknown'),
            'attribution_text': self._generate_attribution_text(document_info, license_info),
            'created_at': datetime.now().isoformat()
        }

        return attribution

    def _check_source_restrictions(self, source_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for source-specific license restrictions"""
        restrictions = []
        source_url = source_metadata.get('source_url', '').lower()

        restrictive_domains = ['proprietary.com', 'internal.company.com', 'private.org']
        for domain in restrictive_domains:
            if domain in source_url:
                restrictions.append({
                    'type': 'restrictive_source',
                    'description': f'Source {domain} may have redistribution restrictions',
                    'source': domain
                })

        if 'copyright' in str(source_metadata).lower():
            restrictions.append({
                'type': 'copyright_notice',
                'description': 'Copyright notice detected in source metadata',
                'recommendation': 'Verify redistribution rights'
            })

        return restrictions

    def _generate_attribution_text(self, document_info: Dict[str, Any], license_info: Dict[str, Any]) -> str:
        """Generate proper attribution text"""
        title = document_info.get('title', 'Unknown Document')
        org = document_info.get('source_organization', 'Unknown Organization')
        url = document_info.get('source_url', '')

        attribution = f"Source: {title} by {org}"
        if url:
            attribution += f" ({url})"

        license_type = license_info.get('license_detected')
        if license_type and license_type != 'unknown':
            attribution += f" - License: {license_type}"

        attribution += f" - Accessed: {datetime.now().strftime('%Y-%m-%d')}"

        return attribution


def get_license_validator() -> LicenseValidator:
    """Factory function to get license validator"""
    return LicenseValidator()
