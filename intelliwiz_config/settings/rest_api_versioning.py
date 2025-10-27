"""
API Versioning Configuration

Handles API deprecation, sunset policies, and version lifecycle management.

Implements RFC 9745 (Deprecation Header) and RFC 8594 (Sunset Header) standards.

Compliance with .claude/rules.md:
- Rule #6: Settings files < 200 lines
"""

API_VERSION_CONFIG = {
    'CURRENT_VERSION': 'v1',
    'SUPPORTED_VERSIONS': ['v1', 'v2'],
    'DEPRECATED_VERSIONS': [],
    'SUNSET_VERSIONS': [],

    'VERSION_HEADER_NAME': 'X-API-Version',
    'DEPRECATION_HEADER_NAME': 'Deprecation',
    'SUNSET_HEADER_NAME': 'Sunset',
    'WARNING_HEADER_NAME': 'Warning',
    'LINK_HEADER_NAME': 'Link',

    'DEFAULT_DEPRECATION_PERIOD_DAYS': 90,
    'DEFAULT_SUNSET_WARNING_DAYS': 30,
    'MINIMUM_SUPPORTED_VERSIONS': 2,

    'ENABLE_DEPRECATION_ANALYTICS': True,
    'ENABLE_VERSION_NEGOTIATION': True,
    'ENABLE_BACKWARD_COMPATIBILITY_MODE': True,
}

GRAPHQL_VERSION_CONFIG = {
    'SCHEMA_VERSION': '1.0',
    'ENABLE_FIELD_DEPRECATION': True,
    'ENABLE_DEPRECATION_TRACKING': True,
    'DEPRECATION_REASON_REQUIRED': True,

    'DEPRECATED_MUTATIONS': [
        {
            'name': 'upload_attachment',
            'deprecated_in': '1.0',
            'removed_in': '2.0',
            'sunset_date': '2026-06-30',
            'replacement': 'secure_file_upload',
            'migration_url': '/docs/api-migrations/file-upload-v2/',
        },
    ],

    'DEPRECATED_FIELDS': [],

    'ENABLE_INTROSPECTION_DEPRECATION_INFO': True,
}

__all__ = [
    'API_VERSION_CONFIG',
    'GRAPHQL_VERSION_CONFIG',
]
