"""
PII Redaction Service for Stream Testbench
Ensures sensitive data is properly stripped/hashed before storage
"""

import hashlib
import json
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from django.conf import settings

logger = logging.getLogger('streamlab.pii')


class PIIRedactor:
    """
    Advanced PII redaction service for stream event data
    Follows principle of data minimization - allowlist approach only
    """

    # Default allowlisted fields per data type
    DEFAULT_ALLOWLISTS = {
        'voice_data': [
            'quality_score', 'duration_ms', 'confidence_score',
            'processing_time_ms', 'timestamp', 'verified'
        ],
        'behavioral_data': [
            'event_type', 'timestamp', 'session_duration_ms',
            'interaction_count', 'performance_score'
        ],
        'session_data': [
            'session_start', 'session_end', 'duration_ms',
            'event_count', 'status'
        ],
        'metrics': [
            'metric_name', 'value', 'timestamp', 'unit',
            'aggregation_type'
        ],
        'websocket_meta': [
            'message_type', 'message_size', 'timestamp',
            'processing_time_ms', 'status_code'
        ],
        'mqtt_meta': [
            'topic', 'qos', 'retain', 'message_size',
            'timestamp', 'broker_timestamp'
        ],
        # LLM logs (Sprint 10.1 - Data Privacy Extension)
        'llm_prompt': [
            'prompt_length', 'model', 'provider', 'timestamp',
            'operation', 'language', 'token_count'
        ],
        'llm_response': [
            'response_length', 'model', 'provider', 'timestamp',
            'confidence_score', 'token_count', 'latency_ms', 'cost_usd'
        ],
        'llm_usage_log': [
            'provider', 'operation', 'input_tokens', 'output_tokens',
            'cost_usd', 'latency_ms', 'created_at', 'model'
        ],
        'recommendation_trace': [
            'recommendation_id', 'operation', 'timestamp',
            'confidence_score', 'status', 'maker_model', 'checker_model'
        ]
    }

    # Fields that should be hashed instead of removed
    HASH_FIELDS = {
        'user_id', 'device_id', 'session_id', 'client_id',
        'verification_id', 'request_id', 'correlation_id'
    }

    # Fields that should ALWAYS be removed (security-critical)
    REMOVE_FIELDS = {
        'password', 'token', 'api_key', 'secret', 'private_key',
        'voice_sample', 'audio_data', 'audio_blob', 'voice_blob',
        'image_data', 'photo_blob', 'biometric_template',
        'precise_location', 'gps_coordinates', 'latitude', 'longitude',
        'full_name', 'email', 'phone_number', 'address',
        'free_text', 'comment', 'message_content', 'chat_message',
        'credit_card', 'ssn', 'national_id', 'passport_number'
    }

    # Patterns for detecting sensitive data in strings
    SENSITIVE_PATTERNS = [
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit cards
        r'\b\d{3}[\s-]?\d{2}[\s-]?\d{4}\b',             # SSN
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{3}[\s-]?\d{3}[\s-]?\d{4}\b',             # Phone numbers
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',                 # IP addresses (basic)
    ]

    def __init__(self, salt: str = None):
        """
        Initialize PII redactor with optional salt for hashing
        """
        self.salt = salt or settings.SECRET_KEY[:16]  # Use first 16 chars of SECRET_KEY

    def redact(self, data: Dict[str, Any], endpoint: str,
               custom_rules: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Redact PII from data payload

        Args:
            data: Original data payload
            endpoint: Endpoint/topic this data came from
            custom_rules: Optional custom redaction rules

        Returns:
            Sanitized data with PII removed/hashed
        """
        try:
            if not isinstance(data, dict):
                # For non-dict data, return minimal metadata
                return {
                    'data_type': type(data).__name__,
                    'size_bytes': len(str(data)) if data else 0,
                    'timestamp': datetime.now().isoformat(),
                    'redacted': True
                }

            # Determine data type from endpoint or payload structure
            data_type = self._identify_data_type(endpoint, data)

            # Get redaction rules (custom rules override defaults)
            rules = custom_rules or self._get_redaction_rules(data_type)

            # Apply redaction
            sanitized = self._apply_redaction(data, rules)

            # Add redaction metadata
            sanitized['_pii_redacted'] = True
            sanitized['_redaction_timestamp'] = datetime.now().isoformat()
            sanitized['_data_type'] = data_type
            sanitized['_endpoint'] = self._sanitize_endpoint(endpoint)

            logger.debug(
                f"PII redaction completed",
                extra={
                    'data_type': data_type,
                    'endpoint': endpoint,
                    'original_fields': len(data),
                    'sanitized_fields': len(sanitized)
                }
            )

            return sanitized

        except (ValueError, TypeError) as e:
            logger.error(f"PII redaction failed: {e}", exc_info=True)
            # In case of error, return minimal safe data
            return {
                'redaction_error': True,
                'error_message': 'Failed to redact PII',
                'timestamp': datetime.now().isoformat(),
                'original_size': len(str(data)) if data else 0
            }

    def _identify_data_type(self, endpoint: str, data: Dict[str, Any]) -> str:
        """Identify the type of data from endpoint and payload structure"""
        endpoint_lower = endpoint.lower()

        # Check endpoint patterns
        if 'voice' in endpoint_lower or 'audio' in endpoint_lower:
            return 'voice_data'
        elif 'behavioral' in endpoint_lower or 'behavior' in endpoint_lower:
            return 'behavioral_data'
        elif 'session' in endpoint_lower:
            return 'session_data'
        elif 'metric' in endpoint_lower:
            return 'metrics'
        elif 'ws/' in endpoint_lower or 'websocket' in endpoint_lower:
            return 'websocket_meta'
        elif 'mqtt' in endpoint_lower or endpoint_lower.startswith('/'):
            return 'mqtt_meta'

        # Check payload structure
        if 'voice_sample' in data or 'audio_data' in data:
            return 'voice_data'
        elif 'event_type' in data and 'interaction' in str(data).lower():
            return 'behavioral_data'
        elif 'session_start' in data or 'session_id' in data:
            return 'session_data'
        elif 'metric_name' in data or 'value' in data:
            return 'metrics'

        return 'unknown'

    def _get_redaction_rules(self, data_type: str) -> Dict[str, Any]:
        """Get redaction rules for specific data type"""
        return {
            'allowlisted_fields': set(self.DEFAULT_ALLOWLISTS.get(data_type, [])),
            'hash_fields': self.HASH_FIELDS,
            'remove_fields': self.REMOVE_FIELDS
        }

    def _apply_redaction(self, data: Dict[str, Any],
                        rules: Dict[str, Any]) -> Dict[str, Any]:
        """Apply redaction rules to data"""
        sanitized = {}
        allowlisted = rules.get('allowlisted_fields', set())
        hash_fields = rules.get('hash_fields', set())
        remove_fields = rules.get('remove_fields', set())

        for key, value in data.items():
            key_lower = key.lower()

            # Always remove sensitive fields
            if key_lower in remove_fields or any(rf in key_lower for rf in remove_fields):
                logger.debug(f"Removing sensitive field: {key}")
                continue

            # Hash ID fields
            if key_lower in hash_fields or any(hf in key_lower for hf in hash_fields):
                sanitized[key] = self._hash_value(str(value))
                continue

            # Include allowlisted fields
            if key in allowlisted or key_lower in allowlisted:
                sanitized[key] = self._sanitize_value(value)
                continue

            # For non-allowlisted fields, check if they contain sensitive patterns
            if self._contains_sensitive_data(str(value)):
                logger.debug(f"Removing field with sensitive pattern: {key}")
                continue

            # GPS coordinates - bucket to city level
            if 'lat' in key_lower or 'lon' in key_lower or 'gps' in key_lower:
                if isinstance(value, (int, float)):
                    sanitized[f"{key}_bucketed"] = round(float(value), 1)  # ~10km accuracy
                continue

            # For unknown fields, be conservative - don't include
            logger.debug(f"Excluding non-allowlisted field: {key}")

        return sanitized

    def _hash_value(self, value: str) -> str:
        """Hash a value with salt for anonymization"""
        if not value:
            return "empty"

        # Use SHA-256 with salt
        hash_input = f"{self.salt}{value}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()[:16]  # First 16 chars for brevity

    def _sanitize_value(self, value: Any) -> Any:
        """Sanitize individual values"""
        if isinstance(value, str):
            # Remove sensitive patterns from strings
            sanitized = value
            for pattern in self.SENSITIVE_PATTERNS:
                sanitized = re.sub(pattern, '[REDACTED]', sanitized)
            return sanitized
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries (limited depth)
            return {k: self._sanitize_value(v) for k, v in value.items()
                   if not self._is_sensitive_key(k)}
        elif isinstance(value, list):
            # Sanitize lists (but limit size)
            return [self._sanitize_value(item) for item in value[:10]]  # Max 10 items
        else:
            return value

    def _contains_sensitive_data(self, text: str) -> bool:
        """Check if text contains sensitive data patterns"""
        if not isinstance(text, str):
            return False

        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a key name indicates sensitive data"""
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self.REMOVE_FIELDS)

    def _sanitize_endpoint(self, endpoint: str) -> str:
        """Sanitize endpoint URL to remove sensitive path parameters"""
        if not endpoint:
            return "unknown"

        # Remove query parameters and sensitive path components
        endpoint = endpoint.split('?')[0]  # Remove query string

        # Replace sensitive path parameters with placeholders
        endpoint = re.sub(r'/users?/\d+', '/users/{id}', endpoint)
        endpoint = re.sub(r'/devices?/[\w-]+', '/devices/{device_id}', endpoint)
        endpoint = re.sub(r'/sessions?/[\w-]+', '/sessions/{session_id}', endpoint)

        return endpoint

    def calculate_schema_hash(self, data: Dict[str, Any]) -> str:
        """Calculate hash of data schema for anomaly detection"""
        if not isinstance(data, dict):
            return hashlib.sha256(str(type(data)).encode()).hexdigest()[:16]

        # Create schema signature based on keys and value types
        schema_signature = {}
        for key, value in data.items():
            if not key.startswith('_'):  # Ignore metadata fields
                schema_signature[key] = type(value).__name__

        # Sort keys for consistent hashing
        schema_json = json.dumps(schema_signature, sort_keys=True)
        return hashlib.sha256(schema_json.encode()).hexdigest()[:16]

    def get_retention_category(self, data_type: str) -> str:
        """Determine retention category for data type (Sprint 10 enhanced)."""
        if data_type in ['voice_data', 'behavioral_data']:
            return 'sanitized_metadata'  # 14 days
        elif data_type in ['websocket_meta', 'mqtt_meta']:
            return 'sanitized_metadata'  # 14 days
        elif data_type == 'metrics':
            return 'aggregated_metrics'  # 90 days
        elif data_type in ['llm_prompt', 'llm_response', 'recommendation_trace']:
            return 'llm_interaction_logs'  # 30 days (Sprint 10.1)
        elif data_type == 'llm_usage_log':
            return 'usage_analytics'  # 90 days (cost tracking)
        else:
            return 'sanitized_metadata'  # Default to 14 days


# Singleton instance
pii_redactor = PIIRedactor()