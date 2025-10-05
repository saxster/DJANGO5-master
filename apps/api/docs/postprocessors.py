"""
OpenAPI Postprocessing Hooks

Enhances generated OpenAPI schema with custom metadata for mobile clients.

Compliance with .claude/rules.md:
- Rule #7: Functions < 50 lines
- Rule #11: Specific exception handling
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def add_kotlin_metadata(result: Dict[str, Any], generator, request, public: bool) -> Dict[str, Any]:
    """
    Add Kotlin/Swift codegen metadata to OpenAPI schema.

    Adds custom OpenAPI extensions (x-*) for mobile client generation:
    - x-kotlin-package: Package name for generated Kotlin code
    - x-mobile-compatible: Flag for mobile-optimized endpoints
    - x-codegen-hints: Additional hints for code generators

    Args:
        result: Generated OpenAPI schema dict
        generator: Schema generator instance
        request: HTTP request (if available)
        public: Whether this is a public schema

    Returns:
        Enhanced OpenAPI schema
    """
    # Add Kotlin package hints
    result['x-kotlin-package'] = 'com.youtility.api'
    result['x-swift-package'] = 'YoutilityAPI'
    result['x-mobile-compatible'] = True

    # Add mobile-specific codegen hints
    result['x-codegen-hints'] = {
        'date_library': 'java8',  # Use java.time.Instant
        'serialization': 'kotlinx_serialization',  # Use kotlinx.serialization
        'enum_property_naming': 'UPPERCASE',
        'null_handling': 'strict',  # Fail on unexpected nulls
    }

    # Add to info section for better visibility
    if 'info' not in result:
        result['info'] = {}

    result['info']['x-api-type'] = 'mobile_first'
    result['info']['x-supported-platforms'] = ['Android', 'iOS', 'Web']

    logger.info("Added Kotlin/Swift metadata to OpenAPI schema")
    return result


def add_idempotency_docs(result: Dict[str, Any], generator, request, public: bool) -> Dict[str, Any]:
    """
    Document idempotency patterns in OpenAPI schema.

    Adds documentation for:
    - Idempotency-Key header usage
    - 24-hour TTL guarantee
    - Retry safety patterns
    - Supported operations

    Args:
        result: Generated OpenAPI schema dict
        generator: Schema generator instance
        request: HTTP request (if available)
        public: Whether this is a public schema

    Returns:
        Enhanced OpenAPI schema
    """
    # Add components section if missing
    if 'components' not in result:
        result['components'] = {}

    # Document idempotency pattern
    result['components']['x-idempotency'] = {
        'enabled': True,
        'ttl_hours': 24,
        'description': """
        All POST, PUT, PATCH, DELETE operations support idempotency via the Idempotency-Key header.

        **Usage**:
        ```
        POST /api/v2/sync/voice/
        Idempotency-Key: unique-key-12345

        {
          "device_id": "android-123",
          "voice_data": [...]
        }
        ```

        **Guarantees**:
        - Same key within 24 hours returns cached response (no re-execution)
        - Prevents duplicate operations from network retries
        - Safe to retry any failed request with same key

        **Implementation**: apps/api/v1/services/idempotency_service.py
        """,
        'header_name': 'Idempotency-Key',
        'required_for': ['POST', 'PUT', 'PATCH', 'DELETE'],
        'optional_for': ['GET'],
    }

    # Add idempotency parameter to relevant operations
    if 'paths' in result:
        for path, methods in result['paths'].items():
            for method, operation in methods.items():
                # Add to POST/PUT/PATCH operations
                if method.upper() in ['POST', 'PUT', 'PATCH', 'DELETE']:
                    if 'parameters' not in operation:
                        operation['parameters'] = []

                    # Add idempotency key parameter
                    idempotency_param = {
                        'name': 'Idempotency-Key',
                        'in': 'header',
                        'required': False,
                        'schema': {'type': 'string', 'minLength': 16, 'maxLength': 255},
                        'description': 'Idempotency key for retry safety (recommended for mobile)',
                        'example': 'batch-2025-10-05-abc123',
                    }

                    # Only add if not already present
                    if not any(p.get('name') == 'Idempotency-Key' for p in operation['parameters']):
                        operation['parameters'].append(idempotency_param)

    logger.info("Added idempotency documentation to OpenAPI schema")
    return result


__all__ = [
    'add_kotlin_metadata',
    'add_idempotency_docs',
]
