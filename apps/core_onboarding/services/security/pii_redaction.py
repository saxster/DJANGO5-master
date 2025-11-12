"""
PII (Personally Identifiable Information) Redaction Service
Sanitizes prompts and logs before LLM processing
"""
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class PIIRedactor:
    """
    PII redaction service with pattern-based detection
    Supports text, dict, and list sanitization
    """

    def __init__(self):
        self.redaction_patterns = self._load_redaction_patterns()
        self.allowlisted_fields = self._load_allowlisted_fields()

    def redact_text(self, text: str, context: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Redact PII from text and return sanitized version with metadata
        """
        if not text:
            return text, {}

        redacted_text = text
        redactions = []

        # Apply redaction patterns
        for pattern_name, pattern_config in self.redaction_patterns.items():
            regex = pattern_config['regex']
            replacement = pattern_config['replacement']
            sensitivity = pattern_config.get('sensitivity', 'high')

            matches = re.finditer(regex, redacted_text, re.IGNORECASE)
            for match in matches:
                original_value = match.group()

                redaction_record = {
                    'type': pattern_name,
                    'original_length': len(original_value),
                    'position': match.start(),
                    'sensitivity': sensitivity,
                    'redacted_at': datetime.now().isoformat()
                }

                # Generate replacement based on type
                if pattern_name == 'email':
                    redacted_value = self._redact_email(original_value)
                elif pattern_name == 'phone':
                    redacted_value = self._redact_phone(original_value)
                elif pattern_name == 'ssn':
                    redacted_value = '[REDACTED_SSN]'
                elif pattern_name == 'credit_card':
                    redacted_value = '[REDACTED_CC]'
                else:
                    redacted_value = replacement

                redacted_text = redacted_text.replace(original_value, redacted_value)
                redactions.append(redaction_record)

        # Context-specific redaction
        if context in ['prompt', 'log']:
            redacted_text, additional_redactions = self._redact_context_specific(
                redacted_text, context
            )
            redactions.extend(additional_redactions)

        redaction_metadata = {
            'redactions_count': len(redactions),
            'redactions': redactions,
            'context': context,
            'redacted_at': datetime.now().isoformat()
        }

        return redacted_text, redaction_metadata

    def redact_dict(self, data: Dict[str, Any], context: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Redact PII from dictionary recursively"""
        if not isinstance(data, dict):
            return data, {}

        redacted_data = {}
        all_redactions = []

        for key, value in data.items():
            if self._is_field_allowlisted(key, context):
                redacted_data[key] = value
                continue

            if isinstance(value, str):
                redacted_value, redaction_meta = self.redact_text(value, context)
                redacted_data[key] = redacted_value
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            elif isinstance(value, dict):
                redacted_value, redaction_meta = self.redact_dict(value, context)
                redacted_data[key] = redacted_value
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            elif isinstance(value, list):
                redacted_value, redaction_meta = self._redact_list(value, context)
                redacted_data[key] = redacted_value
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            else:
                redacted_data[key] = value

        return redacted_data, {'redactions': all_redactions}

    def _load_redaction_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load PII redaction patterns"""
        patterns = {
            'email': {
                'regex': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                'replacement': '[REDACTED_EMAIL]',
                'sensitivity': 'medium'
            },
            'phone': {
                'regex': r'(\+?1[-.\s]?)?(\(?[0-9]{3}\)?[-.\s]?)[0-9]{3}[-.\s]?[0-9]{4}',
                'replacement': '[REDACTED_PHONE]',
                'sensitivity': 'medium'
            },
            'ssn': {
                'regex': r'\b\d{3}-?\d{2}-?\d{4}\b',
                'replacement': '[REDACTED_SSN]',
                'sensitivity': 'high'
            },
            'credit_card': {
                'regex': r'\b(?:\d{4}[-.\s]?){3}\d{4}\b',
                'replacement': '[REDACTED_CC]',
                'sensitivity': 'high'
            },
            'ip_address': {
                'regex': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
                'replacement': '[REDACTED_IP]',
                'sensitivity': 'low'
            }
        }

        custom_patterns = getattr(settings, 'PII_REDACTION_PATTERNS', {})
        patterns.update(custom_patterns)
        return patterns

    def _load_allowlisted_fields(self) -> Dict[str, List[str]]:
        """Load fields allowed to pass through without redaction"""
        default_allowlist = {
            'general': ['id', 'uuid', 'created_at', 'updated_at', 'status'],
            'business': ['business_unit_type', 'security_level', 'max_users'],
            'system': ['trace_id', 'session_id', 'confidence_score']
        }

        custom_allowlist = getattr(settings, 'PII_ALLOWLISTED_FIELDS', {})
        for context, fields in custom_allowlist.items():
            if context in default_allowlist:
                default_allowlist[context].extend(fields)
            else:
                default_allowlist[context] = fields

        return default_allowlist

    def _is_field_allowlisted(self, field_name: str, context: Optional[str] = None) -> bool:
        """Check if field is allowlisted"""
        if field_name in self.allowlisted_fields.get('general', []):
            return True
        if context and field_name in self.allowlisted_fields.get(context, []):
            return True
        return False

    def _redact_email(self, email: str) -> str:
        """Redact email while preserving domain"""
        try:
            local, domain = email.split('@')
            if len(local) > 2:
                redacted_local = local[0] + '*' * (len(local) - 2) + local[-1]
            else:
                redacted_local = '*' * len(local)
            return f"{redacted_local}@{domain}"
        except ValueError:
            return '[REDACTED_EMAIL]'

    def _redact_phone(self, phone: str) -> str:
        """Redact phone while preserving area code"""
        digits = re.sub(r'\D', '', phone)
        if len(digits) >= 10:
            return f"({digits[:3]}) ***-****"
        return '[REDACTED_PHONE]'

    def _redact_context_specific(self, text: str, context: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply context-specific redaction rules"""
        redactions = []
        redacted_text = text

        if context == 'log':
            # Redact potential API keys
            api_key_pattern = r'\b[A-Za-z0-9]{20,}\b'
            matches = re.finditer(api_key_pattern, redacted_text)
            for match in matches:
                if len(match.group()) > 16:
                    redacted_text = redacted_text.replace(match.group(), '[REDACTED_TOKEN]')
                    redactions.append({
                        'type': 'api_token',
                        'position': match.start(),
                        'sensitivity': 'high'
                    })

        return redacted_text, redactions

    def _redact_list(self, data_list: List[Any], context: Optional[str] = None) -> Tuple[List[Any], Dict[str, Any]]:
        """Redact PII from list items"""
        redacted_list = []
        all_redactions = []

        for item in data_list:
            if isinstance(item, str):
                redacted_item, redaction_meta = self.redact_text(item, context)
                redacted_list.append(redacted_item)
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            elif isinstance(item, dict):
                redacted_item, redaction_meta = self.redact_dict(item, context)
                redacted_list.append(redacted_item)
                if redaction_meta.get('redactions'):
                    all_redactions.extend(redaction_meta['redactions'])
            else:
                redacted_list.append(item)

        return redacted_list, {'redactions': all_redactions}


def get_pii_redactor() -> PIIRedactor:
    """Factory function to get PII redactor"""
    return PIIRedactor()
